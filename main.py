
import os
import threading
import requests
import telebot
from flask import Flask
from datetime import date
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.environ["BOT_TOKEN"]
TMDB_KEY = os.environ["TMDB_KEY"]

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

BASE = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/w500"


@app.route("/")
def home():
    return "My Cinema Bot is Running!"


def tmdb(path, params=None):
    p = dict(params or {})
    p["api_key"] = TMDB_KEY
    r = requests.get(BASE + path, params=p, timeout=20)
    r.raise_for_status()
    return r.json()


def show_list(chat_id, results, heading):
    if not results:
        bot.send_message(chat_id, "No movies found.")
        return

    kb = InlineKeyboardMarkup()
    for movie in results[:10]:
        name = movie.get("title", "Unknown")
        year = movie.get("release_date", "")[:4]
        kb.add(InlineKeyboardButton(
            f"🎬 {name} ({year})",
            callback_data=f"movie_{movie['id']}"
        ))

    bot.send_message(chat_id, heading, reply_markup=kb)


def show_movie(chat_id, movie_id):
    try:
        data = tmdb(f"/movie/{movie_id}")
        credits = tmdb(f"/movie/{movie_id}/credits")
        videos = tmdb(f"/movie/{movie_id}/videos")

        title = data.get("title", "Unknown")
        rating = data.get("vote_average", 0)
        release = data.get("release_date", "Unknown")
        overview = data.get("overview", "Story not available")

        cast = credits.get("cast", [])
        cast_names = ", ".join(
            x["name"] for x in cast[:5]
        ) or "Not available"

        trailer = None
        for video in videos.get("results", []):
            if video.get("site") == "YouTube" and video.get("type") == "Trailer":
                trailer = "https://www.youtube.com/watch?v=" + video["key"]
                break

        caption = (
            f"🎬 {title}\n\n"
            f"⭐ Rating: {rating}/10\n"
            f"📅 Release: {release}\n\n"
            f"📖 Story:\n{overview[:650]}\n\n"
            f"🎭 Cast:\n{cast_names}"
        )

        kb = InlineKeyboardMarkup()
        if trailer:
            kb.add(InlineKeyboardButton(
                "▶️ Watch Trailer", url=trailer
            ))

        poster = data.get("poster_path")
        if poster:
            bot.send_photo(
                chat_id, IMG + poster,
                caption=caption[:1024],
                reply_markup=kb
            )
        else:
            bot.send_message(
                chat_id, caption,
                reply_markup=kb
            )

    except Exception as e:
        print("Movie details error:", e)
        bot.send_message(chat_id, "⚠️ Movie details error. Try again.")


@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        "🎬 WELCOME TO MY CINEMA HELP BOT ❤️\n\n"
        "🔎 /search - Search Movies\n"
        "🔥 /trending - Trending Movies\n"
        "🆕 /latest - Latest Movies\n"
        "🌍 /public - Public Domain Movies\n\n"
        "Example: /search Premalu"
    )


@bot.message_handler(commands=["search"])
def search(message):
    try:
        query = message.text.replace("/search", "", 1).strip()
        if not query:
            bot.reply_to(message, "Example: /search Premalu")
            return

        bot.send_message(message.chat.id, "🔎 Searching...")
        data = tmdb("/search/movie", {"query": query})
        show_list(message.chat.id, data.get("results", []), f"🎬 Search Results: {query}")

    except Exception as e:
        print("Search error:", e)
        bot.reply_to(message, "⚠️ Search error. Try again.")


@bot.message_handler(commands=["trending"])
def trending(message):
    try:
        data = tmdb("/trending/movie/week")
        show_list(message.chat.id, data.get("results", []), "🔥 TRENDING MOVIES")
    except Exception as e:
        print("Trending error:", e)
        bot.reply_to(message, "⚠️ Trending error.")


@bot.message_handler(commands=["latest"])
def latest(message):
    try:
        data = tmdb("/discover/movie", {
            "sort_by": "release_date.desc",
            "primary_release_date.lte": str(date.today()),
            "vote_count.gte": 5
        })
        show_list(message.chat.id, data.get("results", []), "🆕 LATEST MOVIES")
    except Exception as e:
        print("Latest error:", e)
        bot.reply_to(message, "⚠️ Latest error.")


@bot.message_handler(commands=["public"])
def public(message):
    try:
        query = message.text.replace("/public", "", 1).strip()
        if not query:
            bot.reply_to(message, "Example: /public Charlie Chaplin")
            return

        params = {
            "q": f'title:({query}) AND mediatype:movies',
            "fl[]": ["identifier", "title"],
            "rows": 5,
            "output": "json"
        }
        r = requests.get(
            "https://archive.org/advancedsearch.php",
            params=params, timeout=20
        )
        r.raise_for_status()
        docs = r.json().get("response", {}).get("docs", [])

        if not docs:
            bot.reply_to(message, "No public archive results found.")
            return

        for item in docs:
            identifier = item.get("identifier")
            title = item.get("title", "Public Archive Movie")
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(
                "🌍 Open Archive",
                url=f"https://archive.org/details/{identifier}"
            ))
            bot.send_message(message.chat.id, f"🎬 {title}", reply_markup=kb)

    except Exception as e:
        print("Public search error:", e)
        bot.reply_to(message, "⚠️ Public search error.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("movie_"))
def movie_callback(call):
    try:
        movie_id = call.data.replace("movie_", "")
        bot.answer_callback_query(call.id)
        show_movie(call.message.chat.id, movie_id)
    except Exception as e:
        print("Callback error:", e)


def run_bot():
    bot.infinity_polling(
        skip_pending=True,
        timeout=30,
        long_polling_timeout=30
    )


if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
