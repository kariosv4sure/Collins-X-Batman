import os
import json
import re
import requests
import threading
import time
from io import BytesIO
import random
from telebot.types import Message
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from deep_translator import GoogleTranslator


START_TIME = time.time()  # bot start time

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

bot = telebot.TeleBot(TOKEN)

# ---------------- DATA FILES ---------------- #
MEMORY_FILE = "data/user_memory.json"
ADMINS_FILE = "data/admins.json"
BANNED_FILE = "data/banned_users.json"
XP_FILE = "data/xp.json"
CHATS_FILE = "data/chats.json"
VERIFIED_FILE = "data/verified.json"
WARNINGS_FILE = "data/warnings.json"
MUTED_FILE = "data/muted.json"
REFERRAL_FILE = "data/referrals.json"
DAILY_FILE = "data/daily.json"

def save_verified():
    save_json(VERIFIED_FILE, verified_users)
# ---------------- HELPERS ---------------- #
def load_json(file, default):
    if os.path.exists(file):
        with open(file) as f:
            return json.load(f)
    return default

def save_json(file, data):
    os.makedirs(os.path.dirname(file), exist_ok=True)
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

def save_referrals():
    with open(REFERRAL_FILE, "w") as f:
        json.dump(referrals_data, f, indent=4)

TIER_REWARDS = {
    5: {"coins": 50, "badge": "🥉"},
    10: {"coins": 150, "badge": "🥈"},
    20: {"coins": 500, "badge": "🥇"}
}

# ---------------- SHOP DATA ---------------- #
SHOP_ITEMS = {
    "vip": {"price": 100, "desc": "VIP Access 🔥"},
    "boost": {"price": 50, "desc": "XP Boost x2 (24hrs) ⚡"},
    "badge": {"price": 30, "desc": "Custom Profile Badge 🏅"}
}

def check_tiers(uid):
    data = referrals_data[uid]
    total = len(data["referrals"])

    for tier, reward in TIER_REWARDS.items():
        if total == tier:
            data["coins"] += reward["coins"]
            bot.send_message(
                uid,
                f"🎉 TIER UNLOCKED!\n"
                f"{tier} referrals reached!\n"
                f"+{reward['coins']} coins\n"
                f"Badge unlocked: {reward['badge']}"
            )

daily_data = load_json(DAILY_FILE, {})

def daily_bonus(uid):
    today = datetime.now().strftime("%Y-%m-%d")
    last = daily_data.get(uid)

    if last != today:
        daily_data[uid] = today
        referrals_data[uid]["coins"] += 5
        save_json(DAILY_FILE,daily_data)
        save_referrals()
        return True
    return False

# -------------------- INITIALIZE FILE -------------------- #
# Create data/referrals.json if it doesn't exist
if not os.path.exists("data"):
    os.makedirs("data")  # make the data folder if missing

if not os.path.exists(REFERRAL_FILE):
    with open(REFERRAL_FILE, "w") as f:
        json.dump({}, f, indent=4)

# -------------------- LOAD DATA -------------------- #
with open(REFERRAL_FILE, "r") as f:
    referrals_data = json.load(f)

def log_user(message):
    os.makedirs("data", exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("data/users.log", "a") as f:
        f.write(f"{now} | @{message.from_user.username} | {message.text}\n")

CHANNEL_USERNAME = "@Collins_AI_101"  # without https
verified_users = load_json(VERIFIED_FILE, [])

# ---------------- VERIFY CALLBACK ---------------- #
@bot.callback_query_handler(func=lambda call: call.data == "verify_join")
def verify_user(call):
    uid = str(call.from_user.id)

    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, uid)

        # ✅ User joined channel
        if member.status in ["member", "administrator", "creator"]:

            if uid not in verified_users:
                verified_users.append(uid)
                save_verified()

            bot.edit_message_text(
                "✅ *Verification successful!*\n\n"
                "Use /help again to access commands 😎🔥",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )

        # ❌ User not in channel
        else:
            bot.answer_callback_query(
                call.id,
                "❌ You haven't joined the channel yet!",
                show_alert=True
            )

    except:
        bot.answer_callback_query(
            call.id,
            "⚠️ Verification failed. Try again.",
            show_alert=True
        )

# ---------------- LOAD DATA ---------------- #
user_memory = load_json(MEMORY_FILE, {})
admins = set(load_json(ADMINS_FILE, []))
banned_users = set(load_json(BANNED_FILE, []))
xp_data = load_json(XP_FILE, {})
chats = load_json(CHATS_FILE, [])
summarize_mode = {}
admin_wait = {}
link_warnings = {}

# ---------------- ANIME GAME DATA ---------------- #
ANIME_FILE = "data/anime_data.json"

def load_anime():
    if os.path.exists(ANIME_FILE):
        with open(ANIME_FILE) as f:
            return json.load(f)
    return {}

def save_anime(data):
    with open(ANIME_FILE, "w") as f:
        json.dump(data, f, indent=4)

def ensure_anime_user(uid):
    data = load_anime()
    uid = str(uid)

    if uid not in data:
        data[uid] = {
            "characters": [],
            "last_train": 0
        }
        save_anime(data)

def create_character(name, verse, rarity):
    return {
        "name": name,
        "verse": verse,
        "level": 1,
        "rarity": rarity,
        "stats": {
            "attack": random.randint(30, 60),
            "speed": random.randint(30, 60),
            "chakra": random.randint(30, 60)
        }
    }

TRAIN_COOLDOWN = 3600  # 1 hour

def can_train(uid):
    data = load_anime()
    last = data[str(uid)]["last_train"]
    return time.time() - last >= TRAIN_COOLDOWN

def update_train(uid):
    data = load_anime()
    data[str(uid)]["last_train"] = time.time()
    save_anime(data)

# ---------------- MEMORY ---------------- #
def update_memory(message):
    user = message.from_user.username
    if not user:
        return

    if user not in user_memory:
        user_memory[user] = []

    if not message.text.startswith("/"):
        user_memory[user].append(message.text)

    if len(user_memory[user]) > 5:
        user_memory[user].pop(0)

    save_json(MEMORY_FILE, user_memory)

