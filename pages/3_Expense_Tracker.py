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
WORKSHEET_NAME = 'Expenses_Form'

# --- SETUP AI (Gemini) ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

def analyze_receipt(image):
    """Sends image to Google Gemini to extract data"""
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = """
    Analyze this receipt image. Extract the following fields in JSON format:
    - Date (YYYY-MM-DD)
    - Amount (number only)
    - Merchant (store name)
    - Category (Choose one: Travel/Parking, Medical Supplies, Professional Fees, Education, Office/Software, Meals, Other)
    """
    try:
        response = model.generate_content([prompt, image])
        # Clean up json response
        clean_json = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_json)
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
        
        # FORCE MAPPING (A=Timestamp, B=Date, C=Category, D=Amount, E=Loc, F=Receipt)
        structured_data = []
        for row in data[1:]:
            while len(row) < 6: row.append("")
            structured_data.append({
                "Date": row[1],
                "Category": row[2],
                "Amount": row[3],
                "Location": row[4],
                "Receipt": row[5],
                "Description": row[2]
            })
        return pd.DataFrame(structured_data)
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"❌ Tab '{WORKSHEET_NAME}' not found.")
        st.stop()

def add_expense(date_val, category, amount, location, receipt_note):
    gc = get_connection()
    sh = gc.open(SHEET_NAME)
    worksheet = sh.worksheet(WORKSHEET_NAME)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_str = date_val.strftime("%Y-%m-%d")
    
    # Append Row (Form Structure)
    worksheet.append_row([timestamp, date_str, category, amount, location, receipt_note])

# --- DASHBOARD ---
def main():
    st.set_page_config(page_title="Expense Tracker", layout="wide")
    
    if st.sidebar.button("⬅️ Back to Home"):
        st.switch_page("Home.py")

    st.title("💸 AI Expense Tracker")

    # Initialize Session State for Form Values
    if 'form_date' not in st.session_state: st.session_state['form_date'] = date.today()
    if 'form_amount' not in st.session_state: st.session_state['form_amount'] = 0.00
    if 'form_merchant' not in st.session_state: st.session_state['form_merchant'] = ""
    if 'form_category' not in st.session_state: st.session_state['form_category'] = "Other"

    # --- 1. RECEIPT SCANNER ---
    with st.expander("📸 Scan Receipt (AI)", expanded=True):
        uploaded_file = st.file_uploader("Upload Receipt Image", type=['jpg', 'png', 'jpeg'])
        
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption='Uploaded Receipt', width=200)
            
            if st.button("✨ Extract Data with AI"):
                with st.spinner("Reading receipt..."):
                    data = analyze_receipt(image)
                    if data:
                        # Update Form Values with AI findings
                        try:
                            st.session_state['form_date'] = datetime.strptime(data.get('Date', str(date.today())), "%Y-%m-%d").date()
                        except:
                            pass # Keep today if date fails
                            
                        st.session_state['form_amount'] = float(data.get('Amount', 0.0))
                        st.session_state['form_merchant'] = data.get('Merchant', 'Unknown')
                        
                        # Map AI category to our list
                        ai_cat = data.get('Category', 'Other')
                        valid_cats = ["Travel/Parking", "Medical Supplies", "Professional Fees", "Education", "Office/Software", "Meals", "Other"]
                        # Simple matching
                        matched_cat = "Other"
                        for v in valid_cats:
                            if v.split("/")[0].lower() in ai_cat.lower():
                                matched_cat = v
                                break
                        st.session_state['form_category'] = matched_cat
                        
                        st.success("Data Extracted! Check the form below.")

    # --- 2. INPUT FORM ---
    st.divider()
    st.subheader("📝 Verify & Save")
    
    with st.form("expense_form"):
        c1, c2 = st.columns(2)
        
        with c1:
            # Use Session State values to pre-fill
            exp_date = st.date_input("Date", value=st.session_state['form_date'])
            category = st.selectbox("Category", [
                "Travel/Parking", "Medical Supplies", "Professional Fees", 
                "Education", "Office/Software", "Meals", "Other"
            ], index=["Travel/Parking", "Medical Supplies", "Professional Fees", "Education", "Office/Software", "Meals", "Other"].index(st.session_state['form_category']) if st.session_state['form_category'] in ["Travel/Parking", "Medical Supplies", "Professional Fees", "Education", "Office/Software", "Meals", "Other"] else 6)
            
            amount = st.number_input("Amount ($)", min_value=0.0, step=0.01, format="%.2f", value=st.session_state['form_amount'])
        
        with c2:
            location = st.selectbox("Location", ["General / Both", "London", "Kitchener"])
            description = st.text_input("Description (Merchant)", value=st.session_state['form_merchant'])
        
        submitted = st.form_submit_button("💾 Save Expense")
        
        if submitted:
            if amount > 0:
                receipt_note = "AI Scanned" if uploaded_file else "Manual Entry"
                add_expense(exp_date, category, amount, location, f"{description} ({receipt_note})")
                st.success("✅ Saved!")
                # Reset
                st.session_state['form_amount'] = 0.0
                st.cache_data.clear()
                st.rerun()
            else:
                st.warning("Amount must be > $0")

    # --- 3. DISPLAY DATA ---
    st.divider()
    
    try:
        df = get_expense_data()
    except Exception as e:
        st.error(f"Error: {e}")
        st.stop()

    if not df.empty:
        # Clean Data
        df['Amount'] = pd.to_numeric(df['Amount'].astype(str).str.replace('$','').str.replace(',',''), errors='coerce').fillna(0)
        df['Date Object'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date Object'])
        df['Year'] = df['Date Object'].dt.year
        
        available_years = sorted(df['Year'].unique(), reverse=True)
        if available_years:
            selected_year = st.sidebar.selectbox("Filter Year", available_years)
            year_df = df[df['Year'] == selected_year]
            
            total_exp = year_df['Amount'].sum()
            st.metric(f"Total Expenses {selected_year}", f"${total_exp:,.2f}")
            
            st.dataframe(
                year_df.sort_values(by="Date Object", ascending=False)[["Date", "Category", "Amount", "Location", "Description"]], 
                use_container_width=True, 
                hide_index=True
            )

if __name__ == "__main__":
    main()
