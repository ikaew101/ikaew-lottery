import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
import os
import json
from datetime import datetime
import pytz
import re
import uuid

# --- Config ---
GENAI_API_KEY = os.getenv('GEMINI_API_KEY')

def get_google_client():
    """เชื่อมต่อ Google Sheets"""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    try:
        if os.getenv('GOOGLE_CREDENTIALS_JSON'):
            creds_dict = json.loads(os.getenv('GOOGLE_CREDENTIALS_JSON'))
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        else:
            creds = Credentials.from_service_account_file('core/credentials.json', scopes=scopes)
            
        return gspread.authorize(creds)
    except Exception as e:
        raise Exception(f"Auth Error: {str(e)}")

# --- Functions จัดการ Google Sheet ---

def save_to_accounting_sheet(data):
    """บันทึกข้อมูล (แบบระบุ Tab แม่นยำ ห้ามลง Sheet อื่น)"""
    try:
        client = get_google_client()
        
        # 1. เปิดไฟล์ LotteryData
        try:
            spreadsheet = client.open('LotteryData')
        except gspread.SpreadsheetNotFound:
            return False, "หาไฟล์ชื่อ 'LotteryData' ไม่เจอ", ""

        # 2. เปิด Tab Accounting (ถ้าไม่เจอ ให้ Error เลย ห้ามไป Sheet1)
        try:
            sheet = spreadsheet.worksheet('Accounting')
        except gspread.WorksheetNotFound:
            return False, "ไม่พบ Tab ชื่อ 'Accounting' ในไฟล์นี้ (กรุณาสร้าง Tab ชื่อ Accounting ให้ถูกต้องเป๊ะๆ)", ""

        tz = pytz.timezone('Asia/Bangkok')
        now = datetime.now(tz)

        tx_id = f"tx_{str(uuid.uuid4())[:8]}"
        
        sheet.append_row([
            now.strftime("%d/%m/%Y %H:%M"),
            data.get('type'),
            data.get('category'),
            float(data.get('amount', 0)),
            data.get('note'),
            tx_id
        ])
        
        # ส่ง URL ของไฟล์กลับไปให้ผู้ใช้กดดูด้วย
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
                if r['Type'] == 'รายรับ':
                    total_income += amt
                else:
                    total_expense += amt
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

    if ("สรุป" in user_text or "ยอด" in user_text) and "เดือนนี้" in user_text and "หมวดหมู่" not in user_text:
        return get_total_summary(mode="simple")
    if "หมวดหมู่" in user_text:
        return get_total_summary(mode="detail")

    try:
        tz = pytz.timezone('Asia/Bangkok')
        current_time = datetime.now(tz).strftime("%d/%m/%Y %H:%M:%S")
        
        system_instruction = f"""
        คุณคือเลขาส่วนตัว 'My Assistant' เก่งบัญชี เวลา: {current_time}
        หน้าที่:
        1. ถ้าผู้ใช้พิมพ์รายการเงิน ตอบ JSON Array:
           [
             {{"action": "record", "type": "รายจ่าย/รายรับ", "category": "หมวดหมู่", "amount": ตัวเลข, "note": "รายละเอียด"}}
           ]
           หมวดหมู่: ['อาหาร', 'เดินทาง', 'ช้อปปิ้ง', 'ของใช้ส่วนตัว', 'ค่าบ้าน/รถ', 'บิลค่าน้ำไฟ', 'บันเทิง', 'สุขภาพ', 'เงินออม', 'รายรับ', 'อื่นๆ']
        2. คำถามทั่วไปตอบปกติ
        """

        genai.configure(api_key=GENAI_API_KEY)
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=system_instruction,
            tools='google_search_retrieval'
        )
        
        response = model.generate_content(user_text)
        res_text = response.text.strip()
        cleaned_text = re.sub(r'```json|```', '', res_text).strip()
        
        start_index = -1
        end_index = -1
        
        if '[' in cleaned_text and ']' in cleaned_text:
            start_index = cleaned_text.find('[')
            end_index = cleaned_text.rfind(']') + 1
        elif '{' in cleaned_text and '}' in cleaned_text:
            start_index = cleaned_text.find('{')
            end_index = cleaned_text.rfind('}') + 1

        if start_index != -1 and end_index != -1:
            try:
                json_str = cleaned_text[start_index:end_index]
                data = json.loads(json_str)
                if isinstance(data, dict): data = [data]
                
                recorded_items = []
                failed_items = []
                total_amount = 0
                file_url = ""
                
                for item in data:
                    if item.get('action') == 'record':
                        success, error_msg, tx_id = save_to_accounting_sheet(item)
                        
                        if success:
                            update_summary(item)
                            recorded_items.append(f"- {item.get('note')}: {item.get('amount')} บาท")
                            total_amount += float(item.get('amount', 0))
                        else:
                            failed_items.append(f"❌ บันทึกไม่ได้: {error_msg}")
                
                reply_msg = ""
                if recorded_items:
                    reply_msg += f"✅ จดบันทึกเรียบร้อย!\n" + "\n".join(recorded_items)
                    reply_msg += f"\n\nรวม: {total_amount:,.2f} บาท"
                
                if failed_items:
                    reply_msg += "\n\n" + "\n".join(failed_items)
                    
                if reply_msg:
                    return reply_msg
                    
            except json.JSONDecodeError:
                pass
        
        return res_text

    except Exception as e:
        return f"❌ ระบบขัดข้อง: {str(e)}"