
import os
import uuid
import threading
import telebot
import yt_dlp

from flask import Flask, request
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from urllib.parse import urlparse

# SETTINGS
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL")

if not BOT_TOKEN or not BASE_URL:
    raise RuntimeError("BOT_TOKEN or RENDER_EXTERNAL_URL is missing")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

user_links = {}

# ALLOWED PUBLIC SITES
ALLOWED_DOMAINS = (
    "youtube.com",
    "youtu.be",
    "instagram.com",
    "facebook.com",
    "fb.watch"
)

def valid_url(url):
    try:
        host = urlparse(url).hostname
        if not host:
            return False

        host = host.lower()
        return any(
            host == domain or host.endswith("." + domain)
            for domain in ALLOWED_DOMAINS
        )
    except Exception:
        return False


# START
@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        "🎬 ALL OF ME ❤️\n\n"
        "🚀 Welcome to Smart Downloader Bot!\n\n"
        "Send a public video link to download.\n\n"
        "Supported: YouTube, Instagram, Facebook\n"
        "Quality: 360p | 480p | 720p\n\n"
        "⚡ Fast • Easy • Smart"
    )


# HELP
@bot.message_handler(commands=["help"])
def help_command(message):
    bot.reply_to(
        message,
        "📥 How to use:\n\n"
        "1. Send a public video link.\n"
        "2. Select video quality.\n"
        "3. Wait for your video.\n\n"
        "Private or restricted videos are not supported."
    )


# LINK HANDLER
@bot.message_handler(func=lambda m: bool(m.text) and m.text.startswith("http"))
def receive_link(message):
    url = message.text.strip()

    if not valid_url(url):
        bot.reply_to(message, "❌ This link is not supported.")
        return

    user_links[message.from_user.id] = url

    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("360p", callback_data="q360"),
        InlineKeyboardButton("480p", callback_data="q480"),
        InlineKeyboardButton("720p", callback_data="q720")
    )

    bot.reply_to(
        message,
        "🎥 Select video quality:",
        reply_markup=keyboard
    )


# QUALITY BUTTONS
@bot.callback_query_handler(func=lambda call: call.data in ["q360", "q480", "q720"])
def select_quality(call):
    user_id = call.from_user.id
    url = user_links.get(user_id)

    bot.answer_callback_query(call.id)

    if not url:
        bot.send_message(user_id, "❌ Please send the video link again.")
        return

    quality = call.data.replace("q", "")

    bot.send_message(
        user_id,
        f"⏳ Downloading in {quality}p...\nPlease wait ❤️"
    )

    thread = threading.Thread(
        target=download_video,
        args=(user_id, url, quality),
        daemon=True
    )
    thread.start()


# DOWNLOAD FUNCTION
def download_video(user_id, url, quality):
    folder = "/tmp/all_of_me"
    os.makedirs(folder, exist_ok=True)

    job_id = uuid.uuid4().hex
    output_template = os.path.join(folder, job_id + ".%(ext)s")

    try:
        format_choice = (
            f"best[height<={quality}][ext=mp4]/"
            f"best[height<={quality}]/"
            "best[ext=mp4]/best"
        )

        options = {
            "format": format_choice,
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,
            "retries": 2
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        if not os.path.isfile(file_path):
            bot.send_message(user_id, "❌ Download failed. Please try another link.")
            return

        file_size = os.path.getsize(file_path)

        # Telegram Bot API upload size limit
        if file_size > 49 * 1024 * 1024:
            bot.send_message(
                user_id,
                "❌ This video is too large to send through Telegram."
            )
            return

        title = info.get("title", "ALL OF ME Video")

        with open(file_path, "rb") as video:
            bot.send_video(
                user_id,
                video,
                caption=f"🎬 {title}\n\n❤️ ALL OF ME"
            )

    except Exception:
        bot.send_message(
            user_id,
            "❌ Download failed.\n"
            "The link may be unavailable or unsupported."
        )

    finally:
        for name in os.listdir(folder):
            if name.startswith(job_id + "."):
                try:
                    os.remove(os.path.join(folder, name))
                except Exception:
                    pass


# WEBHOOK
@app.route("/", methods=["GET"])
def home():
    return "ALL OF ME Bot is running ❤️"


@app.route("/webhook", methods=["POST"])
def webhook():
    if request.headers.get("content_type", "").startswith("application/json"):
        json_data = request.get_json(silent=True)
        if json_data:
            update = telebot.types.Update.de_json(json_data)
            bot.process_new_updates([update])

    return "OK", 200


# START SERVER
bot.remove_webhook()
bot.set_webhook(url=BASE_URL.rstrip("/") + "/webhook")

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
        )
    
