import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import uuid
import json
import os
import plotly.express as px
from io import BytesIO

DATA_FILE = "household_data.json"

# --- Streamlit Page Configuration for Visual Appeal ---
st.set_page_config(
    page_title="Household Splitter",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for visual enhancements ---
st.markdown(
    """
    <style>
    /* Main container background and text color */
    .st-emotion-cache-z5fcl4 {
        background-color: #1e1e1e;
        color: #f0f2f6;
    }
    .st-emotion-cache-1cyp85f {
        background-color: #1e1e1e;
    }

    /* Sidebar background */
    [data-testid="stSidebar"] {
        background-color: #2b2b2b;
    }
    [data-testid="stSidebarContent"] {
        background-color: #2b2b2b;
    }

    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: #64ffda;
    }

    /* Buttons */
    .stButton>button {
        color: #64ffda;
        background-color: #3a3a3a;
        border-radius: 5px;
        border: 1px solid #64ffda;
        padding: 0.6rem 1.2rem;
    }
    .stButton>button:hover {
        background-color: #64ffda;
        color: #1e1e1e;
        border: 1px solid #64ffda;
    }

    /* DataFrames */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #4a4a4a;
    }

    /* Metrics */
    .stMetric {
        background-color: #2b2b2b;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #4a4a4a;
        margin-bottom: 15px;
    }
    /* Make metric labels and values more readable */
    .stMetric label {
        color: #f0f2f6;
        font-size: 1rem;
    }
    .stMetric div[data-testid="stMetricValue"] {
        color: #64ffda;
        font-size: 2.5rem;
        font-weight: bold;
    }
    .stMetric div[data-testid="stMetricDelta"] {
        color: #f0f2f6;
    }

    /* Expander styling */
    .stExpander {
        background-color: #2b2b2b;
        border-radius: 10px;
        border: 1px solid #4a4a4a;
        margin-bottom: 15px;
        padding: 10px;
    }
    .stExpander details summary p {
        color: #f0f2f6;
    }
    .stExpander details summary {
        color: #f0f2f6;
    }

    /* Input fields (text input, selectbox, date input, multiselect) */
    .stTextInput>div>div>input,
    .stSelectbox>div>div>div>div>span,
    .stDateInput>div>div>input,
    .stMultiSelect>div>div>div>div {
        background-color: #3a3a3a;
        color: #f0f2f6;
        border: 1px solid #4a4a4a;
        border-radius: 5px;
        padding: 0.5rem 1rem;
    }
    /* Textarea */
    .stTextArea>div>div>textarea {
        background-color: #3a3a3a;
        color: #f0f2f6;
        border: 1px solid #4a4a4a;
        border-radius: 5px;
        padding: 0.5rem 1rem;
    }

    /* Info/Success/Warning alerts */
    .stAlert {
        border-radius: 8px;
        padding: 10px 15px;
    }
    .stAlert.info {
        background-color: #34495e;
        color: #ecf0f1;
        border-left: 5px solid #2980b9;
    }
    .stAlert.success {
        background-color: #27ae60;
        color: #ecf0f1;
        border-left: 5px solid #2ecc71;
    }
    .stAlert.warning {
        background-color: #f39c12;
        color: #ecf0f1;
        border-left: 5px solid #e67e22;
    }
    .stAlert.error {
        background-color: #c0392b;
        color: #ecf0f1;
        border-left: 5px solid #e74c3c;
    }

    /* Adjust Streamlit specific elements for better dark theme compatibility */
    .st-emotion-cache-10o5u_1 {
        color: #f0f2f6;
    }

    </style>
    """,
    unsafe_allow_html=True
)

# --- Initialize session state variables at the top ---
# This ensures they always exist before being accessed
if 'members' not in st.session_state:
    st.session_state.members = ['Alice', 'Bob', 'Charlie', 'Tim']
if 'expenses' not in st.session_state:
    st.session_state.expenses = []
if 'recurring_expenses' not in st.session_state:
    st.session_state.recurring_expenses = []
if 'data_loaded_flag' not in st.session_state:
    st.session_state.data_loaded_flag = False # Flag to control initial data load

DATA_FILE = "household_data.json"

DEFAULT_CATEGORIES = [
    "Groceries",
    "Utilities",
    "Rent",
    "Transport",
    "Dining Out",
    "Entertainment",
    "Shopping",
    "Health",
    "Education/School",
    "Miscellaneous/other"
]

class Exp:
    def __init__(self, desc, amt, pd_by, parts, dt_obj, category="Uncategorized"):
        self.id = str(uuid.uuid4())
        self.description = desc
        self.amount = float(amt)
        self.paid_by = pd_by
        self.participants = parts
        self.category = category

        if isinstance(dt_obj, (datetime, date)):
            self.date = dt_obj.strftime('%Y-%m-%d')
        elif isinstance(dt_obj, str):
            self.date = dt_obj
        else:
            raise TypeError("Unsupported date type encountered!")

    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "amount": self.amount,
            "paid_by": self.paid_by,
            "participants": self.participants,
            "date": self.date,
            "category": self.category
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            data['description'],
            data['amount'],
            data['paid_by'],
            data['participants'],
            data['date'],
            data.get('category', 'Uncategorized')
        )

