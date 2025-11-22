import streamlit as st
import gspread
import pandas as pd
import json
from datetime import datetime

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
    data = worksheet.get_all_values()
    headers = data[0]
    rows = data[1:]
    cleaned_headers = [h.strip() for h in headers]
    df = pd.DataFrame(rows, columns=cleaned_headers)
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
        # 1. Smart Column Finding
        # Find the column that likely holds the Doctor's name
        doc_col = 'Doctor' # Default
        for col in df.columns:
            if "doctor" in col.lower() or "doc" in col.lower():
                doc_col = col
                break
        
        # 2. Clean Data
        df = df[df['Date'].astype(str).str.strip() != ""]
        df['Date Object'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date Object'])
        df['Amount'] = pd.to_numeric(df['Amount'].astype(str).str.replace('$','').str.replace(',',''), errors='coerce')
        df['Year'] = df['Date Object'].dt.year
        df['Month_Name'] = df['Date Object'].dt.strftime('%B')

        # 3. Filters
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

        # 4. Goal Tracker
        st.sidebar.divider()
        st.sidebar.header("🎯 Goal Tracker")
        monthly_goal = st.sidebar.number_input("Monthly Goal ($)", value=10000, step=500)

        months_divisor = 0
        target_income = 0

        if selected_view == "Last X Months":
            period_opt = st.sidebar.radio("Select Duration", [3, 6, 9, 12, "Custom"], horizontal=True)
            months_back = st.sidebar.number_input("Enter months", min_value=1, value=3) if period_opt == "Custom" else period_opt
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
            months_divisor = datetime.now().month if selected_year == current_year else 12
            target_income = monthly_goal * 12
        else:
            display_df = df[df['Month_Name'] == selected_view]
            view_title = f"Activity in {selected_view}"
            months_divisor = 0
            target_income = monthly_goal

        # 5. Calculate Metrics
        total_income = display_df['Amount'].sum()
        
        # Safe Doctor Split using the found column name
        if doc_col in display_df.columns:
            tripic_total = display_df[display_df[doc_col].astype(str).str.contains("Tripic", case=False)]['Amount'].sum()
            cartagena_total = display_df[display_df[doc_col].astype(str).str.contains("Cartagena", case=False)]['Amount'].sum()
        else:
            tripic_total = 0
            cartagena_total = 0

        # 6. Display
        st.markdown(f"<h2 style='text-align: center; color: #FF4B4B;'>{view_title}</h2>", unsafe_allow_html=True)
        
        if months_divisor > 0:
            monthly_avg = total_income / months_divisor
            st.markdown(f"<h1 style='text-align: center; color: #4CAF50;'>Total: ${total_income:,.2f} <span style='font-size: 0.6em; color: gray;'> (Avg: ${monthly_avg:,.2f}/mo)</span></h1>", unsafe_allow_html=True)
        else:
            st.markdown(f"<h1 style='text-align: center; color: #4CAF50;'>Total: ${total_income:,.2f}</h1>", unsafe_allow_html=True)

        if target_income > 0:
            progress = min(total_income / target_income, 1.0)
            st.progress(progress, text=f"🎯 Goal Progress: {int(progress*100)}% of ${target_income:,.0f}")

        m1, m2, m3 = st.columns(3)
        m1.metric("Date Range", f"{display_df['Date Object'].min().date()} to {display_df['Date Object'].max().date()}" if not display_df.empty else "-")
        
        if months_divisor > 0:
            m2.metric("👨‍⚕️ Dr. Tripic", f"${tripic_total:,.2f}", f"Avg: ${tripic_total/months_divisor:,.2f}/mo")
            m3.metric("👩‍⚕️ Dr. Cartagena", f"${cartagena_total:,.2f}", f"Avg: ${cartagena_total/months_divisor:,.2f}/mo")
        else:
            m2.metric("👨‍⚕️ Dr. Tripic", f"${tripic_total:,.2f}")
            m3.metric("👩‍⚕️ Dr. Cartagena", f"${cartagena_total:,.2f}")

        st.divider()
        
        # Download Button
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(label="📄 Download Report for Accountant", data=csv, file_name=f"Kitchener_Income.csv", mime="text/csv", type="primary")

        # Mobile Card View
        use_card_view = st.toggle("📱 Mobile Card View", value=True)
        if use_card_view:
            st.caption("Showing recent transactions")
            for index, row in display_df.sort_values(by="Date Object", ascending=False).iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([3, 2])
                    sender_name = row.get("Sender", "Unknown")
                    c1.write(f"**{sender_name}**")
                    date_str = row['Date Object'].strftime('%Y-%m-%d')
                    doc_name = row.get(doc_col, "Unknown")
                    c1.caption(f"📅 {date_str} • {doc_name}")
                    amt_val = row.get('Amount', 0)
                    c2.markdown(f"<h3 style='text-align: right; color: #4CAF50; margin: 0;'>${amt_val:,.2f}</h3>", unsafe_allow_html=True)
        else:
            display_cols = ["Date", "Sender", "Amount", doc_col]
            cols_to_show = [c for c in display_cols if c in display_df.columns]
            st.dataframe(display_df.sort_values(by="Date Object", ascending=False)[cols_to_show], use_container_width=True, hide_index=True)
    else:
        st.info("Sheet is connected, but empty.")

if __name__ == "__main__":
    main()
