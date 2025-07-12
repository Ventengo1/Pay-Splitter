import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import json
import os

# --- Configuration ---
DATA_FILE = "household_data.json"

# --- Data Structures ---
# Representing a single expense
class Expense:
    def __init__(self, description, amount, paid_by, participants, date):
        self.id = str(uuid.uuid4()) # Unique ID for each expense
        self.description = description
        self.amount = float(amount)
        self.paid_by = paid_by # Name of the person who paid
        self.participants = participants # List of names of people involved in the split
        # Ensure date is stored as a string for JSON serialization
        self.date = date.strftime('%Y-%m-%d') if isinstance(date, datetime) else date

    def to_dict(self):
        """Converts an Expense object to a dictionary for JSON serialization."""
        return {
            "id": self.id,
            "description": self.description,
            "amount": self.amount,
            "paid_by": self.paid_by,
            "participants": self.participants,
            "date": self.date # Already a string
        }

    @classmethod
    def from_dict(cls, data):
        """Creates an Expense object from a dictionary (e.g., loaded from JSON)."""
        # Convert date string back to datetime object
        date_obj = datetime.strptime(data['date'], '%Y-%m-%d').date()
        return cls(
            data['description'],
            data['amount'],
            data['paid_by'],
            data['participants'],
            date_obj
        )

# --- Data Persistence Functions ---

def save_data(members, expenses):
    """Saves members and expenses data to a JSON file."""
    data_to_save = {
        "members": members,
        "expenses": [exp.to_dict() for exp in expenses]
    }
    with open(DATA_FILE, "w") as f:
        json.dump(data_to_save, f, indent=4)
    st.sidebar.success("Data saved!") # Optional: give feedback

