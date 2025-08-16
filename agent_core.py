# agent_core.py
import re
import os
from typing import Tuple, Dict, Any, Optional

def clear_console():
    """Clear the console screen."""
    # For Windows
    if os.name == 'nt':
        os.system('cls')
    # For Unix/Linux/MacOS
    else:
        os.system('clear')

# Import the tools and memory from your project
try:
    from banking_tools import BankingTools
except Exception as e:
    raise ImportError("Could not import banking_tools. Make sure banking_tools.py exists.") from e

try:
    from state import Memory
except Exception:
    # Fallback minimal Memory if state.py differs
    class Memory:
        def __init__(self):
            self.last_amount = None
            self.last_recipient = None
            self.last_biller = None
            self.last_n = 3
            self.last_month = None
            self.last_intent = None
            self.pending_transfer_to = None
            self.trace = []
            self.trace_enabled = False
            
        def remember(self, **kwargs):
            for k, v in kwargs.items():
                if hasattr(self, k):
                    setattr(self, k, v)

        def add_trace(self, kind: str, text: str):
            self.trace.append(f"{kind}: {text}")
            self.trace = self.trace[-50:]
        def get_trace(self):
            return list(self.trace)


class BankingAgent:
    """
    High-level agent wrapper that:
      - parses intents/slots (deterministic, optionally LLM can be plugged)
      - calls tools in banking_tools.py
      - keeps short-term memory (via state.Memory)
      - keeps a reasoning trace (Memory.add_trace if available)
    """

    def __init__(self, tools: Optional[BankingTools] = None, memory: Optional[Memory] = None):
        self.tools = tools if tools is not None else BankingTools()
        self.memory = memory if memory is not None else Memory()
        self.trace_enabled = False
        self.trace = []  # Local trace storage
        self.last_result = None  # Store last response

        # Capabilities advertised to user
        self.capabilities = {
            "balance": "Check your current account balance",
            "transactions": "Show your last N transactions (e.g., 'show last 3 transactions')",
            "transfer": "Transfer money to someone (e.g., 'transfer 500 to Alice')",
            "deposit": "Add money to your account (e.g., 'deposit 500 from salary')",
            "pay_bill": "Pay a bill (e.g., 'pay 1200 to electricity')",
            "summary": "Show monthly summary (e.g., 'summary for July')",
            "fraud": "Detect suspicious transactions",
            "categorize": "Show spending by category",
            "help": "List capabilities",
            "trace": "Toggle internal reasoning trace"
        }

    # -------------------------
    # Trace helpers
    # -------------------------
    def _add_trace(self, kind: str, text: str):
        """Add a trace entry with timestamp and emoji indicators"""
        if not self.trace_enabled:
            return
            
        # Emoji map for different trace types
        emoji_map = {
            "Start": "🎯",
            "Intent": "🔎",
            "Slots": "📋",
            "Thought": "🤔",
            "Action": "⚡",
            "Error": "❌",
            "Control": "⚙️",
            "Success": "✅",
            "Parse": "🔍",
            "Tool": "🛠️",
            "Memory": "💭"
        }
        
        trace_line = f"{emoji_map.get(kind, '•')} {kind}: {text}"
        self.trace.append(trace_line)
        # Keep only last 20 entries
        self.trace = self.trace[-20:]

    def get_trace(self):
        """Get the latest trace entries with proper formatting"""
        if not self.trace:
            return "No trace history available"
        return "\n".join(self.trace)

    def toggle_trace(self):
        self.trace_enabled = not self.trace_enabled
        msg = f"Reasoning trace {'enabled' if self.trace_enabled else 'disabled'} ✅"
        # Clear previous trace when toggling
        self.trace = []
        if self.trace_enabled:
            self._add_trace("Control", "Trace system initialized ✨")
        return msg

    # -------------------------
    # Intent + slot parsing
    # -------------------------
    def parse_intent_slots(self, user: str) -> Tuple[str, Dict[str, Any]]:
        """
        Deterministic intent + slot parser.
        Returns (intent, slots).
        Slots may include: n, amount, target, biller, month, category
        """
        u = user.strip()
        ul = u.lower()
        self._add_trace("Thought", f"User input: '{u}'")
        
        # Reset trace if it's too long
        if hasattr(self.memory, "trace") and len(self.memory.trace) > 50:
            self.memory.trace = self.memory.trace[-20:]  # Keep last 20 entries
        nums = [float(x[0]) for x in re.findall(r"(?<!\w)(\d+(\.\d+)?)", u)]
        ints = [int(x) for x in nums if float(x).is_integer()]

        # Month names
        month_match = re.search(r"(january|february|march|april|may|june|july|august|september|october|november|december)", ul)
        month = month_match.group(1).title() if month_match else None

        # recipient/biller capture
        # Patterns: "to Alice", "pay Alice", "transfer to Alice"
        target = None
        # Remove currency words for cleaner parsing
        clean_text = re.sub(r'\b(rs\.|rupees|dollars?|inr)\b', '', ul, flags=re.IGNORECASE)
        
        # Look for deposit source
        if "from" in clean_text:
            source_match = re.search(r"from\s+([A-Za-z][A-Za-z0-9 _-]{0,30})", clean_text)
            if source_match:
                target = source_match.group(1).strip()
        # Otherwise look for recipient/biller
        elif "to" in clean_text:
            recipient_match = re.search(r"to\s+([A-Za-z][A-Za-z0-9 _-]{0,30})", clean_text)
            if recipient_match:
                target = recipient_match.group(1).strip()
        # Check for direct biller name
        elif "pay" in clean_text and "bill" in clean_text:
            biller_match = re.search(r"pay\s+(?:bill\s+)?(?:to\s+)?([A-Za-z][A-Za-z0-9 _-]{0,30})", clean_text)
            if biller_match:
                target = biller_match.group(1).strip()

        # category guess: look for common words
        categories = ["groceries", "shopping", "bills", "food", "entertainment", "petrol", "travel", "transfer", "income"]
        category = None
        for cat in categories:
            if cat in ul:
                category = cat
                break

        # Check for follow-up amount for pending transfer
        if nums and getattr(self.memory, 'pending_transfer_to', None):
            return "transfer_money", {
                "amount": nums[0],
                "target": self.memory.pending_transfer_to
            }

        # Intent rules (deterministic)
        if ul in ("help", "options", "what can you do", "menu"):
            intent = "help"
        elif ul == "trace" or "trace" == ul.split()[0]:
            intent = "toggle_trace"
        elif "balance" in ul or "how much money" in ul or "how much do i have" in ul:
            intent = "check_balance"
        elif "fraud" in ul or "suspicious" in ul or "detect" in ul:
            intent = "detect_fraud"
        elif "categorize" in ul or "category" in ul or "spending" in ul:
            intent = "categorize_spending"
        elif any(word in ul for word in ["summary", "month", "spending in"]) or month:
            intent = "monthly_summary"
        elif "pay" in ul and ("bill" in ul or "pay" in ul):
            intent = "pay_bill"
        elif ("deposit" in ul or "add" in ul) and ("from" in ul or len(nums) > 0):
            intent = "deposit_money"
        elif "transfer" in ul or "send" in ul or "give" in ul:
            intent = "transfer_money"
        elif "transaction" in ul or "transactions" in ul or "last" in ul or "recent" in ul or "spent" in ul or ul.strip() == "show":
            intent = "get_last_transactions"
        else:
            intent = "fallback"

        # Initialize slots
        slots: Dict[str, Any] = {
            "n": None,
            "amount": None if not nums else nums[0],
            "target": target,
            "biller": target,
            "month": month,
            "category": category
        }

        # Handle specific slot requirements per intent
        if intent == "deposit_money":
            if "from" in clean_text:
                source_match = re.search(r"from\s+([A-Za-z][A-Za-z0-9 _-]{0,30})", clean_text)
                if source_match:
                    slots["target"] = source_match.group(1).strip()
                elif not slots["target"]:
                    slots["target"] = "unspecified source"

        elif intent == "get_last_transactions":
            # find "last 3" or "last three" (numbers)
            if ints:
                slots["n"] = ints[0]
            else:
                mlast = re.search(r"last\s+(\w+)", ul)
                # attempt to map words to numbers (one,two,three)
                word2num = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
                if mlast:
                    w = mlast.group(1)
                    if w.isdigit():
                        slots["n"] = int(w)
                    elif w in word2num:
                        slots["n"] = word2num[w]
            # Default to last stored n or 3
            if not slots["n"]:
                slots["n"] = getattr(self.memory, "last_n", 3)

        # Fill memory defaults for missing slots
        if slots["n"] is None:
            slots["n"] = getattr(self.memory, "last_n", 3)
        if slots["amount"] is None:
            slots["amount"] = getattr(self.memory, "last_amount", None)
        if slots["target"] is None and intent != "deposit_money":
            slots["target"] = getattr(self.memory, "last_recipient", None)

        self._add_trace("Thought", f"Intent={intent}, Slots={slots}")
        return intent, slots

    # -------------------------
    # Act: call the appropriate tool
    # -------------------------
    def act(self, intent: str, slots: Dict[str, Any]) -> str:
        self._add_trace("Action", f"Processing command: {intent}")
        if slots:
            self._add_trace("Thought", f"Parameters detected: {slots}")
        try:
            if intent == "help":
                lines = [f"- {k}: {v}" for k, v in self.capabilities.items()]
                return "Capabilities:\n" + "\n".join(lines)

            if intent == "toggle_trace":
                return self.toggle_trace()

            if intent == "check_balance":
                return self.tools.check_balance()

            if intent == "get_last_transactions":
                n = int(slots.get("n") or getattr(self.memory, "last_n", 3))
                # remember n
                if hasattr(self.memory, "remember"):
                    try:
                        self.memory.remember(last_n=n)
                    except Exception:
                        pass
                return self.tools.last_transactions(n=n)

            if intent == "deposit_money":
                amt = slots.get("amount")
                source = slots.get("target")
                
                # If we're missing amount
                if amt is None:
                    return "Please specify the amount to deposit, e.g., 'deposit 500 from salary'."
                
                # Use default source if not provided
                if source is None:
                    source = "unspecified source"
                
                # Remember the details
                if hasattr(self.memory, "remember"):
                    try:
                        self.memory.remember(last_amount=amt)
                    except Exception:
                        pass
                
                return self.tools.deposit(amount=amt, source=source)

            if intent == "transfer_money":
                amt = slots.get("amount")
                to = slots.get("target")
                
                # If we have recipient but no amount, save the context and ask for amount
                if to is not None and amt is None:
                    if hasattr(self.memory, "remember"):
                        try:
                            self.memory.remember(pending_transfer_to=to)
                        except Exception:
                            pass
                    return "Please specify the amount to transfer."
                
                # If we're missing either piece of information
                if amt is None or to is None:
                    return "Please specify an amount and a recipient, e.g., 'transfer 500 to Alice'."
                
                # remember last amount and recipient
                if hasattr(self.memory, "remember"):
                    try:
                        self.memory.remember(last_amount=amt, last_recipient=to, pending_transfer_to=None)
                    except Exception:
                        pass
                
                return self.tools.transfer(amount=amt, recipient=to)

            if intent == "pay_bill":
                amt = slots.get("amount")
                biller = slots.get("target") or slots.get("biller")
                
                if amt is None:
                    return "Please specify an amount to pay, e.g., 'pay 1200 to electricity'."
                
                if biller is None:
                    return "Please specify who to pay the bill to, e.g., 'pay 1200 to electricity'."
                
                # remember last amount and biller
                if hasattr(self.memory, "remember"):
                    try:
                        self.memory.remember(last_amount=amt, last_biller=biller)
                    except Exception:
                        pass
                
                return self.tools.pay_bill(amount=amt, biller=biller)

            if intent == "monthly_summary":
                month = slots.get("month") or getattr(self.memory, "last_month", None) or "August"
                if hasattr(self.memory, "remember"):
                    try:
                        self.memory.remember(last_month=month)
                    except Exception:
                        pass
                return self.tools.monthly_summary(month)

            if intent == "detect_fraud":
                return self.tools.detect_fraud()

            if intent == "categorize_spending":
                return self.tools.categorize_spending()

            else:
                self._add_trace("Thought", "No intent matched")
                return "I'm not sure how to handle that. Try asking about balance, transactions, transfers, or bills."

        except Exception as e:
            self._add_trace("Error", str(e))
            return f"Sorry, there was an error: {str(e)}"

    def handle_query(self, user_input: str) -> str:
        try:
            if self.trace_enabled:
                clear_console()
                # Print the last interaction if it exists
                if self.last_result:
                    print(f"Agent: {self.last_result}\n")
                    print(f"You: {user_input}\n")
                # Clear previous trace
                if hasattr(self.memory, "trace"):
                    self.memory.trace = []
                self.trace = []
                # Initialize new trace
                self._add_trace("Control", "Trace system initialized ✨")
                
            # Log the start of processing
            self._add_trace("Start", f"Processing command: '{user_input}'")
            
            # Parse intent and slots
            intent, slots = self.parse_intent_slots(user_input)
            self._add_trace("Parse", f"Detected command type: {intent}")
            
            if slots:
                filtered_slots = {k: v for k, v in slots.items() if v is not None}
                if filtered_slots:
                    self._add_trace("Parse", f"Found parameters: {filtered_slots}")
            
            # Execute the command
            self._add_trace("Action", f"Executing {intent} command")
            result = self.act(intent, slots)
            
            # Store this result for the next interaction
            self.last_result = result
            
            # Log success
            self._add_trace("Success", f"Command completed successfully")
            return result
            
        except Exception as e:
            self._add_trace("Error", f"Failed to process command: {str(e)}")
            raise

if __name__ == "__main__":
    agent = BankingAgent()
    print("🤖 Banking Agent ready! Type 'exit' to quit.")
    while True:
        query = input("\nYou: ")
        if query.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break
        response = agent.handle_query(query)
        print("Agent:", response)
