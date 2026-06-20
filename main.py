 پیام
    all_messages.append({
        "name": user.full_name,
        "username": user.username,
        "text": user_text
    })

    await context.bot.send_message(chat_id=ADMIN_ID, text=f"💬 پیام جدید!\nاز: {user.full_name} (@{user.username})\nپیام: {user_text}")

    if user_waiting_for_image.get(user_id) == "waiting_prompt":
        user_waiting_for_image.pop(user_id)
        photo_url = context.user_data.get("photo_url")
        await update.message.reply_text("⏳ داره ادیت میشه...")
        try:
            img_response = requests.get(photo_url)
            response = requests.post(
                "https://api.stability.ai/v2beta/stable-image/edit/inpaint",
                headers={"authorization": f"Bearer {STABILITY_KEY}", "accept": "image/*"},
                files={"image": ("image.png", img_response.content, "image/png"), "none": ""},
                data={"prompt": user_text, "output_format": "png"},
            )
            if response.status_code == 200:
                await update.message.reply_photo(photo=response.content, caption="✅ عکس ادیت شد!")
            else:
                await update.message.reply_text("❌ خطا در ادیت عکس.")
        except Exception as e:
            logger.error(f"Image edit error: {e}")
            await update.message.reply_text("❌ خطایی پیش اومد.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    if user_id not in user_histories:
        user_histories[user_id] = []
    user_histories[user_id].append({"role": "user", "content": user_text})
    if len(user_histories[user_id]) > MAX_HISTORY:
        user_histories[user_id] = user_histories[user_id][-MAX_HISTORY:]
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + user_histories[user_id],
            max_tokens=1024,
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
    app.add_handler(CommandHandler("editphoto", editphoto))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("ربات شروع به کار کرد...")
    app.run_polling()

if __name__ == "__main__":
    main()

