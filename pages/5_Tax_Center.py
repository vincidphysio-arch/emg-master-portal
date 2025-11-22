import streamlit as st
import gspread
import pandas as pd
import json
from datetime import datetime

# --- CONFIGURATION ---
SHEET_LONDON = 'Tugolov combined questionnaire(Responses)'
SHEET_KITCHENER = 'EMG Payments Kitchener'
CREDENTIALS_FILE = 'credentials.json'

# CRA TAX LINE MAPPING (Feature D1)
CRA_MAP = {
    "🚗 Travel/Parking": "Line 9281 - Motor vehicle expenses",
    "🏥 Medical Supplies": "Line 8810 - Office stationery and supplies",
    "📜 Professional Fees/Licenses": "Line 8760 - Business taxes, licences and memberships",
    "🎓 Continuing Education": "Line 8710 - Seminars/Conventions (or Tuition)",
    "💻 Software/Office": "Line 8810 - Office stationery and supplies",
    "🥣 Meals/Entertainment": "Line 8523 - Meals and entertainment (50%)",
    "Other": "Line 9270 - Other expenses"
}

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

def get_combined_data():
    gc = get_connection()
    
    # 1. GET LONDON DATA (Fees)
    try:
        sh_lon = gc.open(SHEET_LONDON)
        ws_lon = sh_lon.get_worksheet(0)
        data_lon = ws_lon.get_all_records()
        df_lon = pd.DataFrame(data_lon)
        
        # Clean London
        # Find Date Col
        lon_date_col = 'Timestamp' if 'Timestamp' in df_lon.columns else 'Date'
        df_lon['Date Object'] = pd.to_datetime(df_lon[lon_date_col], dayfirst=True, errors='coerce')
        
        # Find Fee/Amount
        df_lon['Amount'] = 0.0
        for index, row in df_lon.iterrows():
            # Re-use calc logic or assume 'Fee' column exists if you saved it
            # Ideally, we recalculate to be safe
            t = str(row.get("Type of encounter", "")).lower()
            fee = 0
            if "new consult" in t: fee = 85.00
            elif "non cts" in t: fee = 65.00
            elif "follow up" in t: fee = 65.00
            df_lon.at[index, 'Amount'] = fee
            
        df_lon['Source'] = 'London (Fees)'
        
    except Exception:
        df_lon = pd.DataFrame(columns=['Date Object', 'Amount', 'Source'])

    # 2. GET KITCHENER DATA (Payments)
    try:
        sh_kit = gc.open(SHEET_KITCHENER)
        ws_kit = sh_kit.worksheet("Payments")
        data_kit = ws_kit.get_all_values()
        # Clean headers manually
        headers = [h.strip() for h in data_kit[0]]
        df_kit = pd.DataFrame(data_kit[1:], columns=headers)
        
        # Clean Kitchener
        df_kit['Date Object'] = pd.to_datetime(df_kit['Date'], dayfirst=True, errors='coerce')
        df_kit['Amount'] = pd.to_numeric(df_kit['Amount'].astype(str).str.replace('$','').str.replace(',',''), errors='coerce')
        df_kit['Source'] = 'Kitchener (Paid)'
        
    except Exception:
        df_kit = pd.DataFrame(columns=['Date Object', 'Amount', 'Source'])

    # 3. GET EXPENSES
    try:
        sh_exp = gc.open(SHEET_KITCHENER)
        ws_exp = sh_exp.worksheet("Expenses_Form") # Or 'Expenses' depending on which you use
        data_exp = ws_exp.get_all_values()
        
        # Mapping for Expenses Form (A=Time, B=Date, C=Category, D=Amount)
        structured_exp = []
        if len(data_exp) > 1:
            for row in data_exp[1:]:
                while len(row) < 4: row.append("")
                structured_exp.append({
                    "Date": row[1],
                    "Category": row[2],
                    "Amount": row[3]
                })
        df_exp = pd.DataFrame(structured_exp)
        
        if not df_exp.empty:
            df_exp['Date Object'] = pd.to_datetime(df_exp['Date'], errors='coerce')
            df_exp['Amount'] = pd.to_numeric(df_exp['Amount'].astype(str).str.replace('$','').str.replace(',',''), errors='coerce')
            
    except Exception:
        df_exp = pd.DataFrame(columns=['Date Object', 'Amount', 'Category'])

    return df_lon, df_kit, df_exp