# New class for recurring expenses
class RecurringExp:
    def __init__(self, desc, amt, pd_by, parts, category, frequency):
        self.id = str(uuid.uuid4())
        self.description = desc
        self.amount = float(amt)
        self.paid_by = pd_by
        self.participants = parts
        self.category = category
        self.frequency = frequency # e.g., "Monthly", "Weekly"
        self.last_generated = None # To store the last date this recurring expense was generated

    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "amount": self.amount,
            "paid_by": self.paid_by,
            "participants": self.participants,
            "category": self.category,
            "frequency": self.frequency,
            "last_generated": self.last_generated
        }

    @classmethod
    def from_dict(cls, data):
        rec_exp = cls(
            data['description'],
            data['amount'],
            data['paid_by'],
            data['participants'],
            data['category'],
            data['frequency']
        )
        rec_exp.last_generated = data.get('last_generated')
        return rec_exp

def sv_dat(mems, exps, rec_exps):
    data_to_save = {
        "members": mems,
        "expenses": [exp.to_dict() for exp in exps],
        "recurring_expenses": [rec_exp.to_dict() for rec_exp in rec_exps]
    }
    with open(DATA_FILE, "w") as f:
        json.dump(data_to_save, f, indent=4)
    st.sidebar.success("Data saved!")

def ld_dat():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data_loaded = json.load(f)
            st.session_state.members = data_loaded.get("members", ['Alice', 'Bob', 'Charlie', 'Tim'])
            st.session_state.expenses = [
                Exp.from_dict(exp_dict) for exp_dict in data_loaded.get("expenses", [])
            ]
            st.session_state.recurring_expenses = [
                RecurringExp.from_dict(rec_exp_dict) for rec_exp_dict in data_loaded.get("recurring_expenses", [])
            ]

        # Ensure all expenses have a category
        for exp in st.session_state.expenses:
            if not hasattr(exp, 'category'):
                exp.category = 'Uncategorized'
        
        st.sidebar.success("Data loaded!")
    # No else block here, as default initialization is done at the very top.

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

    setts = []

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

def disp_mems():
    st.header("Manage Members")
    st.write("Easily add, remove, or update the members of your household/group here. Keeping this list accurate ensures fair splitting!")
    
    col_input, col_button = st.columns([3, 1])
    with col_input:
        curr_mems_input = st.text_area(
            "Edit Members (one name per line)",
            value="\n".join(st.session_state.members),
            height=100
        )
    with col_button:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        if st.button("Update Members"):
            new_mems = [name.strip() for name in curr_mems_input.split('\n') if name.strip()]
            st.session_state.members = new_mems
            sv_dat(st.session_state.members, st.session_state.expenses, st.session_state.recurring_expenses)
            st.success("Members updated!")
            st.rerun()

