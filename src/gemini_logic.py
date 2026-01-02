import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
from datetime import datetime
import pytz

GENAI_API_KEY = os.getenv('GEMINI_API_KEY')

def get_google_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    if os.getenv('GOOGLE_CREDENTIALS_JSON'):
        creds_dict = json.loads(os.getenv('GOOGLE_CREDENTIALS_JSON'))
        return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope))
    return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name('core/credentials.json', scope))

def update_summary(data):
    """อัปเดตยอดรวมในหน้า Summary ทันทีที่มีการจดบันทึก"""
    try:
        client = get_google_client()
        summary_sheet = client.open('LotteryData').worksheet('Summary')
        tz = pytz.timezone('Asia/Bangkok')
        month_str = datetime.now(tz).strftime("%m/%Y")
        
        records = summary_sheet.get_all_records()
        found = False
        
        # ค้นหาว่าเดือน+ประเภท+หมวดหมู่นี้ มีอยู่แล้วหรือยัง
        for i, row in enumerate(records):
            if str(row['Month']) == month_str and row['Type'] == data['type'] and row['Category'] == data['category']:
                new_amount = float(row['Amount']) + float(data['amount'])
                summary_sheet.update_cell(i + 2, 4, new_amount) # อัปเดตช่อง Amount (Column 4)
                found = True
                break
        
        # ถ้ายังไม่มี ให้เพิ่มแถวใหม่
        if not found:
            summary_sheet.append_row([month_str, data['type'], data['category'], data['amount']])
    except Exception as e:
        print(f"Summary Update Error: {e}")

def get_total_summary(mode="simple"):
    """ดึงข้อมูลจากหน้า Summary มาตอบ"""
    try:
        client = get_google_client()
        summary_sheet = client.open('LotteryData').worksheet('Summary')
        records = summary_sheet.get_all_records()
        
        tz = pytz.timezone('Asia/Bangkok')
        month_str = datetime.now(tz).strftime("%m/%Y")
        
        total_income = 0
        total_expense = 0
        categories = []

        for r in records:
            if r['Month'] == month_str:
                amt = float(r['Amount'])
                if r['Type'] == 'รายรับ':
                    total_income += amt
                else:
                    total_expense += amt
                    categories.append(f"- {r['Category']}: {amt:,.2f} บาท")

        if mode == "simple":
            return (f"📊 สรุปยอดรวมเดือน {month_str}\n"
                    f"💰 รายรับ: {total_income:,.2f} บาท\n"
                    f"💸 รายจ่าย: {total_expense:,.2f} บาท\n"
                    f"คงเหลือ: {(total_income - total_expense):,.2f} บาทจ้า")
        else:
            cat_text = "\n".join(categories) if categories else "ไม่มีรายการจ้า"
            return f"📂 รายจ่ายแยกตามหมวดหมู่ ({month_str}):\n{cat_text}"
            
    except Exception as e:
        return f"❌ ดึงข้อมูลสรุปไม่ได้จ้า: {str(e)}"

def get_gemini_response(user_text, user_id):
    if not GENAI_API_KEY: return "⚠️ Missing API Key"

    # --- เช็คคำสั่งสรุปยอด ---
    if "สรุปรายรับรายจ่าย" in user_text or "สรุปยอดเดือนนี้" in user_text:
        return get_total_summary(mode="simple")
    if "แยกตามหมวดหมู่" in user_text:
        return get_total_summary(mode="detail")

    try:
        tz = pytz.timezone('Asia/Bangkok')
        current_time = datetime.now(tz).strftime("%d/%m/%Y %H:%M:%S")

        genai.configure(api_key=GENAI_API_KEY)
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=f"คุณคือเลขาส่วนตัวที่เก่งเรื่องบัญชี เวลาปัจจุบัน {current_time}. "
                               f"หากผู้ใช้พิมพ์รายการเงิน ให้ตอบ JSON รูปแบบ: "
                               f'{{"action": "record", "type": "รายจ่าย/รายรับ", "category": "หมวดหมู่", "amount": ตัวเลข, "note": "รายละเอียด"}}'
        )
        
        response = model.generate_content(user_text)
        res_text = response.text

        if '{"action": "record"' in res_text:
            start = res_text.find('{')
            end = res_text.rfind('}') + 1
            data = json.loads(res_text[start:end])
            
            # บันทึกลงหน้า Accounting (สมุดเล่มหลัก)
            client = get_google_client()
            acc_sheet = client.open('LotteryData').worksheet('Accounting')
            acc_sheet.append_row([datetime.now(tz).strftime("%d/%m/%Y %H:%M"), data['type'], data['category'], data['amount'], data['note']])
            
            # อัปเดตยอดรวมในหน้า Summary (สมุดเล่มสรุป)
            update_summary(data)
            
            return f"✅ จดบันทึกเรียบร้อย: {data['note']} {data['amount']} บาทจ้า"
        
        return res_text
    except Exception as e:
        return f"❌ ข้อผิดพลาด: {str(e)}"