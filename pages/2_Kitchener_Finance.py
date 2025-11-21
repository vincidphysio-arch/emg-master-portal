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
    
    # Safe loading method (Force headers)
    data = worksheet.get_all_values()
    headers = data[0]
    rows = data[1:]
    cleaned_headers = [h.strip() for h in headers]
    df = pd.DataFrame(rows, columns=cleaned_headers)
    return df

# --- DASHBOARD ---
def main():
    st.set_page_config(page_title="Kitchener Finance", layout="wide")
    
    # Navigation Buttons
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

    if not df.empty:
        # 1. CLEAN DATA
        df = df[df['Date'].astype(str).str.strip() != ""]
        df['Date Object'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date Object'])
        
        # Clean Money
        df['Amount'] = pd.to_numeric(df['Amount'].astype(str).str.replace('$','').str.replace(',',''), errors='coerce')
        
        # Create Time Columns
        df['Year'] = df['Date Object'].dt.year
        df['Month_Name'] = df['Date Object'].dt.strftime('%B')
        df['Month_Year'] = df['Date Object'].dt.strftime('%B %Y')

        # --- SIDEBAR CONTROLS ---
        st.sidebar.header("📅 Time Filters")
        
        # Year Selector
        available_years = sorted(df['Year'].unique(), reverse=True)
        if not available_years:
            st.warning("No yearly data found.")
            st.stop()
            
        selected_year = st.sidebar.selectbox("Select Year", available_years)
        
        # Filter data to this year ONLY
        year_df = df[df['Year'] == selected_year]

        # --- MAIN PAGE: YEARLY OVERVIEW ---
        st.title(f"💰 Kitchener Financial Overview: {selected_year}")
        
        # Calculate Yearly Totals
        year_total = year_df['Amount'].sum()
        year_tripic = year_df[year_df['Doctor'].astype(str).str.contains("Tripic", case=False)]['Amount'].sum()
        year_cartagena = year_df[year_df['Doctor'].astype(str).str.contains("Cartagena", case=False)]['Amount'].sum()

        # Display Yearly Metrics
        ym1, ym2, ym3 = st.columns(3)
        ym1.metric(f"Total Kitchener Income ({selected_year})", f"${year_total:,.2f}")
        ym2.metric("👨‍⚕️ Dr. Tripic (Year)", f"${year_tripic:,.2f}")
        ym3.metric("👩‍⚕️ Dr. Cartagena (Year)", f"${year_cartagena:,.2f}")

        st.divider()

        # --- MONTHLY BREAKDOWN ---
        st.subheader(f"🗓️ Monthly Details ({selected_year})")
        
        # Month Selector
        available_months = list(year_df['Month_Name'].unique())
        month_order = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
        available_months.sort(key=lambda x: month_order.index(x) if x in month_order else 99)
        
        view_options = ["All Months"] + available_months
        selected_month_view = st.selectbox("Filter by Month", view_options)

        # Filter Logic
        if selected_month_view == "All Months":
            display_df = year_df
            view_title = f"All Activity in {selected_year}"
        else:
            display_df = year_df[year_df['Month_Name'] == selected_month_view]
            view_title = f"Activity in {selected_month_view} {selected_year}"

        # Calculate Monthly Metrics
        month_total = display_df['Amount'].sum()
        
        # Show Table
        st.markdown(f"**{view_title}** - Total: **${month_total:,.2f}**")
        
        display_cols = ["Date", "Sender", "Amount", "Doctor"]
        # Only display columns that exist
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
