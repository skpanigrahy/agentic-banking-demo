# main.py
from agent_core import BankingAgent

def banner():
    print("🏦 Welcome to your Banking Agent! 🤖")
    print("\nType your query in plain English.")
    print("\nCommands:")
    print("  - 'help'  : Show available commands and examples")
    print("  - 'trace' : Toggle step-by-step reasoning display")
    print("  - 'show trace' : Show recent agent actions")
    print("  - 'quit'  : Exit the agent")
    print("")


def main():
    agent = BankingAgent()
    banner()

    while True:
        try:
            user = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break

        if not user:
            continue

        if user.lower() in ("exit", "quit"):
            print("👋 Goodbye!")
            break

        # quick commands
        if user.lower() in ("trace", "toggle trace"):
            print(agent.toggle_trace())
            continue

        if user.lower() in ("help", "options", "what can you do", "menu"):
            print(agent.act("help", {}))
            continue

        # Check for trace request before regular commands
        if user.lower() in ("show trace", "trace now", "show trace now"):
            print("\n🔍 Agent's Recent Actions:")
            print("------------------------")
            trace = agent.get_trace()
            print(trace if trace else "(No trace available yet)")
            print("------------------------")
            continue

        # Normal chat: agent decides intent and runs tools
        reply = agent.handle_query(user)
        print("Agent:", reply)
        
        # Show trace automatically if enabled
        if agent.trace_enabled:
            print("\n🔍 Thought Process:")
            print("------------------------")
            trace = agent.get_trace()
            if trace:
                print(trace)
            print("------------------------")

if __name__ == "__main__":
    main()
