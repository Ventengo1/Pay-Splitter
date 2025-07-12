import streamlit as st
import pandas as pd
from datetime import datetime, date
import uuid
import json
import os

# --- Configuration ---
DATA_FILE = "household_data.json"

# --- Data Model (Classes) ---
class Expense:
    def __init__(self, description, amount, paid_by, participants, date_obj):
        self.id = str(uuid.uuid4())
        self.description = description
        self.amount = float(amount)
        self.paid_by = paid_by
        self.participants = participants

        if isinstance(date_obj, (datetime, date)):
            self.date = date_obj.strftime('%Y-%m-%d')
        elif isinstance(date_obj, str):
            self.date = date_obj
        else:
            raise TypeError(f"Unsupported date type: {type(date_obj)}. Expected datetime, date, or str.")

    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "amount": self.amount,
            "paid_by": self.paid_by,
            "participants": self.participants,
            "date": self.date
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            data['description'],
            data['amount'],
            data['paid_by'],
            data['participants'],
            data['date']
        )

# --- Data Persistence Functions ---
def save_data(members, expenses):
    data_to_save = {
        "members": members,
        "expenses": [exp.to_dict() for exp in expenses]
    }
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data_to_save, f, indent=4)
        st.sidebar.success("Data saved!")
    except Exception as e:
        st.sidebar.error(f"Error saving data: {e}")

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data_loaded = json.load(f)
                st.session_state.members = data_loaded.get("members", ['Alice', 'Bob', 'Charlie'])
                st.session_state.expenses = [
                    Expense.from_dict(exp_dict) for exp_dict in data_loaded.get("expenses", [])
                ]
            st.sidebar.success("Data loaded!")
        except json.JSONDecodeError:
            st.sidebar.warning("Data file is corrupt or empty. Starting with default data.")
            st.session_state.members = ['Alice', 'Bob', 'Charlie']
            st.session_state.expenses = []
        except Exception as e:
            st.sidebar.error(f"Error loading data: {e}")
            st.session_state.members = ['Alice', 'Bob', 'Charlie']
            st.session_state.expenses = []
    else:
        st.session_state.members = ['Alice', 'Bob', 'Charlie']
        st.session_state.expenses = []

# --- Core Logic Functions ---
def calculate_balances(members, expenses):
    balances = {member: 0.0 for member in members}

    for expense in expenses:
        if expense.paid_by in balances:
            balances[expense.paid_by] += expense.amount

        valid_participants = [p for p in expense.participants if p in members]
        num_participants = len(valid_participants)

        if num_participants > 0:
            split_amount = expense.amount / num_participants
            for participant in valid_participants:
                balances[participant] -= split_amount
    return balances

def suggest_settlements(balances):
    clean_balances = {member: round(balance, 2) for member, balance in balances.items() if abs(balance) > 0.01}

    debtors = {member: abs(balance) for member, balance in clean_balances.items() if balance < 0}
    creditors = {member: balance for member, balance in clean_balances.items() if balance > 0}

    settlements = []

    sorted_debtors = sorted(debtors.items(), key=lambda item: item[1], reverse=True)
    sorted_creditors = sorted(creditors.items(), key=lambda item: item[1], reverse=True)

    debtor_idx = 0
    creditor_idx = 0

    while debtor_idx < len(sorted_debtors) and creditor_idx < len(sorted_creditors):
        debtor_name, current_debt = sorted_debtors[debtor_idx]
        creditor_name, current_credit = sorted_creditors[creditor_idx]

        if current_debt <= 0.01:
            debtor_idx += 1
            continue
        if current_credit <= 0.01:
            creditor_idx += 1
            continue

        payment_amount = min(current_debt, current_credit)
        settlements.append((debtor_name, creditor_name, payment_amount))

        sorted_debtors[debtor_idx] = (debtor_name, current_debt - payment_amount)
        sorted_creditors[creditor_idx] = (creditor_name, current_credit - payment_amount)

    settlements = [(d, c, amt) for d, c, amt in settlements if amt > 0.01]
    return settlements

