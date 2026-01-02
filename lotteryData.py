# main.py
import pandas as pd
# Import จาก folder services ที่เราสร้าง
from src.getOldData import fetch_old_data
from src.getLotto import fetch_current_year_data
from src.gsheet_upload import upload_data

# Config
JSON_KEY_PATH = 'core/credentials.json'
TARGET_SHEET_NAME = 'LotteryData'

def main():
    print("🚀 STARTING LOTTERY PIPELINE...")
    
    # 1. ดึงของเก่า
    df_old = fetch_old_data()
    print(f"   📦 Old Data (GitHub): {len(df_old)} rows (Last: {df_old['date'].max()})")
    
    # 2. ดึงของใหม่ (Auto Date)
    df_new = fetch_current_year_data()
    print(f"   🕵️ New Data (Scraper): {len(df_new)} rows")
    
    # 3. รวมร่าง
    print("\n🔄 3. Merging Data...")
    if not df_new.empty:
        # รวมกัน
        df_final = pd.concat([df_old, df_new])
        
        # แปลงวันที่เป็น datetime ก่อน เพื่อให้ sort และ drop duplicate ได้ถูกต้องแม่นยำ
        df_final['date'] = pd.to_datetime(df_final['date'])
        
        # ลบตัวซ้ำ (เอาตัวใหม่ล่าสุดไว้เสมอ)
        df_final = df_final.drop_duplicates(subset=['date'], keep='last')
    else:
        print("⚠️ Warning: New data is empty! Using old data only.")
        df_final = df_old
        df_final['date'] = pd.to_datetime(df_final['date'])
        
    # จัดระเบียบ
    df_final = df_final.sort_values(by='date', ascending=False)
    print(f"   📊 Final Data: {len(df_final)} rows (Latest date: {df_final['date'].max()})") # เช็คบรรทัดนี้ว่าวันที่ล่าสุดคือ 2025 ไหม?
    
    df_final['date'] = df_final['date'].dt.strftime('%Y-%m-%d')
    df_final = df_final.fillna('-')
    
    # 4. ส่งขึ้น Cloud
    upload_data(df_final, JSON_KEY_PATH, TARGET_SHEET_NAME)

if __name__ == "__main__":
    main()