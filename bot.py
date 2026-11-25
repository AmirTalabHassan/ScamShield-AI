import io
import os
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer

import telebot
from google import genai
from google.genai import types
from PIL import Image

# قراءة المفاتيح من متغيرات البيئة في Render
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not TELEGRAM_TOKEN:
    print("ERROR: TELEGRAM_TOKEN is missing in environment variables!", flush=True)
    sys.exit(1)

if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY is missing in environment variables!", flush=True)
    sys.exit(1)

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY)

# خادم HTTP بسيط لمنفذ Render المجاني (الافتراضي 10000)
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def start_health_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Health server running on port {port}", flush=True)


start_health_server()

SYSTEM_PROMPT = """
أنت مساعد ذكي متخصص في كشف الاحتيال الإلكتروني والرسائل والروابط والصور المشبوهة (ScamShield AI).
حلّل المحتوى المرسل إليك بدقة ووضوح باللغة العربية، وحدد:
1. مستوى الخطورة (آمن / مشبوه / عالي الخطورة - احتيال محتمل).
2. أبرز المؤشرات أو العلامات التي بنيت عليها التقييم (مثل الروابط المريبة، انتحال البنوك أو الجهات الرسمية، طلب رموز OTP، أو الاستعجال الوهمي).
3. نصيحة عملية فورية للمستخدم حول كيفية التصرف بأمان.
"""

MODEL_NAME = "gemini-2.5-flash"


def analyze_with_gemini(contents):
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2,
        ),
    )
    if response and response.text:
        return response.text.strip()
    raise RuntimeError("Empty response received from Gemini API")


@bot.message_handler(commands=["start"])
def handle_start(message):
    welcome_text = (
        "مرحباً بك في درع الحماية الذكي (ScamShield AI) 🛡️\n\n"
        "أرسل لي أي رسالة نصية، رابط، أو لقطة شاشة (Screenshot) تشك في أنها "
        "محاولة احتيال، وسأقوم بفحصها لك فوراً بالذكاء الاصطناعي."
    )
    bot.reply_to(message, welcome_text)


@bot.message_handler(content_types=["text"])
def handle_text(message):
    if not message.text or message.text.startswith("/"):
        return

    status_msg = bot.reply_to(message, "⏳ جاري تحليل الرسالة...")
    try:
        print(f"Analyzing text from user {message.from_user.id}", flush=True)
        result = analyze_with_gemini(message.text)
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=result,
        )
    except Exception as e:
        print("GEMINI TEXT ERROR:", repr(e), flush=True)
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        try:
            bot.edit_message_text(
                chat_id=status_msg.chat.id,
                message_id=status_msg.message_id,
                text="⚠️ حدث خطأ أثناء التحليل، يرجى المحاولة مرة أخرى.",
            )
        except Exception:
            bot.reply_to(message, "⚠️ حدث خطأ أثناء التحليل، يرجى المحاولة مرة أخرى.")


@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    status_msg = bot.reply_to(message, "⏳ جاري فحص الصورة...")
    try:
        print(f"Analyzing photo from user {message.from_user.id}", flush=True)
        photo_info = bot.get_file(message.photo[-1].file_id)
        downloaded_bytes = bot.download_file(photo_info.file_path)
        image = Image.open(io.BytesIO(downloaded_bytes))

        prompt_parts = [image]
        if message.caption:
            prompt_parts.append(f"تعليق المستخدم مع الصورة: {message.caption}")
        else:
            prompt_parts.append("افحص هذه الصورة واكتشف إن كانت تحتوي على احتيال أو روابط أو رسائل مشبوهة.")

        result = analyze_with_gemini(prompt_parts)
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=result,
        )
    except Exception as e:
        print("GEMINI PHOTO ERROR:", repr(e), flush=True)
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        try:
            bot.edit_message_text(
                chat_id=status_msg.chat.id,
                message_id=status_msg.message_id,
                text="⚠️ حدث خطأ أثناء التحليل، يرجى المحاولة مرة أخرى.",
            )
        except Exception:
            bot.reply_to(message, "⚠️ حدث خطأ أثناء التحليل، يرجى المحاولة مرة أخرى.")


if __name__ == "__main__":
    print("Starting ScamShield AI bot polling...", flush=True)
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=25)
