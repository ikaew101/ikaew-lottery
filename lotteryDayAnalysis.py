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

def analyze_by_day(df):
    print("\n" + "="*65)
    print("📅 เจาะลึกสถิติ: เลขท้าย 2 ตัว ตามวันในสัปดาห์ (Top 5)")
    print("="*65)

    # 1. Clean Data & แปลงวันที่
    df['last_two_digits'] = df['last_two_digits'].astype(str).str.zfill(2)
    
    # [FIXED] เพิ่ม errors='coerce' เพื่อเปลี่ยนค่าที่อ่านไม่ได้ (เช่น '-') เป็น NaT (Not a Time)
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    
    # [FIXED] ลบแถวที่วันที่เสีย (NaT) ทิ้งไปเลย กัน Error
    df = df.dropna(subset=['date'])
    
    # 2. สร้างคอลัมน์ "วัน" (Monday=0, Sunday=6)
    days_map = {
        0: 'วันจันทร์ 💛', 
        1: 'วันอังคาร 🩷', 
        2: 'วันพุธ 💚', 
        3: 'วันพฤหัสบดี 🧡', 
        4: 'วันศุกร์ 💙', 
        5: 'วันเสาร์ 💜', 
        6: 'วันอาทิตย์ ❤️'
    }
    df['day_of_week'] = df['date'].dt.dayofweek
    df['day_name'] = df['day_of_week'].map(days_map)

    # 3. วนลูปวิเคราะห์ทีละวัน
    for day_code in range(7):
        day_name = days_map[day_code]
        subset = df[df['day_of_week'] == day_code]
        total_draws = len(subset)
        
        if total_draws == 0: continue

        print(f"\n{day_name} (สถิติจาก {total_draws} งวด)")
        print("-" * 40)
        
        stats = subset['last_two_digits'].value_counts().reset_index()
        stats.columns = ['number', 'frequency']
        
        top_5 = stats.head(5)
        rank_str = []
        for i, row in top_5.iterrows():
            prob = (row['frequency'] / total_draws) * 100
            rank_str.append(f"อันดับ {i+1}: {row['number']} ({prob:.1f}%)")
            
        print("   " + "\n   ".join(rank_str))

    # --- เช็คเฉพาะงวดหน้า (16 ธ.ค. 68 = วันอังคาร) ---
    target_day_code = 1 # Tuesday
    target_day_name = days_map[target_day_code]
    
    print("\n" + "="*65)
    print(f"🔮 เก็งงวดหน้า (16 ธ.ค. 68) ตรงกับ: {target_day_name}")
    print("="*65)
    
    if target_day_code in df['day_of_week'].unique():
        target_subset = df[df['day_of_week'] == target_day_code]
        target_stats = target_subset['last_two_digits'].value_counts().head(5)
        
        print(f"เลขที่ออกบ่อยที่สุดใน {target_day_name} คือ:")
        for num, count in target_stats.items():
            print(f"-> เลข {num} (ออก {count} ครั้ง)")
    else:
        print("ไม่พบข้อมูลสถิติของวันนี้")

if __name__ == "__main__":
    try:
        df = get_data_from_sheet()
        analyze_by_day(df)
    except Exception as e:
        print(f"❌ Error: {e}")