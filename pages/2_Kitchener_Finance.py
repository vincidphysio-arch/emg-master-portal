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
        
        # Data for Selected Year
        year_df = df[df['Year'] == selected_year]
        
        # Data for Previous Year (for YoY comparison)
        prev_year = selected_year - 1
        prev_year_df = df[df['Year'] == prev_year]

        # MONTH SORTING
        available_months = list(year_df['Month_Name'].unique())
        month_order = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
        available_months.sort(key=lambda x: month_order.index(x) if x in month_order else 99, reverse=True)
        
        view_options = ["Current Year (Overview)", "Last X Months"] + available_months
        
        current_month_name = datetime.now().strftime('%B')
        default_idx = 0
        if current_month_name in view_options:
            default_idx = view_options.index(current_month_name)
            
        selected_view = st.sidebar.selectbox("Select View", view_options, index=default_idx)

        # LOGIC & METRICS
        months_divisor = 0
        metric_delta = None # This holds the green/red percentage
        
        if selected_view == "Last X Months":
            # (Code for Last X Months remains the same)
            period_opt = st.sidebar.radio("Select Duration", [3, 6, 9, 12, "Custom"], horizontal=True)
            if period_opt == "Custom":
                months_back = st.sidebar.number_input("Enter number of months", min_value=1, value=3)
            else:
                months_back = period_opt
            
            today = datetime.now()
            start_date = today - pd.DateOffset(months=months_back)
            display_df = df[df['Date Object'] >= start_date]
            view_title = f"Income: Last {months_back} Months"
            months_divisor = months_back
            
        elif selected_view == "Current Year (Overview)":
            current_year = datetime.now().year
            display_df = year_df
            view_title = f"Financial Overview: {selected_year}"
            
            # YoY CALCULATION
            current_total = display_df['Amount'].sum()
            prev_total = prev_year_df['Amount'].sum()
            
            # Only calculate if we have data for previous year
            if prev_total > 0:
                delta_val = current_total - prev_total
                delta_pct = (delta_val / prev_total) * 100
                metric_delta = f"{delta_pct:,.1f}% vs {prev_year}"
            else:
                metric_delta = "No prior year data"

            if selected_year == current_year:
                months_divisor = datetime.now().month
            else:
                months_divisor = 12
            
        else:
            # Specific Month View
            display_df = df[df['Month_Name'] == selected_view]
            # Filter further to ensure it matches the selected YEAR
            display_df = display_df[display_df['Year'] == selected_year]
            view_title = f"Activity in {selected_view} {selected_year}"
            
            # MoM Calculation (Compare to same month last year)
            current_month_total = display_df['Amount'].sum()
            prev_month_df = prev_year_df[prev_year_df['Month_Name'] == selected_view]
            prev_month_total = prev_month_df['Amount'].sum()
            
            if prev_month_total > 0:
                delta_val = current_month_total - prev_month_total
                delta_pct = (delta_val / prev_month_total) * 100
                metric_delta = f"{delta_pct:,.1f}% vs {selected_view} {prev_year}"
            
            months_divisor = 0 

        # --- DISPLAY METRICS ---
        total_income = display_df['Amount'].sum()
        tripic_total = display_df[display_df['Doctor'].astype(str).str.contains("Tripic", case=False)]['Amount'].sum()
        cartagena_total = display_df[display_df['Doctor'].astype(str).str.contains("Cartagena", case=False)]['Amount'].sum()

        st.markdown(f"<h2 style='text-align: center; color: #FF4B4B;'>{view_title}</h2>", unsafe_allow_html=True)
        
        # HEADLINE METRIC WITH DELTA
        if months_divisor > 0:
            monthly_avg = total_income / months_divisor
            st.metric(
                label="Total Income", 
                value=f"${total_income:,.2f}", 
                delta=metric_delta,
                help=f"Average: ${monthly_avg:,.2f}/mo"
            )
        else:
            st.metric(
                label="Total Income", 
                value=f"${total_income:,.2f}", 
                delta=metric_delta
            )

        m1, m2, m3 = st.columns(3)
        m1.metric("Date Range", f"{display_df['Date Object'].min().date()} to {display_df['Date Object'].max().date()}" if not display_df.empty else "-")
        
        if months_divisor > 0:
            m2.metric("👨‍⚕️ Dr. Tripic", f"${tripic_total:,.2f}", f"Avg: ${tripic_total/months_divisor:,.2f}/mo")
            m3.metric("👩‍⚕️ Dr. Cartagena", f"${cartagena_total:,.2f}", f"Avg: ${cartagena_total/months_divisor:,.2f}/mo")
        else:
            m2.metric("👨‍⚕️ Dr. Tripic", f"${tripic_total:,.2f}")
            m3.metric("👩‍⚕️ Dr. Cartagena", f"${cartagena_total:,.2f}")

        st.divider()
        
        # TABLE
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
