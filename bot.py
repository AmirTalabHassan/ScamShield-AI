import io
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer

import telebot
from google import genai
from google.genai import types
from PIL import Image

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODEL_NAME = "gemini-2.5-flash"

if not TELEGRAM_TOKEN:
    print("ERROR: TELEGRAM_TOKEN is missing or empty in environment variables!", flush=True)
    sys.exit(1)

if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY is missing or empty in environment variables!", flush=True)
    sys.exit(1)

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode=None)
client = genai.Client(api_key=GEMINI_API_KEY)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"ScamShield AI is running")

    def log_message(self, format, *args):
        pass


def start_health_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Health server listening on 0.0.0.0:{port}", flush=True)


SYSTEM_PROMPT = """
أنت مساعد ذكي متخصص في كشف الاحتيال الإلكتروني والرسائل والروابط والصور المشبوهة (ScamShield AI).
حلّل المحتوى المرسل إليك بدقة ووضوح باللغة العربية، وقدّم إجابة منظمة تشمل:
1. مستوى الخطورة: (آمن / مشبوه / عالي الخطورة - احتيال محتمل).
2. أبرز المؤشرات أو العلامات التي بنيت عليها التقييم (مثل الروابط المريبة، انتحال البنوك أو الجهات الرسمية، طلب رموز OTP أو بيانات حساسة، أو الاستعجال الوهمي).
3. نصيحة عملية فورية للمستخدم حول كيفية التصرف بأمان.
"""


def analyze_with_gemini(contents):
    print(f"ACTIVE_MODEL: {MODEL_NAME}", flush=True)
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2,
        ),
    )
    if response and response.text and response.text.strip():
        return response.text.strip()
    raise RuntimeError("Empty response received from Gemini API")


def log_exception(tag, exc):
    print(f"{tag}: {repr(exc)}", flush=True)
    traceback.print_exc(file=sys.stdout)
    sys.stdout.flush()


@bot.message_handler(commands=["start"])
def handle_start(message):
    welcome_text = (
        "مرحباً بك في درع الحماية الذكي (ScamShield AI) 🛡️\n\n"
        "أرسل لي أي رسالة نصية، رابط، أو لقطة شاشة (Screenshot) تشك في أنها "
        "محاولة احتيال، وسأقوم بفحصها لك فوراً بالذكاء الاصطناعي."
    )
    try:
        bot.reply_to(message, welcome_text)
    except Exception as e:
        log_exception("START_REPLY_ERROR", e)


@bot.message_handler(content_types=["text"])
def handle_text(message):
    if not message.text or message.text.startswith("/"):
        return

    status_msg = None
    try:
        status_msg = bot.reply_to(message, "⏳ جاري تحليل الرسالة...")
        print(f"Analyzing text from user {message.from_user.id}", flush=True)
        result = analyze_with_gemini(message.text)

        if status_msg:
            bot.edit_message_text(
                chat_id=status_msg.chat.id,
                message_id=status_msg.message_id,
                text=result,
            )
        else:
            bot.reply_to(message, result)
    except Exception as e:
        log_exception("GEMINI_TEXT_ERROR", e)
        error_text = "⚠️ حدث خطأ أثناء التحليل، يرجى المحاولة مرة أخرى."
        try:
            if status_msg:
                bot.edit_message_text(
                    chat_id=status_msg.chat.id,
                    message_id=status_msg.message_id,
                    text=error_text,
                )
            else:
                bot.reply_to(message, error_text)
        except Exception as send_err:
            log_exception("TEXT_ERROR_NOTIFY_FAIL", send_err)


@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    status_msg = None
    try:
        status_msg = bot.reply_to(message, "⏳ جاري فحص الصورة...")
        print(f"Analyzing photo from user {message.from_user.id}", flush=True)

        photo_info = bot.get_file(message.photo[-1].file_id)
        downloaded_bytes = bot.download_file(photo_info.file_path)
        image = Image.open(io.BytesIO(downloaded_bytes))

        prompt_parts = [image]
        if message.caption and message.caption.strip():
            prompt_parts.append(f"تعليق المستخدم مع الصورة: {message.caption.strip()}")
        else:
            prompt_parts.append(
                "افحص هذه الصورة واكتشف إن كانت تحتوي على احتيال أو روابط أو رسائل مشبوهة."
            )

        result = analyze_with_gemini(prompt_parts)

        if status_msg:
            bot.edit_message_text(
                chat_id=status_msg.chat.id,
                message_id=status_msg.message_id,
                text=result,
            )
        else:
            bot.reply_to(message, result)
    except Exception as e:
        log_exception("GEMINI_PHOTO_ERROR", e)
        error_text = "⚠️ حدث خطأ أثناء التحليل، يرجى المحاولة مرة أخرى."
        try:
            if status_msg:
                bot.edit_message_text(
                    chat_id=status_msg.chat.id,
                    message_id=status_msg.message_id,
                    text=error_text,
                )
            else:
                bot.reply_to(message, error_text)
        except Exception as send_err:
            log_exception("PHOTO_ERROR_NOTIFY_FAIL", send_err)


def run_bot():
    start_health_server()
    try:
        bot.remove_webhook()
    except Exception as e:
        log_exception("REMOVE_WEBHOOK_WARNING", e)

    print("Starting ScamShield AI bot polling...", flush=True)
    while True:
        try:
            bot.infinity_polling(
                skip_pending=True,
                timeout=30,
                long_polling_timeout=25,
            )
        except Exception as e:
            log_exception("POLLING_CRASHED", e)
            time.sleep(5)


if __name__ == "__main__":
    run_bot()
