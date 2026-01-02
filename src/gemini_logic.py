import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
from datetime import datetime
import pytz

# --- การตั้งค่าพื้นฐาน ---
GENAI_API_KEY = os.getenv('GEMINI_API_KEY')

def get_google_client():
    """เชื่อมต่อกับ Google Sheets API"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # สำหรับใช้งานบน Render (ใส่ JSON ใน Environment Variable)
    if os.getenv('GOOGLE_CREDENTIALS_JSON'):
        creds_dict = json.loads(os.getenv('GOOGLE_CREDENTIALS_JSON'))
        return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope))
    # สำหรับใช้งาน Local
    return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name('core/credentials.json', scope))

def save_to_accounting_sheet(data):
    """ฟังก์ชันบันทึกข้อมูลรายรับ-รายจ่ายลง Sheet Accounting"""
    try:
        client = get_google_client()
        sheet = client.open('LotteryData').worksheet('Accounting')
        
        # ดึงเวลาปัจจุบันประเทศไทย
        tz = pytz.timezone('Asia/Bangkok')
        now = datetime.now(tz)
        
        # เพิ่มแถวข้อมูล: วันที่เวลา, ประเภท, หมวดหมู่, จำนวนเงิน, หมายเหตุ
        sheet.append_row([
            now.strftime("%d/%m/%Y %H:%M"),
            data.get('type'),
            data.get('category'),
            float(data.get('amount', 0)),
            data.get('note')
        ])
        return True
    except Exception as e:
        print(f"Error saving to sheet: {e}")
        return False

def get_gemini_response(user_text, user_id):
    if not GENAI_API_KEY:
        return "⚠️ กรุณาตั้งค่า GEMINI_API_KEY บน Render ก่อนครับ"

    try:
        # 1. เตรียมข้อมูลเวลาปัจจุบัน
        tz = pytz.timezone('Asia/Bangkok')
        current_time = datetime.now(tz).strftime("%d/%m/%Y %H:%M:%S")

        # 2. ตั้งค่า System Instruction (หัวใจของระบบเลขาบัญชี)
        system_instruction = f"""
        คุณคือ 'My Assistant' เลขาส่วนตัวที่เก่งเรื่องบัญชีและใจดีเหมือนป้านวล
        ขณะนี้เวลาประเทศไทยคือ: {current_time}

        หน้าที่ของคุณ:
        1. หากผู้ใช้พิมพ์รายการเกี่ยวกับเงิน (รายรับหรือรายจ่าย) เช่น 'ซื้อข้าว 50' หรือ 'เงินเดือนออก 30000'
           คุณต้องตอบกลับเป็น JSON รูปแบบนี้เท่านั้น:
           {{"action": "record", "type": "รายจ่าย/รายรับ", "category": "หมวดหมู่", "amount": ตัวเลข, "note": "รายละเอียด"}}

        2. หากผู้ใช้ถามคำถามทั่วไป หรือถามเวลา ให้ตอบอย่างสุภาพ ลงท้ายด้วย 'จ้า' หรือ 'ครับ' ตามความเหมาะสม
        3. หากผู้ใช้ถามเรื่องหวยหรือเลขเด็ด ให้บอกว่า 'กำลังเรียกดูสถิติให้รอสักครู่นะจ๊ะ' (เพื่อให้ระบบหลักทำงานต่อ)
        """

        # 3. เชื่อมต่อโมเดล (ใช้ชื่อรุ่นที่คุณรันสำเร็จ)
        genai.configure(api_key=GENAI_API_KEY)
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash', 
            system_instruction=system_instruction
        )
        
        # 4. ส่งข้อความไปประมวลผล
        response = model.generate_content(user_text)
        res_text = response.text

        # 5. ตรวจสอบว่าต้องบันทึกบัญชีหรือไม่
        if '{"action": "record"' in res_text:
            try:
                # สกัด JSON ออกจากคำตอบ (เผื่อ AI มีข้อความอื่นปนมา)
                start_index = res_text.find('{')
                end_index = res_text.rfind('}') + 1
                json_str = res_text[start_index:end_index]
                data = json.loads(json_str)
                
                if save_to_accounting_sheet(data):
                    return f"✅ จดบันทึกให้แล้วจ้า: {data['note']} {data['amount']} บาท (หมวด{data['category']})"
                else:
                    return "❌ เกิดปัญหาขณะบันทึกลง Google Sheet จ้า"
            except:
                return res_text # หากแปลง JSON พลาดให้ส่งข้อความปกติ
        
        # ส่งคำตอบปกติกลับไป
        return res_text

    except Exception as e:
        return f"❌ ขออภัยจ้า สมองขัดข้องชั่วคราว: {str(e)}"