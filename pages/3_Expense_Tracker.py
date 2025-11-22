import streamlit as st
import gspread
import pandas as pd
import json
from datetime import date, datetime

# --- CONFIGURATION ---
SHEET_NAME = 'EMG Payments Kitchener'
CREDENTIALS_FILE = 'credentials.json'

# --- CONNECT TO GOOGLE ---
@st.cache_resource
def get_connection():
    try:
        if "gcp_json" in st.secrets:
            creds_dict = json.loads(st.secrets["gcp_json"])
            gc = gspread.service_account_from_dict(creds_dict)
        else:
            gc = gspread.service_account(filename=CREDENTIALS_FILE)
        return gc
    except Exception as e:
        st.error(f"❌ Error: {e}")
        st.stop()

def get_expense_data():
    gc = get_connection()
    sh = gc.open(SHEET_NAME)
    try:
        worksheet = sh.worksheet("Expenses")
        data = worksheet.get_all_values()
        # Check if sheet is empty (only headers)
        if len(data) < 2: 
            return pd.DataFrame(columns=["Date", "Category", "Amount", "Description", "Payment Method", "Location"])
        
        headers = data[0]
        rows = data[1:]
        # Create DataFrame using specific headers
        df = pd.DataFrame(rows, columns=headers)
        return df
    except gspread.exceptions.WorksheetNotFound:
        st.error("❌ 'Expenses' tab not found. Please create it in the Kitchener sheet.")
        st.stop()

def add_expense(date_val, category, amount, desc, method, location):
    gc = get_connection()
    sh = gc.open(SHEET_NAME)
    worksheet = sh.worksheet("Expenses")
    
    date_str = date_val.strftime("%Y-%m-%d")
    # Append row WITH Location
    worksheet.append_row([date_str, category, amount, desc, method, location])

# --- DASHBOARD ---
def main():
    st.set_page_config(page_title="Expense Tracker", layout="wide")
    
    if st.sidebar.button("⬅️ Back to Home"):
        st.switch_page("Home.py")

    st.title("💸 Business Expense Tracker")

    # --- INPUT FORM ---
    with st.expander("➕ Log New Expense", expanded=True):
        with st.form("expense_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            
            with c1:
                exp_date = st.date_input("Date", value=date.today())
                category = st.selectbox("Category", [
                    "🚗 Travel/Parking", 
                    "🏥 Medical Supplies", 
                    "📜 Professional Fees/Licenses", 
                    "🎓 Continuing Education",
                    "💻 Software/Office", 
                    "🥣 Meals/Entertainment",
                    "Other"
                ])
                amount = st.number_input("Amount ($)", min_value=0.0, step=0.01, format="%.2f")
            
            with c2:
                # NEW: Location Selector
                location = st.selectbox("Location / Context", ["General / Both", "London", "Kitchener"])
                payment_method = st.selectbox("Paid Via", ["Credit Card", "Debit", "Cash", "E-Transfer"])
                description = st.text_input("Description (e.g., 'Parking at Hospital')")
            
            submitted = st.form_submit_button("💾 Save Expense")
            
            if submitted:
                if amount > 0:
                    add_expense(exp_date, category, amount, description, payment_method, location)
                    st.success("✅ Expense Saved!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning("⚠️ Amount must be greater than $0")

    st.divider()

    # --- DISPLAY DATA ---
    if st.sidebar.button("🔄 FORCE REFRESH"):
        st.cache_data.clear()
        st.rerun()

    try:
        df = get_expense_data()
    except Exception as e:
        st.error(f"Error: {e}")
        st.stop()

    if not df.empty:
        # Clean Data
        df['Amount'] = pd.to_numeric(df['Amount'].astype(str).str.replace('$','').str.replace(',',''), errors='coerce')
        df['Date Object'] = pd.to_datetime(df['Date'], errors='coerce')
        df['Year'] = df['Date Object'].dt.year
        
        # Year Filter
        available_years = sorted(df['Year'].dropna().unique(), reverse=True)
        
        if available_years:
            selected_year = st.sidebar.selectbox("Filter Year", available_years)
            year_df = df[df['Year'] == selected_year]
            
            # Metrics
            total_exp = year_df['Amount'].sum()
            
            # Calculate Split by Location if column exists
            london_exp = 0
            kitchener_exp = 0
            general_exp = 0
            
            if "Location" in year_df.columns:
                london_exp = year_df[year_df['Location'] == "London"]['Amount'].sum()
                kitchener_exp = year_df[year_df['Location'] == "Kitchener"]['Amount'].sum()
                general_exp = year_df[year_df['Location'].str.contains("General", case=False, na=False)]['Amount'].sum()

            st.subheader(f"Expenses for {selected_year}")
            
            # Metrics Row
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("📉 Total", f"${total_exp:,.2f}")
            m2.metric("🏙️ London", f"${london_exp:,.2f}")
            m3.metric("📍 Kitchener", f"${kitchener_exp:,.2f}")
            m4.metric("🏢 General", f"${general_exp:,.2f}")
            
            # Chart & Table
            c1, c2 = st.columns([1, 2])
            with c1:
                st.markdown("**By Category**")
                cat_groups = year_df.groupby("Category")['Amount'].sum().sort_values(ascending=False)
                st.bar_chart(cat_groups)
            
            with c2:
                st.markdown("**Expense Log**")
                cols_to_show = ["Date", "Category", "Amount", "Location", "Description"]
                # Only show cols that exist
                final_cols = [c for c in cols_to_show if c in year_df.columns]
                
                st.dataframe(
                    year_df.sort_values(by="Date Object", ascending=False)[final_cols], 
                    use_container_width=True, 
                    hide_index=True
                )
    else:
        st.info("No expenses logged yet.")

if __name__ == "__main__":
    main()