# ---------------- XP SYSTEM ---------------- #
def get_level(xp):
    return xp // 100

def ensure_user(username):
    if username not in xp_data:
        xp_data[username] = {
            "xp": 0,
            "messages": 0,
            "commands": 0
        }

def add_message_xp(username):
    if username in banned_users:
        return
    ensure_user(username)
    xp_data[username]["messages"] += 1
    xp_data[username]["xp"] += 5
    save_json(XP_FILE, xp_data)

def add_command_xp(username):
    if username in banned_users:
        return
    ensure_user(username)
    xp_data[username]["commands"] += 1
    xp_data[username]["xp"] += 10
    save_json(XP_FILE, xp_data)

# ----------------- BANNED CHECK DECORATORS ----------------- #
def check_banned_user(func):
    """Decorator to block banned users from running any command."""
    def wrapper(message, *args, **kwargs):
        uid = message.from_user.id
        username = str(message.from_user.username)

        # Admins are exempt
        if uid in admins:
            return func(message, *args, **kwargs)

        # Block banned users
        if username in banned_users:
            bot.reply_to(message, "🚫 You've been banned")
            return  # Stop command from running

        return func(message, *args, **kwargs)
    return wrapper

def check_banned_callback(func):
    """Decorator to block banned users from using buttons/callbacks."""
    def wrapper(call, *args, **kwargs):
        uid = call.from_user.id
        username = str(call.from_user.username)

        # Admins are exempt
        if uid in admins:
            return func(call, *args, **kwargs)

        # Block banned users
        if username in banned_users:
            bot.answer_callback_query(call.id, "🚫 You've been banned", show_alert=True)
            return  # Stop callback from running

        return func(call, *args, **kwargs)
    return wrapper

import time

# In your user data
# referrals_data[user_id] = {"referrals": [], "coins": 0, "last_ai_reward": 0}

AI_REWARD = 5
AI_COOLDOWN = 12 * 60 * 60  # 12 hours

def give_ai_reward(uid):
    now = time.time()
    user_data = referrals_data.setdefault(uid, {"referrals": [], "coins": 0, "last_ai_reward": 0})

    if now - user_data.get("last_ai_reward", 0) >= AI_COOLDOWN:
        user_data["coins"] += AI_REWARD
        user_data["last_ai_reward"] = now
        bot.send_message(uid, f"🤖 Thanks for chatting!\n+{AI_REWARD} coins earned (once every 12hrs)")
        save_referrals()

# ----------------- BAN USER ----------------- #
@bot.message_handler(commands=['ban'])
def ban_user(message):
    uid = message.from_user.id

    # Only admins can ban
    if uid not in admins:
        bot.reply_to(message, "🚫 Admin only")
        return

    try:
        user_to_ban = message.text.split()[1].lstrip("@")
        if user_to_ban in admins:
            bot.reply_to(message, "❌ You can't ban an admin!")
            return

        banned_users.add(user_to_ban)
        save_json(BANNED_FILE, list(banned_users))
        bot.reply_to(message, f"🔨 @{user_to_ban} banned")
    except:
        bot.reply_to(message, "Usage: /ban @username")

# ----------------- UNBAN USER ----------------- #
@bot.message_handler(commands=['unban'])
def unban_user(message):
    uid = message.from_user.id

    # Only admins can unban
    if uid not in admins:
        bot.reply_to(message, "🚫 Admin only")
        return

    try:
        user_to_unban = message.text.split()[1].lstrip("@")
        if user_to_unban in banned_users:
            banned_users.remove(user_to_unban)
            save_json(BANNED_FILE, list(banned_users))
            bot.reply_to(message, f"✅ @{user_to_unban} unbanned")
        else:
            bot.reply_to(message, f"⚠ @{user_to_unban} is not banned")
    except:
        bot.reply_to(message, "Usage: /unban @username")

# ---------------- ADMIN ---------------- #
def is_admin(chat_id):
    return chat_id in admins

@bot.message_handler(commands=['admin'])
def admin_login(message):
    bot.reply_to(message, "Enter admin password 🔐")
    admin_wait[message.chat.id] = True

# ---------- BROADCAST ----------
def escape_md(text):
    chars = r'\_*[]()~`>#+-=|{}.!'
    for c in chars:
        text = text.replace(c, '\\' + c)
    return text

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if not is_admin(message.chat.id):
        bot.reply_to(message, "🚫 You are not an admin")
        return

    try:
        raw_text = message.text.split(maxsplit=1)[1]
        text = escape_md(raw_text)
    except IndexError:
        bot.reply_to(message, "Usage: /broadcast <message>")
        return

    sent = 0
    for chat_id in chats:
        if chat_id in banned_users:
            continue
        try:
            bot.send_message(
                chat_id,
                f"📢 *Broadcast*\n\n{text}",
                parse_mode="MarkdownV2"
            )
            sent += 1
        except Exception as e:
            print(f"Failed to send to {chat_id}: {e}")

    bot.reply_to(message, f"✅ Broadcast sent to {sent} users")

# ---------- STATS ----------
@bot.message_handler(commands=['stats'])
def stats(message):
    if not is_admin(message.chat.id):
        bot.reply_to(message, "🚫 You are not an admin")
        return

    bot.reply_to(
        message,
        f"👥 Total users: {len(user_memory)}\n"
        f"🚫 Banned users: {len(banned_users)}\n"
        f"🛠 Admins: {len(admins)}"
    )

# ---------- WIPE ----------
@bot.message_handler(commands=['wipe'])
def wipe_user(message):
    # Check if the sender is an admin
    if not is_admin(message.chat.id):
        bot.reply_to(message, "🚫 You are not an admin")
        return

    # Attempt to get the username from the command
    try:
        user = message.text.split(maxsplit=1)[1].lstrip("@").strip()
    except IndexError:
        bot.reply_to(message, "Usage: /wipe @username")
        return

    # Wipe the memory if it exists
    if user in user_memory:
        user_memory.pop(user)
        save_json(MEMORY_FILE, user_memory)
        bot.reply_to(message, f"🗑 Memory wiped for @{user}")
    else:
        bot.reply_to(message, f"⚠ User @{user} has no memory stored")

