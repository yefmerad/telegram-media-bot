import json, os
from datetime import date
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# ================= CONFIG =================
BOT_TOKEN = os.getenv("8535583017:AAEy8kNpo9499hQs78ktO7w8L-M56V597ak")
ADMINS = [6520104201]# Replace with your Telegram ID(s)

PROGRAMS_FILE = "program_images.json"
USERS_FILE = "users.json"

# ================= LOAD / SAVE =================
def load(file, default):
    if not os.path.exists(file):
        return default
    with open(file, "r") as f:
        return json.load(f)

def save(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

PROGRAMS = load(PROGRAMS_FILE, {})
USERS = load(USERS_FILE, {})
STATE = {}

# ================= KEYBOARDS =================
def main_menu_keyboard(is_admin=False):
    buttons = [[KeyboardButton(p.title())] for p in PROGRAMS]

    if is_admin:
        buttons.extend([
            [KeyboardButton("📤 Upload Media")],
            [KeyboardButton("🗑 Delete Media")],
            [KeyboardButton("❌ Delete Program")]
        ])

    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def back_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("🔙 Back")]], resize_keyboard=True)

def confirm_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("✅ YES DELETE")], [KeyboardButton("❌ CANCEL")]],
        resize_keyboard=True
    )

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    is_admin = update.effective_user.id in ADMINS

    # register user for notifications
    USERS[uid] = True
    save(USERS_FILE, USERS)

    STATE[uid] = "MAIN"
    await update.message.reply_text(
        "🏠 Main Menu\n📸 Please choose which program’s photos you want to see 👇",
        reply_markup=main_menu_keyboard(is_admin)
    )

# ================= TEXT HANDLER =================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    text = update.message.text.strip()
    lower = text.lower().replace(" ", "")
    is_admin = update.effective_user.id in ADMINS

    # ===== BACK =====
    if text == "🔙 Back":
        STATE[uid] = "MAIN"
        await update.message.reply_text(
            "🏠 Main Menu",
            reply_markup=main_menu_keyboard(is_admin)
        )
        return

    # ===== ADMIN: UPLOAD MEDIA =====
    if text == "📤 Upload Media" and is_admin:
        STATE[uid] = "UPLOAD_SELECT_PROGRAM"
        await update.message.reply_text(
            "📸 Select a program to upload media:",
            reply_markup=main_menu_keyboard(True)
        )
        return

    if STATE.get(uid) == "UPLOAD_SELECT_PROGRAM" and is_admin:
        if lower not in PROGRAMS:
            await update.message.reply_text("⚠️ Invalid program.")
            return
        STATE[uid] = f"UPLOAD_{lower}"
        await update.message.reply_text(
            f"📤 Now send photos/videos for *{text.title()}*",
            reply_markup=back_keyboard(),
            parse_mode="Markdown"
        )
        return

    # ===== VIEW PROGRAM =====
    if lower in PROGRAMS:
        events = PROGRAMS[lower]
        if not events:
            await update.message.reply_text("📭 No media yet.", reply_markup=back_keyboard())
            return
        msg = "📅 Select an event/date:\n\n"
        for e in events:
            msg += f"• {e['title']}\n"
        STATE[uid] = f"SELECT_DATE_{lower}"
        await update.message.reply_text(msg, reply_markup=back_keyboard())
        return

    # ===== SELECT DATE =====
    if STATE.get(uid, "").startswith("SELECT_DATE_"):
        program = STATE[uid].replace("SELECT_DATE_", "")
        for e in PROGRAMS[program]:
            if text == e["title"]:
                for m in e["media"]:
                    if m["type"] == "photo":
                        await update.message.reply_photo(m["id"])
                    else:
                        await update.message.reply_video(m["id"])
                await update.message.reply_text("⬅️ Back", reply_markup=back_keyboard())
                return
        await update.message.reply_text("⚠️ Invalid selection.")

# ================= MEDIA UPLOAD =================
async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if update.effective_user.id not in ADMINS:
        return

    state = STATE.get(uid, "")
    if not state.startswith("UPLOAD_"):
        return

    program = state.replace("UPLOAD_", "")
    today = date.today().isoformat()
    event_title = f"Photos {today}"

    # find or create event
    event = next((e for e in PROGRAMS[program] if e["title"] == event_title), None)
    if not event:
        event = {
            "date": today,
            "title": event_title,
            "media": [],
            "notified": False
        }
        PROGRAMS[program].append(event)

    # save media
    if update.message.photo:
        event["media"].append({
            "type": "photo",
            "id": update.message.photo[-1].file_id
        })
    elif update.message.video:
        event["media"].append({
            "type": "video",
            "id": update.message.video.file_id
        })

    save(PROGRAMS_FILE, PROGRAMS)

    # ===== NOTIFY STUDENTS (ONCE PER EVENT) =====
    if not event["notified"]:
        for user_id in USERS:
            if int(user_id) in ADMINS:
                continue
            try:
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=(
                        "📸✨ *New Photos Uploaded!*\n\n"
                        f"📌 Program: *{program.title()}*\n"
                        f"📅 Event: *{event_title}*\n\n"
                        "👉 Open the bot to view them"
                    ),
                    parse_mode="Markdown"
                )
            except:
                pass

        event["notified"] = True
        save(PROGRAMS_FILE, PROGRAMS)

    await update.message.reply_text("✅ Media saved.", reply_markup=back_keyboard())

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, media_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
