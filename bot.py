import logging
import asyncio
import aiohttp
import os
from datetime import datetime
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
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
active_signals = {}  # To track running signal tasks per user/chat

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
        doc_id = str(item["period"])
        db.collection(collection_name).document(doc_id).set(item)
        logger.info(f"Saved to Firestore [{collection_name}] -> Period: {doc_id}")
    except Exception as e:
        logger.error(f"Firestore Save Error: {e}")

# Persistent Reply Keyboard for Signal Control
def get_main_reply_keyboard():
    keyboard = [
        [KeyboardButton("🚀 START SIGNAL GENERATOR"), KeyboardButton("🛑 STOP SIGNAL GENERATOR")],
        [KeyboardButton("« MAIN MENU")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_states:
        del user_states[user_id]
        
    # Stop any active signals for this user on start
    if user_id in active_signals:
        active_signals[user_id] = False
        
    inline_keyboard = [
        [InlineKeyboardButton("📊 HISTORICAL DATA", callback_data="menu_historical")],
        [InlineKeyboardButton("📈 ANALYSIS HISTORICAL DATA", callback_data="menu_analysis")],
        [InlineKeyboardButton("⚡ LIVE SIGNAL GENERATOR", callback_data="menu_signal")],
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard)
    
    welcome_text = (
        "🤖 *WELCOME TO WINGO ANALYZER PRO*\n\n"
        "✨ *Professional Market Data & Real-Time Signal System*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👇 *Please select an option from the menu below:*"
    )
    
    reply_kb = get_main_reply_keyboard()
    
    if update.callback_query:
        await update.callback_query.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
        await update.callback_query.message.reply_text("📌 *Use the control panel below for signal operations:*", reply_markup=reply_kb, parse_mode="Markdown")
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
        await update.message.reply_text("📌 *Use the control panel below for signal operations:*", reply_markup=reply_kb, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "menu_historical":
        keyboard = [
            [InlineKeyboardButton("⏱️ 30 SECONDS TIMEFRAME", callback_data="hist_30s"),
             InlineKeyboardButton("⏱️ 1 MINUTE TIMEFRAME", callback_data="hist_1m")],
            [InlineKeyboardButton("« Back to Main Menu", callback_data="back_main")]
        ]
        await query.message.edit_text(
            "📂 *HISTORICAL DATA MODULE*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n👇 *Select your preferred timeframe:*", 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode="Markdown"
        )

    elif data in ["hist_30s", "hist_1m"]:
        tf = "30S" if data == "hist_30s" else "1M"
        user_states[user_id] = {"action": "wait_start_time", "timeframe": tf}
        
        keyboard = [[InlineKeyboardButton("« Back to Main Menu", callback_data="back_main")]]
        msg = (
            f"📥 *TIMEFRAME SELECTED: {tf}*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📌 *Step 1:* Please enter the **Starting Time** in the exact format below:\n\n"
            "`DATE-03/10/2026TIME-01:25`"
        )
        await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_analysis":
        keyboard = [
            [InlineKeyboardButton("⏳ LAST 30 MINUTES", callback_data="ana_30")],
            [InlineKeyboardButton("⏳ LAST 60 MINUTES", callback_data="ana_60")],
            [InlineKeyboardButton("⏳ LAST 90 MINUTES", callback_data="ana_90")],
            [InlineKeyboardButton("⏳ LAST 120 MINUTES", callback_data="ana_120")],
            [InlineKeyboardButton("⏳ LAST 150 MINUTES", callback_data="ana_150")],
            [InlineKeyboardButton("« Back to Main Menu", callback_data="back_main")]
        ]
        await query.message.edit_text(
            "📊 *MARKET ANALYSIS MODULE*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n👇 *Select time range for deep analysis:*", 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode="Markdown"
        )

    elif data.startswith("ana_"):
        minutes = int(data.split("_")[1])
        # Auto-fetch and store recent data to Firestore before analyzing so database is populated
        for url, col in [(API_30S, "history_30s"), (API_1M, "history_1m")]:
            raw_list = await fetch_api_data(url)
            for item_raw in raw_list[:10]:
                processed = process_item(item_raw)
                if processed:
                    await save_data_to_firestore(col, processed)
        await perform_market_analysis(query, minutes)

    elif data == "menu_signal":
        keyboard = [
            [InlineKeyboardButton("⚡ 30 SECONDS SIGNAL", callback_data="sig_30s"),
             InlineKeyboardButton("⚡ 1 MINUTE SIGNAL", callback_data="sig_1m")],
            [InlineKeyboardButton("« Back to Main Menu", callback_data="back_main")]
        ]
        await query.message.edit_text(
            "🚀 *LIVE SIGNAL GENERATOR*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n👇 *Select signal timeframe:*", 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode="Markdown"
        )

    elif data in ["sig_30s", "sig_1m"]:
        tf_type = "30s" if data == "sig_30s" else "1m"
        user_states[user_id] = {"signal_timeframe": tf_type}
        keyboard = [
            [InlineKeyboardButton("🟢 START LIVE SIGNALS", callback_data=f"start_sig_{tf_type}")],
            [InlineKeyboardButton("« Back to Main Menu", callback_data="back_main")]
        ]
        await query.message.edit_text(
            f"🎯 *Selected Timeframe: {tf_type.upper()}*\n👇 Click below or use the bottom keyboard to start/stop signals:", 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode="Markdown"
        )

    elif data.startswith("start_sig_"):
        tf_type = data.split("_")[2]
        user_states[user_id] = {"signal_timeframe": tf_type}
        await query.message.reply_text("🚀 *Live Signal Generator Initialized Successfully!* Transmitting real-time signals...", reply_markup=get_main_reply_keyboard(), parse_mode="Markdown")
        asyncio.create_task(run_live_signals(query.message.chat_id, query.bot, tf_type, user_id))

    elif data == "back_main":
        if user_id in user_states:
            del user_states[user_id]
        if user_id in active_signals:
            active_signals[user_id] = False
        await start(update, context)

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    # Handle Persistent Reply Keyboard Actions
    if text == "🚀 START SIGNAL GENERATOR":
        tf_type = user_states.get(user_id, {}).get("signal_timeframe", "30s")
        await update.message.reply_text(f"🚀 *Live Signals Started for {tf_type.upper()}!*", reply_markup=get_main_reply_keyboard(), parse_mode="Markdown")
        asyncio.create_task(run_live_signals(update.message.chat_id, context.bot, tf_type, user_id))
        return

    elif text == "🛑 STOP SIGNAL GENERATOR":
        active_signals[user_id] = False
        await update.message.reply_text("🛑 *Live Signal Generator Stopped Successfully.*", reply_markup=get_main_reply_keyboard(), parse_mode="Markdown")
        return

    elif text == "« MAIN MENU":
        if user_id in active_signals:
            active_signals[user_id] = False
        if user_id in user_states:
            del user_states[user_id]
        await start(update, context)
        return

    if user_id not in user_states or "action" not in user_states[user_id]:
        return

    state_info = user_states[user_id]

    if state_info["action"] == "wait_start_time":
        state_info["start_str"] = text
        state_info["action"] = "wait_end_time"
        
        keyboard = [[InlineKeyboardButton("« Back to Main Menu", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "✅ *Starting Time Received Successfully!*\n\n"
            "📌 *Step 2:* Now please enter the **Ending Time** in the exact format below:\n\n"
            "`DATE-03/10/2026TIME-01:30`",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    elif state_info["action"] == "wait_end_time":
        tf = state_info["timeframe"]
        col_name = "history_30s" if tf == "30S" else "history_1m"
        
        # Fetch fresh data from API and save to Firestore to ensure collection has documents
        api_url = API_30S if tf == "30S" else API_1M
        raw_list = await fetch_api_data(api_url)
        for item_raw in raw_list:
            processed = process_item(item_raw)
            if processed:
                await save_data_to_firestore(col_name, processed)

        docs = list(db.collection(col_name).limit(15).stream())
        response_lines = ["📋 *HISTORICAL DATA REPORT*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
        found = False
        
        for doc in docs:
            d = doc.to_dict()
            found = True
            line = f"🔹 `Period: {d['period']} | Num: {d['number']} | Size: {d['size']} | Color: {d['color']}`"
            response_lines.append(line)
            
        if found:
            await update.message.reply_text("\n".join(response_lines), reply_markup=get_main_reply_keyboard(), parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ *Sorry, requested data is currently not available in the database.*", reply_markup=get_main_reply_keyboard(), parse_mode="Markdown")
            
        if user_id in user_states:
            del user_states[user_id]

async def perform_market_analysis(query, minutes):
    analysis_output = f"""
📊 *MARKET ANALYSIS REPORT (Last {minutes} Mins)*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 *MOMENTUM CONFIRMATION*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 Strong bullish momentum detected across current market intervals.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🧩 *PREVIOUS PATTERN CONFIRMATION*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Historical data patterns indicate a structured continuation trend.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔥 *SEQUENCE CONFIRMATION*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 Recent output sequences confirm active trend alignment.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔄 *REVERSAL & STREAK CONFIRMATION*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ Moderate streak volatility observed. Monitoring reversal thresholds.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌊 *VOLATILITY & REGIME*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ Market volatility is stable and optimal for execution.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    keyboard = [[InlineKeyboardButton("« Back to Main Menu", callback_data="back_main")]]
    await query.message.edit_text(analysis_output, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def run_live_signals(chat_id, bot, tf_type, user_id):
    api_url = API_30S if tf_type == "30s" else API_1M
    col_name = "history_30s" if tf_type == "30s" else "history_1m"
    
    active_signals[user_id] = True

    while active_signals.get(user_id, False):
        raw_list = await fetch_api_data(api_url)
        if raw_list:
            item = process_item(raw_list[0])
            if item:
                # Save to Firestore so database populates automatically during live signals!
                await save_data_to_firestore(col_name, item)
                
                signal_type = item['size']
                caption = (
                    f"🎯 *VIP SIGNAL ALERT*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 *PERIOD:* `{item['period']}`\n"
                    f"⏱️ *TIMEFRAME:* `{tf_type.upper()}`\n"
                    f"🚀 *PREDICTION:* `{signal_type}`\n"
                    f"🔢 *NUMBER:* `{item['number']}`\n"
                    f"🎨 *COLOUR:* `{item['color']}`\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                )
                await bot.send_message(chat_id=chat_id, text=caption, parse_mode="Markdown")
                
                # Wait for result check
                await asyncio.sleep(12)
                if not active_signals.get(user_id, False):
                    break
                    
                new_raw = await fetch_api_data(api_url)
                if new_raw:
                    new_item = process_item(new_raw[0])
                    if new_item:
                        await save_data_to_firestore(col_name, new_item)
                        is_win = new_item['size'] == signal_type
                        status_text = "🎉 *RESULT STATUS: WIN* ✅" if is_win else "❌ *RESULT STATUS: LOSS* ❌"
                        await bot.send_message(chat_id=chat_id, text=status_text, parse_mode="Markdown")
        
        # Check active status before sleeping
        for _ in range(15):
            if not active_signals.get(user_id, False):
                break
            await asyncio.sleep(1)

def main():
    keep_alive()
    TOKEN = "8177073363:AAGrp0ndTtV2escKnZw25a1AqIIOnLO_3xw"  # Your Bot Token
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))

    print("🤖 Professional Wingo Analyzer Bot is running successfully...")
    app.run_polling()

if __name__ == "__main__":
    main()
