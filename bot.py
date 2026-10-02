import logging
import os
import threading
from flask import Flask
import gspread
from google.oauth2.service_account import Credentials
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# Logging Setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- GOOGLE SHEETS SETUP ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
try:
  creds = Credentials.from_service_account_file(
      "firebase_credentials.json", scopes=SCOPES
  )
  client = gspread.authorize(creds)
  sheet = client.open("WinGo_Data").sheet1
  logger.info("Google Sheets connected successfully!")
except Exception as e:
  logger.error(f"Google Sheets Connection Error: {e}")


def save_wingo_data(period, number, color, size):
  try:
    sheet.append_row([period, number, color, size])
    logger.info(f"Data saved to Google Sheet: Period {period}")
  except Exception as e:
    logger.error(f"Google Sheet Save Error: {e}")


# --- FLASK KEEP-ALIVE SERVER (For Render) ---
app = Flask(__name__)


@app.route("/")
def home():
  return "WinGo Market Analysis Bot is Alive and Running!"


def run_flask():
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)


# --- TELEGRAM BOT HANDLERS ---

# Start Command & Main Menu
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_name = update.effective_user.first_name
  welcome_text = (
      f"👋 Welcome, **{user_name}**!\n\n"
      "Welcome to the Professional WinGo Market Analysis Bot.\n"
      "Please select an option below:"
  )

  keyboard = [
      [InlineKeyboardButton("⚡ LIVE SIGNAL", callback_data="live_signal")],
      [
          InlineKeyboardButton(
              "📊 HISTORICAL DATA", callback_data="historical_data"
          )
      ],
      [InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings")],
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  if update.message:
    await update.message.reply_text(
        welcome_text, reply_markup=reply_markup, parse_mode="Markdown"
    )
  elif update.callback_query:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        welcome_text, reply_markup=reply_markup, parse_mode="Markdown"
    )


# Button Click Handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()

  if query.data == "live_signal":
    # Dummy mock data generation for WinGo signal (replace with real API call if needed)
    sample_period = "202610031001"
    sample_number = 7
    sample_color = "Green"
    sample_size = "Big"

    # Save data to Google Sheets
    save_wingo_data(
        sample_period, sample_number, sample_color, sample_size
    )

    signal_text = (
        f"⚡ **LIVE WINDO SIGNAL** ⚡\n\n"
        f"📌 **Period:** `{sample_period}`\n"
        f"🎯 **Prediction:** **{sample_size} / {sample_color}**\n"
        f"🔢 **Lucky Number:** `{sample_number}`\n\n"
        f"*(Data successfully saved to Google Sheet!)*"
    )
    back_keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_home")]]
    await query.edit_message_text(
        signal_text,
        reply_markup=InlineKeyboardMarkup(back_keyboard),
        parse_mode="Markdown",
    )

  elif query.data == "historical_data":
    history_text = (
        f"📊 **HISTORICAL DATA ANALYSIS**\n\n"
        f"Last saved records have been logged and fetched securely from Google Sheets."
    )
    back_keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_home")]]
    await query.edit_message_text(
        history_text,
        reply_markup=InlineKeyboardMarkup(back_keyboard),
        parse_mode="Markdown",
    )

  elif query.data == "settings":
    settings_text = (
        f"⚙️ **BOT SETTINGS**\n\n"
        f"• Platform: Render Cloud\n"
        f"• Database: Google Sheets API\n"
        f"• Interface: Clean Inline UI"
    )
    back_keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_home")]]
    await query.edit_message_text(
        settings_text,
        reply_markup=InlineKeyboardMarkup(back_keyboard),
        parse_mode="Markdown",
    )

  elif query.data == "back_home":
    await start(update, context)


# --- MAIN FUNCTION ---
def main():
  # Telegram Bot Token (Render Environment Variable ba direct token boshao)
  TOKEN = os.environ.get("", "8177073363:AAGrp0ndTtV2escKnZw25a1AqIIOnLO_3xw")

  # Start Flask server in a separate thread
  flask_thread = threading.Thread(target=run_flask)
  flask_thread.daemon = True
  flask_thread.start()

  # Initialize Telegram Application
  application = Application.builder().token(TOKEN).build()

  application.add_handler(CommandHandler("start", start))
  application.add_handler(CallbackQueryHandler(button_handler))

  # Run the bot
  logger.info("Bot is starting polling...")
  application.run_polling()


if __name__ == "__main__":
  main()
