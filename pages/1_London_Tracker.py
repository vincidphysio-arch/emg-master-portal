import streamlit as st
import gspread
import pandas as pd
import json
from datetime import datetime

# --- 🏥 DOCTOR CONFIGURATION ---
DOCTOR_SHEETS = {
    "Dr. Tugolov": "Tugolov combined questionnaire(Responses)",
    # "Dr. Smith": "Smith Sheet Name"
}

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

def get_data(sheet_name):
    gc = get_connection()
    try:
        sh = gc.open(sheet_name)
        worksheet = sh.get_worksheet(0) 
        return worksheet.get_all_records()
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"❌ Could not find sheet: '{sheet_name}'.")
        st.stop()

# --- DASHBOARD ---
def main():
    st.set_page_config(page_title="London Tracker", layout="wide")
    
    if st.sidebar.button("⬅️ Back to Home"):
        st.switch_page("Home.py")
        
    st.title("🏙️ London, ON Patient Tracker")

    # --- DOCTOR SELECTOR ---
    st.sidebar.header("👨‍⚕️ Select Doctor")
    selected_doc_name = st.sidebar.selectbox("Choose Dashboard:", list(DOCTOR_SHEETS.keys()))
    target_sheet = DOCTOR_SHEETS[selected_doc_name]
    
    if st.sidebar.button("🔄 FORCE REFRESH"):
        st.cache_data.clear()
        st.rerun()

    try:
        data = get_data(target_sheet)
        df = pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error reading sheet: {e}")
        st.stop()

    if not df.empty:
        # 1. CLEAN DATA
        name_col = 'name' if 'name' in df.columns else 'Name'
        if name_col in df.columns:
            df = df[df[name_col].astype(str).str.strip() != ""]
        
        date_col = 'Timestamp' if 'Timestamp' in df.columns else 'Date'
        df['Date Object'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Date Object'])

        # 2. CALC FEES
        def calc_fee(row):
            encounter_col = None
            for col in df.columns:
                if "encounter" in col.lower() or "consult" in col.lower():
                    encounter_col = col
                    break
            
            if encounter_col:
                t = str(row.get(encounter_col, "")).lower()
                if "new consult" in t: return 85.00
                if "non cts" in t: return 65.00
                if "follow up" in t: return 65.00
            return 0.00

        df['Fee'] = df.apply(calc_fee, axis=1)
        
        # 3. TIME COLUMNS
        df['Year'] = df['Date Object'].dt.year
        df['Month_Name'] = df['Date Object'].dt.strftime('%B')
        
        # --- SIDEBAR: TIME FILTERS ---
        st.sidebar.header("📅 Time Filters")
        
        available_years = sorted(df['Year'].unique(), reverse=True)
        selected_year = st.sidebar.selectbox("Select Year", available_years)
        year_df = df[df['Year'] == selected_year]

        # --- MONTH SORTING (DESCENDING) ---
        available_months = list(year_df['Month_Name'].unique())
        month_order = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
        # Reverse=True makes it Dec -> Jan
        available_months.sort(key=lambda x: month_order.index(x) if x in month_order else 99, reverse=True)
        
        view_options = ["All Months"] + available_months
        
        # Auto-select Current Month if available
        current_month_name = datetime.now().strftime('%B')
        default_idx = 0
        if current_month_name in available_months:
            default_idx = view_options.index(current_month_name)
            
        selected_month_view = st.sidebar.selectbox("Select Month", view_options, index=default_idx)

        # --- MAIN PAGE: METRICS ---
        year_total = year_df['Fee'].sum()
        year_patients = len(year_df)
        
        ym1, ym2, ym3 = st.columns(3)
        ym1.metric(f"Total London Income ({selected_year})", f"${year_total:,.2f}")
        ym2.metric("Total Patients (Year)", f"{year_patients}")
        ym3.metric("Avg per Patient", f"${year_total/year_patients:,.2f}" if year_patients > 0 else "$0.00")

        st.divider()

        # --- MONTHLY DETAILS ---
        if selected_month_view == "All Months":
            display_df = year_df
            view_title = f"All Activity in {selected_year}"
            month_total = display_df['Fee'].sum()
            st.subheader(f"🗓️ {view_title}")
            st.markdown(f"**Total: ${month_total:,.2f}**")
        else:
            display_df = year_df[year_df['Month_Name'] == selected_month_view]
            view_title = f"Details for {selected_month_view} {selected_year}"
            
            period_1 = display_df[display_df['Date Object'].dt.day <= 15]
            period_2 = display_df[display_df['Date Object'].dt.day > 15]
            
            st.subheader(f"🗓️ {view_title}")
            col1, col2 = st.columns(2)
            col1.metric("🗓️ 1st - 15th", f"${period_1['Fee'].sum():,.2f}", f"{len(period_1)} patients")
            col2.metric("🗓️ 16th - End", f"${period_2['Fee'].sum():,.2f}", f"{len(period_2)} patients")
            
            st.markdown(f"**Total for Month: ${display_df['Fee'].sum():,.2f}**")

        # Table Display
        potential_cols = [date_col, name_col, "Type of encounter", "Fee", "finalized report ?", "Doctor"]
        final_cols = [c for c in potential_cols if c in display_df.columns]
        
        st.dataframe(
            display_df.sort_values(by="Date Object", ascending=False)[final_cols], 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("No data found.")

if __name__ == "__main__":
    main()
