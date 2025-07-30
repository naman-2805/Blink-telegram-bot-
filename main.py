import telebot
import re
import threading
import time
import json
import random
import asyncio
import aiohttp
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
from p import check_card  # Braintree चेकर
from gateways import Tele, get_nonce  # Stripe चेकर
import os
from io import BytesIO
import logging
from threading import Lock
from dotenv import load_dotenv

# इनवायरनमेंट वेरिएबल्स लोड करो
load_dotenv()

# लॉगिंग सेटअप
logging.basicConfig(level=logging.INFO, filename="bot.log", format="%(asctime)s - %(levelname)s - %(message)s")

# BOT Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "8031228487:AAGgy3Qkya3mVGvsaQWVcdWBa3rH_cFeGCI")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7567653005"))
CHANNEL_INVITE_LINK = 'https://t.me/BlinkOP2805'
CHANNEL_ID = '@BlinkOP2805'

# aiohttp के साथ telebot को ओवरराइड करें
class AiohttpBot(telebot.TeleBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = None

    async def _make_request(self, method, url, **kwargs):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        try:
            async with self.session.request(method, url, **kwargs) as response:
                return await response.json()
        except Exception as e:
            logging.error(f"Telegram API request failed: {str(e)}")
            raise

bot = AiohttpBot(BOT_TOKEN)

AUTHORIZED_USERS = {}
AUTHORIZED_GROUPS = set()
CHECK_COUNTS = {}
LAST_CHECK_TIME = {}
REGISTERED_USERS = {}
user_quantity = {}
DEFAULT_QUANTITY = 1
CREDITS = {}
CREDIT_LIMIT = 108
CREDIT_EXPIRY = {}
AUTH_LOCK = Lock()

WELCOME_VIDEO_PATH = "welcome_video.mp4"

COUNTRY_FLAGS = {
    "FRANCE": "🇫🇷", "UNITED STATES": "🇺🇸", "BRAZIL": "🇧🇷", "NAMIBIA": "🇳🇦",
    "INDIA": "🇮🇳", "GERMANY": "🇩🇪", "THAILAND": "🇹🇭", "MEXICO": "🇲🇽", "RUSSIA": "🇷🇺",
    "NEPAL": "🇳🇵", "CHINA": "🇨🇳", "ISRAEL": "🇮🇱", "PAKISTAN": "🇵🇰", "KAZAKHSTAN": "🇰🇿",
    "UAE": "🇦🇪", "CANADA": "🇨🇦", "SOUTH KOREA": "🇰🇷", "NORTH KOREA": "🇰🇵",
    "PALESTINE": "🇵🇸", "SWEDEN": "🇸🇪", "JAPAN": "🇯🇵", "MALAYSIA": "🇲🇾",
    "TAIWAN": "🇹🇼", "TURKEY": "🇹🇷", "UNITED KINGDOM": "🇬🇧", "AFGHANISTAN": "🇦🇫",
    "UZBEKISTAN": "🇺🇿", "SINGAPORE": "🇸🇬",
}

# ग्लोबल asyncio लूप
GLOBAL_LOOP = asyncio.get_event_loop() if asyncio.get_event_loop().is_running() else asyncio.new_event_loop()

# ---------------- CC Generator Functions ---------------- #

def extract_bin(bin_input):
    match = re.match(r'(\d{6,16})', bin_input)
    if not match:
        return None
    bin_number = match.group(1)
    return bin_number.ljust(16, 'x') if len(bin_number) == 6 else bin_number

async def generate_cc_async(bin_number, retries=5):
    url = f"https://drlabapis.onrender.com/api/ccgenerator?bin={bin_number}&count=10"
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        raw_text = await response.text()
                        return raw_text.strip().split("\n")
                    else:
                        logging.error(f"CC Generator API error: {response.status}")
                        return {"error": f"API error: {response.status}"}
        except Exception as e:
            logging.error(f"CC Generator attempt {attempt + 1} failed: {str(e)}")
            if attempt == retries - 1:
                return {"error": str(e)}
            await asyncio.sleep(3)

async def lookup_bin(bin_number, retries=5):
    url = f"https://drlabapis.onrender.com/api/bin?bin={bin_number[:6]}"
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        bin_data = await response.json()
                        country_name = bin_data.get('country', 'NOT FOUND').upper()
                        return {
                            "bank": bin_data.get('issuer', 'NOT FOUND').upper(),
                            "card_type": bin_data.get('type', 'NOT FOUND').upper(),
                            "network": bin_data.get('scheme', 'NOT FOUND').upper(),
                            "tier": bin_data.get('tier', 'NOT FOUND').upper(),
                            "country": country_name,
                            "flag": COUNTRY_FLAGS.get(country_name, "🏳️")
                        }
                    else:
                        logging.error(f"BIN Lookup API error: {response.status}")
                        return {"error": f"API error: {response.status}"}
        except Exception as e:
            logging.error(f"BIN Lookup attempt {attempt + 1} failed: {str(e)}")
            if attempt == retries - 1:
                return {"error": str(e)}
            await asyncio.sleep(3)

def format_cc_response(data, bin_number, bin_info):
    if isinstance(data, dict) and "error" in data:
        return f"❌ Error: {data['error']}"
    if not data:
        return "❌ No cards generated"

    formatted_text = f"BIN: {bin_number[:6]}\n"
    formatted_text += f"Amount: {len(data)}\n\n"
    for card in data[:10]:
        formatted_text += f"{card.upper()}\n"
    formatted_text += f"\nInfo: {bin_info.get('card_type', 'NOT FOUND')} {bin_info.get('network', 'NOT FOUND')} {bin_info.get('tier', 'NOT FOUND')}\n"
    formatted_text += f"Issuer: {bin_info.get('bank', 'NOT FOUND')}\n"
    formatted_text += f"Country: {bin_info.get('country', 'NOT FOUND')} {bin_info.get('flag', '🏳️')}\n"
    formatted_text += f"\nBot by: @BlinkOP28"
    return formatted_text

def generate_cc(bin_number):
    try:
        cc_data = GLOBAL_LOOP.run_until_complete(generate_cc_async(bin_number))
        bin_info = GLOBAL_LOOP.run_until_complete(lookup_bin(bin_number))
        return format_cc_response(cc_data, bin_number, bin_info)
    except Exception as e:
        logging.error(f"Generate CC error: {str(e)}")
        return f"❌ Error processing request: {e}"

# ---------------- Helper Functions ---------------- #

def load_auth():
    try:
        with AUTH_LOCK:
            with open("authorized.json", "r") as f:
                data = json.load(f)
                AUTHORIZED_USERS.update(data.get("users", {}))
                AUTHORIZED_GROUPS.update(data.get("groups", []))
                CREDITS.update(data.get("credits", {}))
                CREDIT_EXPIRY.update(data.get("credit_expiry", {}))
                return data
    except FileNotFoundError:
        save_auth({"users": {}, "groups": [], "credits": {}, "credit_expiry": {}})
        return {"users": {}, "groups": [], "credits": {}, "credit_expiry": {}}
    except json.JSONDecodeError:
        save_auth({"users": {}, "groups": [], "credits": {}, "credit_expiry": {}})
        return {"users": {}, "groups": [], "credits": {}, "credit_expiry": {}}
    except Exception as e:
        logging.error(f"Error loading auth file: {e}")
        return {"users": {}, "groups": [], "credits": {}, "credit_expiry": {}}

def save_auth(data):
    with AUTH_LOCK:
        with open("authorized.json", "w") as f:
            json.dump(data, f)

def is_authorized(chat_id, is_group=False):
    if is_group:
        return chat_id in AUTHORIZED_GROUPS
    if chat_id == ADMIN_ID:
        return True
    if str(chat_id) in AUTHORIZED_USERS:
        expiry = AUTHORIZED_USERS[str(chat_id)]
        if expiry == "forever":
            return True
        if time.time() < expiry:
            return True
        else:
            del AUTHORIZED_USERS[str(chat_id)]
            save_auth({"users": AUTHORIZED_USERS, "groups": list(AUTHORIZED_GROUPS), "credits": CREDITS, "credit_expiry": CREDIT_EXPIRY})
    return False

def normalize_card(text):
    if not text:
        return None
    text = text.replace('\n', ' ').replace('/', ' ')
    numbers = re.findall(r'\d+', text)
    cc = mm = yy = cvv = ''
    for part in numbers:
        if len(part) == 16:
            cc = part
        elif len(part) == 4 and part.startswith('20'):
            yy = part
        elif len(part) == 2 and int(part) <= 12 and mm == '':
            mm = part
        elif len(part) == 2 and not part.startswith('20') and yy == '':
            yy = '20' + part
        elif len(part) in [3, 4] and cvv == '':
            cvv = part
    if cc and mm and yy and cvv:
        return f"{cc}|{mm}|{yy}|{cvv}"
    return None

def update_daily_credits(user_id):
    current_time = time.time()
    if str(user_id) not in CREDIT_EXPIRY or current_time > CREDIT_EXPIRY[str(user_id)]:
        CREDITS[str(user_id)] = CREDIT_LIMIT
        CREDIT_EXPIRY[str(user_id)] = current_time + 86400
        save_auth({"users": AUTHORIZED_USERS, "groups": list(AUTHORIZED_GROUPS), "credits": CREDITS, "credit_expiry": CREDIT_EXPIRY})

def get_remaining_credits(user_id):
    update_daily_credits(user_id)
    return CREDITS.get(str(user_id), 0)

def deduct_credits(user_id, amount):
    update_daily_credits(user_id)
    if CREDITS.get(str(user_id), 0) >= amount:
        CREDITS[str(user_id)] -= amount
        save_auth({"users": AUTHORIZED_USERS, "groups": list(AUTHORIZED_GROUPS), "credits": CREDITS, "credit_expiry": CREDIT_EXPIRY})
        return True
    return False

auth_data = load_auth()
AUTHORIZED_USERS = auth_data.get("users", {})
AUTHORIZED_GROUPS = set(auth_data.get("groups", []))
CREDITS = auth_data.get("credits", {})
CREDIT_EXPIRY = auth_data.get("credit_expiry", {})

# ---------------- Broadcast Command ---------------- #

@bot.message_handler(commands=['broadcast'])
def broadcast_handler(msg):
    if msg.from_user.id != ADMIN_ID and not is_authorized(msg.from_user.id):
        return bot.reply_to(msg, "❌ Only owner or authorized admins can broadcast, bhai!")
    
    parts = msg.text.split(None, 1)
    if len(parts) < 2:
        return bot.reply_to(msg, "❌ Usage: /broadcast <message>")
    
    broadcast_msg = parts[1]
    success_count = 0
    fail_count = 0
    errors = []

    all_targets = list(AUTHORIZED_USERS.keys()) + [str(chat_id) for chat_id in AUTHORIZED_GROUPS]
    for target_id in all_targets:
        try:
            bot.send_message(int(target_id), f"📢 Broadcast Message:\n{broadcast_msg}")
            success_count += 1
            time.sleep(1)
        except telebot.apihelper.ApiTelegramException as e:
            fail_count += 1
            errors.append(f"Target {target_id}: {str(e)}")
            logging.error(f"Broadcast failed for {target_id}: {str(e)}")
            if "chat not found" in str(e).lower() or "blocked" in str(e).lower():
                if str(target_id) in AUTHORIZED_USERS:
                    del AUTHORIZED_USERS[str(target_id)]
                elif int(target_id) in AUTHORIZED_GROUPS:
                    AUTHORIZED_GROUPS.remove(int(target_id))
                save_auth({"users": AUTHORIZED_USERS, "groups": list(AUTHORIZED_GROUPS), "credits": CREDITS, "credit_expiry": CREDIT_EXPIRY})

    response = f"✅ Broadcast sent, bhai!\n📩 {success_count} successful\n❌ {fail_count} failed"
    if errors:
        response += "\n\nErrors:\n" + "\n".join(errors)
    bot.reply_to(msg, response)

# ---------------- Start Command ---------------- #

@bot.message_handler(commands=['start'])
def start_handler(msg):
    user = msg.from_user
    username = user.username if user.username else "Unknown"
    user_id = user.id
    user_type = "Owner" if user_id == ADMIN_ID else "Free User" if str(user_id) not in AUTHORIZED_USERS or AUTHORIZED_USERS.get(str(user_id)) == "forever" else "Paid User"

    markup = InlineKeyboardMarkup()
    register_button = InlineKeyboardButton("Join Channel", url=CHANNEL_INVITE_LINK)
    markup.add(register_button)

    def send_welcome_video():
        try:
            if os.path.exists(WELCOME_VIDEO_PATH):
                with open(WELCOME_VIDEO_PATH, 'rb') as video:
                    bot.send_video(
                        chat_id=msg.chat.id,
                        video=video,
                        supports_streaming=True,
                        caption=f"""
━━━━━━━━━━━━━━━━━━━      
⌬ 𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗠𝗘𝗦𝗦𝗔𝗚𝗘

[↯]𝗡𝗮𝗺𝗲: {username}
⌬ 𝗦𝘁𝗮𝘁𝘂𝘀: New Member
[↯]𝗠𝗲𝗺𝗯𝗲𝗿: {user_type}

[↯] 𝗦𝘁𝗮𝗿𝘁: /register
⌬ 𝗡𝗼𝘁𝗲: Click below to join Our official channel and Click On register!
━━━━━━━━━━━━━━━━━━━
""",
                        reply_markup=markup
                    )
            else:
                bot.send_message(msg.chat.id, "❌ Welcome video file not found. Please add 'welcome_video.mp4' in the directory.", reply_markup=markup)
        except Exception as e:
            logging.error(f"Welcome video error: {str(e)}")
            bot.send_message(msg.chat.id, f"❌ Error sending welcome video: {str(e)}", reply_markup=markup)

    threading.Thread(target=send_welcome_video).start()

# ---------------- Register Command ---------------- #

@bot.message_handler(commands=['register'])
def register_handler(msg):
    user = msg.from_user
    username = user.username if user.username else "Unknown"
    user_id = user.id

    try:
        member = bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            REGISTERED_USERS[str(user_id)] = True
            save_auth({"users": AUTHORIZED_USERS, "groups": list(AUTHORIZED_GROUPS), "credits": CREDITS, "credit_expiry": CREDIT_EXPIRY})
            bot.reply_to(msg, f"""
━━━━━━━━━━━━━━━━━━━      
[↯] 𝗥𝗘𝗚𝗜𝗦𝗧𝗥𝗔𝗧𝗜𝗢𝗡 𝗦𝗧𝗔𝗧𝗨𝗦

⌬ 𝗦𝘁𝗮𝘁𝘂𝘀: Registration Successful
[↯]𝗨𝘀𝗲𝗿: @{username}
⌬ 𝗜𝗗: {user_id}

⌬ 𝗔𝘃𝗮𝗶𝗹𝗮𝗯𝗹𝗲 𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀: For All Member:
• /b3 - Braintree Premium Auth (1 Credit)
• /cc - Stripe Charger (2 Credits)
• /gen - For Generate Card Of Any B!N
• /redeem - Redeem Code For Paid Access 
• /id - Your User ID 🪪 
• /bin - Check BIN Details
• /img - Generate Images
• /quantity - Set Image Quantity (1-5)
• /credits - Check Remaining Credits
━━━━━━━━━━━━━━━━━━━
""")
        else:
            bot.reply_to(msg, f"❌ 𝙼𝚊𝚔𝚎 𝚂𝚞𝚛𝚎 𝙹𝚘𝚒𝚗 𝙾𝚞𝚛 𝙲𝚑𝚊𝚗𝚗𝚎𝚕: {CHANNEL_INVITE_LINK}")
    except telebot.apihelper.ApiException as e:
        logging.error(f"Register error: {str(e)}")
        bot.reply_to(msg, f"𝙹𝚘𝚒𝚗 𝙾𝚞𝚛 𝙾𝚏𝚏𝚒𝚌𝚎 𝙲𝚑𝚊𝚗𝚗𝚎𝚜 𝙰𝚗𝚍 𝚂𝚝𝚊𝚰𝚝 𝙱𝚘𝚝 {CHANNEL_INVITE_LINK} or contact admin.")

# ---------------- ID Command ---------------- #

@bot.message_handler(commands=['id'])
def id_handler(msg):
    user = msg.from_user
    user_id = user.id
    try:
        member = bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status not in ['member', 'administrator', 'creator']:
            return bot.reply_to(msg, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
    except telebot.apihelper.ApiException:
        return bot.reply_to(msg, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
    bot.reply_to(msg, f"🪪 Your User ID: {user_id}")

# ---------------- Credits Command ---------------- #

@bot.message_handler(commands=['credits'])
def credits_handler(msg):
    user_id = msg.from_user.id
    try:
        member = bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status not in ['member', 'administrator', 'creator']:
            return bot.reply_to(msg, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
    except telebot.apihelper.ApiException:
        return bot.reply_to(msg, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
    remaining = get_remaining_credits(user_id)
    expiry_time = datetime.fromtimestamp(CREDIT_EXPIRY.get(str(user_id), 0)).strftime('%Y-%m-%d %H:%M:%S')
    bot.reply_to(msg, f"💰 Remaining Credits: {remaining}/{CREDIT_LIMIT}\n⏰ Expiry: {expiry_time} IST")

# ---------------- CC Generator Command ---------------- #

@bot.message_handler(commands=['gen'])
def gen_command(message):
    user_id = message.from_user.id
    try:
        member = bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status not in ['member', 'administrator', 'creator']:
            return bot.send_message(message.chat.id, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
    except telebot.apihelper.ApiException:
        return bot.send_message(message.chat.id, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")

    try:
        command_parts = message.text.split(' ', 1)
        if len(command_parts) < 2:
            bot.send_message(message.chat.id, "❌ Please provide a BIN. Usage: /gen <bin>")
            return

        bin_number = re.match(r'(\d{6,16})', command_parts[1])
        if not bin_number:
            bot.send_message(message.chat.id, "❌ Invalid BIN format.")
            return

        bin_number = bin_number.group(1).ljust(16, 'x') if len(bin_number.group(1)) == 6 else bin_number.group(1)

        def process_gen():
            try:
                cc_data = GLOBAL_LOOP.run_until_complete(generate_cc_async(bin_number))
                bin_info = GLOBAL_LOOP.run_until_complete(lookup_bin(bin_number))
                if isinstance(cc_data, dict) and "error" in cc_data:
                    bot.send_message(message.chat.id, f"❌ Error: {cc_data['error']}")
                else:
                    formatted_text = format_cc_response(cc_data, bin_number, bin_info)
                    bot.send_message(message.chat.id, formatted_text)
            except Exception as e:
                logging.error(f"Gen command error: {str(e)}")
                bot.send_message(message.chat.id, f"❌ Error processing request: {e}")

        threading.Thread(target=process_gen).start()

    except Exception as e:
        logging.error(f"Gen command error: {str(e)}")
        bot.send_message(message.chat.id, f"❌ Error: {e}")

# ---------------- Image Generation Functions ---------------- #

def generate_image_url(prompt: str = ""):
    base_url = "https://image.pollinations.ai/prompt/"
    seed = random.randint(1000000000, 9999999999)
    full_url = f"{base_url}{prompt.replace(' ', '%20')}?width=512&height=512&seed={seed}&nologo=true&model=flux-pro"
    return full_url

async def download_image_async(url, retries=5, timeout=30):
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        return BytesIO(await response.read())
                    else:
                        logging.error(f"Image download failed with status: {response.status}")
                        return None
        except Exception as e:
            logging.error(f"Image download attempt {attempt + 1} failed: {str(e)}")
            if attempt < retries - 1:
                await asyncio.sleep(3)
            else:
                return None

def process_image_request(chat_id, message_id, prompt, quantity):
    start_time = time.time()
    try:
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🖌 Generating your images... Please wait! 😊")
        images = []
        for _ in range(min(quantity, 3)):
            image_url = generate_image_url(prompt)
            image_data = GLOBAL_LOOP.run_until_complete(download_image_async(image_url))
            if image_data:
                images.append(image_data)
            else:
                bot.send_message(chat_id, f"❌ Failed to generate image {_ + 1}: Timeout or network issue.")
                break
        if images:
            media_group = [telebot.types.InputMediaPhoto(image, caption=f"🌟 Image {_ + 1} for: {prompt}") for _, image in enumerate(images)]
            bot.send_media_group(chat_id, media=media_group)
        else:
            bot.send_message(chat_id, "❌ No images generated. Check your prompt or network.")
    except Exception as e:
        logging.error(f"Image generation error: {str(e)}")
        bot.send_message(chat_id, f"❌ Error: {str(e)}")
    finally:
        try:
            bot.delete_message(chat_id, message_id)
        except Exception:
            pass
        end_time = time.time()
        logging.info(f"Image generation took {end_time - start_time:.2f} seconds")

@bot.message_handler(commands=["img"])
def send_images(message):
    user_id = message.from_user.id
    try:
        member = bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status not in ['member', 'administrator', 'creator']:
            return bot.send_message(message.chat.id, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
    except telebot.apihelper.ApiException:
        return bot.send_message(message.chat.id, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
    
    text = message.text.strip()
    if len(text.split(maxsplit=1)) > 1:
        prompt = text.split(maxsplit=1)[1]
    else:
        bot.send_message(message.chat.id, "⚠️ Use a prompt after /img command! Example: /img a beautiful landscape")
        return
    
    quantity = user_quantity.get(message.chat.id, DEFAULT_QUANTITY)
    wait_message = bot.reply_to(message, "⏳ Generating images...")
    threading.Thread(target=lambda: process_image_request(message.chat.id, wait_message.message_id, prompt, quantity), daemon=True).start()

@bot.message_handler(func=lambda message: message.text.startswith(('.img', '!img')))
def alias_commands(message):
    user_id = message.from_user.id
    try:
        member = bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status not in ['member', 'administrator', 'creator']:
            return bot.send_message(message.chat.id, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
    except telebot.apihelper.ApiException:
        return bot.send_message(message.chat.id, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
    
    message.text = message.text.replace('.img', '/img').replace('!img', '/img', 1)
    send_images(message)

@bot.message_handler(commands=["quantity"])
def set_quantity(message):
    user_id = message.from_user.id
    try:
        member = bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status not in ['member', 'administrator', 'creator']:
            return bot.send_message(message.chat.id, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
    except telebot.apihelper.ApiException:
        return bot.send_message(message.chat.id, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
    
    text = message.text.strip()
    if len(text.split(maxsplit=1)) > 1:
        try:
            quantity = int(text.split(maxsplit=1)[1])
            if 1 <= quantity <= 5:
                user_quantity[message.chat.id] = quantity
                bot.reply_to(message, f"✅ Quantity set to {quantity} images per request.")
            else:
                bot.reply_to(message, "⚠️ Please choose a quantity between 1 and 5.")
        except ValueError:
            bot.reply_to(message, "⚠️ Please provide a valid number between 1 and 5.")
    else:
        bot.reply_to(message, "⚠️ Please specify a quantity. Example: /quantity 3")

# ---------------- BIN Command ---------------- #

@bot.message_handler(commands=['bin'])
def bin_handler(msg):
    user_id = msg.from_user.id
    try:
        member = bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status not in ['member', 'administrator', 'creator']:
            return bot.reply_to(msg, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
    except telebot.apihelper.ApiException:
        return bot.reply_to(msg, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
    
    try:
        args = msg.text.split(None, 1)
        if len(args) < 2:
            bot.reply_to(msg, "❌ Please provide a BIN. Usage: /bin <bin_number>")
            return

        bin_number = args[1][:6]
        user = msg.from_user
        username = user.username if user.username else "Unknown"

        bin_info = GLOBAL_LOOP.run_until_complete(lookup_bin(bin_number))
        if isinstance(bin_info, dict) and "error" in bin_info:
            bot.reply_to(msg, f"❌ Error: {bin_info['error']}")
            return

        country_name = bin_info.get('country', 'NOT FOUND').upper()
        vbv_status = "❌ VBV ❌" if bin_info.get('card_type', '').lower() in ['vbv', 'verified_by_visa'] else "✅ Non VBV ✅"
        bot.reply_to(msg, f"""
━━━━ 🏦 Valid BIN ☂️ ━━━━

🍀 BIN ➜ {bin_number}
🏦 Bank ➜ {bin_info.get('bank', 'NOT FOUND')}
🌍 Country ➜ {country_name} {bin_info.get('flag', '🏳️')}
💳 Info ➜ {bin_info.get('card_type', 'NOT FOUND')} {bin_info.get('network', 'NOT FOUND')} {bin_info.get('tier', 'NOT FOUND')}
{vbv_status}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Checked By: @{username}

💀 Bot Made By: @BlinkOP28
""")
    except Exception as e:
        logging.error(f"BIN command error: {str(e)}")
        bot.reply_to(msg, f"❌ Error: {str(e)}")

# ---------------- Auth Commands ---------------- #

@bot.message_handler(commands=['auth'])
def authorize_user(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            bot.reply_to(msg, "❌ Usage: /auth <user_id> [days] or /auth <group_id> [days]")
            return
        target_id = parts[1]
        days = int(parts[2]) if len(parts) > 2 else None
        if target_id.startswith('@'):
            bot.reply_to(msg, "❌ Use numeric Telegram ID or group ID, not @username")
            return
        target_id = int(target_id)
        expiry = "forever" if not days else time.time() + (days * 86400)
        is_group = msg.chat.type in ['group', 'supergroup']
        if is_group and target_id == msg.chat.id:
            AUTHORIZED_GROUPS.add(target_id)
            save_auth({"users": AUTHORIZED_USERS, "groups": list(AUTHORIZED_GROUPS), "credits": CREDITS, "credit_expiry": CREDIT_EXPIRY})
            bot.reply_to(msg, f"✅ Authorized group {target_id} for {days} days" if days else f"✅ Authorized group {target_id} forever")
        AUTHORIZED_USERS[str(target_id)] = expiry
        save_auth({"users": AUTHORIZED_USERS, "groups": list(AUTHORIZED_GROUPS), "credits": CREDITS, "credit_expiry": CREDIT_EXPIRY})
        bot.reply_to(msg, f"✅ Authorized user {target_id} for {days} days" if days else f"✅ Authorized user {target_id} forever")
    except ValueError:
        bot.reply_to(msg, "❌ Invalid input. Use numeric ID and optional days.")
    except Exception as e:
        logging.error(f"Auth command error: {str(e)}")
        bot.reply_to(msg, f"❌ Error: {e}")

@bot.message_handler(commands=['rm'])
def remove_auth(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, "❌ Usage: /rm <user_id> or /rm <group_id>")
        target_id = int(parts[1])
        is_group = msg.chat.type in ['group', 'supergroup']
        if is_group and target_id == msg.chat.id:
            if target_id in AUTHORIZED_GROUPS:
                AUTHORIZED_GROUPS.remove(target_id)
                save_auth({"users": AUTHORIZED_USERS, "groups": list(AUTHORIZED_GROUPS), "credits": CREDITS, "credit_expiry": CREDIT_EXPIRY})
                bot.reply_to(msg, f"✅ Removed group {target_id} from authorized")
            else:
                bot.reply_to(msg, "❌ Group is not authorized")
        else:
            if str(target_id) in AUTHORIZED_USERS:
                del AUTHORIZED_USERS[str(target_id)]
                save_auth({"users": AUTHORIZED_USERS, "groups": list(AUTHORIZED_GROUPS), "credits": CREDITS, "credit_expiry": CREDIT_EXPIRY})
                bot.reply_to(msg, f"✅ Removed user {target_id} from authorized")
            else:
                bot.reply_to(msg, "❌ User is not authorized")
    except Exception as e:
        logging.error(f"Remove auth command error: {str(e)}")
        bot.reply_to(msg, f"❌ Error: {e}")

@bot.message_handler(commands=['code'])
def generate_code(msg):
    if msg.from_user.id != ADMIN_ID:
        return bot.reply_to(msg, "❌ Only the owner can generate codes")
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, "❌ Usage: /code <days> [num]")
        days = int(parts[1])
        num = int(parts[2]) if len(parts) > 2 else 1
        if days <= 0 or num <= 0:
            return bot.reply_to(msg, "❌ Days and number must be positive")
        codes = []
        for _ in range(num):
            code = f"PREM_{int(time.time())}_{days}_{_}"
            expiry = time.time() + (days * 86400)
            AUTHORIZED_USERS[code] = expiry
            save_auth({"users": AUTHORIZED_USERS, "groups": list(AUTHORIZED_GROUPS), "credits": CREDITS, "credit_expiry": CREDIT_EXPIRY})
            codes.append(code)
        bot.reply_to(msg, f"✅ Generated {num} code(s) valid for {days} days:\n" + "\n".join([f"{c}" for c in codes]))
    except ValueError:
        bot.reply_to(msg, "❌ Invalid days or number value. Use numbers")
    except Exception as e:
        logging.error(f"Code command error: {str(e)}")
        bot.reply_to(msg, f"❌ Error: {e}")

@bot.message_handler(commands=['redeem'])
def redeem_code(msg):
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, "❌ Usage: /redeem <code>")
        code = parts[1]
        user_id = msg.from_user.id
        try:
            member = bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return bot.reply_to(msg, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
        except telebot.apihelper.ApiException:
            return bot.reply_to(msg, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
        if code in AUTHORIZED_USERS:
            expiry = AUTHORIZED_USERS[code]
            if expiry == "forever" or (isinstance(expiry, (int, float)) and time.time() < expiry):
                if str(user_id) in AUTHORIZED_USERS and AUTHORIZED_USERS[str(user_id)] != "forever":
                    del AUTHORIZED_USERS[str(user_id)]
                AUTHORIZED_USERS[str(user_id)] = expiry
                del AUTHORIZED_USERS[code]
                save_auth({"users": AUTHORIZED_USERS, "groups": list(AUTHORIZED_GROUPS), "credits": CREDITS, "credit_expiry": CREDIT_EXPIRY})
                bot.reply_to(msg, f"✅ Redeemed code `{code}` successfully! You now have premium access until {datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M:%S')} if applicable")
            else:
                bot.reply_to(msg, "❌ This code has expired")
        else:
            bot.reply_to(msg, "❌ Invalid redeem code")
    except Exception as e:
        logging.error(f"Redeem command error: {str(e)}")
        bot.reply_to(msg, f"❌ Error: {e}")

# ---------------- Braintree Commands (/b3, /mb3) ---------------- #

@bot.message_handler(commands=['b3'])
def b3_handler(msg):
    user_id = msg.from_user.id
    try:
        member = bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status not in ['member', 'administrator', 'creator']:
            return bot.reply_to(msg, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
    except telebot.apihelper.ApiException:
        return bot.reply_to(msg, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")

    chat_id = msg.chat.id
    is_group = msg.chat.type in ['group', 'supergroup']
    if is_group and not is_authorized(chat_id, is_group):
        bot.reply_to(msg, """❌ Invalid Format

- You are not authorized to use this bot in this group
- Only authorized groups can use this bot

Contact admin if you need help""")
        return

    cc = None
    if msg.reply_to_message:
        replied_text = msg.reply_to_message.text or ""
        cc = normalize_card(replied_text)
        if not cc:
            return bot.reply_to(msg, """✦━━━[ ɪɴᴠᴀʟɪᴅ ꜰᴏʀᴍᴀᴛ ]━━━✦

⟡ ᴘʟᴇᴀꜱᴇ ᴜꜱᴇ ᴛʜᴇ ᴄᴏʀʀᴇᴄᴛ ꜰᴏʀᴍᴀᴛ ᴛᴏ ᴄʜᴇᴄᴋ ᴄᴀʀᴅꜱ

ᴄᴏʀʀᴇᴄᴛ ꜰᴏʀᴍᴀᴛ

`/b3 4556737586899855|12|2026|123`

ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇꜱꜱᴀɢᴇ ᴄᴏɴᴛᴀɪɴɪɴɢ ᴄᴄ ᴡɪᴛʜ `/b3 and /cc`

✧ ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ɪꜰ ʏᴏᴜ ɴᴇᴇᴅ ʜᴇʟᴘ""")
    else:
        args = msg.text.split(None, 1)
        if len(args) < 2:
            return bot.reply_to(msg, """✦━━━[ ɪɴᴠᴀʟɪᴅ ꜰᴏʀᴍᴀᴛ ]━━━✦

⟡ ᴘʟᴇᴀꜱᴇ ᴜꜱᴇ ᴛʜᴇ ᴄᴏʀʀᴇᴄᴛ ꜰᴏʀᴍᴀᴛ ᴛᴏ ᴄʜᴇᴄᴋ ᴄᴀʀᴅꜱ

ᴄᴏʀʀᴇᴄᴛ ꜰᴏʀᴍᴀᴛ

`/b3 4556737586899855|12|2026|123`

ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇꜱꜱᴀɢᴇ ᴄᴏɴᴛᴀɪɴɪɴɢ ᴄᴄ ᴡɪᴛʜ `/b3 and /cc`

✧ ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ɪꜰ ʏᴏᴜ ɴᴇᴇᴅ ʜᴇʟᴘ""")
        raw_input = args[1]
        if re.match(r'^\d{16}\|\d{2}\|\d{2,4}\|\d{3,4}$', raw_input):
            cc = raw_input
        else:
            cc = normalize_card(raw_input)
            if not cc:
                cc = raw_input

    if not is_authorized(user_id) and not is_authorized(chat_id, is_group):
        if not deduct_credits(user_id, 1):
            bot.reply_to(msg, f"❌ Insufficient credits. You have {get_remaining_credits(user_id)} credits left. Wait until tomorrow for 108 new credits.")
            return
        CHECK_COUNTS[str(user_id)] = CHECK_COUNTS.get(str(user_id), 0) + 1
        if CHECK_COUNTS[str(user_id)] % 3 == 0:
            last_time = LAST_CHECK_TIME.get(str(user_id), 0)
            if time.time() - last_time < 6:
                return bot.reply_to(msg, f"⏳ Please wait {6 - (time.time() - last_time):.1f} seconds before checking another card")

    processing = bot.reply_to(msg, """⏳ Processing (Braintree)

- Your card is being checked...
- Please wait a few seconds

🚫 Do not spam or resubmit""")

    def check_and_reply():
        try:
            result = asyncio.run(check_card(cc, retries=5))
            if "Authorization failed" in result:
                bot.edit_message_text("❌ Authorization failed. Please update cookies or token in p.py with fresh ones from Braintree sandbox.", msg.chat.id, processing.message_id)
            else:
                bot.edit_message_text(result, msg.chat.id, processing.message_id)
        except Exception as e:
            logging.error(f"Braintree check error: {str(e)}")
            bot.edit_message_text(f"❌ Error: {str(e)}", msg.chat.id, processing.message_id)

    threading.Thread(target=check_and_reply).start()
    if not is_authorized(user_id) and not is_authorized(chat_id, is_group):
        LAST_CHECK_TIME[str(user_id)] = time.time()

@bot.message_handler(commands=['mb3'])
def mb3_handler(msg):
    user_id = msg.from_user.id
    try:
        member = bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status not in ['member', 'administrator', 'creator']:
            return bot.reply_to(msg, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
    except telebot.apihelper.ApiException:
        return bot.reply_to(msg, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")

    chat_id = msg.chat.id
    if not (msg.from_user.id == ADMIN_ID or (str(user_id) in AUTHORIZED_USERS and AUTHORIZED_USERS[str(user_id)] == "forever")):
        bot.reply_to(msg, "❌ This command is only for VIP members (Owner or forever authorized users).")
        return

    if not is_authorized(chat_id, True):
        last_time = LAST_CHECK_TIME.get(str(user_id), 0)
        if time.time() - last_time < 300:
            return bot.reply_to(msg, f"⏳ Please wait {300 - (time.time() - last_time):.1f} seconds before using /mb3 again")

    if not msg.reply_to_message:
        return bot.reply_to(msg, """❌ Invalid Format

- Please reply to a .txt file or credit card text

Contact admin if you need help""")

    reply = msg.reply_to_message
    if reply.document:
        file_info = bot.get_file(reply.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        text = downloaded_file.decode('utf-8', errors='ignore')
    else:
        text = reply.text or ""
        if not text.strip():
            return bot.reply_to(msg, "❌ Empty text message")

    cc_lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        normalized_cc = normalize_card(line)
        if normalized_cc:
            cc_lines.append(normalized_cc)
        else:
            found = re.findall(r'\b(?:\d[ -]*?){13,16}\b.*?\|.*?\|.*?\|.*', line)
            if found:
                cc_lines.extend(found)
            else:
                parts = re.findall(r'\d{12,16}[|: -]\d{1,2}[|: -]\d{2,4}[|: -]\d{3,4}', line)
                cc_lines.extend(parts)

    if not cc_lines:
        return bot.reply_to(msg, """❌ Invalid Format

- No valid credit cards detected in the file
- Please make sure the cards are in correct format: 4556737586899855|12|2026|123

Contact admin if you need help""")

    if not reply.document and len(cc_lines) > 15:
        return bot.reply_to(msg, """❌ Invalid Format

- Only 15 cards allowed in raw paste
- For more cards, please upload a .txt file

Contact admin if you need help""")

    total = len(cc_lines)
    kb = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton(f"Approved 0 ✅", callback_data="none"),
        InlineKeyboardButton(f"Declined 0 ❌", callback_data="none"),
        InlineKeyboardButton(f"Total Checked 0", callback_data="none"),
        InlineKeyboardButton(f"Total {total} ✅", callback_data="none"),
        InlineKeyboardButton("Stop 🛑", callback_data="stop_mb3")
    ]
    for btn in buttons:
        kb.add(btn)

    status_msg = bot.reply_to(msg, """⏳ Processing (Braintree)

- Your cards are being checked...
- Please wait a few moments

🚫 Do not spam or resubmit""", reply_markup=kb)

    approved, declined, checked = 0, 0, 0
    stop_flag = False

    def process_all():
        nonlocal approved, declined, checked, stop_flag
        for cc in cc_lines:
            if stop_flag:
                break
            try:
                checked += 1
                result = asyncio.run(check_card(cc.strip(), retries=5))
                if "[APPROVED]" in result:
                    approved += 1
                    bot.send_message(user_id, result)
                    if ADMIN_ID != user_id:
                        bot.send_message(ADMIN_ID, f"✅ Approved by {user_id}:\n{result}")
                else:
                    declined += 1
                new_kb = InlineKeyboardMarkup(row_width=2)
                new_kb.add(
                    InlineKeyboardButton(f"Approved {approved} ✅", callback_data="none"),
                    InlineKeyboardButton(f"Declined {declined} ❌", callback_data="none"),
                    InlineKeyboardButton(f"Total Checked {checked}", callback_data="none"),
                    InlineKeyboardButton(f"Total {total} ✅", callback_data="none"),
                    InlineKeyboardButton("Stop 🛑", callback_data="stop_mb3")
                )
                bot.edit_message_reply_markup(user_id, status_msg.message_id, reply_markup=new_kb)
                time.sleep(2)
            except Exception as e:
                logging.error(f"Mass Braintree check error: {str(e)}")
                bot.send_message(user_id, f"❌ Error: {e}")

        if not stop_flag:
            bot.send_message(user_id, """✅ Checking Completed (Braintree)

- All cards have been processed
- Thank you for using mass check

ℹ️ Only approved cards were shown to you""")
        else:
            bot.send_message(user_id, "🛑 Mass checking stopped by user.")

    @bot.callback_query_handler(func=lambda call: call.data == "stop_mb3")
    def stop_mb3_handler(call):
        nonlocal stop_flag
        stop_flag = True
        bot.answer_callback_query(call.id, "🛑 Mass checking stopped!")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

    threading.Thread(target=process_all).start()
    if not is_authorized(user_id) and not is_authorized(chat_id, True):
        LAST_CHECK_TIME[str(user_id)] = time.time()

# ---------------- Stripe Commands (/cc, /mcc) ---------------- #

@bot.message_handler(commands=['cc'])
def cc_handler(msg):
    user_id = msg.from_user.id
    try:
        member = bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status not in ['member', 'administrator', 'creator']:
            return bot.reply_to(msg, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
    except telebot.apihelper.ApiException:
        return bot.reply_to(msg, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")

    chat_id = msg.chat.id
    is_group = msg.chat.type in ['group', 'supergroup']
    if is_group and not is_authorized(chat_id, is_group):
        bot.reply_to(msg, """❌ Invalid Format

- You are not authorized to use this bot in this group
- Only authorized groups can use this bot

Contact admin if you need help""")
        return

    cc = None
    if msg.reply_to_message:
        replied_text = msg.reply_to_message.text or ""
        cc = normalize_card(replied_text)
        if not cc:
            return bot.reply_to(msg, """✦━━━[ ɪɴᴠᴀʟɪᴅ ꜰᴏʀᴍᴀᴛ ]━━━✦

⟡ ᴘʟᴇᴀꜱᴇ ᴜꜱᴇ ᴛʜᴇ ᴄᴏʀʀᴇᴄᴛ ꜰᴏʀᴍᴀᴛ ᴛᴏ ᴄʜᴇᴄᴋ ᴄᴀʀᴅꜱ

ᴄᴏʀʀᴇᴄᴛ ꜰᴏʀᴍᴀᴛ

/cc 4556737586899855|12|2026|123

ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇꜱꜱᴀɢᴇ ᴄᴏɴᴛᴀɪɴɪɴɢ ᴄᴄ ᴡɪᴛʜ /b3 and /cc

✧ ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ɪꜰ ʏᴏᴜ ɴᴇᴇᴅ ʜᴇʟᴘ""")
    else:
        args = msg.text.split(None, 1)
        if len(args) < 2:
            return bot.reply_to(msg, """✦━━━[ ɪɴᴠᴀʟɪᴅ ꜰᴏʀᴍᴀᴛ ]━━━✦

⟡ ᴘʟᴇᴀꜱᴇ ᴜꜱᴇ ᴛʜᴇ ᴄᴏʀʀᴇᴄᴛ ꜰᴏʀᴍᴀᴛ ᴛᴏ ᴄʜᴇᴄᴋ ᴄᴀʀᴅꜱ

ᴄᴏʀʀᴇᴄᴛ ꜰᴏʀᴍᴀᴛ

/cc 4556737586899855|12|2026|123

ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇꜱꜱᴀɢᴇ ᴄᴏɴᴛᴀɪɴɪɴɢ ᴄᴄ ᴡɪᴛʜ /b3 and /cc

✧ ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ɪꜰ ʏᴏᴜ ɴᴇᴇᴅ ʜᴇʟᴘ""")
        raw_input = args[1]
        if re.match(r'^\d{16}\|\d{2}\|\d{2,4}\|\d{3,4}$', raw_input):
            cc = raw_input
        else:
            cc = normalize_card(raw_input)
            if not cc:
                cc = raw_input

    if not is_authorized(user_id) and not is_authorized(chat_id, is_group):
        if not deduct_credits(user_id, 2):
            bot.reply_to(msg, f"❌ Insufficient credits. You have {get_remaining_credits(user_id)} credits left. Wait until tomorrow for 108 new credits.")
            return
        CHECK_COUNTS[str(user_id)] = CHECK_COUNTS.get(str(user_id), 0) + 1
        if CHECK_COUNTS[str(user_id)] % 3 == 0:
            last_time = LAST_CHECK_TIME.get(str(user_id), 0)
            if time.time() - last_time < 6:
                return bot.reply_to(msg, f"⏳ Please wait {6 - (time.time() - last_time):.1f} seconds before checking another card")

    processing = bot.reply_to(msg, """⏳ Processing (Stripe)

- Your card is being checked...
- Please wait a few seconds

🚫 Do not spam or resubmit""")

    def check_and_reply():
        try:
            result = asyncio.run(Tele(cc, retries=5))
            if "Authorization failed" in result:
                bot.edit_message_text("❌ Authorization failed. Please check API key in gateways.py or contact admin.", msg.chat.id, processing.message_id)
            else:
                bot.edit_message_text(result, msg.chat.id, processing.message_id)
        except Exception as e:
            logging.error(f"Stripe check error: {str(e)}")
            bot.edit_message_text(f"❌ Error: {str(e)}", msg.chat.id, processing.message_id)

    threading.Thread(target=check_and_reply).start()
    if not is_authorized(user_id) and not is_authorized(chat_id, is_group):
        LAST_CHECK_TIME[str(user_id)] = time.time()

@bot.message_handler(commands=['mcc'])
def mcc_handler(msg):
    user_id = msg.from_user.id
    try:
        member = bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status not in ['member', 'administrator', 'creator']:
            return bot.reply_to(msg, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")
    except telebot.apihelper.ApiException:
        return bot.reply_to(msg, f"❌ Join our channel first: {CHANNEL_INVITE_LINK}")

    chat_id = msg.chat.id
    if not (msg.from_user.id == ADMIN_ID or (str(user_id) in AUTHORIZED_USERS and AUTHORIZED_USERS[str(user_id)] == "forever")):
        bot.reply_to(msg, "❌ This command is only for VIP members (Owner or forever authorized users).")
        return

    if not is_authorized(chat_id, True):
        last_time = LAST_CHECK_TIME.get(str(user_id), 0)
        if time.time() - last_time < 300:
            return bot.reply_to(msg, f"⏳ Please wait {300 - (time.time() - last_time):.1f} seconds before using /mcc again")

    if not msg.reply_to_message:
        return bot.reply_to(msg, """❌ Invalid Format

- Please reply to a .txt file or credit card text

Contact admin if you need help""")

    reply = msg.reply_to_message
    if reply.document:
        file_info = bot.get_file(reply.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        text = downloaded_file.decode('utf-8', errors='ignore')
    else:
        text = reply.text or ""
        if not text.strip():
            return bot.reply_to(msg, "❌ Empty text message")

    cc_lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        normalized_cc = normalize_card(line)
        if normalized_cc:
            cc_lines.append(normalized_cc)
        else:
            found = re.findall(r'\b(?:\d[ -]*?){13,16}\b.*?\|.*?\|.*?\|.*', line)
            if found:
                cc_lines.extend(found)
            else:
                parts = re.findall(r'\d{12,16}[|: -]\d{1,2}[|: -]\d{2,4}[|: -]\d{3,4}', line)
                cc_lines.extend(parts)

    if not cc_lines:
        return bot.reply_to(msg, """❌ Invalid Format

- No valid credit cards detected in the file
- Please make sure the cards are in correct format: 4556737586899855|12|2026|123

Contact admin if you need help""")

    if not reply.document and len(cc_lines) > 15:
        return bot.reply_to(msg, """❌ Invalid Format

- Only 15 cards allowed in raw paste
- For more cards, please upload a .txt file

Contact admin if you need help""")

    total = len(cc_lines)
    kb = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton(f"Approved 0 ✅", callback_data="none"),
        InlineKeyboardButton(f"Declined 0 ❌", callback_data="none"),
        InlineKeyboardButton(f"Total Checked 0", callback_data="none"),
        InlineKeyboardButton(f"Total {total} ✅", callback_data="none"),
        InlineKeyboardButton("Stop 🛑", callback_data="stop_mcc")
    ]
    for btn in buttons:
        kb.add(btn)

    status_msg = bot.reply_to(msg, """⏳ Processing (Stripe)

- Your cards are being checked...
- Please wait a few moments

🚫 Do not spam or resubmit""", reply_markup=kb)

    approved, declined, checked = 0, 0, 0
    stop_flag = False

    def process_all():
        nonlocal approved, declined, checked, stop_flag
        for cc in cc_lines:
            if stop_flag:
                break
            try:
                checked += 1
                result = asyncio.run(Tele(cc.strip(), retries=5))
                if "✅ Succeeded" in result:
                    approved += 1
                    bot.send_message(user_id, result)
                    if ADMIN_ID != user_id:
                        bot.send_message(ADMIN_ID, f"✅ Approved by {user_id}:\n{result}")
                else:
                    declined += 1
                new_kb = InlineKeyboardMarkup(row_width=2)
                new_kb.add(
                    InlineKeyboardButton(f"Approved {approved} ✅", callback_data="none"),
                    InlineKeyboardButton(f"Declined {declined} ❌", callback_data="none"),
                    InlineKeyboardButton(f"Total Checked {checked}", callback_data="none"),
                    InlineKeyboardButton(f"Total {total} ✅", callback_data="none"),
                    InlineKeyboardButton("Stop 🛑", callback_data="stop_mcc")
                )
                bot.edit_message_reply_markup(user_id, status_msg.message_id, reply_markup=new_kb)
                time.sleep(2)
            except Exception as e:
                logging.error(f"Mass Stripe check error: {str(e)}")
                bot.send_message(user_id, f"❌ Error: {e}")

        if not stop_flag:
            bot.send_message(user_id, """✅ Checking Completed (Stripe)

- All cards have been processed
- Thank you for using mass check

ℹ️ Only approved cards were shown to you""")
        else:
            bot.send_message(user_id, "🛑 Mass checking stopped by user.")

    @bot.callback_query_handler(func=lambda call: call.data == "stop_mcc")
    def stop_mcc_handler(call):
        nonlocal stop_flag
        stop_flag = True
        bot.answer_callback_query(call.id, "🛑 Mass checking stopped!")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

    threading.Thread(target=process_all).start()
    if not is_authorized(user_id) and not is_authorized(chat_id, is_group):
        LAST_CHECK_TIME[str(user_id)] = time.time()

# ---------------- Main Execution ---------------- #

if __name__ == "__main__":
    webhook_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    try:
        async def delete_webhook():
            async with aiohttp.ClientSession() as session:
                async with session.get(webhook_url, timeout=30) as response:
                    if response.status == 200:
                        logging.info("Webhook deleted successfully")
                    else:
                        logging.error(f"Webhook deletion failed: {response.status}")
        GLOBAL_LOOP.run_until_complete(delete_webhook())
    except Exception as e:
        logging.error(f"Error deleting webhook: {str(e)}")
    while True:
        try:
            logging.info(f"Bot started at {datetime.now().strftime('%H:%M:%S %d-%m-%Y')} IST")
            bot.polling(none_stop=True, interval=0)
        except Exception as e:
            logging.error(f"Bot crashed due to {e}, restarting in 5 seconds...")
            time.sleep(5)