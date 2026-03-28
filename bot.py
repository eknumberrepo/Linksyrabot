import time
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN
from db import save_file, get_file
from utils import generate_token, hash_password, get_expiry

user_state = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    if args:
        token = args[0]
        data = get_file(token)

        if not data:
            await update.message.reply_text("❌ File not found")
            return

        _, file_id, password, expiry = data

        if expiry and time.time() > expiry:
            await update.message.reply_text("⏳ Link expired")
            return

        if password:
            user_state[update.effective_user.id] = ("verify", token)
            await update.message.reply_text("🔐 Enter password:")
            return

        await update.message.reply_document(file_id)
        return

    await update.message.reply_text(
        "👋 Send me a file to generate secure link 🔗"
    )


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    if msg.document:
        file = msg.document
    elif msg.video:
        file = msg.video
    elif msg.photo:
        file = msg.photo[-1]
    else:
        return

    file_id = file.file_id

    user_state[update.effective_user.id] = ("set_password", file_id)
    await msg.reply_text("🔐 Send password or type 'skip'")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in user_state:
        return

    state, data = user_state[user_id]

    if state == "set_password":
        file_id = data

        password = None if text.lower() == "skip" else hash_password(text)

        token = generate_token()
        expiry = get_expiry(3600)  # 1 hour

        save_file(token, file_id, password, expiry)

        link = f"https://t.me/{context.bot.username}?start={token}"

        await update.message.reply_text(
            f"🔗 Link:\n{link}\n⏳ Expires in 1 hour"
        )

        del user_state[user_id]

    elif state == "verify":
        token = data
        db_data = get_file(token)

        if not db_data:
            await update.message.reply_text("❌ Invalid link")
            return

        _, file_id, password, expiry = db_data

        if expiry and time.time() > expiry:
            await update.message.reply_text("⏳ Link expired")
            return

        if hash_password(text) == password:
            await update.message.reply_document(file_id)
        else:
            await update.message.reply_text("❌ Wrong password")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(
            filters.Document.ALL | filters.VIDEO | filters.PHOTO,
            handle_file
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text
        )
    )

    print("✅ Bot running...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
