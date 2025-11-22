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
WORKSHEET_NAME = 'Expenses'

# --- SETUP AI ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

def analyze_receipt(image):
    # Use the specific, stable Flash model
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = """
        Analyze this receipt image. Return ONLY a raw JSON object with these fields:
        {
            "Date": "YYYY-MM-DD",
            "Amount": 0.00,
            "Merchant": "Store Name",
            "Category": "Best Fit Category"
        }
        Categories to choose from: 
        - Gas
        - Travel/Parking
        - Medical Supplies
        - Professional Fees
        - Education
        - Office/Software
        - Meals
        - Other
        """
        response = model.generate_content([prompt, image])
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text)
    except Exception as e:
        st.error(f"AI Error: {e}")
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
            while len(row) < 8: row.append("")
            
            # HYBRID LOGIC
            date_val = row[1]
            cat_val = row[2]
            amt_val = row[3]
            loc_val = row[4]
            desc_val = row[2]
            receipt_val = row[5]

            # Check for OLD Data (Date in Col A)
            is_old_data = False
            try:
                float(str(row[2]).replace('$','').replace(',',''))
                if len(str(row[1])) > 0 and not str(row[1])[0].isdigit():
                    is_old_data = True
            except:
                pass

            if is_old_data:
                date_val = row[0]
                cat_val = row[1]
                amt_val = row[2]
                desc_val = row[3]
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

    # Initialize Session State
    if 'form_date' not in st.session_state: st.session_state['form_date'] = date.today()
    if 'form_amount' not in st.session_state: st.session_state['form_amount'] = 0.00
    if 'form_merch' not in st.session_state: st.session_state['form_merch'] = ""
    if 'form_cat_index' not in st.session_state: st.session_state['form_cat_index'] = 7 # Default Other

    # --- 1. AI SCANNER ---
    with st.expander("📸 Scan Receipt (AI)", expanded=True):
        uploaded_file = st.file_uploader("Upload Receipt", type=['jpg','png','jpeg'], label_visibility="collapsed")
        
        if uploaded_file:
            st.image(uploaded_file, width=150)
            
            if st.button("✨ Extract Data"):
                with st.spinner("Reading receipt..."):
                    data = analyze_receipt(Image.open(uploaded_file))
                    
                    if data:
                        # Amount
                        try: st.session_state['form_amount'] = float(str(data.get('Amount', 0)).replace('$','').replace(',',''))
                        except: pass
                        
                        # Merchant
                        st.session_state['form_merch'] = data.get('Merchant', '')
                        
                        # Date
                        try: st.session_state['form_date'] = datetime.strptime(data.get('Date'), "%Y-%m-%d").date()
                        except: pass
                        
                        # Category Matching (Updated for Gas)
                        ai_cat = str(data.get('Category', '')).lower()
                        
                        # List must match the selectbox below exactly
                        cat_options = [
                            "Gas",              # Index 0
                            "Travel/Parking",   # Index 1
                            "Medical Supplies", # Index 2
                            "Professional Fees",# Index 3
                            "Education",        # Index 4
                            "Office/Software",  # Index 5
                            "Meals",            # Index 6
                            "Other"             # Index 7
                        ]
                        
                        found_index = 7 # Default to Other
                        
                        if "gas" in ai_cat or "fuel" in ai_cat: found_index = 0
                        elif "parking" in ai_cat or "travel" in ai_cat or "uber" in ai_cat: found_index = 1
                        elif "medical" in ai_cat: found_index = 2
                        elif "fee" in ai_cat: found_index = 3
                        elif "edu" in ai_cat: found_index = 4
                        elif "soft" in ai_cat or "office" in ai_cat: found_index = 5
                        elif "meal" in ai_cat or "food" in ai_cat: found_index = 6
                        
                        st.session_state['form_cat_index'] = found_index
                        
                        st.success("✅ Data Extracted!")
                        st.rerun()

    # ---
