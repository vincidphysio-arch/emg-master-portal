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
        
        # --- SIDEBAR: FILTERS ---
        st.sidebar.header("📅 Time Filters")
        available_years = sorted(df['Year'].unique(), reverse=True)
        selected_year = st.sidebar.selectbox("Select Year", available_years)
        year_df = df[df['Year'] == selected_year]

        available_months = list(year_df['Month_Name'].unique())
        month_order = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
        available_months.sort(key=lambda x: month_order.index(x) if x in month_order else 99, reverse=True)
        
        view_options = ["Current Year (Overview)", "Last X Months"] + available_months
        
        current_month_name = datetime.now().strftime('%B')
        default_idx = 0
        if current_month_name in view_options:
            default_idx = view_options.index(current_month_name)
            
        selected_view = st.sidebar.selectbox("Select View", view_options, index=default_idx)

        # --- SIDEBAR: GOAL TRACKER (Feature C5) ---
        st.sidebar.divider()
        st.sidebar.header("🎯 Goal Tracker")
        monthly_goal = st.sidebar.number_input("Monthly Goal ($)", value=10000, step=500)

        # LOGIC
        months_back = 0
        months_divisor = 0
        target_income = 0

        if selected_view == "Last X Months":
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
            target_income = monthly_goal * months_back

        elif selected_view == "Current Year (Overview)":
            current_year = datetime.now().year
            display_df = df[df['Year'] == current_year]
            view_title = f"Financial Overview: {current_year}"
            
            # YoY Logic
            prev_year = current_year - 1
            prev_year_df = df[df['Year'] == prev_year]
            current_total = display_df['Fee'].sum()
            prev_total = prev_year_df['Fee'].sum()
            
            metric_delta = None
            if prev_total > 0:
                delta_val = current_total - prev_total
                delta_pct = (delta_val / prev_total) * 100
                metric_delta = f"{delta_pct:,.1f}% vs {prev_year}"

            if selected_year == current_year:
                months_divisor = datetime.now().month
            else:
                months_divisor = 12
            
            target_income = monthly_goal * 12
            
        else:
            display_df = df[df['Month_Name'] == selected_view]
            view_title = f"Details for {selected_view}"
            months_divisor = 0
            target_income = monthly_goal
            metric_delta = None

        # --- METRICS ---
        total_period_income = display_df['Fee'].sum()
        total_patients = len(display_df)

        st.markdown(f"<h2 style='text-align: center; color: #FF4B4B;'>{view_title}</h2>", unsafe_allow_html=True)
        
        if months_divisor > 0:
            monthly_avg = total_period_income / months_divisor
            st.markdown(f"<h1 style='text-align: center; color: #4CAF50;'>Total: ${total_period_income:,.2f} <span style='font-size: 0.6em; color: gray;'> (Avg: ${monthly_avg:,.2f}/mo)</span></h1>", unsafe_allow_html=True)
        else:
            st.markdown(f"<h1 style='text-align: center; color: #4CAF50;'>Total: ${total_period_income:,.2f}</h1>", unsafe_allow_html=True)

        # GOAL PROGRESS
        if target_income > 0:
            progress = min(total_period_income / target_income, 1.0)
            st.progress(progress, text=f"🎯 Goal Progress: {int(progress*100)}% of ${target_income:,.0f}")

        m1, m2, m3 = st.columns(3)
        if metric_delta:
            m1.metric("Total London Income", f"${total_period_income:,.2f}", delta=metric_delta)
        else:
            m1.metric("Total London Income", f"${total_period_income:,.2f}")
            
        m2.metric("Total Patients", f"{total_patients}")
        
        if total_patients > 0:
            m3.metric("Avg per Patient", f"${total_period_income/total_patients:,.2f}")
        else:
            m3.metric("Avg per Patient", "$0.00")

        st.divider()

        # If specific month, show pay periods
        if months_divisor == 0: 
             period_1 = display_df[display_df['Date Object'].dt.day <= 15]
             period_2 = display_df[display_df['Date Object'].dt.day > 15]
             
             c1, c2 = st.columns(2)
             c1.metric("🗓️ 1st - 15th", f"${period_1['Fee'].sum():,.2f}", f"{len(period_1)} patients")
             c2.metric("🗓️ 16th - End", f"${period_2['Fee'].sum():,.2f}", f"{len(period_2)} patients")
             st.divider()

        # --- DOWNLOAD BUTTON (Feature D3) ---
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📄 Download Report for Accountant",
            data=csv,
            file_name=f"London_Income_{selected_year}.csv",
            mime="text/csv",
            type="primary"
        )

        # --- MOBILE CARD VIEW ---
        use_card_view = st.toggle("📱 Mobile Card View", value=True)
        
        if use_card_view:
            st.caption("Showing recent activity")
            for index, row in display_df.sort_values(by="Date Object", ascending=False).iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([3, 2])
                    
                    patient_name = row.get(name_col, "Patient")
                    c1.write(f"**{str(patient_name)}**")
                    
                    encounter_type = str(row.get("Type of encounter", "Unknown"))
                    date_str = row['Date Object'].strftime('%Y-%m-%d')
                    c1.caption(f"📅 {date_str} • {encounter_type}")
                    
                    fee_val = row.get('Fee', 0)
                    c2.markdown(f"<h3 style='text-align: right; color: #4CAF50; margin: 0;'>${fee_val:.0f}</h3>", unsafe_allow_html=True)
                    
                    finalized_col = None
                    for col in df.columns:
                        if "finalized" in col.lower():
                            finalized_col = col
                            break
                    if finalized_col:
                        status = str(row[finalized_col]).strip()
                        if status and status.lower() != "yes":
                            st.caption(f"⚠️ Report: {status}")
        else:
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