# ---------------- UPTIME ---------------- #
@bot.message_handler(commands=['uptime'])
def uptime_cmd(message):

    uid = message.from_user.id

    if not is_admin(uid):  # your admin checker
        bot.reply_to(message, "🚫 Admin only command.")
        return

    now = time.time()
    seconds = int(now - START_TIME)

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    bot.reply_to(
        message,
        f"⏳ *BOT UPTIME*\n\n"
        f"🗓 {days} days\n"
        f"⏰ {hours} hours\n"
        f"⌛ {minutes} minutes\n"
        f"⚡ {secs} seconds",
        parse_mode="Markdown"
    )

# ---------------- GROQ ---------------- #
def ask_groq(username, prompt):
    memory = "\n".join(user_memory.get(username, []))
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content":
             "You are Collins AI, a smart and friendly Telegram assistant. "
             "Your creator is Ifeanyichukwu Collins Chibueze, aka Karios Vantari. "
             "Keep answers short, helpful, and chill. "
             "Mention your creator subtly when relevant, never overdo it."},
            {"role": "user", "content": f"Chat memory:\n{memory}\n\n{prompt}"}
        ],
        "temperature": 0.5,
        "max_completion_tokens": 250
    }

    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json=payload
        )
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("Groq error:", e)
        return "Network error 😕"

# ---------------- USER COMMANDS ---------------- #
@bot.message_handler(commands=['start'])
@check_banned_user
def start(message):
    user_id = str(message.from_user.id)
    first_name = message.from_user.first_name
    args = message.text.split()

    # Add XP, log user, update memory
    add_command_xp(user_id)
    log_user(message)
    update_memory(message)

    # Add to chats if not already present
    if message.chat.id not in chats:
        chats.append(message.chat.id)
        save_json(CHATS_FILE, chats)

    # 🔥 DAILY LOGIN BONUS
    if daily_bonus(user_id):
        bot.send_message(
            message.chat.id,
            "🔥 Daily login! +5 coins"
        )

    # Initialize referral data for new user
    is_new_user = False
    if user_id not in referrals_data:
        referrals_data[user_id] = {"referrals": [], "coins": 0}
        is_new_user = True

    # Handle referral
    if is_new_user and len(args) > 1:
        referrer_id = args[1]

        # Prevent self referral
        if referrer_id != user_id:
            referrals_data.setdefault(referrer_id, {"referrals": [], "coins": 0})

            # Prevent duplicate referral
            if user_id not in referrals_data[referrer_id]["referrals"]:
                referrals_data[referrer_id]["referrals"].append(user_id)
                referrals_data[referrer_id]["coins"] += 5

                # Notify referrer
                bot.send_message(
                    referrer_id,
                    f"🎉 New referral joined!\n"
                    f"+5 coins earned\n"
                    f"Total coins: {referrals_data[referrer_id]['coins']}"
                )

                # Check tiers
                check_tiers(referrer_id)

                # Notify new user
                bot.send_message(
                    message.chat.id,
                    "🎉 You were referred by a friend!"
                )

    save_referrals()

    # Reply to user
    bot.reply_to(
        message,
        f"Hi {first_name} 👋\n"
        "Collins AI active.\n"
        "Type /help to see commands.\n"
        "OR\n"
        "Use /refinfo to learn about the referral system!"
    )

# ------------------- REFERRAL SYSTEM ------------------- #
@bot.message_handler(commands=['refinfo'])
@check_banned_user
def refinfo_cmd(message):
    """Shows detailed referral guide"""
    bot.send_message(
        message.chat.id,
        "🎯 *Referral System Guide*\n\n"
        "1️⃣ Share your referral link using /refer\n"
        "2️⃣ Each friend who starts the bot with your link = 1 Referral\n"
        "3️⃣ Each referral = 5 coins\n"
        "4️⃣ Track your referrals & coins anytime: /referrals\n"
        "5️⃣ Convert coins to cash or VIP features: /convert\n"
        "6️⃣ See the top referrers: /refleaderboard\n\n"
        "💡 T&C: 100 coins = Access to VIP features or #100\n"
        "Keep sharing and watch your coins grow! 😎",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['refer'])
@check_banned_user
def refer_cmd(message):
    """Send referral link with buttons"""
    uid = str(message.from_user.id)
    link = f"https://t.me/Collins_X_Batman_bot?start={uid}"

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={link}"),
        InlineKeyboardButton("📊 My Stats", callback_data=f"ref_stats_{uid}")
    )

    bot.send_message(
        message.chat.id,
        f"🎯 <b>Your Referral Link</b>\n{link}\n\nEarn <b>5 coins</b> per invite 😎",
        reply_markup=markup,
        parse_mode="HTML"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("ref_stats_"))
@check_banned_callback
def ref_stats_btn(call):
    """Show user's referral stats safely"""
    uid = call.data.replace("ref_stats_", "")
    data = referrals_data.get(uid, {"referrals": [], "coins": 0})

    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"📊 *Your Stats*\n\n"
        f"👥 Referrals: {len(data['referrals'])}\n"
        f"💰 Coins: {data['coins']}",
        parse_mode="Markdown"
    )


@bot.message_handler(commands=['referrals'])
@check_banned_user
def referrals_cmd(message):
    """Shows total referrals and coins"""
    uid = str(message.from_user.id)
    data = referrals_data.get(uid, {"referrals": [], "coins": 0})
    total_referrals = len(data["referrals"])
    coins = data["coins"]

    bot.send_message(
        message.chat.id,
        f"👥 *Total Referrals:* {total_referrals}\n"
        f"💰 *Coins:* {coins}\n\nKeep sharing your link with /refer to earn more!",
        parse_mode="Markdown"
    )


@bot.message_handler(commands=['convert'])
@check_banned_user
def convert_cmd(message):
    """Convert coins to cash or VIP access"""
    uid = str(message.from_user.id)
    data = referrals_data.get(uid, {"referrals": [], "coins": 0})
    coins = data["coins"]

    if coins >= 100:
        bot.send_message(
            message.chat.id,
            f"🎉 You have {coins} coins!\n"
            "DM @Just_Collins101 to convert to cash or VIP access.\n"
            "T&C: 100 coins = #100 / VIP unlock",
            parse_mode="Markdown"
        )
    else:
        bot.send_message(
            message.chat.id,
            "❌ You need at least 100 coins to convert.\nKeep inviting friends using /refer! 😎",
            parse_mode="Markdown"
        )


