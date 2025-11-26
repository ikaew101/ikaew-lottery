import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime
import time
import random
import pandas as pd

def generate_lotto_dates(year):
    """
    สร้างวันที่หวยออกโดยอัตโนมัติ (ฉบับปรับปรุงตามปฏิทิน 2568)
    """
    dates = []
    current_date = datetime.now()
    
    for month in range(1, 13):
        # กฎพื้นฐาน: ออกวันที่ 1 และ 16
        d1 = datetime(year, month, 1)
        d2 = datetime(year, month, 16)
        
        # --- กฎยกเว้น (วันหยุดสำคัญ) ---
        
        # 1. เดือนมกราคม: 
        # - งวดปีใหม่: ปกติออก 1 ม.ค. ปีนี้เลื่อนเป็น 2 ม.ค.
        # - วันครู: 16 ม.ค. เลื่อนไป 17 ม.ค.
        if month == 1:
            d1 = datetime(year, month, 2)  # แก้ไข: เปลี่ยนจาก None เป็นวันที่ 2
            d2 = datetime(year, month, 17) # 16 เลื่อนไป 17
            
        # 2. เดือนพฤษภาคม: 
        # - วันแรงงาน: 1 พ.ค. เลื่อนไป 2 พ.ค.
        elif month == 5:
            d1 = datetime(year, month, 2)
            
        # 3. เดือนมิถุนายน:
        # - 1 มิ.ย. (ถ้าตรงวันสำคัญทางศาสนาอาจเลื่อน แต่ปี 2025 น่าจะปกติ หรือออก 2 มิ.ย. เผื่อไว้)
        # * เพื่อความชัวร์ ลองเช็ควันที่ 1 ก่อน ถ้าพลาดค่อยว่ากัน *

        # 4. เดือนธันวาคม:
        # - 30 ธ.ค. (บางปีมีงวดพิเศษส่งท้าย)
        if month == 12:
            d3 = datetime(year, month, 30)
            if d3 <= current_date: dates.append(d3)

        # --- เพิ่มวันที่ลง List (กรองเฉพาะวันที่ถึงกำหนดแล้ว) ---
        if d1 and d1 <= current_date: dates.append(d1)
        if d2 and d2 <= current_date: dates.append(d2)
    
    # เรียงลำดับจากเก่าไปใหม่ และตัดตัวซ้ำ
    return sorted(list(set(dates)))

def get_lotto_result(date_obj):
    """ เจาะดึงเลขจากวันที่ระบุ (Sanook Scraper) """
    buddhist_year = date_obj.year + 543
    date_str_url = f"{date_obj.day:02d}{date_obj.month:02d}{buddhist_year}"
    url = f"https://news.sanook.com/lotto/check/{date_str_url}/"
    
    # ตั้งค่า Scraper ให้เนียน
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            resp = scraper.get(url, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, 'html.parser')
                
                data = {'date': date_obj}
                
                # 1. หาจาก Class (วิธีหลัก)
                p1 = soup.find('strong', class_='lotto__number--first')
                if p1: data['first_prize'] = p1.text.strip()
                
                # 2. หาจากกล่อง (วิธีสำรอง)
                columns = soup.find_all('div', class_='lottocheck__column')
                for col in columns:
                    header = col.find('span', class_='default-font--reward')
                    if not header: continue
                    txt = header.text.strip()
                    nums = [n.text.strip() for n in col.find_all('strong', class_='lotto__number')]
                    
                    if not nums: continue

                    if "รางวัลที่ 1" in txt and 'first_prize' not in data: 
                        data['first_prize'] = nums[0]
                    elif "เลขท้าย 2 ตัว" in txt: 
                        data['last_two_digits'] = nums[0]
                    elif "เลขหน้า 3 ตัว" in txt: 
                        data['prize_pre_3digit'] = str(nums).replace("'", "'")
                    elif "เลขท้าย 3 ตัว" in txt: 
                        data['prize_suf_3digit'] = str(nums).replace("'", "'")
                
                if 'first_prize' in data and 'last_two_digits' in data:
                    return data 
            
        except Exception:
            pass 
        
        # ถ้าพลาด ให้พักแป๊บนึงแล้วลองใหม่
        time.sleep(random.uniform(2, 4) * attempt)
        
    return None

def fetch_current_year_data():
    current_year = datetime.now().year
    print(f"🕵️ 2. Generating dates for {current_year} (Corrected Rules)...")
    
    # สร้างวันที่ตามกฎใหม่ (รวม 2 ม.ค.)
    target_dates = generate_lotto_dates(current_year)
    
    results = []
    for i, d in enumerate(target_dates):
        date_str = d.strftime('%d/%m/%Y')
        print(f"   [{i+1}/{len(target_dates)}] Fetching: {date_str}", end="")
        
        res = get_lotto_result(d)
        
        if res:
            print(f" ✅ -> {res.get('first_prize')} | {res.get('last_two_digits')}")
            results.append(res)
        else:
            print(" ❌ Failed")
        
        time.sleep(random.uniform(2, 4))
        
    return pd.DataFrame(results)