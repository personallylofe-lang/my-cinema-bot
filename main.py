
import os
import requests
import telebot
from flask import Flask, request
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import date

TOKEN = os.environ["BOT_TOKEN"]
TMDB_KEY = os.environ["TMDB_KEY"]

WEBHOOK_URL = os.environ.get(
    "RENDER_EXTERNAL_URL",
    "https://my-cinema-bot-yzqv.onrender.com"
)

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

BASE = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/w500"


def tmdb(path, params=None):
    p = dict(params or {})
    p["api_key"] = TMDB_KEY
    r = requests.get(BASE + path, params=p, timeout=20)
    r.raise_for_status()
    return r.json()


@app.route("/", methods=["GET"])
def home():
    return "MY CINEMA BOT IS RUNNING ❤️"


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = telebot.types.Update.de_json(
            request.get_data().decode("utf-8")
        )
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        print("Webhook Error:", e)
        return "ERROR", 500


def show_list(chat_id, results, heading):
    if not results:
        bot.send_message(chat_id, "❌ No movies found.")
        return

    kb = InlineKeyboardMarkup()

    for movie in results[:10]:
        name = movie.get("title", "Unknown")
        year = movie.get("release_date", "")[:4]

        kb.add(InlineKeyboardButton(
            f"🎬 {name} ({year})",
            callback_data=f"movie_{movie['id']}"
        ))

    bot.send_message(
        chat_id,
        heading,
        reply_markup=kb
    )


def show_movie(chat_id, movie_id):
    data = tmdb(f"/movie/{movie_id}")
    credits = tmdb(f"/movie/{movie_id}/credits")
    videos = tmdb(f"/movie/{movie_id}/videos")

    title = data.get("title", "Unknown")
    rating = data.get("vote_average", 0)
    release = data.get("release_date", "Unknown")
    overview = data.get("overview", "Story unavailable")

    cast = credits.get("cast", [])
    cast_names = ", ".join(
        x["name"] for x in cast[:5]
    ) or "Not available"

    trailer = None

    for video in videos.get("results", []):
        if video.get("site") == "YouTube" and video.get("type") == "Trailer":
            trailer = (
                "https://www.youtube.com/watch?v="
                + video["key"]
            )
            break

    caption = (
        f"🎬 {title}\n\n"
        f"⭐ Rating: {rating}/10\n"
        f"📅 Release: {release}\n\n"
        f"📖 Story:\n{overview[:550]}\n\n"
        f"🎭 Cast:\n{cast_names}"
    )

    kb = InlineKeyboardMarkup()

    if trailer:
        kb.add(InlineKeyboardButton(
            "▶️ WATCH TRAILER",
            url=trailer
        ))

    poster = data.get("poster_path")

    if poster:
        bot.send_photo(
            chat_id,
            IMG + poster,
            caption=caption[:1024],
            reply_markup=kb
        )
    else:
        bot.send_message(
            chat_id,
            caption,
            reply_markup=kb
        )


@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        "🎬 WELCOME TO MY CINEMA HELP BOT ❤️\n\n"
        "🔎 /search - Search Movies\n"
        "🔥 /trending - Trending Movies\n"
        "🆕 /latest - Latest Movies\n"
        "🌍 /public - Public Archive Search\n\n"
        "Example: /search Premalu"
    )


@bot.message_handler(commands=["search"])
def search(message):
    try:
        query = message.text.replace(
            "/search", "", 1
        ).strip()

        if not query:
            bot.reply_to(
                message,
                "Example: /search Premalu"
            )
            return

        bot.send_message(
            message.chat.id,
            "🔎 Searching Movies..."
        )

        data = tmdb(
            "/search/movie",
            {"query": query}
        )

        show_list(
            message.chat.id,
            data.get("results", []),
            f"🎬 SEARCH RESULTS: {query}"
        )

    except Exception as e:
        print("Search Error:", e)
        bot.reply_to(message, "Search Error!")


@bot.message_handler(commands=["trending"])
def trending(message):
    try:
        data = tmdb("/trending/movie/week")

        show_list(
            message.chat.id,
            data.get("results", []),
            "🔥 TRENDING MOVIES"
        )

    except Exception as e:
        print("Trending Error:", e)
        bot.reply_to(message, "Trending Error!")


@bot.message_handler(commands=["latest"])
def latest(message):
    try:
        data = tmdb(
            "/discover/movie",
            {
                "sort_by": "release_date.desc",
                "primary_release_date.lte": str(date.today()),
                "vote_count.gte": 5
            }
        )

        show_list(
            message.chat.id,
            data.get("results", []),
            "🆕 LATEST MOVIES"
        )

    except Exception as e:
        print("Latest Error:", e)
        bot.reply_to(message, "Latest Error!")


@bot.message_handler(commands=["public"])
def public(message):
    try:
        query = message.text.replace(
            "/public", "", 1
        ).strip()

        if not query:
            bot.reply_to(
                message,
                "Example: /public Charlie Chaplin"
            )
            return

        params = {
            "q": f'title:({query}) AND mediatype:movies',
            "fl[]": ["identifier", "title"],
            "rows": 5,
            "output": "json"
        }

        r = requests.get(
            "https://archive.org/advancedsearch.php",
            params=params,
            timeout=20
        )

        r.raise_for_status()

        docs = r.json().get(
            "response", {}
        ).get("docs", [])

        if not docs:
            bot.reply_to(message, "No results found.")
            return

        for item in docs:
            identifier = item.get("identifier")
            title = item.get(
                "title", "Archive Movie"
            )

            kb = InlineKeyboardMarkup()

            kb.add(InlineKeyboardButton(
                "🌍 OPEN ARCHIVE",
                url=f"https://archive.org/details/{identifier}"
            ))

            bot.send_message(
                message.chat.id,
                f"🎬 {title}",
                reply_markup=kb
            )

    except Exception as e:
        print("Public Error:", e)
        bot.reply_to(message, "Public Search Error!")


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("movie_")
)
def movie_callback(call):
    try:
        bot.answer_callback_query(call.id)

        movie_id = call.data.replace(
            "movie_", "", 1
        )

        show_movie(
            call.message.chat.id,
            movie_id
        )

    except Exception as e:
        print("Movie Details Error:", e)
        bot.send_message(
            call.message.chat.id,
            "Movie Details Error!"
        )


if __name__ == "__main__":

    bot.remove_webhook()

    result = bot.set_webhook(
        url=WEBHOOK_URL + "/webhook"
    )

    print("Webhook Setup:", result)

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
