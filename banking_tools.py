import pandas as pd
from tabulate import tabulate
import os

class BankingTools:
    def __init__(self):
        self.file_path = os.path.join("data", "transactions.csv")
        # Create transactions file if it doesn't exist
        if not os.path.exists(self.file_path):
            if not os.path.exists('data'):
                os.makedirs('data')
            initial_data = {
                'date': [pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")],
                'description': ['Opening Balance'],
                'amount': [50000],
                'category': ['Income']
            }
            pd.DataFrame(initial_data).to_csv(self.file_path, index=False)
        
        self.transactions = pd.read_csv(self.file_path)
        # Parse dates properly - try multiple formats if needed
        try:
            self.transactions['date'] = pd.to_datetime(self.transactions['date'], format='mixed')
        except:
            try:
                self.transactions['date'] = pd.to_datetime(self.transactions['date'])
            except:
                # If all else fails, try parsing as string and convert
                self.transactions['date'] = pd.to_datetime(self.transactions['date'].astype(str))

    def check_balance(self):
        balance = self.transactions["amount"].sum()
        return f"Your current balance is ₹{balance}"

    def last_transactions(self, n=5):
        last_txns = self.transactions.tail(n)
        return tabulate(last_txns, headers="keys", tablefmt="pretty")

    def transfer(self, amount, recipient):
        if amount is None or recipient is None:
            return "Incomplete transfer details."
            
        current_balance = self.transactions["amount"].sum()
        if amount > current_balance:
            return f"Insufficient funds. Current balance: ₹{current_balance}"
            
        new_entry = pd.DataFrame([{
            "date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "description": f"Transfer to {recipient}", 
            "amount": -float(amount), 
            "category": "Transfer"
        }])
        self.transactions = pd.concat([self.transactions, new_entry], ignore_index=True)
        self.transactions.to_csv(self.file_path, index=False)
        new_balance = self.transactions["amount"].sum()
        return f"Transferred ₹{amount} to {recipient}. New balance: ₹{new_balance}"

    def deposit(self, amount, source):
        if amount is None or source is None:
            return "Incomplete deposit details."
            
        new_entry = pd.DataFrame([{
            "date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "description": f"Deposit from {source}", 
            "amount": float(amount), 
            "category": "Income"
        }])
        self.transactions = pd.concat([self.transactions, new_entry], ignore_index=True)
        self.transactions.to_csv(self.file_path, index=False)
        new_balance = self.transactions["amount"].sum()
        return f"Deposited ₹{amount} from {source}. New balance: ₹{new_balance}"

    def pay_bill(self, amount, biller):
        if amount is None or biller is None:
            return "Incomplete bill payment details."
            
        current_balance = self.transactions["amount"].sum()
        if amount > current_balance:
            return f"Insufficient funds. Current balance: ₹{current_balance}"
            
        new_entry = pd.DataFrame([{
            "date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "description": f"Bill payment to {biller}", 
            "amount": -float(amount), 
            "category": "Bills"
        }])
        self.transactions = pd.concat([self.transactions, new_entry], ignore_index=True)
        self.transactions.to_csv(self.file_path, index=False)
        new_balance = self.transactions["amount"].sum()
        return f"Paid ₹{amount} to {biller}. New balance: ₹{new_balance}"

    def detect_fraud(self):
        # Look for suspicious patterns:
        # 1. Very large transactions (>20000)
        # 2. Multiple transactions in short time
        # 3. Exclude regular transactions like salary
        large_txns = self.transactions[
            (self.transactions["amount"].abs() > 20000) & 
            (self.transactions["category"] != "Income")
        ]
        
        if large_txns.empty:
            return "✅ No suspicious transactions detected."
        
        return ("⚠️ Suspicious transactions found:\n" + 
                tabulate(large_txns, headers="keys", tablefmt="pretty", 
                        colalign=("left", "left", "left", "right", "left")))

    def monthly_summary(self, month=None):
        if month is None:
            # Use current month if none specified
            current_date = pd.Timestamp.now()
        else:
            # Try to parse the month name
            try:
                # Handle month names (e.g., "August")
                month_map = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4,
                    'may': 5, 'june': 6, 'july': 7, 'august': 8,
                    'september': 9, 'october': 10, 'november': 11, 'december': 12
                }
                month_str = month.lower().strip()
                if month_str in month_map:
                    current_date = pd.Timestamp(f"2025-{month_map[month_str]:02d}-01")
                else:
                    # Try parsing as YYYY-MM format
                    current_date = pd.to_datetime(month)
            except:
                return f"Please specify a valid month (e.g., 'August' or '2025-08')"

        # Make sure date column is datetime
        if not pd.api.types.is_datetime64_any_dtype(self.transactions['date']):
            self.transactions['date'] = pd.to_datetime(self.transactions['date'])
        
        # Filter transactions for the specified month
        month_transactions = self.transactions[
            (self.transactions['date'].dt.year == current_date.year) & 
            (self.transactions['date'].dt.month == current_date.month)
        ]

        # Format the output
        output = [f"\n📊 Monthly Summary for {current_date.strftime('%B %Y')}"]
        
        if month_transactions.empty:
            output.append("\n❌ No transactions found for this period.")
            return "\n".join(output)
            
        # Calculate statistics
        income_txns = month_transactions[month_transactions["amount"] > 0]
        expense_txns = month_transactions[month_transactions["amount"] < 0]
        
        total_income = income_txns["amount"].sum() if not income_txns.empty else 0
        total_expenses = abs(expense_txns["amount"].sum()) if not expense_txns.empty else 0
        net_change = total_income - total_expenses
        
        # Add summary section
        output.extend([
            f"\n💰 Total Income: ₹{total_income:,.2f}",
            f"💸 Total Expenses: ₹{total_expenses:,.2f}",
            f"📈 Net Change: ₹{net_change:,.2f}"
        ])
        
        # Add category breakdowns
        if not expense_txns.empty:
            expenses_by_cat = expense_txns.groupby("category")["amount"].sum().abs()
            if not expenses_by_cat.empty:
                output.append("\n🔍 Expenses by Category:")
                for cat, amount in expenses_by_cat.items():
                    output.append(f"  • {cat:.<15} ₹{amount:,.2f}")
        
        if not income_txns.empty:
            income_by_cat = income_txns.groupby("category")["amount"].sum()
            if not income_by_cat.empty:
                output.append("\n💹 Income by Category:")
                for cat, amount in income_by_cat.items():
                    output.append(f"  • {cat:.<15} ₹{amount:,.2f}")
        
        # Add transaction count
        output.append(f"\n🔄 Number of Transactions: {len(month_transactions)}")
        
        return "\n".join(output)
        output = [f"\n📊 Monthly Summary for {current_date.strftime('%B %Y')}"]
        
        if not month_transactions.empty:
            total_income = month_transactions[month_transactions["amount"] > 0]["amount"].sum()
            total_expenses = abs(month_transactions[month_transactions["amount"] < 0]["amount"].sum())
            net_change = month_transactions["amount"].sum()
            
            output.extend([
                f"\n💰 Income: ₹{total_income:,.2f}",
                f"💸 Expenses: ₹{total_expenses:,.2f}",
                f"📈 Net Change: ₹{net_change:,.2f}"
            ])
            
            # Categorize transactions
            expenses = month_transactions[month_transactions["amount"] < 0].groupby("category")["amount"].sum()
            income = month_transactions[month_transactions["amount"] > 0].groupby("category")["amount"].sum()
            
            if not expenses.empty:
                output.append("\n🔍 Expenses by Category:")
                for cat, amount in expenses.items():
                    output.append(f"  • {cat:.<15} ₹{abs(amount):,.2f}")
            
            if not income.empty:
                output.append("\n💹 Income by Category:")
                for cat, amount in income.items():
                    output.append(f"  • {cat:.<15} ₹{amount:,.2f}")
                    
            output.append(f"\n🔄 Number of Transactions: {len(month_transactions)}")
        else:
            output.append("\n❌ No transactions found for this period.")
        
        if month_txns.empty:
            return f"📅 No transactions found for {full_month}."
        
        # Group by category
        cat_summary = month_txns.groupby("category")["amount"].sum()
        expenses = cat_summary[cat_summary < 0]
        income = cat_summary[cat_summary > 0]
        
        output = [f"📊 {full_month} Summary:"]
        
        if not expenses.empty:
            output.append("\n💸 Expenses by Category:")
            for cat, amount in expenses.items():
                output.append(f"  • {cat:.<15} ₹{abs(amount):,.2f}")
        
        if not income.empty:
            output.append("\n💰 Income by Category:")
            for cat, amount in income.items():
                output.append(f"  • {cat:.<15} ₹{amount:,.2f}")
        
        total_spent = abs(expenses.sum()) if not expenses.empty else 0
        total_earned = income.sum() if not income.empty else 0
        net_change = total_earned - total_spent
        
        output.append("\n� Totals:")
        output.append(f"  • Income:    ₹{total_earned:,.2f}")
        output.append(f"  • Expenses:  ₹{total_spent:,.2f}")
        output.append(f"  • Net:       ₹{net_change:,.2f}")
        output.append(f"\n🔄 Number of Transactions: {len(month_txns)}")
        
        return "\n".join(output)

    def categorize_spending(self):
        # Group transactions by category
        grouped = self.transactions.groupby("category")["amount"].sum().round(2)
        
        # Separate income and expenses
        income = grouped[grouped > 0]
        expenses = grouped[grouped < 0]
        
        output = ["📊 Spending Analysis:\n"]
        
        if not expenses.empty:
            output.append("💸 Expenses:")
            for cat, amount in expenses.items():
                output.append(f"  • {cat:.<15} ₹{abs(amount):,.2f}")
        
        if not income.empty:
            output.append("\n💰 Income:")
            for cat, amount in income.items():
                output.append(f"  • {cat:.<15} ₹{amount:,.2f}")
        
        total_expenses = abs(expenses.sum()) if not expenses.empty else 0
        total_income = income.sum() if not income.empty else 0
        net_balance = total_income - total_expenses
        
        output.append(f"\n📈 Total Summary:")
        output.append(f"  • Total Income:   ₹{total_income:,.2f}")
        output.append(f"  • Total Expenses: ₹{total_expenses:,.2f}")
        output.append(f"  • Net Balance:    ₹{net_balance:,.2f}")
        
        return "\n".join(output)