def disp_add_exp():
    st.header("➕ Add New Expense")
    st.write("Log new expenses quickly and accurately. Specify who paid, who shared the cost, and categorize it for better tracking.")
    st.image("https://bookkeepers.com/wp-content/uploads/2020/01/monthly-expenses-planning-checklist-receipts-wallet-how-to-stick-to-a-budget-ss-featured.jpg", caption="Record your latest spending with ease", use_container_width =True)

    with st.form("add_expense_form", clear_on_submit=True):
        desc = st.text_input("Description")
        amt = st.number_input("Amount ($)", min_value=0.01, format="%.2f")
        category = st.selectbox("Category", options=DEFAULT_CATEGORIES, key="category_select")

        pd_by = None
        parts = []
        if st.session_state.members:
            col_paidby, col_participants = st.columns(2)
            with col_paidby:
                pd_by = st.selectbox("Who Paid?", options=st.session_state.members, key="paid_by_select")
            with col_participants:
                parts = st.multiselect(
                    "Who is involved in the split?",
                    options=st.session_state.members,
                    default=st.session_state.members,
                    key="participants_multiselect"
                )
        else:
            st.warning("Add members first in the 'Manage Members' section to add expenses.")

        exp_dt = st.date_input("Date", value=datetime.now().date(), key="expense_date_input")

        sub = st.form_submit_button("Add Expense")

        if sub:
            if not desc or pd_by is None or not parts:
                st.error("Please fill in all fields (description, who paid, and who is involved).")
            else:
                new_exp = Exp(desc, amt, pd_by, parts, exp_dt, category)
                st.session_state.expenses.append(new_exp)
                sv_dat(st.session_state.members, st.session_state.expenses, st.session_state.recurring_expenses)
                st.success("Expense added successfully!")
                st.rerun()

