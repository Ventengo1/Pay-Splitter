import streamlit as st
import pandas as pd
from datetime import datetime
import uuid

#still want to work on adding some data record
#Right now if you refresh page then all the data will go away

# Representing a single expense
class Expense:
    def __init__(self, description, amount, paid_by, participants, date):
        self.id = str(uuid.uuid4()) # Unique ID for each expense
        self.description = description
        self.amount = float(amount)
        self.paid_by = paid_by # Name of the person who paid
        self.participants = participants # List of names of people involved in the split
        self.date = date

# --- Session State Initialization ---
# Streamlit's session_state allows data to persist across reruns
if 'members' not in st.session_state:
    st.session_state.members = ['Alice', 'Bob', 'Charlie'] # Default members
if 'expenses' not in st.session_state:
    st.session_state.expenses = []

# --- Functions for Core Logic ---

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
    # Filter out near-zero balances due to floating point inaccuracies
    clean_balances = {member: round(balance, 2) for member, balance in balances.items() if abs(balance) > 0.01}

    # Separate debtors (owe money) and creditors (are owed money)
    debtors = {member: abs(balance) for member, balance in clean_balances.items() if balance < 0}
    creditors = {member: balance for member, balance in clean_balances.items() if balance > 0}

    settlements = []

    # Simple settlement algorithm: process one by one
    for debtor, debt_amount in sorted(debtors.items(), key=lambda item: item[1], reverse=True):
        for creditor, credit_amount in sorted(creditors.items(), key=lambda item: item[1], reverse=True):
            if debt_amount > 0 and credit_amount > 0:
                payment_amount = min(debt_amount, credit_amount)
                settlements.append((debtor, creditor, payment_amount))

                debt_amount -= payment_amount
                creditors[creditor] -= payment_amount # Reduce creditor's outstanding credit

                # If creditor's balance is settled, remove them
                if creditors[creditor] < 0.01:
                    del creditors[creditor]
        # Update debtor's remaining debt (if any)
        debtors[debtor] = debt_amount

    # Filter out any remaining zero-debtors
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
    
    expense_date = st.date_input("Date", value=datetime.now())

    submitted = st.form_submit_button("Add Expense")

    if submitted:
        if not description or amount <= 0 or not paid_by or not participants:
            st.error("Please fill in all fields (description, amount, who paid, and who is involved).")
        else:
            new_expense = Expense(description, amount, paid_by, participants, expense_date)
            st.session_state.expenses.append(new_expense)
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

# --- Expense History Section ---
st.header("🧾 Expense History")
if st.session_state.expenses:

    expenses_data = []
    for exp in st.session_state.expenses:
        expenses_data.append({
            'ID': exp.id[:8] + '...', 
            'Date': exp.date.strftime('%Y-%m-%d'),
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
        st.success("All expenses cleared!")
        st.rerun()

else:
    st.info("No expenses recorded yet. Use the form above to add one!")
