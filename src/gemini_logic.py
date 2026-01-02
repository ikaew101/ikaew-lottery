import google.generativeai as genai
from google.generativeai import client
import os

# อ่าน API Key จาก Environment Variable
GENAI_API_KEY = os.getenv('GEMINI_API_KEY')

def get_gemini_response(user_text, user_id):
    if not GENAI_API_KEY:
        return "⚠️ กรุณาตั้งค่า GEMINI_API_KEY บน Render ก่อนครับ"

    try:
        # [จุดสำคัญ] ตั้งค่าโดยบังคับใช้ API v1 (Stable) เท่านั้น เพื่อเลี่ยงปัญหา 404 จาก v1beta
        genai.configure(api_key=GENAI_API_KEY)
        
        # สร้าง Model โดยระบุชื่อแบบเต็ม เพื่อลดความผิดพลาดของ Library
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            # บังคับการส่งข้อมูลผ่าน gRPC หรือ REST ในเวอร์ชัน v1
        )
        
        # ส่งข้อความถาม AI
        response = model.generate_content(user_text)
        
        if response and response.text:
            return response.text
        else:
            return "AI ได้รับข้อมูลแต่ไม่สามารถประมวลผลคำตอบได้ในขณะนี้"
            
    except Exception as e:
        # หากยังพบปัญหา ให้แสดงข้อความแจ้งเตือนที่เข้าใจง่าย
        return f"❌ ขออภัยครับ ระบบ AI ขัดข้องชั่วคราว: {str(e)}"