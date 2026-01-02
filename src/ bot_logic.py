import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
from datetime import datetime

# --- Config ---
SHEET_NAME = 'LotteryData'

def get_google_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # 1. ลองอ่านจาก Cloud (Environment Variable)
    if os.getenv('GOOGLE_CREDENTIALS_JSON'):
        creds_dict = json.loads(os.getenv('GOOGLE_CREDENTIALS_JSON'))
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    # 2. ถ้าไม่มี ให้อ่านจากไฟล์ในเครื่อง (Local)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name('core/credentials.json', scope)
        
    return gspread.authorize(creds)

def get_data():
    client = get_google_client()
    sheet = client.open(SHEET_NAME).sheet1
    return pd.DataFrame(sheet.get_all_records())

def get_prediction_message():
    try:
        df = get_data()
        
        # Clean Data
        df['last_two_digits'] = df['last_two_digits'].astype(str).str.zfill(2)
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date'])
        
        total_draws = len(df)
        
        # วิเคราะห์วันปัจจุบัน (หรือวันล่าสุด)
        today = datetime.now()
        days_map = {0: 'จันทร์', 1: 'อังคาร', 2: 'พุธ', 3: 'พฤหัส', 4: 'ศุกร์', 5: 'เสาร์', 6: 'อาทิตย์'}
        day_name = days_map[today.weekday()]
        
        msg = f"🤖 **AI วิเคราะห์หวย** 🤖\n"
        msg += f"📅 ข้อมูลถึง: {df['date'].max().strftime('%d/%m/%Y')}\n"
        msg += f"🗓 วันนี้: วัน{day_name}\n\n"
        
        # 1. Top 5 รวม
        stats = df['last_two_digits'].value_counts().head(5)
        msg += "🏆 **TOP 5 สถิติรวม:**\n"
        for num, count in stats.items():
            prob = (count/total_draws)*100
            msg += f"- {num} (ออก {count} ครั้ง | {prob:.1f}%)\n"
            
        # 2. Top 3 ประจำวัน
        day_code = today.weekday()
        df['day_of_week'] = df['date'].dt.dayofweek
        subset = df[df['day_of_week'] == day_code]
        if not subset.empty:
            day_stats = subset['last_two_digits'].value_counts().head(3)
            msg += f"\n🌞 **มาแรงเฉพาะวัน{day_name}:**\n"
            for num, count in day_stats.items():
                msg += f"- {num} (มา {count} ครั้ง)\n"
        
        return msg

    except Exception as e:
        return f"ระบบขัดข้อง: {str(e)}"