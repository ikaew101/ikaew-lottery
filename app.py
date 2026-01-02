# app.py
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os

# Import ทั้ง 2 แผนก
from src.bot_logic import get_prediction_message   # แผนกหวย
from src.gemini_logic import get_gemini_response   # แผนกคุยเล่น (มาใหม่)

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

@app.route("/", methods=['GET'])
def home():
    return "Super Bot is Running!", 200

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()
    
    # 1. เช็คว่าเป็นเรื่องหวยไหม?
    lottery_keywords = ["เลขเด็ด", "หวย", "วิเคราะห์", "แนวทาง"]
    
    if any(k in user_msg for k in lottery_keywords):
        # ส่งไปแผนกหวย
        reply_text = get_prediction_message()
    else:
        # 2. ถ้าไม่ใช่เรื่องหวย ให้ส่งไปคุยกับ Gemini
        # (บอกให้ user รอแป๊บนึง เพราะ AI อาจคิดนาน)
        reply_text = get_gemini_response(user_msg)
        
    # ส่งคำตอบกลับไป
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)