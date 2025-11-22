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
        
        # --- HARDCODED MAPPING (The Fix) ---
        # We force the columns based on position so "Name" never fails
        data = worksheet.get_all_values()
        
        structured_data = []
        # Skip header row
        for row in data[1:]:
            # Ensure row has data
            if len(row) >= 2:
                # GOOGLE FORM STANDARD LAYOUT:
                # Col A [0] = Timestamp
                # Col B [1] = Name
                # We try to find "Encounter" and "Finalized" by scanning the row
                
                # Convert row to string to search keywords easily
                row_str = str(row).lower()
                
                # Logic to find fee
                fee = 0.00
                encounter_type = "Unknown"
                
                # Look through all cells in the row to find the encounter type
                for cell in row:
                    c = str(cell).lower()
                    if "new consult" in c: 
                        fee = 85.00
                        encounter_type = "New Consult"
                        break
                    if "non cts" in c:
                        fee = 65.00
                        encounter_type = "Non CTS"
                        break
                    if "follow up" in c:
                        fee = 65.00
                        encounter_type = "Follow Up"
                        break

                # Find Finalized status (look for "yes" or "no" in later columns)
                finalized = "NA"
                if "yes" in row_str: finalized = "Yes"
                elif "no" in row_str: finalized = "No"

                structured_data.append({
                    "Timestamp": row[0],
                    "Name": row[1],  # Force Column B as Name
                    "Type": encounter_type,
                    "Fee": fee,
                    "Finalized": finalized,
                    "Doctor": "Dr. Tugolov" # Default for now
                })
        
        df = pd.DataFrame(structured_data)
        return df

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
        df = get_data(target_sheet)
    except Exception as e:
        st.error(f"Error reading sheet: {e}")
        st.stop()

    if not df.empty:
        # 1. CLEAN DATA
        df = df[df['Name'].str.strip() != ""]
        df['Date Object'] = pd.to_datetime(df['Timestamp'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Date Object'])
        
        # 3. TIME COLUMNS
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
        
        view_options = ["Current Year (Overview)", "Last X Months"] + available_months
        
        current_month_name = datetime.now().strftime('%B')
        default_idx = view_options.index(current_month_name) if current_month_name in view_options else 0
        selected_view = st.sidebar.selectbox("Select View", view_options, index=default_idx)

        # --- GOAL TRACKER ---
        st.sidebar.divider()
        st.sidebar.header("🎯 Goal Tracker")
        monthly_goal = st.sidebar.number_input("Monthly Goal ($)", value=10000, step=500)

        # LOGIC
        months_divisor = 0
        target_income = 0

        if selected_view == "Last X Months":
            months_back = st.sidebar.number_input("Months", 1, 12, 3)
            start_date = datetime.now() - pd.DateOffset(months=months_back)
            display_df = df[df['Date Object'] >= start_date]
            view_title = f"Income: Last {months_back} Months"
            months_divisor = months_back
            target_income = monthly_goal * months_back

        elif selected_view == "Current Year (Overview)":
            display_df = df[df['Year'] == datetime.now().year]
            view_title = f"Financial Overview: {datetime.now().year}"
            months_divisor = datetime.now().month
            target_income = monthly_goal * 12
            
        else:
            display_df = df[df['Month_Name'] == selected_view]
            view_title = f"Details for {selected_view}"
            months_divisor = 0
            target_income = monthly_goal

        # --- METRICS ---
        total_period_income = display_df['Fee'].sum()
        total_patients = len(display_df)

        st.markdown(f"<h2 style='text-align: center; color: #FF4B4B;'>{view_title}</h2>", unsafe_allow_html=True)
        
        if months_divisor > 0:
            monthly_avg = total_period_income / months_divisor
            st.markdown(f"<h1 style='text-align: center; color: #4CAF50;'>Total: ${total_period_income:,.2f} <span style='font-size: 0.6em; color: gray;'> (Avg: ${monthly_avg:,.2f}/mo)</span></h1>", unsafe_allow_html=True)
        else:
            st.markdown(f"<h1 style='text-align: center; color: #4CAF50;'>Total: ${total_period_income:,.2f}</h1>", unsafe_allow_html=True)

        # Progress Bar
        if target_income > 0:
            progress = min(total_period_income / target_income, 1.0)
            st.progress(progress, text=f"🎯 Goal Progress: {int(progress*100)}%")

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Patients", f"{total_patients}")
        if total_patients > 0:
            m2.metric("Avg per Patient", f"${total_period_income/total_patients:,.2f}")
        else:
            m2.metric("Avg per Patient", "$0.00")
        m3.metric("Date Range", f"{display_df['Date Object'].min().date()} to {display_df['Date Object'].max().date()}" if not display_df.empty else "-")

        st.divider()

        # Pay Periods (Crucial for London Billing)
        if months_divisor == 0: 
             period_1 = display_df[display_df['Date Object'].dt.day <= 15]
             period_2 = display_df[display_df['Date Object'].dt.day > 15]
             c1, c2 = st.columns(2)
             c1.metric("🗓️ 1st - 15th", f"${period_1['Fee'].sum():,.2f}", f"{len(period_1)} patients")
             c2.metric("🗓️ 16th - End", f"${period_2['Fee'].sum():,.2f}", f"{len(period_2)} patients")
             st.divider()

        # --- MOBILE CARD VIEW ---
        use_card_view = st.toggle("📱 Mobile Card View", value=True)
        
        if use_card_view:
            for index, row in display_df.sort_values(by="Date Object", ascending=False).iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([3, 2])
                    c1.write(f"**{row['Name']}**") # Now correctly finds Name
                    date_str = row['Date Object'].strftime('%Y-%m-%d')
                    c1.caption(f"📅 {date_str} • {row['Type']}")
                    c2.markdown(f"<h3 style='text-align: right; color: #4CAF50; margin: 0;'>${row['Fee']:.0f}</h3>", unsafe_allow_html=True)
        else:
            st.dataframe(
                display_df.sort_values(by="Date Object", ascending=False)[["Timestamp", "Name", "Type", "Fee", "Finalized"]], 
                use_container_width=True, 
                hide_index=True
            )
    else:
        st.info("No data found.")

if __name__ == "__main__":
    main()
