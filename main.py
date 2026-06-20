import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(name)

client = Groq(api_key=os.environ["GROQ_API_KEY"])
STABILITY_KEY = os.environ["STABILITY_API_KEY"]
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
    await update.message.reply_text(
        "سلام! 👋 من یک دستیار هوشمند هستم.\n\n"
        "💬 هر سوالی داری بپرس!\n"
        "🖼 برای ادیت عکس: /editphoto\n"
        "/clear - پاک کردن تاریخچه"
    )

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_histories[update.effective_user.id] = []
    await update.message.reply_text("✅ تاریخچه پاک شد!")

async def editphoto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_waiting_for_image[user_id] = "waiting_photo"
    await update.message.reply_text("🖼 عکسی که میخوای ادیت بشه رو بفرست!")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_waiting_for_image.get(user_id) == "waiting_photo":
        user_waiting_for_image[user_id] = "waiting_prompt"
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        context.user_data["photo_url"] = file.file_path
        await update.message.reply_text("✏️ حالا بنویس چه تغییری میخوای؟\nمثال: پس‌زمینه رو آبی کن")
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
        photo_url = context.user_data.get("photo_url")
        await update.message.reply_text("⏳ داره ادیت میشه...")
        try:
            img_response = requests.get(photo_url)
            response = requests.post(
                "https://api.stability.ai/v2beta/stable-image/edit/search-and-replace",
                headers={"authorization": f"Bearer {STABILITY_KEY}", "accept": "image/*"},
                files={"image": ("image.png", img_response.content, "image/png")},
                data={"prompt": user_text, "output_format": "png"},
            )
            if response.status_code == 200:
                await update.message.reply_photo(photo=response.content, caption="✅ عکس ادیت شد!")