@bot.message_handler(commands=['refleaderboard'])
@check_banned_user
def ref_leaderboard(message):
    """Shows top referrers (ignores users with 0 coins)"""
    # Filter out users with 0 coins
    active_refs = {uid: data for uid, data in referrals_data.items() if data["coins"] > 0}

    if not active_refs:
        bot.send_message(message.chat.id, "No referrals yet 😅 Start sharing your link!")
        return

    # Sort top 10
    top = sorted(active_refs.items(), key=lambda x: x[1]["coins"], reverse=True)[:10]

    text = "🏅 *TOP REFERRERS* 🏅\n\n"

    for i, (uid, data) in enumerate(top, 1):
        try:
            user_obj = bot.get_chat(uid)
            username = f"@{user_obj.username}" if user_obj.username else user_obj.first_name
        except Exception:
            username = f"User {uid}"  # fallback

        text += f"{i}. {username} — {data['coins']} coins — {len(data['referrals'])} refs\n"

    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ------------------- HELP COMMAND -------------------
@bot.message_handler(commands=['help'])
@check_banned_user
def help_cmd(message):
    uid = str(message.from_user.id)

    # 🔒 Verification check
    if uid not in verified_users:
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📢 Follow Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"),
            InlineKeyboardButton("✅ Verify", callback_data="verify_join")
        )
        bot.send_message(
            message.chat.id,
            "🚫 *Access Locked!*\nJoin the channel first and verify to unlock commands!",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    add_command_xp(uid)

    # ---------- MAIN HELP MENU ----------
    markup = InlineKeyboardMarkup(row_width=2)

    # Fun
    markup.add(
        InlineKeyboardButton("😂 Joke", callback_data="help_fun"),
        InlineKeyboardButton("✂️ RPS", callback_data="help_fun_rps")
    )

    # AI Tools
    markup.add(
        InlineKeyboardButton("📝 Summarize", callback_data="help_ai_summarize"),
        InlineKeyboardButton("📖 Define", callback_data="help_ai_define"),
        InlineKeyboardButton("🌐 Translate", callback_data="help_ai_translate")
    )

    # Images / Logo
    markup.add(
        InlineKeyboardButton("🖼 Image", callback_data="help_image"),
        InlineKeyboardButton("🎨 Logo", callback_data="help_logo")
    )

    # Music
    markup.add(
        InlineKeyboardButton("🎵 Lyrics", callback_data="help_lyrics")
    )

    # Profile, Leaderboards & Referral
    markup.add(
        InlineKeyboardButton("👤 Profile", callback_data="help_profile"),
        InlineKeyboardButton("🏆 Leaderboard", callback_data="help_leaderboard"),
        InlineKeyboardButton("🎯 Referral System", callback_data="help_referral")
    )

    # Tools
    markup.add(
        InlineKeyboardButton("⏰ Remind", callback_data="help_remind")
    )

    # Anime
    markup.add(
        InlineKeyboardButton("🎴 Anime System", callback_data="help_anime")
    )

    # Info
    markup.add(
        InlineKeyboardButton("ℹ About", callback_data="help_about"),
        InlineKeyboardButton("🛠 Support", callback_data="help_support")
    )

    bot.send_message(
        message.chat.id,
        "🌐 *COLLINS AI COMMANDS*\n\nClick a button to see usage for a category!",
        reply_markup=markup,
        parse_mode="Markdown"
    )


# ------------------- HELP CALLBACKS -------------------
HELP_RESPONSES = {
    "fun": "😂 Joke: /joke\n✂️ RPS: /rps <rock|paper|scissors>",
    "fun_rps": "Usage: /rps <rock|paper|scissors>",
    "ai_summarize": "Usage: /summarize <text>",
    "ai_define": "Usage: /define <word>",
    "ai_translate": "Usage: /translate <lang> <text>",
    "image": "Usage: /image <description>",
    "logo": "Usage: /logo <description>",
    "lyrics": "Send artist - title like /lyrics Rustage - Kurama",
    "profile": None,  # dynamic
    "leaderboard": None,  # calls leaderboard function
    "referral": None,  # handled inline
    "remind": "Set a reminder using /remind <minutes> <text>",
    "anime": "🎴 *Anime Characters System*\n"
             "• /search <verse> → Search & recruit a character\n"
             "• /character → View your squad\n"
             "• /train → Train your squad (+2 levels)\n"
             "• /remove → Remove a character\n"
             "Max 5 characters per user. Cooldowns apply.",
    "about": None,  # calls about()
    "support": None  # calls support()
}


@bot.callback_query_handler(func=lambda call: call.data.startswith("help_"))
@check_banned_callback
def help_callback(call):
    chat_id = call.message.chat.id
    uid = str(call.from_user.id)
    add_command_xp(uid)

    category = call.data.replace("help_", "")
    response = HELP_RESPONSES.get(category)

    if category == "profile":
        ensure_user(uid)
        data = xp_data.get(uid, {"xp": 0, "messages": 0, "commands": 0})
        level = get_level(data["xp"])
        bot.send_message(
            chat_id,
            f"👤 @{call.from_user.username}\n"
            f"⭐ Level: {level}\n"
            f"⚡ XP: {data['xp']}\n"
            f"💬 Messages: {data['messages']}\n"
            f"⌨ Commands: {data['commands']}"
        )

    elif category == "leaderboard":
        leaderboard(call.message)

    elif category == "referral":
        # INLINE MENU FOR REFERRAL SYSTEM
        data = referrals_data.get(uid, {"referrals": [], "coins": 0})
        link = f"https://t.me/Collins_X_Batman_bot?start={uid}"

        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("📤 My Referral Link", url=f"https://t.me/share/url?url={link}"),
            InlineKeyboardButton("📊 My Referral Stats", callback_data="ref_stats"),
            InlineKeyboardButton("🏅 Top Referrers", callback_data="ref_leaderboard")
        )

        bot.send_message(
            chat_id,
            f"🎯 *Referral System*\n\n"
            f"Share your link, earn coins, and track your progress!\n\n"
            f"Your link: {link}\nCoins: {data['coins']}\nReferrals: {len(data['referrals'])}",
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif category == "about":
        about(call.message)

    elif category == "support":
        support(call.message)

    else:
        bot.send_message(chat_id, response, parse_mode="Markdown")

    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

# ---------------- PROFILE COMMAND ---------------- #
@bot.message_handler(commands=['profile'])
@check_banned_user
def profile(message):
    user = message.from_user.username
    uid = str(message.from_user.id)

    ensure_user(user)
    level = get_level(xp_data[user]["xp"])
    coins = referrals_data.get(uid, {"coins": 0})["coins"]

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🛒 Shop", callback_data="open_shop"),
        InlineKeyboardButton("🎯 Refer", callback_data="open_refer")
    )

    bot.send_message(
        message.chat.id,
        f"👤 @{user}\n"
        f"⭐ Level: {level}\n"
        f"⚡ XP: {xp_data[user]['xp']}\n"
        f"💰 Coins: {coins}",
        reply_markup=markup
    )

