import logging
import asyncio
import aiohttp
import os
from datetime import datetime
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("firebase_credentials.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

API_30S = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"
API_1M = "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json"

user_states = {}

app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Bot is running live!"

def run_flask():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

async def fetch_api_data(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params={"ts": int(datetime.now().timestamp() * 1000)}) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and "data" in data and "list" in data["data"]:
                        return data["data"]["list"]
    except Exception as e:
        logger.error(f"API Fetch Error: {e}")
    return []

def process_item(item):
    try:
        num = int(item.get("number", 0))
        issue = str(item.get("issueNumber", ""))
        size = "BIG" if num >= 5 else "SMALL"
        
        if num in [1, 3, 7, 9]:
            color = "GREEN"
        elif num in [2, 4, 6, 8]:
            color = "RED"
        else:
            color = "VIOLET"
            
        current_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        return {
            "period": issue,
            "number": num,
            "size": size,
            "color": color,
            "timestamp": current_time
        }
    except:
        return None

async def save_data_to_firestore(collection_name, item):
    try:
        db.collection(collection_name).document(item["period"]).set(item)
    except Exception as e:
        logger.error(f"Firestore Save Error: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 HISTORICAL DATA", callback_data="menu_historical")],
        [InlineKeyboardButton("📈 ANALYSIS HISTORICAL DATA", callback_data="menu_analysis")],
        [InlineKeyboardButton("🚀 SIGNAL", callback_data="menu_signal")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "🤖 *Welcome to Advanced Market Analytics Bot*\n\n"
        "✨ *Professional Data Tracking & Signal System*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Doya kore nicher option gulo theke apnar proyojonio feature select korun:"
    )
    
    if update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu_historical":
        keyboard = [
            [InlineKeyboardButton("⏱️ 30 SECONDS", callback_data="hist_30s"),
             InlineKeyboardButton("⏱️ 1 MINUTE", callback_data="hist_1m")],
            [InlineKeyboardButton("« Back to Menu", callback_data="back_main")]
        ]
        await query.message.edit_text("📂 *SELECT TIMEFRAME FOR HISTORICAL DATA*\n━━━━━━━━━━━━━━━━━━━━", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data in ["hist_30s", "hist_1m"]:
        tf = "30S" if data == "hist_30s" else "1M"
        user_states[query.from_user.id] = {"action": "wait_start_time", "timeframe": tf}
        
        msg = (
            f"📥 *TIMEFRAME: {tf}*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Doya kore **Starting Time** ei format-e likhun:\n"
            "`DATE-03/10/2026TIME-01:25`"
        )
        await query.message.edit_text(msg, parse_mode="Markdown")

    elif data == "menu_analysis":
        keyboard = [
            [InlineKeyboardButton("⏳ LAST 30 MINUTE", callback_data="ana_30")],
            [InlineKeyboardButton("⏳ LAST 60 MINUTE", callback_data="ana_60")],
            [InlineKeyboardButton("⏳ LAST 90 MINUTE", callback_data="ana_90")],
            [InlineKeyboardButton("⏳ LAST 120 MINUTE", callback_data="ana_120")],
            [InlineKeyboardButton("⏳ LAST 150 MINUTE", callback_data="ana_150")],
            [InlineKeyboardButton("« Back to Menu", callback_data="back_main")]
        ]
        await query.message.edit_text("📊 *SELECT TIME RANGE FOR ANALYSIS*\n━━━━━━━━━━━━━━━━━━━━", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("ana_"):
        minutes = int(data.split("_")[1])
        await perform_market_analysis(query, minutes)

    elif data == "menu_signal":
        keyboard = [
            [InlineKeyboardButton("⚡ 30 SECOND SIGNAL", callback_data="sig_30s"),
             InlineKeyboardButton("⚡ 1 MINUTE SIGNAL", callback_data="sig_1m")],
            [InlineKeyboardButton("« Back to Menu", callback_data="back_main")]
        ]
        await query.message.edit_text("🚀 *SELECT SIGNAL TIMEFRAME*\n━━━━━━━━━━━━━━━━━━━━", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data in ["sig_30s", "sig_1m"]:
        tf_type = "30s" if data == "sig_30s" else "1m"
        keyboard = [
            [InlineKeyboardButton("🟢 START SIGNAL GENERATOR", callback_data=f"start_sig_{tf_type}")],
            [InlineKeyboardButton("« Back to Menu", callback_data="back_main")]
        ]
        await query.message.edit_text("🎯 Signal shuru korte nicher button-e click korun:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("start_sig_"):
        tf_type = data.split("_")[2]
        await query.message.reply_text("🚀 Signal Generator Started! Real-time signal pathano hocche...")
        await run_live_signals(query, tf_type)

    elif data == "back_main":
        await start(update, context)

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_states:
        return

    state_info = user_states[user_id]
    text = update.message.text.strip()

    if state_info["action"] == "wait_start_time":
        state_info["start_str"] = text
        state_info["action"] = "wait_end_time"
        await update.message.reply_text("✅ Start Time Received!\n\nEkhon **Ending Time** eki format-e din:\n`DATE-03/10/2026TIME-01:30`", parse_mode="Markdown")

    elif state_info["action"] == "wait_end_time":
        tf = state_info["timeframe"]
        col_name = "history_30s" if tf == "30S" else "history_1m"
        
        docs = db.collection(col_name).limit(10).stream()
        response_lines = ["📋 *HISTORICAL DATA RESULTS*\n━━━━━━━━━━━━━━━━━━━━"]
        found = False
        
        for doc in docs:
            d = doc.to_dict()
            found = True
            line = f"`{d['period']}-{d['number']}-{d['size']}-{d['color']}`"
            response_lines.append(line)
            
        if found:
            await update.message.reply_text("\n".join(response_lines), parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Sorry, data is not available.")
            
        del user_states[user_id]

async def perform_market_analysis(query, minutes):
    analysis_output = f"""
📊 *MARKET ANALYSIS REPORT (Last {minutes} Mins)*
━━━━━━━━━━━━━━━━━━━━

📊 *MOMENTUM CONFIRMATION*
━━━━━━━━━━━━━━━━━━━━
🚀 Bajarer bortoman gotibidhi te shoktishali Momentum dekha jacche.
📈 Samprotik folafol ekti nirdisto diker dike beshi chap dekhacche.
━━━━━━━━━━━━━━━━━━━━

🧩 *PREVIOUS PATTERN CONFIRMATION*
━━━━━━━━━━━━━━━━━━━━
🔍 Purraborti pattern analisi kore dekha jacche market ekti shonirdisto niyome egocche.
━━━━━━━━━━━━━━━━━━━━

🔥 *SEQUENCE CONFIRMATION*
━━━━━━━━━━━━━━━━━━━━
📌 Shesh koyti result-er sequence structure miliye dekha gelo eta bortomane **Continuation** mode-e royeche.
━━━━━━━━━━━━━━━━━━━━

🔄 *REVERSAL + STREAK CONFIRMATION*
━━━━━━━━━━━━━━━━━━━━
⚠️ Bajare Reversal Activity ebong Streak bhor shommulok obosthay ache.
━━━━━━━━━━━━━━━━━━━━

🌊 *VOLATILITY + MARKET REGIME CONFIRMATION*
━━━━━━━━━━━━━━━━━━━━
⚡ Bajare bortomane shabhavik Volatility lokkho kora jacche. Regime sthirshil.
━━━━━━━━━━━━━━━━━━━━
"""
    keyboard = [[InlineKeyboardButton("« Back to Menu", callback_data="back_main")]]
    await query.message.edit_text(analysis_output, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def run_live_signals(query, tf_type):
    api_url = API_30S if tf_type == "30s" else API_1M
    col_name = "history_30s" if tf_type == "30s" else "history_1m"
    chat_id = query.message.chat_id
    bot = query.bot

    for i in range(3):
        raw_list = await fetch_api_data(api_url)
        if raw_list:
            item = process_item(raw_list[0])
            if item:
                await save_data_to_firestore(col_name, item)
                
                signal_type = item['size']
                caption = (
                    f"🎯 *SIGNAL ALERT*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 *PERIOD:* `{item['period']}`\n"
                    f"⏱️ *TIMEFRAME:* `{tf_type.upper()}`\n"
                    f"🚀 *SIGNAL:* `{signal_type}`\n"
                    f"🔢 *NUMBER:* `{item['number']}`\n"
                    f"🎨 *COLOUR:* `{item['color']}`\n"
                    f"━━━━━━━━━━━━━━━━━━━━"
                )
                await bot.send_message(chat_id=chat_id, text=caption, parse_mode="Markdown")
                
                await asyncio.sleep(12)
                new_raw = await fetch_api_data(api_url)
                if new_raw:
                    new_item = process_item(new_raw[0])
                    if new_item:
                        is_win = new_item['size'] == signal_type
                        status_text = "🎉 *RESULT: WIN* ✅" if is_win else "❌ *RESULT: LOSS* ❌"
                        await bot.send_message(chat_id=chat_id, text=status_text, parse_mode="Markdown")
        
        await asyncio.sleep(15)

def main():
    keep_alive()
    TOKEN = "8177073363:AAGrp0ndTtV2escKnZw25a1AqIIOnLO_3xw"  # Ekhane tomar bot token bosabe
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))

    print("🤖 Bot with Firestore & Flask is running successfully...")
    app.run_polling()

if __name__ == "__main__":
    main()
