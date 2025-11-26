# services/gsheet_manager.py
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def upload_data(df, json_path, sheet_name):
    print(f"\n☁️ 4. Uploading {len(df)} rows to Google Sheets...")
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
        client = gspread.authorize(creds)
        sheet = client.open(sheet_name).sheet1
        
        sheet.clear()
        sheet.update(range_name='A1', values=[df.columns.tolist()] + df.values.tolist())
        print("🎉 Upload Success!")
    except Exception as e:
        print(f"❌ Upload Failed: {e}")