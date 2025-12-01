import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Config ---
JSON_KEY_PATH = 'core/credentials.json'
SHEET_NAME = 'LotteryData'

def get_data_from_sheet():
    print("☁️ กำลังดึงข้อมูลจาก Google Sheet...")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_KEY_PATH, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def analyze_and_predict(df):
    # 1. Cleaning Data
    df['last_two_digits'] = df['last_two_digits'].astype(str).str.zfill(2)
    total_draws = len(df)
    
    print(f"\n📊 ฐานข้อมูล: {total_draws} งวด ({df['date'].min()} - {df['date'].max()})")
    
    # 2. คำนวณความถี่ (Frequency)
    stats = df['last_two_digits'].value_counts().reset_index()
    stats.columns = ['number', 'frequency']
    
    # 3. คำนวณความน่าจะเป็น (%)
    # สูตร: (จำนวนครั้งที่ออก / จำนวนงวดทั้งหมด) * 100
    stats['probability'] = (stats['frequency'] / total_draws) * 100
    
    # --- ส่วนทำนาย: TOP 5 ---
    print("\n" + "="*55)
    print(f"🏆 TOP 5 เลขท้าย 2 ตัว ที่มีโอกาสมามากที่สุด")
    print("="*55)
    print(f"{'อันดับ':<6} | {'เลข':<6} | {'เคยออก (ครั้ง)':<15} | {'ความน่าจะเป็น (%)'}")
    print("-" * 55)
    
    top_5 = stats.head(5)
    
    for i, row in top_5.iterrows():
        rank = i + 1
        number = row['number']
        count = row['frequency']
        percent = row['probability']
        
        # แสดงผล
        print(f"{rank:<6} | {number:<6} | {count:<15} | {percent:.2f}%")
        
    print("-" * 55)
    
    # แถม: เลขที่น่าจับตามอง (Overdue + High Frequency)
    # คือเลขที่ "ปกติออกบ่อย" แต่ "หายหน้าไปนาน" (ระเบิดเวลา)
    print("\n💣 เลขระเบิดเวลา (ออกบ่อย แต่หายไปนาน):")
    
    # หาว่าเลขแต่ละตัว ออกครั้งล่าสุดเมื่อไหร่
    last_seen = []
    for n in top_5['number']: # เช็คเฉพาะตัวท็อป 5
        matches = df.index[df['last_two_digits'] == n].tolist()
        if matches:
            draws_ago = matches[0] # index 0 คือล่าสุด
            last_seen.append({'number': n, 'draws_ago': draws_ago})
            
    # เรียงลำดับตามความนานที่หายไป
    overdue_top = sorted(last_seen, key=lambda x: x['draws_ago'], reverse=True)
    
    for item in overdue_top:
        print(f"   -> เลข {item['number']} ไม่มาแล้ว {item['draws_ago']} งวด")

if __name__ == "__main__":
    try:
        df = get_data_from_sheet()
        analyze_and_predict(df)
    except Exception as e:
        print(f"❌ Error: {e}")