# Function for recurring expenses manager
def disp_recurring_exp_manager():
    st.header("🔄 Manage Recurring Expenses")
    st.write("Define expenses that happen regularly (e.g., rent, subscriptions) and easily add them to your history.")

    with st.form("add_recurring_expense_form", clear_on_submit=True):
        rec_desc = st.text_input("Recurring Expense Description")
        rec_amt = st.number_input("Recurring Amount ($)", min_value=0.01, format="%.2f")
        rec_category = st.selectbox("Recurring Category", options=DEFAULT_CATEGORIES, key="rec_category_select")

        rec_pd_by = None
        rec_parts = []
        if st.session_state.members:
            col_rec_paidby, col_rec_participants = st.columns(2)
            with col_rec_paidby:
                rec_pd_by = st.selectbox("Who Usually Pays?", options=st.session_state.members, key="rec_paid_by_select")
            with col_rec_participants:
                rec_parts = st.multiselect(
                    "Who is Usually Involved?",
                    options=st.session_state.members,
                    default=st.session_state.members,
                    key="rec_participants_multiselect"
                )
        else:
            st.warning("Add members first to define recurring expenses.")

        rec_frequency = st.selectbox("Frequency", ["Monthly", "Weekly", "Annually"], key="rec_frequency_select")

        sub_rec = st.form_submit_button("Add Recurring Expense Definition")

        if sub_rec:
            if not rec_desc or rec_pd_by is None or not rec_parts:
                st.error("Please fill in all fields for the recurring expense definition.")
            else:
                new_rec_exp = RecurringExp(rec_desc, rec_amt, rec_pd_by, rec_parts, rec_category, rec_frequency)
                st.session_state.recurring_expenses.append(new_rec_exp)
                sv_dat(st.session_state.members, st.session_state.expenses, st.session_state.recurring_expenses)
                st.success(f"Recurring expense '{rec_desc}' added!")
                st.rerun()

    st.markdown("---")
    st.subheader("Defined Recurring Expenses")
    if st.session_state.recurring_expenses:
        rec_exps_data = []
        for rec_exp in st.session_state.recurring_expenses:
            rec_exps_data.append({
                'ID': rec_exp.id[:8] + '...',
                'Full ID': rec_exp.id,
                'Description': rec_exp.description,
                'Amount': f"${rec_exp.amount:.2f}",
                'Paid By': rec_exp.paid_by,
                'Participants': ", ".join(rec_exp.participants),
                'Category': rec_exp.category,
                'Frequency': rec_exp.frequency,
                'Last Generated': rec_exp.last_generated if rec_exp.last_generated else 'Never'
            })
        df_rec_exps = pd.DataFrame(rec_exps_data)
        st.dataframe(df_rec_exps.drop(columns=['Full ID']).set_index('ID'), use_container_width=True)

        st.markdown("---")
        st.subheader("Generate Recurring Expenses for Today")
        st.info("Click this button to add current recurring expenses to your main expense history. It will only add expenses not generated recently (within the last 30 days for simplicity).")
        if st.button("Generate Recurring Expenses Now"):
            generated_count = 0
            current_date_str = date.today().strftime('%Y-%m-%d')
            for rec_exp in st.session_state.recurring_expenses:
                already_generated_recently = False
                for existing_exp in st.session_state.expenses:
                    # Check for similar expense added within the last 30 days
                    if (existing_exp.description == rec_exp.description and
                        existing_exp.amount == rec_exp.amount and
                        existing_exp.paid_by == rec_exp.paid_by and
                        existing_exp.category == rec_exp.category and
                        (datetime.strptime(current_date_str, '%Y-%m-%d').date() - datetime.strptime(existing_exp.date, '%Y-%m-%d').date()).days < 30):
                        already_generated_recently = True
                        break

                if not already_generated_recently:
                    new_exp = Exp(rec_exp.description, rec_exp.amount, rec_exp.paid_by, rec_exp.participants, datetime.now().date(), rec_exp.category)
                    st.session_state.expenses.append(new_exp)
                    rec_exp.last_generated = current_date_str # Update last generated date
                    generated_count += 1

            sv_dat(st.session_state.members, st.session_state.expenses, st.session_state.recurring_expenses)
            if generated_count > 0:
                st.success(f"Successfully generated {generated_count} recurring expense(s)!")
            else:
                st.info("No new recurring expenses to generate at this time, or they've been generated recently.")
            st.rerun()

        st.markdown("---")
        st.subheader("Delete a Specific Recurring Expense Definition")
        rec_exp_id_to_del_display = st.text_input("Enter the (short) ID of the recurring expense to delete:", key="del_rec_exp_id_input")
        if st.button("Delete Recurring Expense Definition"):
            full_id_to_delete = None
            for row in rec_exps_data:
                if row['ID'] == rec_exp_id_to_del_display:
                    full_id_to_delete = row['Full ID']
                    break

            if full_id_to_delete:
                st.session_state.recurring_expenses = [
                    rec_exp for rec_exp in st.session_state.recurring_expenses if rec_exp.id != full_id_to_delete
                ]
                sv_dat(st.session_state.members, st.session_state.expenses, st.session_state.recurring_expenses)
                st.success(f"Recurring expense definition '{rec_exp_id_to_del_display}' deleted!")
                st.rerun()
            else:
                st.error("Recurring Expense ID not found. Please enter a valid shortened ID from the list.")

    else:
        st.info("No recurring expenses defined yet. Use the form above to add one!")

def disp_curr_bals():
    st.header("Current Balances")
    st.write("See who owes what to whom. This section provides a real-time overview of how much each person owes other members.")

    bals = calc_bals(st.session_state.members, st.session_state.expenses)

    st.dataframe(pd.DataFrame(
        [{'Member': mem, 'Balance': f"${bal:.2f}"} for mem, bal in bals.items()]
    ).set_index('Member'), use_container_width=True)

    st.subheader("Suggested Settlements")
    setts = sug_setts(bals)
    if setts:
        for deb, cred, amt in setts:
            st.info(f"**{deb}** pays **{cred}** **${amt:.2f}**")
    else:
        st.success("All balances are currently settled!")