# ---------------- PROFILE BUTTON CALLBACK ---------------- #
@bot.callback_query_handler(func=lambda call: call.data in ["open_shop", "open_refer", "ref_stats"])
@check_banned_callback
def profile_buttons(call):
    uid = str(call.from_user.id)  # 🔑 always use the user clicking the button
    user = call.from_user.username
    data = referrals_data.get(uid, {"referrals": [], "coins": 0})

    if call.data == "open_refer":
        link = f"https://t.me/Collins_X_Batman_bot?start={uid}"
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={link}"),
            InlineKeyboardButton("📊 My Stats", callback_data="ref_stats")
        )
        bot.send_message(
            call.message.chat.id,
            f"🎯 Your Referral Link\n{link}\nEarn 5 coins per invite 😎",
            reply_markup=markup
        )

    elif call.data == "ref_stats":
        bot.send_message(
            call.message.chat.id,
            f"📊 Your Stats\n\n👥 Referrals: {len(data['referrals'])}\n💰 Coins: {data['coins']}"
        )

    elif call.data == "open_shop":
        bot.send_message(call.message.chat.id, "🛒 Shop coming soon! Stay tuned 😎")

    bot.answer_callback_query(call.id)

@bot.message_handler(commands=["about"])
@check_banned_user
def about(m):
    add_command_xp(m.from_user.username)
    bot.reply_to(m,
        "✨ *ABOUT COLLINS AI* ✨\n\n"
        "👑 Name: Collins AI\n"
        "👨‍💻 Creator: Ifeanyichukwu Collins Chibueze\n"
        "🔥 Alias: Karios Vantari\n\n"
        "💡 Features:\n"
        "• Chat & AI responses\n"
        "• Fun games 🎮\n"
        "• XP system & leaderboard 🏆\n"
        "• Reminders ⏰\n"
        "• Admin tools & broadcast 📢\n\n"
        "🌐 Portfolio: https://karios-portfolio.onrender.com\n"
        "🚀 Built with Python + Telebot + Groq API\n"
        "💙 Made with passion and late-night coding",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["support"])
@check_banned_user
def support(m):
    add_command_xp(m.from_user.username)
    bot.reply_to(
        m,
        "🌟 <b>COLLINS AI – SUPPORT CENTER</b> \n\n"
        "💬 Need help? Got issues? Suggestions? Wanna vibe? 😎🔥\n\n"
        "📧 Email: ifeanyichukwucollins008@gmail.com\n\n"
        "💬 Telegram: @Just_Collins101\n\n"
        "📲 WhatsApp: https://wa.me/2348089368681\n\n"
        "📺 Channel: https://t.me/Collins_AI_101\n\n"
        "🎮 Daily AI chats 😆😂🎉\n"
        "⚡ Jokes, fun, games 🎮🎯\n"
        "⏰ Reminders & tips 💡💥\n"
        "💎 Powered by Karios Vantari + Groq AI 💙💫\n\n"
        "🔥💯💥🚀💎😎💫🎮💡",
        parse_mode="HTML"
    )
@bot.message_handler(commands=['joke'])
@check_banned_user
def joke(message):
    add_command_xp(message.from_user.username)
    ans = ask_groq(message.from_user.username,"Tell a funny short joke")
    bot.reply_to(message, ans)

@bot.message_handler(commands=['summarize'])
@check_banned_user
def summarize(message):
    add_command_xp(message.from_user.username)
    summarize_mode[message.from_user.username] = True
    bot.reply_to(message, "Send text to summarize")

# 🏆 leaderboard without banned
@bot.message_handler(commands=['leaderboard'])
@check_banned_user
def leaderboard(message):
    add_command_xp(message.from_user.username)

    clean = {
        u:d for u,d in xp_data.items()
        if u not in banned_users
    }

    if not clean:
        bot.reply_to(message, "No users yet 😅")
        return

    top = sorted(
        clean.items(),
        key=lambda x: x[1]["xp"],
        reverse=True
    )[:10]

    text = "🏆 LEADERBOARD\n\n"
    for i,(user,data) in enumerate(top,1):
        text += f"{i}. @{user} — {data['xp']} XP\n"

    bot.reply_to(message, text)

@bot.message_handler(commands=['image'])
@check_banned_user
def image_cmd(message):
    prompt = message.text.replace("/image", "").strip()
    if not prompt:
        bot.reply_to(message, "Usage: /image <describe your image>")
        return

    url = f"https://image.pollinations.ai/prompt/{prompt}"

    try:
        r = requests.get(url, timeout=45)
        r.raise_for_status()  # make sure we got the image
        bot.send_photo(message.chat.id, photo=BytesIO(r.content), caption="🖼 AI Generated Image")
    except Exception as e:
        print("Image fetch/send error:", e)
        bot.reply_to(message, "⚠ Failed to generate image. Try again later.")