def load_data():
    """Loads members and expenses data from a JSON file."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data_loaded = json.load(f)
            st.session_state.members = data_loaded.get("members", ['Alice', 'Bob', 'Charlie'])
            # Reconstruct Expense objects from dictionaries
            st.session_state.expenses = [
                Expense.from_dict(exp_dict) for exp_dict in data_loaded.get("expenses", [])
            ]
        st.sidebar.success("Data loaded!") # Optional: give feedback
    else:
        # Initialize with defaults if file doesn't exist
        st.session_state.members = ['Alice', 'Bob', 'Charlie']
        st.session_state.expenses = []

# --- Initial Data Load (before any Streamlit widgets are rendered) ---
# This ensures data is loaded when the app starts or refreshes
if 'data_loaded' not in st.session_state: # Use a flag to load only once per session
    load_data()
    st.session_state.data_loaded = True


# --- Functions for Core Logic (No changes needed here from previous version) ---

def calculate_balances(members, expenses):
    """Calculates who owes whom based on recorded expenses."""
    balances = {member: 0.0 for member in members}

    for expense in expenses:
        # The person who paid for the expense gets a credit
        balances[expense.paid_by] += expense.amount

        # The expense is split evenly among participants
        num_participants = len(expense.participants)
        if num_participants > 0:
            split_amount = expense.amount / num_participants
            for participant in expense.participants:
                # Each participant owes their share
                balances[participant] -= split_amount
    return balances

def suggest_settlements(balances):
    """
    Suggests the simplest way to settle balances.
    Finds who has positive balances (is owed money) and who has negative (owes money).
    """
    clean_balances = {member: round(balance, 2) for member, balance in balances.items() if abs(balance) > 0.01}

    debtors = {member: abs(balance) for member, balance in clean_balances.items() if balance < 0}
    creditors = {member: balance for member, balance in clean_balances.items() if balance > 0}

    settlements = []

    # Sort debtors and creditors for a consistent settlement order (largest first)
    sorted_debtors = sorted(debtors.items(), key=lambda item: item[1], reverse=True)
    sorted_creditors = sorted(creditors.items(), key=lambda item: item[1], reverse=True)

    # Use pointers to manage lists efficiently
    debtor_idx = 0
    creditor_idx = 0

    while debtor_idx < len(sorted_debtors) and creditor_idx < len(sorted_creditors):
        debtor_name, current_debt = sorted_debtors[debtor_idx]
        creditor_name, current_credit = sorted_creditors[creditor_idx]

        if current_debt <= 0.01: # Debtor has paid off
            debtor_idx += 1
            continue
        if current_credit <= 0.01: # Creditor has been paid
            creditor_idx += 1
            continue

        payment_amount = min(current_debt, current_credit)
        settlements.append((debtor_name, creditor_name, payment_amount))

        # Update remaining amounts
        sorted_debtors[debtor_idx] = (debtor_name, current_debt - payment_amount)
        sorted_creditors[creditor_idx] = (creditor_name, current_credit - payment_amount)


    settlements = [(d, c, amt) for d, c, amt in settlements if amt > 0.01]
    return settlements


# --- Streamlit UI ---

st.title("🏡 Simple Household Splitter")

st.markdown("---")

# --- Manage Members Section ---
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
        save_data(st.session_state.members, st.session_state.expenses) # Save after update
        st.success("Members updated!")
        st.rerun() # Rerun to update select boxes
    else:
        st.error("Please add at least one member.")

st.markdown("---")

# --- Add Expense Section ---
st.header("➕ Add New Expense")
with st.form("add_expense_form", clear_on_submit=True):
    description = st.text_input("Description")
    amount = st.number_input("Amount ($)", min_value=0.01, format="%.2f")
    
    # Dropdown for who paid
    paid_by = st.selectbox("Who Paid?", options=st.session_state.members)
    
    # Multiselect for who participated in the split
    participants = st.multiselect("Who is involved in the split?", options=st.session_state.members, default=st.session_state.members)
    
    # Use datetime.date for simplicity, as datetime.datetime can cause JSON issues with timezones
    expense_date = st.date_input("Date", value=datetime.now().date()) 

    submitted = st.form_submit_button("Add Expense")

    if submitted:
        if not description or amount <= 0 or not paid_by or not participants:
            st.error("Please fill in all fields (description, amount, who paid, and who is involved).")
        else:
            new_expense = Expense(description, amount, paid_by, participants, expense_date)
            st.session_state.expenses.append(new_expense)
            save_data(st.session_state.members, st.session_state.expenses) # Save after adding expense
            st.success("Expense added successfully!")
            st.rerun() # Rerun to update balances and expense list

st.markdown("---")

# --- Current Balances Section ---
st.header("📊 Current Balances")
balances = calculate_balances(st.session_state.members, st.session_state.expenses)

# Display balances in a DataFrame
balances_df = pd.DataFrame(
    [{'Member': member, 'Balance': f"${balance:.2f}"} for member, balance in balances.items()]
)
st.dataframe(balances_df.set_index('Member'), use_container_width=True)

# Display settlements
st.subheader("🤝 Suggested Settlements")
settlements = suggest_settlements(balances)
if settlements:
    for debtor, creditor, amount in settlements:
        st.info(f"**{debtor}** pays **{creditor}** **${amount:.2f}**")
else:
    st.success("All balances are currently settled!")

st.markdown("---")

# --- Expense History Section --- (my robotics teacher always wanted me to split things up like this)
st.header("🧾 Expense History")
if st.session_state.expenses:
    # Prepare data for DataFrame display
    expenses_data = []
    for exp in st.session_state.expenses:
        expenses_data.append({
            'ID': exp.id[:8] + '...', # Shorten ID for display
            'Date': exp.date, 
            'Description': exp.description,
            'Amount': f"${exp.amount:.2f}",
            'Paid By': exp.paid_by,
            'Participants': ", ".join(exp.participants)
        })
    df_expenses = pd.DataFrame(expenses_data)
    st.dataframe(df_expenses.set_index('ID'), use_container_width=True)

    # Option to clear all expenses (for demo purposes)
    st.markdown("---")
    if st.button("Clear All Expenses (Start Fresh)"):
        st.session_state.expenses = []
        save_data(st.session_state.members, st.session_state.expenses) # Save after clearing
        st.success("All expenses cleared!")
        st.rerun()

else:
    st.info("No expenses recorded yet. Use the form above to add one!")
