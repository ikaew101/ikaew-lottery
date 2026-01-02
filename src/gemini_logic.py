import google.generativeai as genai
import os

# ตั้งค่า API Key (เดี๋ยวไปใส่ใน Render)
GENAI_API_KEY = os.getenv('GEMINI_API_KEY')

def get_gemini_response(user_text):
    if not GENAI_API_KEY:
        return "⚠️ ขออภัยครับ ยังไม่ได้ตั้งค่า Gemini API Key"

    try:
        genai.configure(api_key=GENAI_API_KEY)
        
        # เลือกโมเดล (Gemini 1.5 Flash เร็วและเก่งพอตัว)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # ส่งข้อความไปถาม
        response = model.generate_content(user_text)
        
        return response.text
        
    except Exception as e:
        return f"เกิดข้อผิดพลาดจาก AI: {str(e)}"