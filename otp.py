from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import pyotp
import asyncio
import os
import json
import firebase_admin
from firebase_admin import credentials, db

# ------------------ CONFIG ------------------

BOT_TOKEN = os.getenv("BOT_TOKEN")
INTERVAL = 20

# ------------------ FIREBASE SETUP ------------------

firebase_key = json.loads(os.getenv("FIREBASE_KEY"))

cred = credentials.Certificate(firebase_key)

firebase_admin.initialize_app(cred, {
    "databaseURL": "https://secret-50385.firebaseio.com/"
})

# ------------------ LOAD / SAVE ------------------

def load_data():
    data = db.reference("users").get()
    return data if data else {}

def save_data(data):
    db.reference("users").set(data)

user_data = load_data()

# ------------------ START ------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send a secret → I'll generate OTP and refresh every 20s\n\n"
        "/save name → save secret\n"
        "/otp name → get OTP\n"
        "/list → show saved\n"
        "/delete name → delete"
    )

# ------------------ BACKGROUND REFRESH ------------------

async def refresh_otp(msg, totp):
    while True:
        await asyncio.sleep(INTERVAL)
        otp = totp.now()
        try:
            await msg.edit_text(
                f"🔑 OTP: `{otp}`\n⏱️ Refreshing every {INTERVAL}s",
                parse_mode="Markdown"
            )
        except:
            break

# ------------------ RECEIVE SECRET ------------------

async def receive_secret(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global user_data

    user_id = str(update.effective_user.id)
    secret = update.message.text.strip()

    if user_id not in user_data:
        user_data[user_id] = {}

    user_data[user_id]["temp_secret"] = secret

    try:
        totp = pyotp.TOTP(secret, interval=INTERVAL)
        otp = totp.now()

        msg = await update.message.reply_text(
            f"🔑 OTP: `{otp}`\n⏱️ Refreshing every {INTERVAL}s",
            parse_mode="Markdown"
        )

        asyncio.create_task(refresh_otp(msg, totp))

    except Exception:
        await update.message.reply_text("❌ Invalid secret!")

# ------------------ SAVE ------------------

async def save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global user_data

    user_id = str(update.effective_user.id)

    if user_id not in user_data or "temp_secret" not in user_data[user_id]:
        await update.message.reply_text("❌ Send a secret first")
        return

    if len(context.args) == 0:
        await update.message.reply_text("❌ Usage: /save name")
        return

    name = context.args[0]
    secret = user_data[user_id]["temp_secret"]

    if "secrets" not in user_data[user_id]:
        user_data[user_id]["secrets"] = {}

    if name in user_data[user_id]["secrets"]:
        await update.message.reply_text("⚠️ Name exists, overwriting...")

    user_data[user_id]["secrets"][name] = secret

    del user_data[user_id]["temp_secret"]

    save_data(user_data)

    await update.message.reply_text(f"✅ Saved as '{name}'")

# ------------------ OTP ------------------

async def otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if len(context.args) == 0:
        await update.message.reply_text("❌ Usage: /otp name")
        return

    name = context.args[0]

    try:
        secret = user_data[user_id]["secrets"][name]
    except:
        await update.message.reply_text("❌ Name not found")
        return

    totp = pyotp.TOTP(secret, interval=INTERVAL)
    otp = totp.now()

    await update.message.reply_text(
        f"🔑 OTP ({name}): `{otp}`",
        parse_mode="Markdown"
    )

# ------------------ LIST ------------------

async def list_secrets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id not in user_data or "secrets" not in user_data[user_id] or not user_data[user_id]["secrets"]:
        await update.message.reply_text("❌ No saved secrets")
        return

    names = list(user_data[user_id]["secrets"].keys())

    await update.message.reply_text(
        "📂 Saved:\n" + "\n".join(names)
    )

# ------------------ DELETE ------------------

async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global user_data

    user_id = str(update.effective_user.id)

    if len(context.args) == 0:
        await update.message.reply_text("❌ Usage: /delete name")
        return

    name = context.args[0]

    try:
        del user_data[user_id]["secrets"][name]
        save_data(user_data)
        await update.message.reply_text(f"🗑️ '{name}' deleted")
    except:
        await update.message.reply_text("❌ Name not found")

# ------------------ RUN ------------------

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("save", save))
app.add_handler(CommandHandler("otp", otp))
app.add_handler(CommandHandler("list", list_secrets))
app.add_handler(CommandHandler("delete", delete))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_secret))

print("Bot running...")
app.run_polling()