import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
import os
import json
from datetime import datetime
import pytz
import re
import uuid
import cloudscraper
from bs4 import BeautifulSoup

# --- Config ---
GENAI_API_KEY = os.getenv('GEMINI_API_KEY')

def get_google_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        if os.getenv('GOOGLE_CREDENTIALS_JSON'):
            creds_dict = json.loads(os.getenv('GOOGLE_CREDENTIALS_JSON'))
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        else:
            creds = Credentials.from_service_account_file('core/credentials.json', scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        raise Exception(f"Auth Error: {str(e)}")

# --- Search Function ---
def search_weather_or_info(query):
    try:
        scraper = cloudscraper.create_scraper()
        url = f"https://html.duckduckgo.com/html/?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = scraper.get(url, headers=headers)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            results = [r.get_text() for r in soup.find_all('a', class_='result__a', limit=3)]
            snippets = [s.get_text() for s in soup.find_all('a', class_='result__snippet', limit=3)]
            return (" ".join(results) + " " + " ".join(snippets))[:2500]
    except Exception as e:
        print(f"Search Error: {e}")
    return ""

# --- Sheet Functions ---
def save_to_accounting_sheet(data):
    try:
        client = get_google_client()
        try: spreadsheet = client.open('LotteryData')
        except: return False, "หาไฟล์ 'LotteryData' ไม่เจอ", ""
        try: sheet = spreadsheet.worksheet('Accounting')
        except: return False, "ไม่พบ Tab 'Accounting'", ""

        tz = pytz.timezone('Asia/Bangkok')
        now = datetime.now(tz)
        tx_id = f"tx_{str(uuid.uuid4())[:8]}"
        sheet.append_row([
            now.strftime("%d/%m/%Y %H:%M"),
            data.get('type'), data.get('category'), float(data.get('amount', 0)), data.get('note'), tx_id
        ])
        return True, "", tx_id
    except Exception as e:
        return False, str(e), ""

def update_summary(data):
    try:
        client = get_google_client()
        sheet = client.open('LotteryData').worksheet('Summary')
        tz = pytz.timezone('Asia/Bangkok')
        month_str = datetime.now(tz).strftime("%m/%Y")
        records = sheet.get_all_records()
        found = False
        for i, row in enumerate(records):
            if str(row['Month']) == month_str and row['Type'] == data['type'] and row['Category'] == data['category']:
                new_amount = float(row['Amount']) + float(data['amount'])
                sheet.update_cell(i + 2, 4, new_amount) 
                found = True
                break
        if not found:
            sheet.append_row([month_str, data['type'], data['category'], float(data['amount'])])
    except Exception as e:
        print(f"Summary Error: {e}")

def get_total_summary(mode="simple"):
    try:
        client = get_google_client()
        sheet = client.open('LotteryData').worksheet('Summary')
        records = sheet.get_all_records()
        tz = pytz.timezone('Asia/Bangkok')
        month_str = datetime.now(tz).strftime("%m/%Y")
        total_income = 0
        total_expense = 0
        categories = {}
        for r in records:
            if str(r['Month']) == month_str:
                amt = float(r['Amount'])
                if r['Type'] == 'รายรับ': total_income += amt
                else:
                    total_expense += amt
                    categories[r['Category']] = categories.get(r['Category'], 0) + amt
        if mode == "simple":
            return (f"📊 สรุปยอดเดือน {month_str}\n💰 รายรับ: {total_income:,.2f} บาท\n💸 รายจ่าย: {total_expense:,.2f} บาท\nคงเหลือ: {(total_income - total_expense):,.2f} บาทจ้า")
        else:
            cat_list = [f"- {k}: {v:,.2f} บาท" for k, v in categories.items()]
            return f"📂 รายจ่ายแยกหมวดหมู่ ({month_str}):\n" + ("\n".join(cat_list) if cat_list else "ยังไม่มีรายการจ้า")
    except Exception as e:
        return f"❌ ดึงข้อมูลไม่ได้จ้า: {str(e)}"

# --- Main Logic with VALID MODEL LIST ---

def get_gemini_response(user_text, user_id):
    if not GENAI_API_KEY: return "⚠️ Missing API Key"

    if ("สรุป" in user_text or "ยอด" in user_text) and "เดือนนี้" in user_text and "หมวดหมู่" not in user_text:
        return get_total_summary(mode="simple")
    if "หมวดหมู่" in user_text:
        return get_total_summary(mode="detail")

    try:
        genai.configure(api_key=GENAI_API_KEY)
        tz = pytz.timezone('Asia/Bangkok')
        current_time = datetime.now(tz).strftime("%d/%m/%Y %H:%M:%S")
        
        # 1. ระบบค้นหา
        external_context = ""
        do_search = False
        if any(kw in user_text for kw in ["อากาศ", "weather", "ราคา", "ข่าว"]): do_search = True
        if user_text.startswith("ค้นหา") or user_text.lower().startswith("search"):
             do_search = True
             query = user_text.replace("ค้นหา", "").replace("search", "").strip()
             if query:
                print(f"Searching: {query}")
                res = search_weather_or_info(query)
                if res: external_context = f"\n[ข้อมูลจากการค้นหา]: {res}\n"

        # 2. Prompt
        system_instruction = f"""
        คุณคือเลขาส่วนตัว 'My Assistant' เก่งบัญชี เวลา: {current_time}
        {external_context}
        หน้าที่:
        1. อ้างอิงผลการค้นหาด้านบนถ้ามี
        2. ถ้าพิมพ์รายการเงิน ตอบ JSON Array: [{{"action": "record", "type": "รายจ่าย/รายรับ", "category": "หมวดหมู่", "amount": ตัวเลข, "note": "รายละเอียด"}}]
           หมวดหมู่: ['อาหาร', 'เดินทาง', 'ช้อปปิ้ง', 'ของใช้ส่วนตัว', 'ค่าบ้าน/รถ', 'บิลค่าน้ำไฟ', 'บันเทิง', 'สุขภาพ', 'เงินออม', 'รายรับ', 'อื่นๆ']
        3. คำถามทั่วไปตอบปกติ
        """

        # 3. [สำคัญ] รายชื่อโมเดลที่ใช้ได้จริง (เรียงจากโควต้าเยอะ -> น้อย)
        # เราจะไม่เดาชื่อแล้ว เอาชื่อจากที่คุณส่งมาใส่เลย
        models_to_try = [
            'gemini-2.0-flash-lite',         # หวังผลตัวนี้สุด (Lite = ถูก/ฟรีเยอะ)
            'gemini-2.0-flash-exp',          # ตัวทดลอง มักใจป้ำให้ใช้ฟรี
            'gemini-2.5-flash-lite',         # Lite ตัวใหม่
            'gemini-2.5-flash',              # ตัวนี้ใช้ได้ชัวร์ (แต่โควต้าน้อย ไว้กันตาย)
            'gemini-flash-lite-latest'       # เผื่อฟลุ๊ค
        ]

        response = None
        used_model = ""
        last_error = ""

        # วนลูปจนกว่าจะเจอตัวที่ยอมให้ใช้
        for model_name in models_to_try:
            try:
                # print(f"Trying model: {model_name}")
                model = genai.GenerativeModel(model_name=model_name, system_instruction=system_instruction)
                response = model.generate_content(user_text)
                used_model = model_name
                break # เจอตัวที่ใช่ หยุดทันที
            except Exception as e:
                last_error = str(e)
                continue 
        
        if not response:
            return f"❌ ทุกโมเดลปฏิเสธการทำงาน (Error ล่าสุด: {last_error})"

        # 4. ประมวลผล
        res_text = response.text.strip()
        cleaned_text = re.sub(r'```json|```', '', res_text).strip()
        start_index = -1
        if '[' in cleaned_text and ']' in cleaned_text:
            start_index = cleaned_text.find('[')
            end_index = cleaned_text.rfind(']') + 1
        elif '{' in cleaned_text and '}' in cleaned_text:
            start_index = cleaned_text.find('{')
            end_index = cleaned_text.rfind('}') + 1

        if start_index != -1 and end_index != -1:
            try:
                data = json.loads(cleaned_text[start_index:end_index])
                if isinstance(data, dict): data = [data]
                recorded_items = []
                failed_items = []
                total_amount = 0
                for item in data:
                    if item.get('action') == 'record':
                        success, error_msg, tx_id = save_to_accounting_sheet(item)
                        if success:
                            update_summary(item)
                            recorded_items.append(f"- {item.get('note')}: {item.get('amount')} บาท")
                            total_amount += float(item.get('amount', 0))
                        else:
                            failed_items.append(f"❌ บันทึกไม่ได้: {error_msg}")
                if recorded_items:
                    msg = f"✅ จดเรียบร้อย! (Model: {used_model})\n" + "\n".join(recorded_items)
                    msg += f"\n\nรวม: {total_amount:,.2f} บาท"
                    if failed_items: msg += "\n\n" + "\n".join(failed_items)
                    return msg
            except: pass
        
        return res_text

    except Exception as e:
        return f"❌ ระบบขัดข้อง: {str(e)}"

def get_dashboard_data():
    """ดึงข้อมูลสรุปยอดเดือนนี้ เพื่อส่งให้หน้าเว็บทำกราฟ"""
    try:
        client = get_google_client()
        sheet = client.open('LotteryData').worksheet('Summary')
        records = sheet.get_all_records()
        
        tz = pytz.timezone('Asia/Bangkok')
        month_str = datetime.now(tz).strftime("%m/%Y")
        
        categories = {}
        total_income = 0
        total_expense = 0
        
        for r in records:
            # ดึงเฉพาะข้อมูลเดือนปัจจุบัน
            if str(r['Month']) == month_str:
                amt = float(r['Amount'])
                if r['Type'] == 'รายรับ':
                    total_income += amt
                else:
                    total_expense += amt
                    # รวมยอดตามหมวดหมู่
                    cat = r['Category']
                    categories[cat] = categories.get(cat, 0) + amt
        
        # เตรียมข้อมูลส่งกลับเป็น JSON
        # แปลงข้อมูลกราฟ (แยกชื่อหมวดหมู่ และ ตัวเลขออกจากกัน)
        chart_labels = list(categories.keys())
        chart_data = list(categories.values())
        
        return {
            "month": month_str,
            "income": total_income,
            "expense": total_expense,
            "balance": total_income - total_expense,
            "chart_labels": chart_labels,
            "chart_data": chart_data
        }
        
    except Exception as e:
        print(f"Dashboard Error: {e}")
        return {}