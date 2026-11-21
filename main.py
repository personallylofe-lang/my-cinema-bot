
import os
import threading
import requests
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask

TOKEN = os.environ["BOT_TOKEN"]
TMDB_KEY = os.environ["TMDB_KEY"]
OMDB_KEY = os.environ.get("OMDB_KEY", "")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

BASE = "https://api.themoviedb.org/3"

@app.route("/")
def home():
    return "My Cinema Bot is running!"

def tmdb(path, params=None):
    params = params or {}
    params["api_key"] = TMDB_KEY
    r = requests.get(BASE + path, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

def movie_text(movie):
    title = movie.get("title", "Unknown")
    date = movie.get("release_date", "Unknown")
    rating = movie.get("vote_average", "N/A")
    overview = movie.get("overview", "No description available.")
    return (
        f"🎬 {title}\n"
        f"📅 Release: {date}\n"
        f"⭐ TMDB Rating: {rating}\n\n"
        f"📖 {overview[:700]}"
    )

def send_movie(chat_id, movie):
    movie_id = movie["id"]
    text = movie_text(movie)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(
            "🎥 Movie Details",
            callback_data=f"details_{movie_id}"
        )
    )

    poster = movie.get("poster_path")
    if poster:
        image_url = "https://image.tmdb.org/t/p/w500" + poster
        bot.send_photo(
            chat_id,
            image_url,
            caption=text[:1024],
            reply_markup=keyboard
        )
    else:
        bot.send_message(chat_id, text, reply_markup=keyboard)

@bot.message_handler(commands=["start"])
def start(message):
    text = (
        "🎬 WELCOME TO MY CINEMA HELP BOT ❤️\n\n"
        "🔎 /search - Search Movies\n"
        "🔥 /trending - Trending Movies\n"
        "🆕 /latest - Latest Movies\n"
        "🌍 /public - Search Archive Movies\n\n"
        "Example: /search Premalu"
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=["search"])
def search(message):
    query = message.text.replace("/search", "", 1).strip()
    if not query:
        bot.reply_to(message, "Type movie name:\n/search Premalu")
        return

    try:
        data = tmdb("/search/movie", {"query": query})
        results = data.get("results", [])[:5]

        if not results:
            bot.reply_to(message, "❌ Movie not found.")
            return

        bot.send_message(message.chat.id, "🎬 Search Results:")
        for movie in results:
            send_movie(message.chat.id, movie)

    except Exception:
        bot.reply_to(message, "⚠️ Search error. Try again.")

@bot.message_handler(commands=["trending"])
def trending(message):
    try:
        data = tmdb("/trending/movie/week")
        for movie in data.get("results", [])[:5]:
            send_movie(message.chat.id, movie)
    except Exception:
        bot.reply_to(message, "⚠️ Could not load trending movies.")

@bot.message_handler(commands=["latest"])
def latest(message):
    try:
        data = tmdb("/movie/now_playing", {"region": "IN"})
        for movie in data.get("results", [])[:5]:
            send_movie(message.chat.id, movie)
    except Exception:
        bot.reply_to(message, "⚠️ Could not load latest movies.")

@bot.message_handler(commands=["public"])
def public_command(message):
    query = message.text.replace("/public", "", 1).strip()
    if not query:
        bot.reply_to(message, "Use:\n/public movie name")
        return

    try:
        url = "https://archive.org/advancedsearch.php"
        params = {
            "q": f'title:({query}) AND mediatype:movies',
            "fl[]": ["identifier", "title"],
            "rows": 5,
            "output": "json"
        }
        data = requests.get(url, params=params, timeout=20).json()
        docs = data.get("response", {}).get("docs", [])

        if not docs:
            bot.reply_to(message, "No Archive results found.")
            return

        for item in docs:
            identifier = item.get("identifier")
            title = item.get("title", "Archive Movie")
            link = f"https://archive.org/details/{identifier}"
            bot.send_message(
                message.chat.id,
                f"🎬 {title}\n{link}\n\n"
                "Please check the item's copyright and license "
                "before downloading or sharing."
            )
    except Exception:
        bot.reply_to(message, "⚠️ Archive search error.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("details_"))
def details(call):
    movie_id = call.data.replace("details_", "")
    try:
        data = tmdb(f"/movie/{movie_id}")
        text = (
            f"🎬 {data.get('title', 'Unknown')}\n"
            f"📅 {data.get('release_date', 'Unknown')}\n"
            f"⏱ Runtime: {data.get('runtime', 'N/A')} minutes\n"
            f"⭐ Rating: {data.get('vote_average', 'N/A')}\n"
            f"🎭 Genres: {', '.join(g['name'] for g in data.get('genres', []))}\n\n"
            f"📖 {data.get('overview', 'No description')}"
        )

        credits = tmdb(f"/movie/{movie_id}/credits")
        cast = [person["name"] for person in credits.get("cast", [])[:5]]
        text += "\n\n👥 Cast: " + (", ".join(cast) if cast else "N/A")

        videos = tmdb(f"/movie/{movie_id}/videos")
        trailer = next(
            (v for v in videos.get("results", [])
             if v.get("site") == "YouTube"
             and v.get("type") == "Trailer"),
            None
        )

        if trailer:
            text += f"\n\n🎥 Trailer: https://www.youtube.com/watch?v={trailer['key']}"

        bot.send_message(call.message.chat.id, text)
        bot.answer_callback_query(call.id)

    except Exception:
        bot.answer_callback_query(call.id, "Could not load details.")

def run_bot():
    bot.infinity_polling(skip_pending=True, timeout=30)

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