@bot.message_handler(commands=['logo'])
@check_banned_user
def logo_cmd(message):
    prompt = message.text.replace("/logo", "").strip()
    if not prompt:
        bot.reply_to(message, "Usage: /logo <brand description>")
        return

    prompt = "logo design " + prompt
    url = f"https://image.pollinations.ai/prompt/{prompt}"

    try:
        r = requests.get(url, timeout=45)
        r.raise_for_status()
        bot.send_photo(message.chat.id, photo=BytesIO(r.content), caption="🎨 AI Generated Logo")
    except Exception as e:
        print("Logo fetch/send error:", e)
        bot.reply_to(message, "⚠ Failed to generate logo. Try again later.")

# ---------------- ANIME GUIDE COMMAND ---------------- #
@bot.message_handler(commands=['anime'])
@check_banned_user
def anime_guide(message):
    add_command_xp(message.from_user.username)

    text = "✨ *Anime Character System* ✨\n\n"
    text += "You can search, recruit, and train anime characters! Here's how it works:\n\n"
    text += "📜 *Commands*\n"
    text += "• /search <verse> — Find a character in a verse and recruit them\n"
    text += "• /character — Show your recruited characters\n"
    text += "• /train — Level up your characters (cooldown: 1hr)\n"
    text += "• /remove <character> — Remove a character from your squad\n\n"
    text += "🎮 *Details*\n"
    text += "• Each verse has a list of characters you can find\n"
    text += "• Characters have levels and rarities (Common, Rare, Legendary)\n"
    text += "• You can recruit up to 5 characters\n"
    text += "• Train adds +2 levels per session, max 20 levels per 12h\n\n"
    text += "📚 *Available Verses & Characters*\n"

    for verse, chars in ANIME_VERSES.items():
        char_list = ", ".join(chars)
        text += f"• *{verse}*: {char_list}\n"

    bot.reply_to(message, text, parse_mode="Markdown")

# ---------------- ANIME SEARCH COMMAND ---------------- #
ANIME_VERSES = {
    "Naruto": ["Naruto Uzumaki","Sasuke Uchiha","Sakura Haruno","Kakashi Hatake","Itachi Uchiha",
               "Gaara","Shikamaru Nara","Hinata Hyuga","Rock Lee","Tsunade"],
    "DBZ": ["Goku","Vegeta","Gohan","Frieza","Piccolo","Trunks","Cell","Majin Buu","Krillin","Tien"],
    "One Piece": ["Luffy","Zoro","Nami","Sanji","Usopp","Chopper","Robin","Franky","Brook","Jinbe"],
    "Bleach": ["Ichigo Kurosaki","Rukia Kuchiki","Renji Abarai","Orihime Inoue","Uryu Ishida",
               "Yasutora Sado","Kenpachi Zaraki","Byakuya Kuchiki","Toshiro Hitsugaya","Grimmjow"],
    "Seven Deadly Sins": ["Meliodas","Elizabeth","Diane","Ban","King","Gowther","Merlin","Escanor",
                           "Hawk","Arthur"],
    "Black Clover": ["Asta","Yuno","Noelle Silva","Yami Sukehiro","Finral","Luck Voltia","Magna Swing",
                     "Gauche","Charmy","Secre"]
}

RARITY_LIST = ["Common","Rare","Legendary"]

@bot.message_handler(commands=["search"])
@check_banned_user
def search_character(message):
    user = message.from_user.username
    uid = message.from_user.id
    add_command_xp(user)
    ensure_anime_user(uid)

    try:
        verse = message.text.split(maxsplit=1)[1]
    except IndexError:
        bot.reply_to(message, f"Usage: /search <anime verse>\nAvailable: {', '.join(ANIME_VERSES.keys())}")
        return

    verse = verse.strip()
    if verse not in ANIME_VERSES:
        bot.reply_to(message, f"❌ Verse not found. Available: {', '.join(ANIME_VERSES.keys())}")
        return

    # Random character
    name = random.choice(ANIME_VERSES[verse])
    rarity = random.choices(RARITY_LIST, weights=[70,25,5])[0]
    character = create_character(name, verse, rarity)

    # Ask user to accept
    msg = bot.reply_to(message, f"Found: {name} ({rarity}) from {verse}\nReply with 'yes' to recruit or 'no' to reject.")

    # Wait for answer
    def recruit_handler(reply):
        text = reply.text.lower()
        data = load_anime()

        if text == "yes":
            data[str(uid)]["characters"].append(character)
            save_anime(data)
            bot.reply_to(reply, f"✅ {name} added to your squad!")
        else:
            bot.reply_to(reply, f"❌ {name} rejected.")

        bot.remove_message_handler(recruit_handler)  # remove after use

    bot.register_next_step_handler(msg, recruit_handler)

# ---------------- CHARACTER COMMAND ---------------- #
@bot.message_handler(commands=["character"])
@check_banned_user
def show_characters(message):
    user = message.from_user.username
    uid = str(message.from_user.id)
    add_command_xp(user)
    ensure_anime_user(uid)

    data = load_anime()
    squad = data.get(uid, {}).get("characters", [])

    if not squad:
        bot.reply_to(message, "😅 You haven't recruited any characters yet. Use /search <anime verse> to find some!")
        return

    text = f"👾 @{user}'s Squad:\n\n"
    for i, c in enumerate(squad, 1):
        text += f"{i}. {c['name']} ({c['verse']}) — {c['rarity']} | Level {c['level']}\n"

    bot.reply_to(message, text)

# ---------------- TRAIN COMMAND ---------------- #
TRAIN_COOLDOWN = 3600  # 1 hour in seconds
last_train = {}  # stores uid: timestamp of last train

@bot.message_handler(commands=["train"])
@check_banned_user
def train_characters(message):
    user = message.from_user.username
    uid = str(message.from_user.id)
    add_command_xp(user)
    ensure_anime_user(uid)

    data = load_anime()
    squad = data.get(uid, {}).get("characters", [])

    if not squad:
        bot.reply_to(message, "😅 You have no characters to train. Use /search <anime verse> first!")
        return

    now = time.time()
    last = last_train.get(uid, 0)
    if now - last < TRAIN_COOLDOWN:
        remaining = int(TRAIN_COOLDOWN - (now - last))
        mins, secs = divmod(remaining, 60)
        bot.reply_to(message, f"⏳ You need to wait {mins}m {secs}s before training again.")
        return

    # Train all characters +2 levels
    for c in squad:
        c["level"] += 2

    last_train[uid] = now
    save_anime(data)
    bot.reply_to(message, f"💪 Your squad trained! All characters gained 2 levels. Come back in 1 hour for more.")