def disp_exp_hist():
    st.header("Expense History")
    st.write("Review all past expenses. You can also delete specific entries or clear the entire history if you want to start fresh.")

    if st.session_state.expenses:
        # Prepare data for export
        export_data = []
        for exp in st.session_state.expenses:
            export_data.append({
                'Date': exp.date,
                'Description': exp.description,
                'Amount': exp.amount,
                'Paid By': exp.paid_by,
                'Participants': ", ".join(exp.participants),
                'Category': exp.category,
                'ID': exp.id
            })
        df_export = pd.DataFrame(export_data)

        # Export buttons (now styled to be small and inline)
        col_buttons = st.columns(2) # Create two columns for the buttons
        with col_buttons[0]:
            st.download_button(
                label="**Export to CSV**", # Bold label for emphasis
                data=df_export.to_csv(index=False).encode('utf-8'),
                file_name="household_expenses.csv",
                mime="text/csv",
                help="Download all recorded expenses in CSV format."
            )
        with col_buttons[1]:
            try:
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='Expenses')
                output.seek(0)
                st.download_button(
                    label="**Export to Excel**", # Bold label for emphasis
                    data=output.read(),
                    file_name="household_expenses.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Download all recorded expenses in Excel (.xlsx) format."
                )
            except ImportError:
                st.warning("Install `openpyxl` (`pip install openpyxl`) to enable Excel export.")

        st.markdown("---") # Add a separator after the buttons

        exps_data = []
        for exp in st.session_state.expenses:
            exps_data.append({
                'ID': exp.id[:8] + '...',
                'Full ID': exp.id,
                'Date': exp.date,
                'Description': exp.description,
                'Amount': f"${exp.amount:.2f}",
                'Paid By': exp.paid_by,
                'Participants': ", ".join(exp.participants),
                'Category': exp.category
            })
        df_exps = pd.DataFrame(exps_data)
        st.dataframe(df_exps.drop(columns=['Full ID']).set_index('ID'), use_container_width=True)

        st.markdown("---")
        st.subheader("Delete a Specific Expense")
        exp_id_to_del_display = st.text_input("Enter the (short) ID of the expense to delete:", key="del_exp_id_input")
        if st.button("Delete Expense"):
            full_id_to_delete = None
            for row in exps_data:
                if row['ID'] == exp_id_to_del_display:
                    full_id_to_delete = row['Full ID']
                    break

            if full_id_to_delete:
                st.session_state.expenses = [
                    exp for exp in st.session_state.expenses if exp.id != full_id_to_delete
                ]
                sv_dat(st.session_state.members, st.session_state.expenses, st.session_state.recurring_expenses)
                st.success(f"Expense '{exp_id_to_del_display}' deleted!")
                st.rerun()
            else:
                st.error("Expense ID not found. Please enter a valid shortened ID from the list.")

        st.markdown("---")
        if st.button("Clear All Expenses (Start Fresh)"):
            st.session_state.expenses = []
            sv_dat(st.session_state.members, st.session_state.expenses, st.session_state.recurring_expenses)
            st.success("All expenses cleared!")
            st.rerun()

    else:
        st.info("No expenses recorded yet. Use the form above to add one.")

