import streamlit as st
import gspread
import pandas as pd
import json
from datetime import datetime

# --- CONFIGURATION ---
SHEET_NAME = 'EMG Payments Kitchener'
CREDENTIALS_FILE = 'credentials.json'

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
    
    # Force standard loading
    data = worksheet.get_all_values()
    
    # Manually map the columns based on your known sheet structure (A, B, C, D)
    # A=Date, B=Sender, C=Amount, D=Doctor
    # We skip the header row [0] and map the rest
    processed_data = []
    for row in data[1:]:
        # Ensure row has enough columns
        if len(row) >= 4:
            processed_data.append({
                "Date": row[0],
                "Sender": row[1],
                "Amount": row[2],
                "Doctor": row[3]
            })
            
    df = pd.DataFrame(processed_data)
    return df

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
        # 1. Clean Data
        df = df[df['Date'].astype(str).str.strip() != ""]
        # Force Date format DD/MM/YYYY
        df['Date Object'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Date Object'])
        
        df['Amount'] = pd.to_numeric(df['Amount'].astype(str).str.replace('$','').str.replace(',',''), errors='coerce')
        df['Year'] = df['Date Object'].dt.year
        df['Month_Name'] = df['Date Object'].dt.strftime('%B')

        # 2. Filters
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

        # 3. Metrics Logic
        months_divisor = 0
        if selected_view == "Last X Months":
            period_opt = st.sidebar.radio("Select Duration", [3, 6, 9, 12, "Custom"], horizontal=True)
            months_back = st.sidebar.number_input("Enter months", 1, 100, 3) if period_opt == "Custom" else period_opt
            start_date = datetime.now() - pd.DateOffset(months=months_back)
            display_df = df[df['Date Object'] >= start_date]
            view_title = f"Income: Last {months_back} Months"
            months_divisor = months_back
        elif selected_view == "Current Year (Overview)":
            display_df = df[df['Year'] == datetime.now().year]
            view_title = f"Financial Overview: {datetime.now().year}"
            months_divisor = datetime.now().month
        else:
            display_df = df[df['Month_Name'] == selected_view]
            display_df = display_df[display_df['Year'] == selected_year]
            view_title = f"Activity in {selected_view} {selected_year}"
            months_divisor = 0

        # 4. Metrics Calculation
        total_income = display_df['Amount'].sum()
        # Exact matching for Doctor names since we know them now
        tripic_total = display_df[display_df['Doctor'].str.contains("Tripic", case=False, na=False)]['Amount'].sum()
        cartagena_total = display_df[display_df['Doctor'].str.contains("Cartagena", case=False, na=False)]['Amount'].sum()

        st.markdown(f"<h2 style='text-align: center; color: #FF4B4B;'>{view_title}</h2>", unsafe_allow_html=True)
        
        if months_divisor > 0:
            monthly_avg = total_income / months_divisor
            st.markdown(f"<h1 style='text-align: center; color: #4CAF50;'>Total: ${total_income:,.2f} <span style='font-size: 0.6em; color: gray;'> (Avg: ${monthly_avg:,.2f}/mo)</span></h1>", unsafe_allow_html=True)
        else:
            st.markdown(f"<h1 style='text-align: center; color: #4CAF50;'>Total: ${total_income:,.2f}</h1>", unsafe_allow_html=True)

        m1, m2, m3 = st.columns(3)
        date_range = f"{display_df['Date Object'].min().date()} to {display_df['Date Object'].max().date()}" if not display_df.empty else "-"
        m1.metric("Date Range", date_range)
        
        avg_text_t = f"Avg: ${tripic_total/months_divisor:,.2f}/mo" if months_divisor > 0 else None
        avg_text_c = f"Avg: ${cartagena_total/months_divisor:,.2f}/mo" if months_divisor > 0 else None
        
        m2.metric("👨‍⚕️ Dr. Tripic", f"${tripic_total:,.2f}", avg_text_t)
        m3.metric("👩‍⚕️ Dr. Cartagena", f"${cartagena_total:,.2f}", avg_text_c)

        st.divider()
        
        # 5. Mobile View & Table
        use_card_view = st.toggle("📱 Mobile Card View", value=True)
        
        if use_card_view:
            for index, row in display_df.sort_values(by="Date Object", ascending=False).iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([3, 2])
                    c1.write(f"**{row['Sender']}**")
                    date_str = row['Date Object'].strftime('%Y-%m-%d')
                    c1.caption(f"📅 {date_str} • {row['Doctor']}")
                    c2.markdown(f"<h3 style='text-align: right; color: #4CAF50; margin: 0;'>${row['Amount']:,.2f}</h3>", unsafe_allow_html=True)
        else:
            st.dataframe(
                display_df.sort_values(by="Date Object", ascending=False)[["Date", "Sender", "Amount", "Doctor"]], 
                use_container_width=True, 
                hide_index=True
            )
    else:
        st.info("Sheet is connected, but empty.")

if __name__ == "__main__":
    main()