# ---------------- REMOVE CHARACTER ---------------- #
@bot.message_handler(commands=["remove"])
@check_banned_user
def remove_character(message):
    user = message.from_user.username
    uid = str(message.from_user.id)
    add_command_xp(user)
    ensure_anime_user(uid)

    data = load_anime()
    squad = data.get(uid, {}).get("characters", [])

    if not squad:
        bot.reply_to(message, "😅 You have no characters to remove.")
        return

    try:
        # Expect format: /remove <character name>
        char_name = message.text.split(maxsplit=1)[1].strip().lower()
    except IndexError:
        # List user's squad
        names = [f"{c['name']} (Lvl {c['level']})" for c in squad]
        bot.reply_to(message, f"Your squad:\n" + "\n".join(names) + 
                         "\n\nUsage: /remove <character name>")
        return

    # Find character
    for c in squad:
        if c["name"].lower() == char_name:
            squad.remove(c)
            save_anime(data)
            bot.reply_to(message, f"🗑 {c['name']} removed from your squad.")
            return

    bot.reply_to(message, f"❌ Character '{char_name}' not found in your squad.")

# ---------------- SQUAD LEADERBOARD ---------------- #
@bot.message_handler(commands=['squad_leaderboard'])
@check_banned_user
def squad_leaderboard(message):
    user = message.from_user.username
    add_command_xp(user)

    data = load_anime()  # your anime data file with all users' characters
    if not data:
        bot.reply_to(message, "No squads recruited yet 😅 Go search some anime heroes first!")
        return

    # Calculate strength per user
    rarity_bonus = {"Common": 1, "Rare": 3, "Legendary": 7}
    leaderboard = []

    for uid, info in data.items():
        characters = info.get("characters", [])
        if not characters:
            continue

        strength = sum(char["level"] + rarity_bonus.get(char["rarity"], 0) for char in characters)

        try:
            user_obj = bot.get_chat(uid)  # fetch real Telegram user
            username = f"@{user_obj.username}" if user_obj.username else user_obj.first_name
        except Exception:
            username = f"User{uid}"  # fallback

        leaderboard.append((username, strength, characters))

    if not leaderboard:
        bot.reply_to(message, "No squads recruited yet 😅 Go search some anime heroes first!")
        return

    # Sort top 10
    top = sorted(leaderboard, key=lambda x: x[1], reverse=True)[:10]

    # Build leaderboard message
    text = "🏆 *SQUAD LEADERBOARD* 🏆\n\n"
    for rank, (username, strength, chars) in enumerate(top, 1):
        text += f"*{rank}. {username} — Strength: {strength}* 💥\n"
        for c in chars:
            emoji = "✨" if c["rarity"] == "Rare" else "🌟" if c["rarity"] == "Legendary" else "⚔"
            text += f"  {emoji} {c['name']} (Lvl {c['level']}) [{c['rarity']}]\n"
        text += "\n"

    text += "🔥 Recruit, train, and dominate the anime world! 💪😎"

    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['translate'])
@check_banned_user
def translate_text(message):
    add_command_xp(message.from_user.username)

    try:
        parts = message.text.split(maxsplit=2)
        lang, text = parts[1], parts[2]

        translated = GoogleTranslator(
            source='auto',
            target=lang
        ).translate(text)

        bot.reply_to(message, f"🌐 {translated}")

    except:
        bot.reply_to(message, "Usage: /translate <lang> <text>")

@bot.message_handler(commands=['define'])
@check_banned_user
def define_word(message):
    add_command_xp(message.from_user.username)

    try:
        word = message.text.split(maxsplit=1)[1]
        res = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}")

        if res.status_code==200:
            meaning = res.json()[0]["meanings"][0]["definitions"][0]["definition"]
            bot.reply_to(message,f"📖 {word}: {meaning}")
        else:
            bot.reply_to(message,"Word not found")
    except:
        bot.reply_to(message,"Usage: /define <word>")

@bot.message_handler(commands=['remind'])
@check_banned_user
def set_reminder(message):
    add_command_xp(message.from_user.username)

    try:
        parts = message.text.split(maxsplit=2)
        mins = int(parts[1])
        text = parts[2]

        bot.reply_to(message,f"⏰ Reminder set for {mins} minutes")

        def remind():
            time.sleep(mins*60)
            bot.send_message(message.chat.id,f"🔔 Reminder: {text}")

        threading.Thread(target=remind).start()
    except:
        bot.reply_to(message,"Usage: /remind <minutes> <text>")

@bot.message_handler(commands=['rps'])
@check_banned_user
def rps_game(message):
    add_command_xp(message.from_user.username)

    try:
        choice = message.text.split()[1].lower()
        options=["rock","paper","scissors"]

        bot_choice=random.choice(options)

        if choice==bot_choice:
            result="Tie 🙆"
        elif (choice=="rock" and bot_choice=="scissors") or \
             (choice=="scissors" and bot_choice=="paper") or \
             (choice=="paper" and bot_choice=="rock"):
            result="You win 🎉"
        else:
            result="You lose 😭"

        bot.reply_to(message,f"You: {choice}\nMe: {bot_choice}\n{result}")
    except:
        bot.reply_to(message,"Usage: /rps <rock|paper|scissors>")

