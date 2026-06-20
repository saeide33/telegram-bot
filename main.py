import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import anthropic

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

user_histories = {}

SYSTEM_PROMPT = """تو یک دستیار هوشمند فارسی‌زبان هستی. 
به سوالات کاربران با دقت و مهربانی پاسخ می‌دهی.
پاسخ‌هایت را به فارسی روان و قابل فهم بنویس."""

MAX_HISTORY = 20

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text(
        "سلام! 👋 من یک دستیار هوشمند هستم.\n"
        "هر سوالی داری بپرس!\n\n"
        "دستورات:\n"
        "/start - شروع مجدد\n"
        "/clear - پاک کردن تاریخچه مکالمه"
    )

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text("✅ تاریخچه مکالمه پاک شد!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    if user_id not in user_histories:
        user_histories[user_id] = []
    user_histories[user_id].append({"role": "user", "content": user_text})
    if len(user_histories[user_id]) > MAX_HISTORY:
        user_histories[user_id] = user_histories[user_id][-MAX_HISTORY:]
    try:
        response = claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=user_histories[user_id],
        )
        assistant_reply = response.content[0].text
        user_histories[user_id].append({"role": "assistant", "content": assistant_reply})
        await update.message.reply_text(assistant_reply)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ خطایی پیش اومد. دوباره امتحان کن.")

def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN تنظیم نشده!")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY تنظیم نشده!")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("ربات شروع به کار کرد...")
    app.run_polling()

if __name__ == "__main__":
    main()