def disp_vis_sum():
    st.header("Visual Summary of Expenses")
    st.write("Understand your spending habits with these charts. Understand who pays what, where your money goes, and how spending trends over time.")

    if not st.session_state.expenses:
        st.info("Add some expenses to see the visualizations here!")
        return

    col1, col2 = st.columns(2)

    with col1:
        total_spent = sum(exp.amount for exp in st.session_state.expenses)
        st.metric(label="Total Household Spending", value=f"${total_spent:.2f}")

    with col2:
        exp_df = pd.DataFrame([exp.to_dict() for exp in st.session_state.expenses])
        
        st.expander("Spending by Payer", expanded=True)
        st.write("This pie chart illustrates the proportion of expenses paid by each member, giving you a sense of financial contributions.")
        payer_spending = exp_df.groupby('paid_by')['amount'].sum().reset_index()
        payer_spending.columns = ['Payer', 'Amount Paid']
        fig_payer = px.pie(payer_spending, values='Amount Paid', names='Payer',
                           title='Who Paid What?', hole=0.3,
                           color_discrete_sequence=px.colors.sequential.RdBu,
                           template='plotly_dark')
        fig_payer.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_payer, use_container_width=True)
    
    st.markdown("---")
    st.subheader("Spending by Category")
    st.expander("Category Breakdown", expanded=True)
    st.write("Understand where your household spending is concentrated. This bar chart breaks down expenses by category.")
    category_spending = exp_df.groupby('category')['amount'].sum().reset_index()
    category_spending.columns = ['Category', 'Amount']
    fig_category = px.bar(category_spending, x='Category', y='Amount',
                          title='Spending Per Category',
                          color='Amount',
                          color_continuous_scale='Viridis',
                          template='plotly_dark')
    st.plotly_chart(fig_category, use_container_width=True)

    st.markdown("---")
    st.subheader("Individual Balance Overview")

    bals = calc_bals(st.session_state.members, st.session_state.expenses)
    bals_df = pd.DataFrame(list(bals.items()), columns=['Member', 'Balance'])

    st.expander("Net Balances", expanded=False)
    st.write("This chart visualizes the net balance for each member. Positive bars indicate money owed to them, while negative bars show what they owe.")
    fig_bals = px.bar(bals_df, x='Member', y='Balance',
                      color='Balance',
                      color_continuous_scale='RdYlGn',
                      title='Net Balance Per Member',
                      template='plotly_dark')
    fig_bals.update_layout(showlegend=False)
    st.plotly_chart(fig_bals, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.expander("Spending Trend Over Time")
    st.write("Track your household's spending patterns over time to identify trends or peak spending periods.")
    
    exp_df['date'] = pd.to_datetime(exp_df['date'])
    daily_spending = exp_df.groupby('date')['amount'].sum().reset_index()
    daily_spending = daily_spending.sort_values('date')

    fig_trend = px.line(daily_spending, x='date', y='amount',
                        title='Daily Spending Trend',
                        labels={'date': 'Date', 'amount': 'Amount ($)'},
                        template='plotly_dark')
    st.plotly_chart(fig_trend, use_container_width=True)

def main():
    st.title("🏡 Simple Household Splitter (No More Cheating... You pay what you truly owe💵💵💵)")
    st.write("Welcome to your ultimate tool for managing shared household expenses! Easily track spending, calculate balances, and simplify settlements among housemates.")

    # Only load data from file if not already loaded in this session
    if not st.session_state.data_loaded_flag:
        ld_dat()
        st.session_state.data_loaded_flag = True

    st.sidebar.header("Navigation")
    page_sel = st.sidebar.radio("Go To", ["Home", "Visual Summary"])

    st.sidebar.markdown("---")
    st.sidebar.header("About This App")
    st.sidebar.info(
        "This application helps households fairly split expenses. "
        "Add members, log expenses, and instantly see who owes whom. "
        "The visual summary provides insights into spending habits."
    )

    st.markdown("---")

    if page_sel == "Home":
        disp_mems()

        st.markdown("---")
        disp_add_exp()

        st.markdown("---")
        disp_recurring_exp_manager()

        st.markdown("---")
        disp_curr_bals()

        st.markdown("---")
        disp_exp_hist()
        
    elif page_sel == "Visual Summary":
        disp_vis_sum()

if __name__ == "__main__":
    main()
