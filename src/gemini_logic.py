import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
from datetime import datetime
import pytz
import re  # เพิ่ม module สำหรับจัดการข้อความ

# --- Config ---
GENAI_API_KEY = os.getenv('GEMINI_API_KEY')

def get_google_client():
    scope = ["[https://spreadsheets.google.com/feeds](https://spreadsheets.google.com/feeds)", "[https://www.googleapis.com/auth/drive](https://www.googleapis.com/auth/drive)"]
    if os.getenv('GOOGLE_CREDENTIALS_JSON'):
        creds_dict = json.loads(os.getenv('GOOGLE_CREDENTIALS_JSON'))
        return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope))
    return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name('core/credentials.json', scope))

# --- Functions จัดการ Google Sheet ---

def save_to_accounting_sheet(data):
    try:
        client = get_google_client()
        sheet = client.open('LotteryData').worksheet('Accounting')
        tz = pytz.timezone('Asia/Bangkok')
        now = datetime.now(tz)
        sheet.append_row([
            now.strftime("%d/%m/%Y %H:%M"),
            data.get('type'),
            data.get('category'), # หมวดหมู่จะตรงกันเป๊ะแล้ว
            float(data.get('amount', 0)),
            data.get('note')
        ])
        return True
    except Exception as e:
        print(f"Save Error: {e}")
        return False

def update_summary(data):
    try:
        client = get_google_client()
        sheet = client.open('LotteryData').worksheet('Summary')
        tz = pytz.timezone('Asia/Bangkok')
        month_str = datetime.now(tz).strftime("%m/%Y")
        records = sheet.get_all_records()
        found = False
        
        for i, row in enumerate(records):
            # เปรียบเทียบแบบ String เพื่อความชัวร์
            if str(row['Month']) == month_str and row['Type'] == data['type'] and row['Category'] == data['category']:
                new_amount = float(row['Amount']) + float(data['amount'])
                sheet.update_cell(i + 2, 4, new_amount) 
                found = True
                break
        
        if not found:
            sheet.append_row([month_str, data['type'], data['category'], float(data['amount'])])     
    except Exception as e:
        print(f"Summary Update Error: {e}")

def get_total_summary(mode="simple"):
    try:
        client = get_google_client()
        sheet = client.open('LotteryData').worksheet('Summary')
        records = sheet.get_all_records()
        tz = pytz.timezone('Asia/Bangkok')
        month_str = datetime.now(tz).strftime("%m/%Y")
        
        total_income = 0
        total_expense = 0
        categories = {} # ใช้ Dict เพื่อรวมยอดหมวดเดียวกัน

        for r in records:
            if str(r['Month']) == month_str:
                amt = float(r['Amount'])
                if r['Type'] == 'รายรับ':
                    total_income += amt
                else:
                    total_expense += amt
                    # รวมยอดหมวดหมู่เดียวกันเข้าด้วยกัน (แก้ปัญหาหมวดซ้ำในรายงาน)
                    cat_name = r['Category']
                    categories[cat_name] = categories.get(cat_name, 0) + amt

        if mode == "simple":
            return (f"📊 สรุปยอดเดือน {month_str}\n"
                    f"💰 รายรับ: {total_income:,.2f} บาท\n"
                    f"💸 รายจ่าย: {total_expense:,.2f} บาท\n"
                    f"คงเหลือ: {(total_income - total_expense):,.2f} บาทจ้า")
        else:
            cat_list = [f"- {k}: {v:,.2f} บาท" for k, v in categories.items()]
            cat_text = "\n".join(cat_list) if cat_list else "ยังไม่มีรายการจ้า"
            return f"📂 รายจ่ายแยกหมวดหมู่ ({month_str}):\n{cat_text}"
            
    except Exception as e:
        return f"❌ ดึงข้อมูลไม่ได้จ้า: {str(e)}"

# --- Main Logic ---

def get_gemini_response(user_text, user_id):
    if not GENAI_API_KEY: return "⚠️ Missing API Key"

    if "สรุปรายรับรายจ่าย" in user_text or "สรุปยอดเดือนนี้" in user_text:
        return get_total_summary(mode="simple")
    if "แยกตามหมวดหมู่" in user_text:
        return get_total_summary(mode="detail")

    try:
        tz = pytz.timezone('Asia/Bangkok')
        current_time = datetime.now(tz).strftime("%d/%m/%Y %H:%M:%S")
        
        # [แก้จุดที่ 2] ล็อคหมวดหมู่มาตรฐาน เพื่อไม่ให้ AI คิดชื่อเองมั่ว
        system_instruction = f"""
        คุณคือเลขาส่วนตัว 'My Assistant' ที่ใจดีและเก่งบัญชี เวลา: {current_time}
        
        หน้าที่:
        1. ถ้าผู้ใช้พิมพ์รายการเงิน ให้ตอบ JSON เท่านั้น โดยเลือกหมวดหมู่ (category) จากรายการนี้เท่านั้น ห้ามคิดคำอื่น:
           ['อาหาร', 'เดินทาง', 'ช้อปปิ้ง', 'ของใช้ส่วนตัว', 'ค่าบ้าน/รถ', 'บิลค่าน้ำไฟ', 'บันเทิง', 'สุขภาพ', 'เงินออม', 'รายรับ', 'อื่นๆ']
           
           รูปแบบ JSON:
           {{"action": "record", "type": "รายจ่าย/รายรับ", "category": "เลือกจากรายการข้างบน", "amount": ตัวเลข, "note": "รายละเอียด"}}
           
        2. ถ้าเป็นคำถามทั่วไป ตอบตามปกติ สุภาพ เป็นกันเอง
        """

        genai.configure(api_key=GENAI_API_KEY)
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=system_instruction
        )
        
        response = model.generate_content(user_text)
        res_text = response.text.strip()

        # [แก้จุดที่ 1] ระบบทำความสะอาดข้อความที่ฉลาดขึ้น
        # 1. ลบ ```json และ ``` ออก ไม่ว่าจะอยู่ตรงไหน
        cleaned_text = re.sub(r'```json|```', '', res_text).strip()
        
        # 2. ค้นหา { และ } เพื่อดึงเฉพาะ JSON ออกมา
        start_index = cleaned_text.find('{')
        end_index = cleaned_text.rfind('}') + 1

        if start_index != -1 and end_index != -1:
            try:
                json_str = cleaned_text[start_index:end_index]
                data = json.loads(json_str)
                
                if data.get('action') == 'record':
                    save_to_accounting_sheet(data)
                    update_summary(data)
                    return f"✅ จดเรียบร้อย!\nรายการ: {data.get('note')}\nจำนวน: {data.get('amount')} บาท\nหมวด: {data.get('category')}"
            except json.JSONDecodeError:
                pass # ถ้าแปลงไม่ได้ ก็ให้ถือว่าเป็นข้อความธรรมดา
        
        return res_text

    except Exception as e:
        return f"❌ ระบบขัดข้อง: {str(e)}"