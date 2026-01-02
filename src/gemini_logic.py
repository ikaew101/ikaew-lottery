import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
from datetime import datetime
import pytz

# --- Config ---
GENAI_API_KEY = os.getenv('GEMINI_API_KEY')

def get_google_client():
    """เชื่อมต่อกับ Google Sheets API"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # กรณีใช้บน Render (ดึง JSON จาก Environment Variable)
    if os.getenv('GOOGLE_CREDENTIALS_JSON'):
        creds_dict = json.loads(os.getenv('GOOGLE_CREDENTIALS_JSON'))
        return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope))
    
    # กรณีรันบนเครื่องตัวเอง (ดึงจากไฟล์)
    return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name('core/credentials.json', scope))

# --- Functions จัดการ Google Sheet ---

def save_to_accounting_sheet(data):
    """(ฟังก์ชันที่ขาดไป) บันทึกข้อมูลลง Sheet 'Accounting'"""
    try:
        client = get_google_client()
        sheet = client.open('LotteryData').worksheet('Accounting')
        
        tz = pytz.timezone('Asia/Bangkok')
        now = datetime.now(tz)
        
        # บันทึก: วันที่, ประเภท, หมวดหมู่, จำนวนเงิน, รายละเอียด
        sheet.append_row([
            now.strftime("%d/%m/%Y %H:%M"),
            data.get('type'),
            data.get('category'),
            float(data.get('amount', 0)),
            data.get('note')
        ])
        return True
    except Exception as e:
        print(f"Save Error: {e}")
        return False

def update_summary(data):
    """อัปเดตยอดรวมในหน้า 'Summary'"""
    try:
        client = get_google_client()
        sheet = client.open('LotteryData').worksheet('Summary')
        
        tz = pytz.timezone('Asia/Bangkok')
        month_str = datetime.now(tz).strftime("%m/%Y")
        
        records = sheet.get_all_records()
        found = False
        
        # วนลูปหาแถวที่ตรงกับ เดือน+ประเภท+หมวดหมู่ เพื่อบวกยอดเงินเพิ่ม
        for i, row in enumerate(records):
            if str(row['Month']) == month_str and row['Type'] == data['type'] and row['Category'] == data['category']:
                new_amount = float(row['Amount']) + float(data['amount'])
                # i + 2 เพราะ row ใน list เริ่มที่ 0 แต่ใน sheet แถวแรกคือ header (1) + ข้อมูลเริ่มแถว 2
                sheet.update_cell(i + 2, 4, new_amount) 
                found = True
                break
        
        # ถ้ายังไม่มีหมวดหมู่นี้ในเดือนนี้ ให้สร้างแถวใหม่
        if not found:
            sheet.append_row([month_str, data['type'], data['category'], float(data['amount'])])
            
    except Exception as e:
        print(f"Summary Update Error: {e}")

def get_total_summary(mode="simple"):
    """ดึงข้อมูลสรุปยอดจาก Sheet 'Summary' มาตอบ"""
    try:
        client = get_google_client()
        sheet = client.open('LotteryData').worksheet('Summary')
        records = sheet.get_all_records()
        
        tz = pytz.timezone('Asia/Bangkok')
        month_str = datetime.now(tz).strftime("%m/%Y")
        
        total_income = 0
        total_expense = 0
        categories = []

        for r in records:
            if str(r['Month']) == month_str:
                amt = float(r['Amount'])
                if r['Type'] == 'รายรับ':
                    total_income += amt
                else:
                    total_expense += amt
                    categories.append(f"- {r['Category']}: {amt:,.2f} บาท")

        if mode == "simple":
            return (f"📊 สรุปยอดเดือน {month_str}\n"
                    f"💰 รายรับ: {total_income:,.2f} บาท\n"
                    f"💸 รายจ่าย: {total_expense:,.2f} บาท\n"
                    f"คงเหลือ: {(total_income - total_expense):,.2f} บาทจ้า")
        else:
            cat_text = "\n".join(categories) if categories else "ยังไม่มีรายการจ้า"
            return f"📂 รายจ่ายแยกหมวดหมู่ ({month_str}):\n{cat_text}"
            
    except Exception as e:
        return f"❌ ดึงข้อมูลไม่ได้จ้า: {str(e)}"

# --- Main Logic ---

def get_gemini_response(user_text, user_id):
    if not GENAI_API_KEY: return "⚠️ Missing API Key"

    # เช็คคำสั่งดูยอดเงิน (ไม่ต้องถาม AI)
    if "สรุปรายรับรายจ่าย" in user_text or "สรุปยอดเดือนนี้" in user_text:
        return get_total_summary(mode="simple")
    if "แยกตามหมวดหมู่" in user_text:
        return get_total_summary(mode="detail")

    try:
        # เตรียม System Instruction
        tz = pytz.timezone('Asia/Bangkok')
        current_time = datetime.now(tz).strftime("%d/%m/%Y %H:%M:%S")
        
        system_instruction = f"""
        คุณคือเลขาส่วนตัว 'My Assistant' ที่ใจดีและเก่งบัญชี
        เวลาปัจจุบัน: {current_time}
        
        หน้าที่:
        1. ถ้าผู้ใช้พิมพ์รายการเงิน (เช่น 'ซื้อน้ำ 20', 'ได้เงิน 500') ให้ตอบเป็น JSON เท่านั้น:
           {{"action": "record", "type": "รายจ่าย/รายรับ", "category": "หมวดหมู่ที่เหมาะสม", "amount": ตัวเลข, "note": "รายละเอียด"}}
           
        2. ถ้าเป็นคำถามทั่วไป ให้ตอบตามปกติ สุภาพและเป็นกันเอง
        """

        genai.configure(api_key=GENAI_API_KEY)
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=system_instruction
        )
        
        response = model.generate_content(user_text)
        res_text = response.text

        # ตรวจสอบว่า AI ตอบกลับมาเป็น JSON สำหรับบันทึกบัญชีหรือไม่
        if '{"action": "record"' in res_text:
            try:
                # Clean JSON string
                start = res_text.find('{')
                end = res_text.rfind('}') + 1
                json_str = res_text[start:end]
                data = json.loads(json_str)
                
                # เรียกฟังก์ชันบันทึก (ตอนนี้มีครบแล้ว ไม่ Error แน่นอน)
                save_to_accounting_sheet(data)
                update_summary(data)
                
                # ตอบกลับผู้ใช้เป็นภาษาคน
                return f"✅ จดเรียบร้อย!\nรายการ: {data['note']}\nจำนวน: {data['amount']} บาท\nหมวด: {data['category']}"
            except:
                # ถ้าแปลงไม่ได้จริงๆ ให้ส่งข้อความเดิมกลับไป
                return res_text
        
        return res_text

    except Exception as e:
        return f"❌ ระบบขัดข้อง: {str(e)}"