import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN, CHANNEL_ID, CHANNEL_USERNAME, PREMIUM_USERS
from db import save_file, get_file, delete_file, increment_views, get_expired
from utils import generate_token, hash_password, get_expiry

user_state = {}


# 🔒 Check subscription
async def check_sub(update, context):
    try:
        member = await context.bot.get_chat_member(
            CHANNEL_USERNAME, update.effective_user.id
        )
        return member.status in ["member", "administrator", "creator"]
    except:
        return False


# 🚀 Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    if args:
        token = args[0]
        data = get_file(token)

        if not data:
            return await update.message.reply_text("❌ File not found")

        token, msg_id, password, expiry, views, one_time = data

        if expiry and time.time() > expiry:
            return await update.message.reply_text("⏳ Link expired")

        if password:
            user_state[update.effective_user.id] = ("verify", token)
            return await update.message.reply_text("🔐 Enter password:")

        increment_views(token)

        await context.bot.copy_message(
            chat_id=update.effective_chat.id,
            from_chat_id=CHANNEL_ID,
            message_id=msg_id
        )

        if one_time:
            delete_file(token)

        return

    if not await check_sub(update, context):
        buttons = [
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton("✅ I Joined", callback_data="check_sub")]
        ]
        return await update.message.reply_text(
            "🔒 Join our channel to use the bot",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    await update.message.reply_text("📤 Send a file to generate link")


# 📦 Handle file
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_sub(update, context):
        return await start(update, context)

    sent = await context.bot.copy_message(
        chat_id=CHANNEL_ID,
        from_chat_id=update.message.chat_id,
        message_id=update.message.message_id
    )

    msg_id = sent.message_id

    user_state[update.effective_user.id] = ("ask_password", msg_id)

    buttons = [
        [
            InlineKeyboardButton("🔐 Password", callback_data="set_pass"),
            InlineKeyboardButton("⏭ Skip", callback_data="skip_pass")
        ]
    ]

    await update.message.reply_text(
        "🔐 Protect this file?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# 🎛️ Buttons
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "check_sub":
        if await check_sub(update, context):
            return await query.message.edit_text("✅ Send file now")
        else:
            return await query.answer("❌ Not joined", show_alert=True)

    if query.data in ["set_pass", "skip_pass"]:
        state, msg_id = user_state[user_id]

        if query.data == "set_pass":
            user_state[user_id] = ("set_password", msg_id)
            return await query.message.edit_text("🔐 Send password")
        else:
            user_state[user_id] = ("set_expiry", (msg_id, None, 0))
            return await send_expiry_buttons(query)

    if query.data == "one_time":
        msg_id, password, _ = user_state[user_id][1]
        user_state[user_id] = ("set_expiry", (msg_id, password, 1))
        return await send_expiry_buttons(query)

    if query.data.startswith("exp_"):
        msg_id, password, one_time = user_state[user_id][1]

        if user_id not in PREMIUM_USERS:
            expiry = get_expiry(3600)
        else:
            expiry = {
                "exp_10": 600,
                "exp_1h": 3600,
                "exp_1d": 86400
            }.get(query.data, 3600)
            expiry = get_expiry(expiry)

        token = generate_token()
        save_file(token, msg_id, password, expiry, one_time)

        link = f"https://t.me/{context.bot.username}?start={token}"

        await query.message.edit_text(f"🔗 {link}")
        del user_state[user_id]


# ⏳ Expiry UI
async def send_expiry_buttons(query):
    buttons = [
        [
            InlineKeyboardButton("⏳ 10m", callback_data="exp_10"),
            InlineKeyboardButton("⏳ 1h", callback_data="exp_1h"),
        ],
        [
            InlineKeyboardButton("⏳ 1d", callback_data="exp_1d"),
            InlineKeyboardButton("🔥 One-time", callback_data="one_time")
        ]
    ]

    await query.message.edit_text(
        "⏳ Select expiry:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# 🔐 Password + verify
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_state:
        return

    state, data = user_state[user_id]

    if state == "set_password":
        msg_id = data
        password = hash_password(update.message.text)

        user_state[user_id] = ("set_expiry", (msg_id, password, 0))

        await update.message.reply_text("⏳ Choose expiry")
        return await send_expiry_buttons(update)

    if state == "verify":
        token = data
        db_data = get_file(token)

        if not db_data:
            return await update.message.reply_text("❌ Invalid")

        token, msg_id, password, expiry, views, one_time = db_data

        if hash_password(update.message.text) == password:
            increment_views(token)

            await context.bot.copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=CHANNEL_ID,
                message_id=msg_id
            )

            if one_time:
                delete_file(token)
        else:
            await update.message.reply_text("❌ Wrong password")


# 🧹 Cleanup
async def cleanup(context):
    now = int(time.time())
    rows = get_expired(now)

    for token, msg_id in rows:
        try:
            await context.bot.delete_message(CHANNEL_ID, msg_id)
        except:
            pass
        delete_file(token)


# 📖 Help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📖 Send file → get secure link")


# ℹ️ About
async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔐 LinksyraBot - Secure sharing")


# 🚀 Main
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about))

    app.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.PHOTO, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.add_handler(CallbackQueryHandler(button_handler))

    app.job_queue.run_repeating(cleanup, interval=300)

    print("🚀 PRO BOT RUNNING")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()        token = args[0]
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

    # Force subscribe
    if not await check_sub(update, context):
        buttons = [
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton("✅ I Joined", callback_data="check_sub")]
        ]

        await update.message.reply_text(
            "🔒 You must join our channel to use this bot.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    await update.message.reply_text("📤 Send me a file to begin")


# 📦 Handle file
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_sub(update, context):
        return await start(update, context)

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

    user_state[update.effective_user.id] = ("ask_password", file_id)

    buttons = [
        [
            InlineKeyboardButton("🔐 Set Password", callback_data="set_pass"),
            InlineKeyboardButton("⏭ Skip", callback_data="skip_pass")
        ]
    ]

    await msg.reply_text(
        "🔐 Do you want to protect this file?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# 🎛️ Button handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    # Check subscription button
    if query.data == "check_sub":
        if await check_sub(update, context):
            await query.message.edit_text("✅ You can now use the bot!\n📤 Send a file")
        else:
            await query.answer("❌ Still not joined!", show_alert=True)

    # Password choice
    elif query.data in ["set_pass", "skip_pass"]:
        state, file_id = user_state.get(user_id, (None, None))

        if query.data == "set_pass":
            user_state[user_id] = ("set_password", file_id)
            await query.message.edit_text("🔐 Send your password")
        else:
            user_state[user_id] = ("set_expiry", (file_id, None))
            await send_expiry_buttons(query)

    # Expiry selection
    elif query.data.startswith("exp_"):
        file_id, password = user_state[user_id][1]

        if query.data == "exp_10":
            expiry = get_expiry(600)
        elif query.data == "exp_1h":
            expiry = get_expiry(3600)
        else:
            expiry = get_expiry(86400)

        token = generate_token()
        save_file(token, file_id, password, expiry)

        link = f"https://t.me/{context.bot.username}?start={token}"

        await query.message.edit_text(
            f"🔗 Your Link:\n{link}\n⏳ Expiry set!"
        )

        del user_state[user_id]


# ⏳ Expiry buttons
async def send_expiry_buttons(query):
    buttons = [
        [
            InlineKeyboardButton("⏳ 10 min", callback_data="exp_10"),
            InlineKeyboardButton("⏳ 1 hour", callback_data="exp_1h"),
        ],
        [
            InlineKeyboardButton("⏳ 1 day", callback_data="exp_1d")
        ]
    ]

    await query.message.edit_text(
        "⏳ Select expiry time:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# 🔐 Handle text (password + verify)
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in user_state:
        return

    state, data = user_state[user_id]

    # Set password
    if state == "set_password":
        file_id = data
        password = hash_password(text)

        user_state[user_id] = ("set_expiry", (file_id, password))

        await update.message.reply_text("⏳ Choose expiry time:")
        await send_expiry_buttons(update)

    # Verify password
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


# ℹ️ About
async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔐 *LinksyraBot*\n\n"
        "A smart file sharing bot designed for privacy and control.\n\n"
        "✨ Features:\n"
        "• Secure link generation\n"
        "• Password protection\n"
        "• Expiry-based access\n"
        "• Fast Telegram delivery\n\n"
        "Built for creators & power users 🚀",
        parse_mode="Markdown"
    )


# 📖 Help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *How to use LinksyraBot*\n\n"
        "1️⃣ Send any file\n"
        "2️⃣ Choose password option\n"
        "3️⃣ Select expiry time\n"
        "4️⃣ Get your secure link 🔗\n\n"
        "Simple & secure 🚀",
        parse_mode="Markdown"
    )


# 🚀 Main
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("help", help_command))

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

    app.add_handler(CallbackQueryHandler(button_handler))

    print("✅ Bot running...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()            await update.message.reply_text("🔐 Enter password:")
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
