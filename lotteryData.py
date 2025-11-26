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
    
    # 2. ดึงของใหม่ (Auto Date)
    df_new = fetch_current_year_data()
    
    # 3. รวมร่าง
    print("\n🔄 3. Merging Data...")
    if not df_new.empty:
        df_final = pd.concat([df_old, df_new]).drop_duplicates(subset=['date'], keep='last')
    else:
        df_final = df_old
        
    # จัดระเบียบ
    df_final['date'] = pd.to_datetime(df_final['date'])
    df_final = df_final.sort_values(by='date', ascending=False)
    df_final['date'] = df_final['date'].dt.strftime('%Y-%m-%d')
    df_final = df_final.fillna('-')
    
    # 4. ส่งขึ้น Cloud
    upload_data(df_final, JSON_KEY_PATH, TARGET_SHEET_NAME)

if __name__ == "__main__":
    main()