import os
import logging
import requests
import base64
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
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
    keyboard = [[InlineKeyboardButton("🖼 ادیت عکس", callback_data="editphoto"), InlineKeyboardButton("👗 عوض کردن لباس", callback_data="changecloth")], [InlineKeyboardButton("⚽ پیش‌بینی مسابقات", callback_data="predict"), InlineKeyboardButton("💬 چت هوشمند", callback_data="chat")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("سلام! 👋 من یک دستیار هوشمند هستم.\nیکی از گزینه‌ها رو انتخاب کن:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data == "editphoto":
        user_waiting_for_image[user_id] = "edit_waiting_photo"
        await query.message.reply_text("🖼 عکست رو بفرست تا ادیت کنم!")
    elif query.data == "changecloth":
        user_waiting_for_image[user_id] = "cloth_waiting_photo"
        await query.message.reply_text("👗 عکست رو بفرست تا لباست رو عوض کنم!")
    elif query.data == "predict":
        await query.message.reply_text("⚽ اسم تیم‌ها یا مسابقه‌ای که میخوای پیش‌بینی بشه رو بنویس!\nمثال: رئال مادرید vs بارسلونا")
    elif query.data == "chat":
        await query.message.reply_text("💬 هر سوالی داری بپرس!")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_histories[update.effective_user.id] = []
    await update.message.reply_text("✅ تاریخچه پاک شد!")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_waiting_for_image.get(user_id)
    if state in ["edit_waiting_photo", "cloth_waiting_photo"]:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        img_data = await file.download_as_bytearray()
        context.user_data["photo_bytes"] = bytes(img_data)
        if state == "edit_waiting_photo":
            user_waiting_for_image[user_id] = "edit_waiting_prompt"
            await update.message.reply_text("✏️ چه تغییری میخوای؟\nمثال: پس‌زمینه رو آبی کن")
        elif state == "cloth_waiting_photo":
            user_waiting_for_image[user_id] = "cloth_waiting_prompt"
            await update.message.reply_text("👗 چه لباسی میخوای؟\nمثال: یه پیراهن قرمز رسمی")
    else:
        await update.message.reply_text("برای ادیت عکس از منو استفاده کن! /start")

async def edit_with_gemini(photo_bytes, prompt):
    img_b64 = base64.b64encode(photo_bytes).decode()
    payload = {
        "contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}]}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}
    }
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-preview-image-generation:generateContent?key={GEMINI_KEY}",
        json=payload
    )
    result = response.json()
    if "candidates" in result:
        for part in result["candidates"][0]["content"]["parts"]:
            if "inlineData" in part:
                return base64.b64decode(part["inlineData"]["data"])
    return None

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

    state = user_waiting_for_image.get(user_id)

    if state == "edit_waiting_prompt":
        user_waiting_for_image.pop(user_id)
        await update.message.reply_text("⏳ داره ادیت میشه...")
        try:
            img = await edit_with_gemini(context.user_data["photo_bytes"], f"این عکس رو ادیت کن: {user_text}")
            if img:
                await update.message.reply_photo(photo=img, caption="✅ عکس ادیت شد!")
            else:
                await update.message.reply_text("❌ خطا در ادیت عکس.")
        except Exception as e:
            logger.error(f"Error: {e}")
            await update.message.reply_text("❌ خطایی پیش اومد.")
        return

    if state == "cloth_waiting_prompt":
        user_waiting_for_image.pop(user_id)
        await update.message.reply_text("⏳ داره لباس عوض میشه...")
        try:
            prompt = f"لباس شخص توی عکس رو عوض کن و بهش بپوشون: {user_text}. چهره و بدن رو دست نزن."
            img = await edit_with_gemini(context.user_data["photo_bytes"], prompt)
            if img:
                await update.message.reply_photo(photo=img, caption="✅ لباس عوض شد!")
            else:
                await update.message.reply_text("❌ خطا در عوض کردن لباس.")
        except Exception as e:
            logger.error(f"Error: {e}")
            await update.message.reply_text("❌ خطایی پیش اومد.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    if user_id not in user_histories:
        user_histories[user_id] = []

    is_predict = any(word in user_text.lower() for word in ["vs", "پیش‌بینی", "پیش بینی", "مسابقه", "بازی", "فینال", "لیگ"])
    if is_predict:
        predict_prompt = f"یک پیش‌بینی دقیق و حرفه‌ای برای این مسابقه بده: {user_text}. آمار، فرم تیم‌ها، و احتمال برد هر طرف رو بگو. به فارسی جواب بده."
        user_histories[user_id].append({"role": "user", "content": predict_prompt})
    else:
        user_histories[user_id].append({"role": "user", "content": user_text})

    if len(user_histories[user_id]) > MAX_HISTORY:
        user_histories[user_id] = user_histories[user_id][-MAX_HISTORY:]
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + user_histories[user_id],
            max_tokens=1024
        )
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
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("ربات شروع به کار کرد...")
    app.run_polling()

if __name__ == "__main__":
    main()
