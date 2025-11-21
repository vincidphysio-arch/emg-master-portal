import streamlit as st
import gspread
import pandas as pd
import json
from datetime import datetime

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

def get_data():
    gc = get_connection()
    sh = gc.open(SHEET_NAME)
    worksheet = sh.worksheet("Payments")
    
    data = worksheet.get_all_values()
    headers = data[0]
    rows = data[1:]
    cleaned_headers = [h.strip() for h in headers]
    df = pd.DataFrame(rows, columns=cleaned_headers)
    return df

# --- DASHBOARD ---
def main():
    st.set_page_config(page_title="Kitchener Finance", layout="wide")
    
    if st.sidebar.button("⬅️ Back to Home"):
        st.switch_page("Home.py")

    if st.sidebar.button("🔄 FORCE REFRESH"):
        st.cache_data.clear()
        st.rerun()

    try:
        df = get_data()
    except Exception as e:
        st.error(f"Error reading sheet: {e}")
        st.stop()

    st.title("📍 Kitchener Payments")

    if not df.empty:
        # 1. CLEAN DATA
        df = df[df['Date'].astype(str).str.strip() != ""]
        df['Date Object'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date Object'])
        df['Amount'] = pd.to_numeric(df['Amount'].astype(str).str.replace('$','').str.replace(',',''), errors='coerce')
        df['Year'] = df['Date Object'].dt.year
        df['Month_Name'] = df['Date Object'].dt.strftime('%B')

        # --- SIDEBAR ---
        st.sidebar.header("📅 Time Filters")
        available_years = sorted(df['Year'].unique(), reverse=True)
        selected_year = st.sidebar.selectbox("Select Year", available_years)
        year_df = df[df['Year'] == selected_year]

        available_months = list(year_df['Month_Name'].unique())
        month_order = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
        available_months.sort(key=lambda x: month_order.index(x) if x in month_order else 99, reverse=True)
        
        view_options = ["All Months"] + available_months
        
        current_month_name = datetime.now().strftime('%B')
        default_idx = 0
        if current_month_name in available_months:
            default_idx = view_options.index(current_month_name) + 1 
            
        selected_month_view = st.sidebar.selectbox("Select Month", view_options, index=default_idx if current_month_name in available_months else 0)

        # --- YEARLY METRICS ---
        year_total = year_df['Amount'].sum()
        year_tripic = year_df[year_df['Doctor'].astype(str).str.contains("Tripic", case=False)]['Amount'].sum()
        year_cartagena = year_df[year_df['Doctor'].astype(str).str.contains("Cartagena", case=False)]['Amount'].sum()

        st.markdown(f"### 💰 Kitchener Overview: {selected_year}")
        ym1, ym2, ym3 = st.columns(3)
        ym1.metric("Total Income", f"${year_total:,.2f}")
        ym2.metric("👨‍⚕️ Dr. Tripic", f"${year_tripic:,.2f}")
        ym3.metric("👩‍⚕️ Dr. Cartagena", f"${year_cartagena:,.2f}")

        st.divider()

        # --- MONTHLY DETAILS ---
        if selected_month_view == "All Months":
            display_df = year_df
            view_title = f"All Activity in {selected_year}"
        else:
            display_df = year_df[year_df['Month_Name'] == selected_month_view]
            view_title = f"Activity in {selected_month_view} {selected_year}"

        month_total = display_df['Amount'].sum()
        
        # *** NEW BIG CENTERED TITLE ***
        st.markdown(f"<h2 style='text-align: center;'>{view_title}</h2>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='text-align: center; color: #4CAF50;'>Total: ${month_total:,.2f}</h1>", unsafe_allow_html=True)
        
        display_cols = ["Date", "Sender", "Amount", "Doctor"]
        cols_to_show = [c for c in display_cols if c in display_df.columns]
        
        st.dataframe(
            display_df.sort_values(by="Date Object", ascending=False)[cols_to_show], 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("Sheet is connected, but empty.")

if __name__ == "__main__":
    main()
