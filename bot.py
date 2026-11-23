import os
import telebot
from google import genai
from PIL import Image
import io

# قراءة المفاتيح من متغيرات البيئة بأمان
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
أنت نظام "درع مكافحة الجريمة الإلكترونية (ScamShield AI)" المصمم لحماية المجتمع في دولة الإمارات من الاحتيال الإلكتروني.
مهمتك تحليل الرسائل النصية، الروابط، أو لقطات الشاشة (Screenshots) المرسلة إليك.
انتبه بشكل خاص لأساليب الاحتيال الشائعة في الإمارات:
- انتحال صفة جهات حكومية (شرطة أبوظبي، الهوية الرقمية UAE Pass، بريد الإمارات، سالك، درب، هيئة الاتصالات).
- الروابط المزيفة التي تطلب دفع مخالفات أو رسوم شحن أو تحديث بيانات بنكية.
- إيصالات التحويل البنكي المزورة أو عروض التوظيف والاستثمار الوهمية.

أجب دائماً بتنسيق منظم ومختصر وواضح باللغة التي كتب بها المستخدم (عربي أو إنجليزي):
1. التقييم: (🚨 احتيال مؤكد / ⚠️ مشبوه جداً / ✅ يبدو آمناً) مع نسبة الخطورة (0% إلى 100%).
2. السبب: اشرح في سطرين بوضوح علامات الخطر (مثل: رابط غير رسمي، لغة استعجال وتهديد، طلب بيانات سرية).
3. النصيحة الفورية: ماذا يجب أن يفعل المستخدم الآن.
"""

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "🛡️ مرحباً بك في **درع الحماية الذكي (ScamShield AI)**\n\n"
        "أرسل لي أي رسالة نصية، رابط، أو لقطة شاشة (Screenshot) تشك في أنها محاولة احتيال، وسأقوم بفحصها لك فوراً بالذكاء الاصطناعي."
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(content_types=['text'])
def analyze_text(message):
    wait_msg = bot.reply_to(message, "🔍 جاري فحص الرسالة وتحليل الروابط...")
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[SYSTEM_PROMPT, f"حلل هذه الرسالة:\n{message.text}"]
        )
        bot.edit_message_text(response.text, chat_id=message.chat.id, message_id=wait_msg.message_id)
    except Exception:
        bot.edit_message_text("⚠️ حدث خطأ أثناء التحليل، يرجى المحاولة مرة أخرى.", chat_id=message.chat.id, message_id=wait_msg.message_id)

@bot.message_handler(content_types=['photo'])
def analyze_image(message):
    wait_msg = bot.reply_to(message, "🖼️ جاري فحص الصورة وتحليل النصوص والروابط بداخلها...")
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        image = Image.open(io.BytesIO(downloaded_file))

        caption = message.caption if message.caption else "افحص هذه الصورة وتأكد هل هي محاولة احتيال أو إيصال مزور أم لا."
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[SYSTEM_PROMPT, image, caption]
        )
        bot.edit_message_text(response.text, chat_id=message.chat.id, message_id=wait_msg.message_id)
    except Exception:
        bot.edit_message_text("⚠️ تعذر قراءة الصورة، تأكد من وضوحها وحاول مجدداً.", chat_id=message.chat.id, message_id=wait_msg.message_id)

print("ScamShield Bot is running...")
bot.infinity_polling()
