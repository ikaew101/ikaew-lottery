import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

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

def get_next_lotto_date():
    """ คำนวณหาวันหวยออกงวดถัดไป (1 หรือ 16) โดยอิงจากวันนี้ """
    today = datetime.now()
    
    # ถ้าวันนี้เป็นวันหวยออก (1 หรือ 16) ก็ใช้วันนี้เลย
    if today.day == 1 or today.day == 16 or (today.month == 1 and today.day == 2): # เช็คเคส 2 ม.ค.
        return today

    # ถ้าไม่ใช่ ให้ลองขยับวันไปข้างหน้าเรื่อยๆ จนกว่าจะเจอวันหวยออก
    next_date = today
    while True:
        next_date += timedelta(days=1)
        # กฎปกติ: วันที่ 1 หรือ 16
        if next_date.day == 1 or next_date.day == 16:
            # เช็ควันครู (16 ม.ค. -> 17)
            if next_date.month == 1 and next_date.day == 16:
                next_date += timedelta(days=1)
            # เช็ควันแรงงาน (1 พ.ค. -> 2)
            elif next_date.month == 5 and next_date.day == 1:
                next_date += timedelta(days=1)
            return next_date
        
        # กฎพิเศษ: หวยปีใหม่ (2 ม.ค.)
        if next_date.month == 1 and next_date.day == 2:
            return next_date

def analyze_by_day(df):
    print("\n" + "="*65)
    print("📅 เจาะลึกสถิติ: เลขท้าย 2 ตัว ตามวันในสัปดาห์")
    print("="*65)

    df['last_two_digits'] = df['last_two_digits'].astype(str).str.zfill(2)
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date']).copy()
    
    days_map = {
        0: 'วันจันทร์ 💛', 1: 'วันอังคาร 🩷', 2: 'วันพุธ 💚', 
        3: 'วันพฤหัสบดี 🧡', 4: 'วันศุกร์ 💙', 5: 'วันเสาร์ 💜', 6: 'วันอาทิตย์ ❤️'
    }
    df['day_of_week'] = df['date'].dt.dayofweek
    df['day_name'] = df['day_of_week'].map(days_map)

    # --- ส่วนที่แก้ไข: คำนวณวันงวดหน้าอัตโนมัติ ---
    target_date = get_next_lotto_date()
    target_day_code = target_date.weekday()
    target_day_name = days_map[target_day_code]
    
    # แปลง ค.ศ. เป็น พ.ศ. (เช่น 2026 -> 2569)
    thai_year = target_date.year + 543
    date_str = f"{target_date.day:02d}/{target_date.month:02d}/{str(thai_year)[2:]}" # format dd/mm/yy

    print("\n" + "="*65)
    print(f"🔮 เก็งงวดหน้า ({date_str}) ตรงกับ: {target_day_name}")
    print("="*65)
    
    if target_day_code in df['day_of_week'].unique():
        target_subset = df[df['day_of_week'] == target_day_code]
        total_recs = len(target_subset)
        print(f"สถิติย้อนหลังของ {target_day_name} (ทั้งหมด {total_recs} งวด):")
        
        target_stats = target_subset['last_two_digits'].value_counts().head(5)
        
        print(f"\n🏆 เลขที่ออกบ่อยที่สุดใน {target_day_name} คือ:")
        for num, count in target_stats.items():
            prob = (count / total_recs) * 100
            print(f"-> เลข {num} (ออก {count} ครั้ง | {prob:.1f}%)")
    else:
        print("ไม่พบข้อมูลสถิติของวันนี้")

if __name__ == "__main__":
    try:
        df = get_data_from_sheet()
        analyze_by_day(df)
    except Exception as e:
        print(f"❌ Error: {e}")