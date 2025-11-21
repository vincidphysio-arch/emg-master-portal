import streamlit as st
import gspread
import pandas as pd
import json
from datetime import datetime

# --- 🏥 DOCTOR CONFIGURATION ---
DOCTOR_SHEETS = {
    "Dr. Tugolov": "Tugolov combined questionnaire(Responses)",
    # Add new doctors here later: "Dr. Smith": "Smith Sheet Name"
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
        st.error(f"❌ Could not find sheet: '{sheet_name}'. Did you share it with the robot?")
        st.stop()

# --- DASHBOARD ---
def main():
    st.set_page_config(page_title="London Tracker", layout="wide")
    
    if st.sidebar.button("⬅️ Back to Home"):
        st.switch_page("Home.py")
        
    # *** UPDATED TITLE HERE ***
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
        # 1. CLEAN DATES
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

        # 3. MONTH SELECTOR
        df['Month_Year'] = df['Date Object'].dt.strftime('%B %Y')
        available_months = sorted(df['Month_Year'].unique(), key=lambda x: datetime.strptime(x, '%B %Y'), reverse=True)
        
        if available_months:
            current_month_str = datetime.now().strftime('%B %Y')
            default_index = available_months.index(current_month_str) if current_month_str in available_months else 0
            
            selected_month = st.sidebar.selectbox("Choose Month", available_months, index=default_index)
            monthly_df = df[df['Month_Year'] == selected_month]

            # 4. SPLIT PAY PERIODS
            period_1 = monthly_df[monthly_df['Date Object'].dt.day <= 15]
            period_2 = monthly_df[monthly_df['Date Object'].dt.day > 15]

            st.markdown(f"### 📅 Earnings for {selected_month}")
            
            m1, m2, m3 = st.columns(3)
            m1.metric("🗓️ 1st - 15th", f"${period_1['Fee'].sum():,.2f}", f"{len(period_1)} patients")
            m2.metric("🗓️ 16th - End", f"${period_2['Fee'].sum():,.2f}", f"{len(period_2)} patients")
            m3.metric("💰 Month Total", f"${monthly_df['Fee'].sum():,.2f}", "Gross Income")

            st.divider()
            
            # TABLE DISPLAY
            potential_cols = [date_col, name_col, "Type of encounter", "Fee", "finalized report ?", "Doctor"]
            final_cols = [c for c in potential_cols if c in monthly_df.columns]
            
            st.dataframe(
                monthly_df.sort_values(by="Date Object", ascending=False)[final_cols], 
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.warning("No valid dates found.")
    else:
        st.info("No data found.")

if __name__ == "__main__":
    main()
