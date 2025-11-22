import streamlit as st
import gspread
import pandas as pd
import json
from datetime import date, datetime
import google.generativeai as genai
from PIL import Image

# --- CONFIGURATION ---
SHEET_NAME = 'EMG Payments Kitchener'
CREDENTIALS_FILE = 'credentials.json'
WORKSHEET_NAME = 'Expenses' # Ensure this matches your tab name

# --- SETUP AI ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

def analyze_receipt(image):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = """
    Analyze this receipt. Extract to JSON:
    - Date (YYYY-MM-DD)
    - Amount (number)
    - Merchant
    - Category (Travel/Parking, Medical Supplies, Professional Fees, Education, Office/Software, Meals, Other)
    """
    try:
        response = model.generate_content([prompt, image])
        clean_json = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_json)
    except:
        return None

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

def get_expense_data():
    gc = get_connection()
    sh = gc.open(SHEET_NAME)
    try:
        worksheet = sh.worksheet(WORKSHEET_NAME)
        data = worksheet.get_all_values()
        
        structured_data = []
        
        # Skip header
        for row in data[1:]:
            # Pad row to avoid index errors
            while len(row) < 8: row.append("")
            
            # --- HYBRID LOGIC: DETECT OLD VS NEW DATA ---
            
            # Default: Assume NEW Form Data (Date in Col B [1], Amount in Col D [3])
            date_val = row[1]
            cat_val = row[2]
            amt_val = row[3]
            loc_val = row[4]
            desc_val = row[2] # Default desc is category
            receipt_val = row[5]

            # Check for OLD Data (Date in Col A [0], Amount in Col C [2])
            # We check if Col C looks like a number
            is_old_data = False
            try:
                # Try to convert Col C to float
                float(str(row[2]).replace('$','').replace(',',''))
                # If successful, and Col B is NOT a date (it's likely a category string), it's old data
                if len(str(row[1])) > 0 and not str(row[1])[0].isdigit():
                    is_old_data = True
            except:
                pass

            if is_old_data:
                date_val = row[0]
                cat_val = row[1]
                amt_val = row[2]
                desc_val = row[3]
                # Payment Method was row[4], Location was row[5] (maybe)
                # We map loosely here
                loc_val = row[5] 
                receipt_val = ""

            structured_data.append({
                "Date": date_val,
                "Category": cat_val,
                "Amount": amt_val,
                "Location": loc_val,
                "Description": desc_val,
                "Receipt": receipt_val
            })
        
        df = pd.DataFrame(structured_data)
        return df

    except gspread.exceptions.WorksheetNotFound:
        st.error(f"❌ Tab '{WORKSHEET_NAME}' not found.")
        st.stop()

def add_expense(date_val, category, amount, location, receipt_note):
    gc = get_connection()
    sh = gc.open(SHEET_NAME)
    worksheet = sh.worksheet(WORKSHEET_NAME)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    worksheet.append_row([timestamp, str(date_val), category, amount, location, receipt_note])

# --- DASHBOARD ---
def main():
    st.set_page_config(page_title="Expense Tracker", layout="wide")
    
    if st.sidebar.button("⬅️ Back to Home"):
        st.switch_page("Home.py")

    st.title("💸 AI Expense Tracker")

    # --- FORM ---
    if 'form_date' not in st.session_state: st.session_state['form_date'] = date.today()
    if 'form_amount' not in st.session_state: st.session_state['form_amount'] = 0.00
    if 'form_cat' not in st.session_state: st.session_state['form_cat'] = "Other"
    if 'form_merch' not in st.session_state: st.session_state['form_merch'] = ""

    with st.expander("📸 Scan Receipt (AI)", expanded=True):
        uploaded_file = st.file_uploader("Upload", type=['jpg','png','jpeg'], label_visibility="collapsed")
        if uploaded_file:
            if st.button("✨ Extract Data"):
                with st.spinner("Analyzing..."):
                    data = analyze_receipt(Image.open(uploaded_file))
                    if data:
                        st.session_state['form_amount'] = float(data.get('Amount', 0))
                        st.session_state['form_merch'] = data.get('Merchant', '')
                        # Try date parse
                        try: st.session_state['form_date'] = datetime.strptime(data.get('Date'), "%Y-%m-%d").date()
                        except: pass
                        
    with st.form("main_form"):
        c1, c2 = st.columns(2)
        with c1:
            d = st.date_input("Date", st.session_state['form_date'])
            c = st.selectbox("Category", ["Travel/Parking", "Medical Supplies", "Professional Fees", "Education", "Office/Software", "Meals", "Other"], index=6)
            a = st.number_input("Amount", value=st.session_state['form_amount'])
        with c2:
            l = st.selectbox("Location", ["General / Both", "London", "Kitchener"])
            desc = st.text_input("Description", value=st.session_state['form_merch'])
        
        if st.form_submit_button("Save"):
            add_expense(d, c, a, l, desc)
            st.success("Saved!")
            st.cache_data.clear()
            st.rerun()

    st.divider()

    # --- DATA ---
    try:
        df = get_expense_data()
    except:
        st.stop()

    if not df.empty:
        df['Amount'] = pd.to_numeric(df['Amount'].astype(str).str.replace('$','').str.replace(',',''), errors='coerce').fillna(0)
        df['Date Object'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date Object'])
        df['Year'] = df['Date Object'].dt.year
        
        years = sorted(df['Year'].unique(), reverse=True)
        sel_year = st.sidebar.selectbox("Year", years) if years else 2025
        
        y_df = df[df['Year'] == sel_year]
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total", f"${y_df['Amount'].sum():,.2f}")
        m2.metric("London", f"${y_df[y_df['Location'].str.contains('London', case=False, na=False)]['Amount'].sum():,.2f}")
        m3.metric("Kitchener", f"${y_df[y_df['Location'].str.contains('Kitch', case=False, na=False)]['Amount'].sum():,.2f}")
        m4.metric("General", f"${y_df[y_df['Location'].str.contains('General', case=False, na=False)]['Amount'].sum():,.2f}")
        
        st.dataframe(y_df.sort_values('Date Object', ascending=False)[["Date", "Category", "Amount", "Location", "Description"]], use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
