import streamlit as st
import pandas as pd
from datetime import datetime, date
import uuid
import json
import os

 # --- Config ---
DATA_FILE = "household_data.json"

# --- Data Model ---
class Exp:
    def __init__(self, desc, amt, pd_by, parts, dt_obj):
        self.id = str(uuid.uuid4())
        self.description = desc
        self.amount = float(amt)
        self.paid_by = pd_by
        self.participants = parts

        # Simplified date handling - expects correct input or will error
        if isinstance(dt_obj, (datetime, date)):
            self.date = dt_obj.strftime('%Y-%m-%d')
        elif isinstance(dt_obj, str):
            self.date = dt_obj
        else:
            raise TypeError("Unsupported date type encountered!") # Less specific error message

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

# --- Data Persistence ---
def sv_dat(mems, exps):
    data_to_save = {
        "members": mems,
        "expenses": [exp.to_dict() for exp in exps]
    }
    # No explicit try-except for file I/O for less "perfect" handling
    with open(DATA_FILE, "w") as f:
        json.dump(data_to_save, f, indent=4)
    st.sidebar.success("Data saved!")

def ld_dat():
    if os.path.exists(DATA_FILE):
        # No explicit try-except for JSON decode/file access for less "perfect" handling
        with open(DATA_FILE, "r") as f:
            data_loaded = json.load(f)
            st.session_state.members = data_loaded.get("members", ['Alice', 'Bob', 'Charlie'])
            st.session_state.expenses = [
                Exp.from_dict(exp_dict) for exp_dict in data_loaded.get("expenses", [])
            ]
        st.sidebar.success("Data loaded!")
    else:
        st.session_state.members = ['Alice', 'Bob', 'Charlie', 'Tim']
        st.session_state.expenses = []

# --- Core Logic ---
def calc_bals(mems, exps):
    bals = {mem: 0.0 for mem in mems}

    for exp in exps:
        if exp.paid_by in bals:
            bals[exp.paid_by] += exp.amount

        valid_parts = [p for p in exp.participants if p in mems]
        num_parts = len(valid_parts)

        if num_parts > 0:
            split_amt = exp.amount / num_parts
            for part in valid_parts:
                bals[part] -= split_amt
    return bals

def sug_setts(bals):
    clean_bals = {mem: round(bal, 2) for mem, bal in bals.items() if abs(bal) > 0.01}

    debtors = {mem: abs(bal) for mem, bal in clean_bals.items() if bal < 0}
    creds = {mem: bal for mem, bal in clean_bals.items() if bal > 0}

    setts = [ ]

    sorted_debtors = sorted(debtors.items(), key=lambda item: item[1], reverse=True)
    sorted_creds = sorted(creds.items(), key=lambda item: item[1], reverse=True)

    d_idx = 0
    c_idx = 0

    while d_idx < len(sorted_debtors) and c_idx < len(sorted_creds):
        deb_name, current_deb = sorted_debtors[d_idx]
        cred_name, current_cred = sorted_creds[c_idx]

        if current_deb <= 0.01:
            d_idx += 1
            continue
        if current_cred <= 0.01:
            c_idx += 1
            continue

        pay_amt = min(current_deb, current_cred)
        setts.append((deb_name, cred_name, pay_amt))

        sorted_debtors[d_idx] = (deb_name, current_deb - pay_amt)
        sorted_creds[c_idx] = (cred_name, current_cred - pay_amt)

    setts = [(d, c, amt) for d, c, amt in setts if amt > 0.01]
    return setts

# --- UI Components ---

def disp_mems():
    st.header("Manage Members")
    curr_mems_input = st.text_area(
        "Edit Members (one name per line)",
        value="\n".join(st.session_state.members),
        height=100
    )
    if st.button("Update Members") :
        new_mems = [name.strip() for name in curr_mems_input.split('\n') if name.strip()]
        st.session_state.members = new_mems
        sv_dat(st.session_state.members, st.session_state.expenses)
        st.success("Members updated!")
        st.rerun()

def disp_add_exp():
    st.header("➕ Add New Expense")
    with st.form("add_expense_form", clear_on_submit=True):
        desc = st.text_input("Description")
        amt = st.number_input("Amount ($)", min_value=0.01, format="%.2f")

        pd_by = None
        parts = []
        if st.session_state.members:
            pd_by = st.selectbox("Who Paid?", options=st.session_state.members, key="paid_by_select")
            parts = st.multiselect(
                "Who is involved in the split?",
                options=st.session_state.members,
                default=st.session_state.members,
                key="participants_multiselect"
            )
        else:
            st.warning("Please add members first in the 'Manage Members' section to add expenses.")

        exp_dt = st.date_input("Date", value=datetime.now().date(), key="expense_date_input")

        sub = st.form_submit_button("Add Expense")

        if sub:
            # Less strict error checks
            if not desc or pd_by is None or not parts:
                st.error("Please fill in all fields (description, who paid, and who is involved).")
            else:
                new_exp = Exp(desc, amt, pd_by, parts, exp_dt)
                st.session_state.expenses.append(new_exp)
                sv_dat(st.session_state.members, st.session_state.expenses)
                st.success("Expense added successfully!")
                st.rerun()

def disp_curr_bals():
    st.header("Current Balances")
    bals = calc_bals(st.session_state.members, st.session_state.expenses)

    bals_df = pd.DataFrame(
        [{'Member': mem, 'Balance': f"${bal:.2f}"} for mem, bal in bals.items()]
    )
    st.dataframe(bals_df.set_index('Member'), use_container_width=True)

    st.subheader("🤝 Suggested Settlements")
    setts = sug_setts(bals)
    if setts:
        for deb, cred, amt in setts:
            st.info(f"**{deb}** pays **{cred}** **${amt:.2f}**")
    else:
        st.success("All balances are currently settled!")

def disp_exp_hist():
    st.header("Expense History")
    if st.session_state.expenses:
        exps_data = [ ]
        for exp in st.session_state.expenses:
            exps_data.append({
                'ID': exp.id[:8] + '...',
                'Date': exp.date,
                'Description': exp.description,
                'Amount': f"${exp.amount:.2f}",
                'Paid By': exp.paid_by,
                'Participants': ", ".join(exp.participants)
            })
        df_exps = pd.DataFrame(exps_data)
        st.dataframe(df_exps.set_index('ID'), use_container_width=True)

        st.markdown("---")
        if st.button("Clear All Expenses (Start Fresh)"):
            st.session_state.expenses = []
            sv_dat(st.session_state.members, st.session_state.expenses)
            st.success("All expenses cleared!")
            st.rerun()

    else:
        st.info("No expenses recorded yet. Use the form above to add one!")

# --- Main App ---
def main():
    st.title("Simple Household Splitter(No More Cheating... You pay what you truly owe💵💵💵)")

    # Initial data load check
    if 'data_loaded_flag' not in st.session_state:
        ld_dat()
        st.session_state.data_loaded_flag = True

    st.markdown("---")
    disp_mems()

    st.markdown("---")
    disp_add_exp()

    st.markdown("---")
    disp_curr_bals()

    st.markdown("---")
    disp_exp_hist()

# Run the code here
if __name__ == "__main__":
    main()
