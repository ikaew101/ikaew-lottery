import google.generativeai as genai
import os

# อ่าน API Key จาก Environment Variable บน Render
GENAI_API_KEY = os.getenv('GEMINI_API_KEY')

def get_gemini_response(user_text, user_id):
    if not GENAI_API_KEY:
        return "⚠️ กรุณาตั้งค่า GEMINI_API_KEY บน Render ก่อนครับ"

    try:
        # 1. ตั้งค่า API Key
        genai.configure(api_key=GENAI_API_KEY)
        
        # 2. ระบุ Model แบบเจาะจง Full Path 
        # แนะนำ 'gemini-1.5-flash' ซึ่งเป็นรุ่นล่าสุดที่เสถียร
        model = genai.GenerativeModel(model_name='gemini-2.0-flash-exp')
        
        # 3. ส่งข้อความ (สามารถเพิ่มการตั้งค่า Safety หรือ Generation Config ได้ที่นี่)
        response = model.generate_content(user_text)
        
        if response and response.text:
            return response.text
        else:
            return "AI ได้รับข้อความ แต่ไม่สามารถสร้างคำตอบได้ในขณะนี้ครับ"
            
    except Exception as e:
        # Fallback กรณีเวอร์ชันข้างบนมีปัญหา ให้ลองใช้รุ่น 1.0 Pro
        try:
            fallback_model = genai.GenerativeModel(model_name='gemini-1.0-pro')
            return fallback_model.generate_content(user_text).text
        except:
            return f"❌ เกิดข้อผิดพลาดจาก AI: {str(e)}"