# --- Streamlit UI Components ---

def display_manage_members():
    st.header("👨‍👩‍👧‍👦 Manage Members")
    current_members_input = st.text_area(
        "Edit Members (one name per line)",
        value="\n".join(st.session_state.members),
        height=100
    )
    if st.button("Update Members"):
        new_members = [name.strip() for name in current_members_input.split('\n') if name.strip()]
        if new_members:
            st.session_state.members = new_members
            save_data(st.session_state.members, st.session_state.expenses)
            st.success("Members updated!")
            st.rerun()
        else:
            st.error("Please add at least one member.")

def display_add_expense():
    st.header("➕ Add New Expense")
    with st.form("add_expense_form", clear_on_submit=True):
        description = st.text_input("Description")
        amount = st.number_input("Amount ($)", min_value=0.01, format="%.2f")

        paid_by = None
        participants = []
        if st.session_state.members:
            paid_by = st.selectbox("Who Paid?", options=st.session_state.members, key="paid_by_select")
            participants = st.multiselect(
                "Who is involved in the split?",
                options=st.session_state.members,
                default=st.session_state.members,
                key="participants_multiselect"
            )
        else:
            st.warning("Please add members first in the 'Manage Members' section to add expenses.")

        expense_date = st.date_input("Date", value=datetime.now().date(), key="expense_date_input")

        submitted = st.form_submit_button("Add Expense")

        if submitted:
            if not description or amount <= 0 or paid_by is None or not participants:
                st.error("Please fill in all fields (description, amount, who paid, and who is involved).")
            else:
                new_expense = Expense(description, amount, paid_by, participants, expense_date)
                st.session_state.expenses.append(new_expense)
                save_data(st.session_state.members, st.session_state.expenses)
                st.success("Expense added successfully!")
                st.rerun()

def display_current_balances():
    st.header("📊 Current Balances")
    balances = calculate_balances(st.session_state.members, st.session_state.expenses)

    balances_df = pd.DataFrame(
        [{'Member': member, 'Balance': f"${balance:.2f}"} for member, balance in balances.items()]
    )
    st.dataframe(balances_df.set_index('Member'), use_container_width=True)

    st.subheader("🤝 Suggested Settlements")
    settlements = suggest_settlements(balances)
    if settlements:
        for debtor, creditor, amount in settlements:
            st.info(f"**{debtor}** pays **{creditor}** **${amount:.2f}**")
    else:
        st.success("All balances are currently settled!")

def display_expense_history():
    st.header("🧾 Expense History")
    if st.session_state.expenses:
        expenses_data = []
        for exp in st.session_state.expenses:
            expenses_data.append({
                'ID': exp.id[:8] + '...',
                'Date': exp.date,
                'Description': exp.description,
                'Amount': f"${exp.amount:.2f}",
                'Paid By': exp.paid_by,
                'Participants': ", ".join(exp.participants)
            })
        df_expenses = pd.DataFrame(expenses_data)
        st.dataframe(df_expenses.set_index('ID'), use_container_width=True)

        st.markdown("---")
        if st.button("Clear All Expenses (Start Fresh)"):
            st.session_state.expenses = []
            save_data(st.session_state.members, st.session_state.expenses)
            st.success("All expenses cleared!")
            st.rerun()

    else:
        st.info("No expenses recorded yet. Use the form above to add one!")

# --- Main Application Logic ---
def main():
    st.title("🏡 Simple Household Splitter")

    # Initial data load check (runs once per session)
    if 'data_loaded_flag' not in st.session_state:
        load_data()
        st.session_state.data_loaded_flag = True

    st.markdown("---")
    display_manage_members()

    st.markdown("---")
    display_add_expense()

    st.markdown("---")
    display_current_balances()

    st.markdown("---")
    display_expense_history()

# Run the main application
if __name__ == "__main__":
    main()
