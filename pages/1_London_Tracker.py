import streamlit as st
import gspread
import pandas as pd
import json
import io

def get_google_sheet_df(sheet_name, worksheet_name):
    creds_dict = json.loads(st.secrets["gcpjson"])
    gc = gspread.service_account_from_dict(creds_dict)
    sh = gc.open(sheet_name)
    worksheet = sh.worksheet(worksheet_name)
    data = worksheet.get_all_values()
    headers = data[0]
    df = pd.DataFrame(data[1:], columns=headers)
    return df

SHEET_NAME = "London Encounters"      # <--- Your sheet name
WORKSHEET_NAME = "Tracker"            # <--- Your worksheet/tab name

st.title('London Tracker Dashboard')
if st.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

df = get_google_sheet_df(SHEET_NAME, WORKSHEET_NAME)
st.dataframe(df)

csv = df.to_csv(index=False).encode('utf-8')
st.download_button("Download CSV", csv, "LondonTracker.csv", "text/csv")
buffer = io.BytesIO()
df.to_excel(buffer, index=False)
buffer.seek(0)
st.download_button("Download Excel", buffer, "LondonTracker.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