# --- DASHBOARD ---
def main():
    st.set_page_config(page_title="Tax Center", layout="wide")
    
    if st.sidebar.button("⬅️ Back to Home"):
        st.switch_page("Home.py")
        
    st.title("🏛️ Tax Command Center")
    st.caption("Consolidated Financials (London + Kitchener)")

    if st.sidebar.button("🔄 FORCE REFRESH"):
        st.cache_data.clear()
        st.rerun()

    try:
        df_lon, df_kit, df_exp = get_combined_data()
    except Exception as e:
        st.error(f"Data Error: {e}")
        st.stop()

    # --- GLOBAL TIME FILTER ---
    current_year = datetime.now().year
    selected_year = st.sidebar.selectbox("Select Tax Year", [current_year, current_year-1, current_year-2])

    # Filter Dataframes
    df_lon = df_lon[df_lon['Date Object'].dt.year == selected_year]
    df_kit = df_kit[df_kit['Date Object'].dt.year == selected_year]
    df_exp = df_exp[df_exp['Date Object'].dt.year == selected_year]

    # --- CALCULATIONS ---
    london_total = df_lon['Amount'].sum()
    kitchener_total = df_kit['Amount'].sum()
    gross_income = london_total + kitchener_total
    
    total_expenses = df_exp['Amount'].sum()
    net_income = gross_income - total_expenses

    # --- TAX ESTIMATOR (Feature D2) ---
    st.sidebar.divider()
    st.sidebar.header("⚖️ Tax Settings")
    tax_rate = st.sidebar.slider("Est. Tax Rate (%)", 15, 50, 30, help="Include Income Tax + CPP")
    estimated_tax = net_income * (tax_rate / 100)
    safe_to_spend = net_income - estimated_tax

    # --- DISPLAY METRICS ---
    st.subheader(f"Financials for {selected_year}")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Gross Revenue", f"${gross_income:,.2f}", help="London Fees + Kitchener Payments")
    c2.metric("📉 Expenses", f"${total_expenses:,.2f}", delta=f"-{total_expenses/gross_income*100:.1f}%" if gross_income > 0 else "0%")
    c3.metric("💵 Net Income (Profit)", f"${net_income:,.2f}")
    c4.metric("🏛️ Est. Tax Due", f"${estimated_tax:,.2f}", f"@ {tax_rate}% Rate")

    # BIG SUMMARY
    st.markdown(f"""
    <div style="background-color: #d4edda; padding: 20px; border-radius: 10px; text-align: center; border: 1px solid #c3e6cb;">
        <h2 style="color: #155724; margin:0;">✅ Safe to Spend: ${safe_to_spend:,.2f}</h2>
        <p style="color: #155724; margin:0;">(After Expenses & Estimated Taxes)</p>
    </div>
    <br>
    """, unsafe_allow_html=True)

    # --- CRA CATEGORIZATION (Feature D1) ---
    st.subheader("📂 CRA Expense Categories (T2125)")
    
    if not df_exp.empty:
        # Map categories
        df_exp['CRA Line'] = df_exp['Category'].map(CRA_MAP).fillna("Other")
        cra_summary = df_exp.groupby('CRA Line')['Amount'].sum().reset_index()
        
        col_a, col_b = st.columns([2, 1])
        with col_a:
            st.dataframe(cra_summary, use_container_width=True, hide_index=True, column_config={"Amount": st.column_config.NumberColumn(format="$%.2f")})
        with col_b:
            # Show Income Split
            income_data = pd.DataFrame({
                "Source": ["London", "Kitchener"],
                "Amount": [london_total, kitchener_total]
            })
            st.markdown("**Revenue Source**")
            st.bar_chart(income_data.set_index("Source"))
    else:
        st.info("No expenses to categorize yet.")

if __name__ == "__main__":
    main()
