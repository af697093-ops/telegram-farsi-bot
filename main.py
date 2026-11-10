import os
import logging
from collections import defaultdict, deque

from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import Update
from telegram.constants import ChatAction, ChatType
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters
)

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "").strip()

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("لطفاً TELEGRAM_BOT_TOKEN و OPENAI_API_KEY را در فایل .env تنظیم کنید.")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("farsi-telegram-assistant")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
histories = defaultdict(lambda: deque(maxlen=12))
paused = False
disabled_chats = set()

SYSTEM_PROMPT = """
تو دستیار پاسخ‌گوی فارسیِ صاحب این ربات هستی.
به پیام‌ها فارسی روان، طبیعی، صمیمی، محترمانه و کوتاه جواب بده؛
مثل یک فرد واقعی که دوستانه و باحوصله گفتگو می‌کند، نه مثل متن اداری یا ربات.
لحن را با لحن مخاطب هماهنگ کن. از ایموجی فقط گاهی و به‌اندازه استفاده کن.
اگر اطلاعات کافی نداری، حدس نزن و یک سؤال کوتاه بپرس.
قول، قیمت، زمان، تعهد یا اطلاعات شخصی از طرف صاحب ربات نساز.
برای موضوعات حساس، مالی، حقوقی، پزشکی یا تصمیم‌های مهم، پاسخ قطعی و تعهدآور نده
و پیشنهاد کن صاحب حساب شخصاً بررسی کند.
اگر مخاطب پرسید آیا هوش مصنوعی هستی، صادقانه بگو دستیار هوشمند این حساب هستی.
خودت را صاحب حساب جا نزن و ادعای انجام کاری در دنیای واقعی نکن.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام، خوش اومدی 🌷\\nپیامت رو بفرست تا پاسخ‌گو باشم.\\n"
        "برای توقف پاسخ‌گویی در این گفتگو /stop و برای فعال‌سازی دوباره /start رو بزن."
    )
    disabled_chats.discard(update.effective_chat.id)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    disabled_chats.add(update.effective_chat.id)
    await update.message.reply_text("باشه، پاسخ‌گویی خودکار در این گفتگو متوقف شد.")

async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global paused
    if not OWNER_CHAT_ID or str(update.effective_chat.id) != OWNER_CHAT_ID:
        return
    paused = True
    await update.message.reply_text("پاسخ‌گویی خودکار برای همه گفتگوها متوقف شد.")

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global paused
    if OWNER_CHAT_ID and str(update.effective_chat.id) == OWNER_CHAT_ID:
        paused = False
        await update.message.reply_text("پاسخ‌گویی خودکار دوباره فعال شد.")

async def reply_to_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global paused
    message = update.effective_message
    chat = update.effective_chat

    # فقط چت خصوصی؛ هیچ پاسخی در گروه‌ها ارسال نمی‌شود.
    if not message or not chat or chat.type != ChatType.PRIVATE or not message.text:
        return
    if paused or chat.id in disabled_chats:
        return

    try:
        await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)
        history = histories[chat.id]
        history.append({"role": "user", "content": message.text})

        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, *list(history)],
            temperature=0.75,
            max_tokens=450,
        )
        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            answer = "ببخشید، الان نتونستم پاسخ مناسبی آماده کنم. کمی بعد دوباره پیام بده."
        history.append({"role": "assistant", "content": answer})
        await message.reply_text(answer)
    except Exception:
        logger.exception("خطا در پاسخ‌گویی")
        await message.reply_text(
            "ببخشید، الان در پاسخ‌گویی مشکلی پیش اومده. لطفاً کمی بعد دوباره پیام بده."
        )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("pause", pause))
    app.add_handler(CommandHandler("resume", resume))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, reply_to_message))
    logger.info("ربات فعال شد و فقط به پیام‌های خصوصی پاسخ می‌دهد.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
