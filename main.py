import os
import logging
import requests
import base64
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

client = Groq(api_key=os.environ["GROQ_API_KEY"])
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
ADMIN_ID = 8334444877
ADMIN_CODE = "532014"
user_histories = {}
user_waiting_for_image = {}
all_messages = []
MAX_HISTORY = 20
SYSTEM_PROMPT = "تو یک دستیار هوشمند فارسی‌زبان هستی. به سوالات کاربران با دقت و مهربانی پاسخ می‌دهی."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_histories[update.effective_user.id] = []
    user = update.effective_user
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"👤 کاربر جدید!\nاسم: {user.full_name}\nیوزرنیم: @{user.username}\nآیدی: {user.id}")
    await update.message.reply_text("سلام! 👋 من یک دستیار هوشمند هستم.\nهر سوالی داری بپرس!\n\n🖼 ادیت عکس: /editphoto\n/clear - پاک کردن تاریخچه")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_histories[update.effective_user.id] = []
    await update.message.reply_text("✅ تاریخچه پاک شد!")

async def editphoto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_waiting_for_image[update.effective_user.id] = "waiting_photo"
    await update.message.reply_text("🖼 عکست رو بفرست!")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_waiting_for_image.get(user_id) == "waiting_photo":
        user_waiting_for_image[user_id] = "waiting_prompt"
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        img_data = await file.download_as_bytearray()
        context.user_data["photo_bytes"] = bytes(img_data)
        await update.message.reply_text("✏️ چه تغییری میخوای؟\nمثال: پس‌زمینه رو آبی کن")
    else:
        await update.message.reply_text("برای ادیت عکس از /editphoto استفاده کن!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = update.effective_user
    user_text = update.message.text
    if user_text == ADMIN_CODE and user_id == ADMIN_ID:
        if not all_messages:
            await update.message.reply_text("📭 هنوز پیامی نیست!")
            return
        text = "📋 آخرین پیام‌های کاربران:\n\n"
        for msg in all_messages[-20:]:
            text += f"👤 {msg['name']} (@{msg['username']}):\n💬 {msg['text']}\n\n"
        await update.message.reply_text(text)
        return
    all_messages.append({"name": user.full_name, "username": user.username, "text": user_text})
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"💬 پیام جدید!\nاز: {user.full_name} (@{user.username})\nپیام: {user_text}")
    if user_waiting_for_image.get(user_id) == "waiting_prompt":
        user_waiting_for_image.pop(user_id)
        photo_bytes = context.user_data.get("photo_bytes")
        await update.message.reply_text("⏳ داره ادیت میشه...")
        try:
            img_b64 = base64.b64encode(photo_bytes).decode()
            payload = {"contents": [{"parts": [{"text": f"این عکس رو ادیت کن: {user_text}. فقط عکس خروجی بده."}, {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}]}], "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}}
            response = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp-image-generation:generateContent?key={GEMINI_KEY}", json=payload)
            result = response.json()
            if "candidates" in result:
                for part in result["candidates"][0]["content"]["parts"]:
                    if "inlineData" in part:
                        img_bytes = base64.b64decode(part["inlineData"]["data"])
                        await update.message.reply_photo(photo=img_bytes, caption="✅ عکس ادیت شد!")
                        return
            await update.message.reply_text("❌ خطا در ادیت عکس.")
        except Exception as e:
            logger.error(f"Error: {e}")
            await update.message.reply_text("❌ خطایی پیش اومد.")
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    if user_id not in user_histories:
        user_histories[user_id] = []
    user_histories[user_id].append({"role": "user", "content": user_text})
    if len(user_histories[user_id]) > MAX_HISTORY:
        user_histories[user_id] = user_histories[user_id][-MAX_HISTORY:]
    try:
        response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": SYSTEM_PROMPT}] + user_histories[user_id], max_tokens=1024)
        reply = response.choices[0].message.content
        user_histories[user_id].append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ خطایی پیش اومد.")

def main():
    app = ApplicationBuilder().token(os.environ["TELEGRAM_TOKEN"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("editphoto", editphoto))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("ربات شروع به کار کرد...")
    app.run_polling()

if __name__ == "__main__":
    main()
