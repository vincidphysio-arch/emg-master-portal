import streamlit as st
import gspread
import pandas as pd
import io

SHEET_NAME = 'London Encounters'         # <<-- Put your actual Sheet name here
WORKSHEET_NAME = 'Tracker'               # <<-- Put your actual Worksheet name here
CREDENTIALS_FILE = 'credentials.json'

def get_google_sheet_df(sheet, worksheet, cred):
    gc = gspread.service_account(filename=cred)
    sh = gc.open(sheet)
    ws = sh.worksheet(worksheet)
    data = ws.get_all_values()
    headers = data[0]
    df = pd.DataFrame(data[1:], columns=headers)
    return df

st.title('London Tracker Dashboard')
if st.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

df = get_google_sheet_df(SHEET_NAME, WORKSHEET_NAME, CREDENTIALS_FILE)
st.dataframe(df)

csv = df.to_csv(index=False).encode('utf-8')
st.download_button("Download CSV Backup", csv, "LondonTracker.csv", "text/csv")

buffer = io.BytesIO()
df.to_excel(buffer, index=False)
buffer.seek(0)
st.download_button("Download Excel Backup", buffer, "LondonTracker.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