# ---------------- AZLYRICS FETCHER FIX ---------------- #
def fetch_azlyrics(artist: str, title: str) -> Optional[str]:
    """
    Scrapes AZLyrics for given artist and title.
    Returns lyrics string or None if not found.
    """
    try:
        # Clean artist/title for URL
        artist_clean = re.sub(r"[^a-zA-Z0-9]", "", artist.lower())
        title_clean = re.sub(r"[^a-zA-Z0-9]", "", title.lower())
        url = f"https://www.azlyrics.com/lyrics/{artist_clean}/{title_clean}.html"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }

        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, "html.parser")

        # Lyrics div is after <div class="ringtone">, no class/id itself
        divs = soup.find_all("div")
        lyrics_div = None
        for i, div in enumerate(divs):
            if 'class' in div.attrs and div['class'] == ['ringtone']:
                lyrics_div = divs[i + 1]
                break

        if not lyrics_div:
            return None

        lyrics = lyrics_div.get_text(strip=True, separator="\n")
        return lyrics

    except Exception as e:
        print(f"fetch_azlyrics error: {e}")
        return None

# ---------------- LYRICS COMMAND ---------------- #
@bot.message_handler(commands=['lyrics'])
@check_banned_user
def lyrics_cmd(message):
    if not force_join(message):
        return
    uid = str(message.from_user.id)
    add_command_xp(uid)

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or '-' not in parts[1]:
        bot.reply_to(
            message,
            "📝 Usage: /lyrics <artist> - <song title>\nExample: /lyrics Rustage - Kurama"
        )
        return

    artist, title = [x.strip() for x in parts[1].split('-', 1)]
    bot.reply_to(message, f"🔎 Searching lyrics for {artist} - {title}...")

    lyrics_text = fetch_azlyrics(artist, title)
    if lyrics_text:
        max_chars = 15000
        response = lyrics_text[:max_chars]
        if len(lyrics_text) > max_chars:
            response += "\n…(truncated)"

        try:
            bot.send_message(
                message.chat.id,
                f"🎤 Lyrics for {artist} - {title}:\n\n{response}"
            )
        except Exception as e:
            print(f"send_message error: {e}")
            bot.reply_to(message, "⚠️ Failed to send lyrics. They might be too long.")
    else:
        bot.reply_to(message, f"❌ Lyrics not found for {artist} - {title}")

# ------------------- NEW CHAT MEMBERS ------------------- #
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_members(message):
    for new_user in message.new_chat_members:
        bot.send_message(
            message.chat.id,
            f"🎉 Welcome @{new_user.username or new_user.first_name}! Enjoy Collins AI ✨"
        )

# ------------------- PRIVATE DM HANDLER ------------------- #
@bot.message_handler(func=lambda m: m.chat.type == 'private')
def handle_private_dm(message):
    user = message.from_user.username
    uid = str(message.from_user.id)
    chat_id = message.chat.id

    # ---- First Message Bonus ---- #
    if uid not in referrals_data:
        referrals_data[uid] = {"referrals": [], "coins": 2}
        bot.send_message(chat_id, "🎉 Welcome! First message bonus: +2 coins")
        save_referrals()

    # ---- Hard Block ---- #
    if user in banned_users:
        bot.reply_to(message, "🚫 You have been banned")
        return

    # ---- Admin Unlock ---- #
    if admin_wait.get(chat_id):
        if message.text == ADMIN_PASSWORD:
            admins.add(chat_id)
            save_json(ADMINS_FILE, list(admins))
            bot.reply_to(chat_id, "✅ Admin unlocked")
        else:
            bot.reply_to(chat_id, "❌ Wrong password")
        admin_wait.pop(chat_id)
        return

    # ---- Normal Bot Flow ---- #
    log_user(message)
    update_memory(message)
    ensure_user(user)
    add_message_xp(user)

    # ---- Summarize Mode ---- #
    if summarize_mode.get(user):
        ans = ask_groq(user, f"Summarize:\n{message.text}")
        bot.reply_to(message, ans)
        summarize_mode.pop(user)
        return

    # ---- Bad Word Filter ---- #
    bad_words = ["hack", "ddos", "malware", "exploit", "crack"]
    if any(word in message.text.lower() for word in bad_words):
        bot.reply_to(message, "Ethical cyber only 👨‍💻")
        return

    # ---- GROQ AI Response ---- #
    ans = ask_groq(user, message.text)
    bot.reply_to(message, ans)

# ------------------- GROUP LINK MODERATION ------------------- #
@bot.message_handler(func=lambda m: m.chat.type != 'private')
def group_link_moderation(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Check if user is admin
    try:
        member = bot.get_chat_member(chat_id, user_id)
        is_admin = member.status in ['administrator', 'creator']
    except:
        is_admin = False

    if is_admin:
        return

    # Detect links
    if any(x in message.text.lower() for x in ["http://", "https://", ".com"]):
        # Delete the offending message
        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception as e:
            print(f"Failed to delete message: {e}")

        # Track warnings
        chat_warnings = link_warnings.setdefault(chat_id, {})
        chat_warnings[user_id] = chat_warnings.get(user_id, 0) + 1
        warning_count = chat_warnings[user_id]

        # Send warning messages
        if warning_count == 1:
            bot.send_message(chat_id, f"⚠️ Warning 1: Links are not allowed, @{message.from_user.username}!")
        elif warning_count == 2:
            bot.send_message(chat_id, f"⚠️ Warning 2: Second time posting links. Next time you'll be muted, @{message.from_user.username}!")
        elif warning_count >= 3:
            until_date = int(time.time() + 24*3600)
            bot.restrict_chat_member(chat_id, user_id, can_send_messages=False, until_date=until_date)
            bot.send_message(chat_id, f"🚫 @{message.from_user.username} has been muted for 24 hours for posting links!")
            chat_warnings[user_id] = 0


# ---------------- RUN ---------------- #
import threading
from flask import Flask
import os

print("🚀 Collins AI running...")

# --- Telegram bot polling in a thread ---
def run_bot():
    while True:
        try:
            bot.polling(non_stop=True, timeout=60)
        except Exception as e:
            print(f"⚠ Bot crashed: {e}")
            print("⏳ Restarting in 5s...")
            print("Muhahahahaha...")
            time.sleep(5)

threading.Thread(target=run_bot).start()

# --- Dummy Flask server for Render free tier ---
app = Flask(__name__)

@app.route("/")
def index():
    return "Collins AI bot is running 🚀"

port = int(os.environ.get("PORT", 10000))  # Render assigns PORT automatically
app.run(host="0.0.0.0", port=port)


