import streamlit as st
import gspread
import pandas as pd
import json
from datetime import datetime

# --- 🏥 DOCTOR CONFIGURATION ---
DOCTOR_SHEETS = {
    "Dr. Tugolov": "Tugolov combined questionnaire(Responses)",
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
        
        # Get available months for dropdown
        available_months = list(df['Month_Name'].unique())
        month_order = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
        available_months.sort(key=lambda x: month_order.index(x) if x in month_order else 99, reverse=True)
        
        # VIEW OPTIONS
        view_options = ["Current Year (Overview)", "Last X Months"] + available_months
        
        # Default logic
        current_month_name = datetime.now().strftime('%B')
