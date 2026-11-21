
import os
import requests
import telebot
from flask import Flask, request
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import date

TOKEN = os.environ["BOT_TOKEN"]
TMDB_KEY = os.environ["TMDB_KEY"]
WEBHOOK_URL = os.environ["RENDER_EXTERNAL_URL"]

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

BASE = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/w500"

LANGUAGES = {
    "ml": "ml-IN",
    "malayalam": "ml-IN",
    "ta": "ta-IN",
    "tamil": "ta-IN",
    "hi": "hi-IN",
    "hindi": "hi-IN",
    "en": "en-US",
    "english": "en-US"
}


def tmdb(path, params=None):
    p = dict(params or {})
    p["api_key"] = TMDB_KEY
    r = requests.get(BASE + path, params=p, timeout=25)
    r.raise_for_status()
    return r.json()


@app.route("/", methods=["GET"])
def home():
    return "MY CINEMA BOT RUNNING ❤️"


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = telebot.types.Update.de_json(
            request.get_data().decode("utf-8")
        )
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        print("Webhook error:", e)
        return "ERROR", 500


def show_list(chat_id, results, heading, kind="movie"):
    if not results:
        bot.send_message(chat_id, "❌ No results found.")
        return

    kb = InlineKeyboardMarkup()

    for item in results[:10]:
        name = item.get("title") or item.get("name") or "Unknown"
        year = (
            item.get("release_date") or
            item.get("first_air_date") or ""
        )[:4]

        kb.add(InlineKeyboardButton(
            f"🎬 {name} ({year})",
            callback_data=f"{kind}_{item['id']}"
        ))

    bot.send_message(chat_id, heading, reply_markup=kb)


def show_movie(chat_id, movie_id):
    data = tmdb(f"/movie/{movie_id}")
    credits = tmdb(f"/movie/{movie_id}/credits")
    videos = tmdb(f"/movie/{movie_id}/videos")

    title = data.get("title", "Unknown")
    rating = data.get("vote_average", 0)
    release = data.get("release_date", "Unknown")
    overview = data.get("overview", "Story unavailable")
    runtime = data.get("runtime", 0)

    cast = credits.get("cast", [])
    cast_names = ", ".join(
        x["name"] for x in cast[:6]
    ) or "Not available"

    trailer = None
    for video in videos.get("results", []):
        if video.get("site") == "YouTube" and video.get("type") == "Trailer":
            trailer = "https://www.youtube.com/watch?v=" + video["key"]
            break

    caption = (
        f"🎬 {title}\n\n"
        f"⭐ Rating: {rating}/10\n"
        f"📅 Release: {release}\n"
        f"⏱️ Runtime: {runtime} minutes\n\n"
        f"📖 Story:\n{overview[:450]}\n\n"
        f"🎭 Cast:\n{cast_names}"
    )

    kb = InlineKeyboardMarkup()

    if trailer:
        kb.add(InlineKeyboardButton(
            "▶️ WATCH TRAILER", url=trailer
        ))

    poster = data.get("poster_path")

    if poster:
        bot.send_photo(
            chat_id, IMG + poster,
            caption=caption[:1024],
            reply_markup=kb
        )
    else:
        bot.send_message(chat_id, caption, reply_markup=kb)


def show_tv(chat_id, tv_id):
    data = tmdb(f"/tv/{tv_id}")
    videos = tmdb(f"/tv/{tv_id}/videos")
    credits = tmdb(f"/tv/{tv_id}/credits")

    title = data.get("name", "Unknown")
    rating = data.get("vote_average", 0)
    overview = data.get("overview", "Story unavailable")
    seasons = data.get("number_of_seasons", 0)

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
        f"📺 {title}\n\n"
        f"⭐ Rating: {rating}/10\n"
        f"📚 Seasons: {seasons}\n\n"
        f"📖 Story:\n{overview[:450]}\n\n"
        f"🎭 Cast:\n{cast_names}"
    )

    kb = InlineKeyboardMarkup()
    if trailer:
        kb.add(InlineKeyboardButton(
            "▶️ WATCH TRAILER", url=trailer
        ))

    poster = data.get("poster_path")
    if poster:
        bot.send_photo(
            chat_id, IMG + poster,
            caption=caption[:1024],
            reply_markup=kb
        )
    else:
        bot.send_message(chat_id, caption, reply_markup=kb)


def show_actor(chat_id, person_id):
    data = tmdb(f"/person/{person_id}")
    credits = tmdb(f"/person/{person_id}/movie_credits")

    name = data.get("name", "Unknown")
    bio = data.get("biography", "Biography unavailable")
    known = data.get("known_for_department", "Unknown")

    movies = credits.get("cast", [])
    movies.sort(
        key=lambda x: x.get("popularity", 0),
        reverse=True
    )

    titles = "\n".join(
        "🎬 " + x.get("title", "Unknown")
        for x in movies[:8]
    )

    caption = (
        f"🎭 ACTOR: {name}\n\n"
        f"⭐ Known for: {known}\n\n"
        f"📖 Biography:\n{bio[:450]}\n\n"
        f"🎬 Popular Movies:\n{titles or 'Not available'}"
    )

    photo = data.get("profile_path")
    if photo:
        bot.send_photo(
            chat_id, IMG + photo,
            caption=caption[:1024]
        )
    else:
        bot.send_message(chat_id, caption[:4000])


@bot.message_handler(commands=["start", "help"])
def start(message):
    bot.reply_to(
        message,
        "🎬 WELCOME TO MY CINEMA HELP BOT ❤️\n\n"
        "🔎 /search Premalu - Search Movies\n"
        "🔥 /trending - Trending Movies\n"
        "🆕 /latest - Latest Movies\n"
        "🌐 /lang ml Premalu - Language Search\n"
        "🔍 /advanced ml 2024 - Advanced Search\n"
        "🎭 /actor Fahadh Faasil - Actor Search\n"
        "📺 /tv Stranger Things - TV Series\n"
        "📱 /where Premalu - Legal Streaming Info\n"
        "🌍 /public Charlie Chaplin - Archive Search\n\n"
        "Languages: ml, ta, hi, en"
    )


@bot.message_handler(commands=["search"])
def search(message):
    try:
        query = message.text.replace("/search", "", 1).strip()
        if not query:
            bot.reply_to(message, "Example: /search Premalu")
            return

        data = tmdb("/search/movie", {"query": query})
        show_list(
            message.chat.id,
            data.get("results", []),
            f"🎬 SEARCH: {query}"
        )
    except Exception as e:
        print("Search:", e)
        bot.reply_to(message, "Search error!")


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
        print("Trending:", e)
        bot.reply_to(message, "Trending error!")


@bot.message_handler(commands=["latest"])
def latest(message):
    try:
        data = tmdb("/discover/movie", {
            "sort_by": "release_date.desc",
            "primary_release_date.lte": str(date.today()),
            "vote_count.gte": 5
        })
        show_list(
            message.chat.id,
            data.get("results", []),
            "🆕 LATEST MOVIES"
        )
    except Exception as e:
        print("Latest:", e)
        bot.reply_to(message, "Latest error!")


@bot.message_handler(commands=["lang"])
def language_search(message):
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(
                message,
                "Example: /lang ml Premalu\n"
                "Languages: ml, ta, hi, en"
            )
            return

        code = LANGUAGES.get(parts[1].lower())
        query = parts[2]

        if not code:
            bot.reply_to(message, "Use ml, ta, hi or en.")
            return

        data = tmdb("/search/movie", {
            "query": query,
            "language": code
        })

        results = [
            x for x in data.get("results", [])
            if x.get("original_language") == code[:2]
        ]

        show_list(
            message.chat.id,
            results,
            f"🌐 {parts[1].upper()} MOVIES"
        )
    except Exception as e:
        print("Language:", e)
        bot.reply_to(message, "Language search error!")


@bot.message_handler(commands=["advanced"])
def advanced(message):
    try:
        parts = message.text.split()

        if len(parts) < 3:
            bot.reply_to(
                message,
                "Example: /advanced ml 2024\n"
                "Languages: ml, ta, hi, en"
            )
            return

        code = LANGUAGES.get(parts[1].lower())
        year = parts[2]

        if not code or not year.isdigit() or len(year) != 4:
            bot.reply_to(message, "Example: /advanced ml 2024")
            return

        data = tmdb("/discover/movie", {
            "with_original_language": code[:2],
            "primary_release_year": year,
            "sort_by": "popularity.desc"
        })

        show_list(
            message.chat.id,
            data.get("results", []),
            f"🔍 {parts[1].upper()} MOVIES - {year}"
        )
    except Exception as e:
        print("Advanced:", e)
        bot.reply_to(message, "Advanced search error!")


@bot.message_handler(commands=["actor"])
def actor(message):
    try:
        query = message.text.replace("/actor", "", 1).strip()
        if not query:
            bot.reply_to(message, "Example: /actor Fahadh Faasil")
            return

        data = tmdb("/search/person", {"query": query})

        show_list(
            message.chat.id,
            data.get("results", []),
            f"🎭 ACTORS: {query}",
            "person"
        )
    except Exception as e:
        print("Actor:", e)
        bot.reply_to(message, "Actor search error!")


@bot.message_handler(commands=["tv"])
def tv(message):
    try:
        query = message.text.replace("/tv", "", 1).strip()
        if not query:
            bot.reply_to(message, "Example: /tv Stranger Things")
            return

        data = tmdb("/search/tv", {"query": query})

        show_list(
            message.chat.id,
            data.get("results", []),
            f"📺 TV SERIES: {query}",
            "tv"
        )
    except Exception as e:
        print("TV:", e)
        bot.reply_to(message, "TV search error!")


@bot.message_handler(commands=["where"])
def where(message):
    try:
        query = message.text.replace("/where", "", 1).strip()
        if not query:
            bot.reply_to(message, "Example: /where Premalu")
            return

        data = tmdb("/search/movie", {"query": query})
        results = data.get("results", [])

        if not results:
            bot.reply_to(message, "Movie not found.")
            return

        movie = results[0]
        providers = tmdb(
            f"/movie/{movie['id']}/watch/providers"
        )

        india = providers.get("results", {}).get("IN", {})
        link = india.get("link")

        kb = InlineKeyboardMarkup()
        if link:
            kb.add(InlineKeyboardButton(
                "📱 CHECK LEGAL STREAMING OPTIONS",
                url=link
            ))

        names = []
        for category in ("flatrate", "rent", "buy"):
            for item in india.get(category, []):
                if item["provider_name"] not in names:
                    names.append(item["provider_name"])

        text = (
            f"🎬 {movie.get('title')}\n\n"
            "📱 Legal viewing options in India:\n"
            + ("\n".join("• " + x for x in names)
               if names else "No provider information available.")
        )

        bot.send_message(
            message.chat.id,
            text,
            reply_markup=kb
        )
    except Exception as e:
        print("Where:", e)
        bot.reply_to(message, "Streaming search error!")


@bot.message_handler(commands=["public"])
def public(message):
    try:
        query = message.text.replace("/public", "", 1).strip()
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

        docs = r.json().get("response", {}).get("docs", [])

        if not docs:
            bot.reply_to(message, "No archive results found.")
            return

        for item in docs:
            identifier = item.get("identifier")
            title = item.get("title", "Archive Movie")

            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(
                "🌍 OPEN ARCHIVE",
                url=f"https://archive.org/details/{identifier}"
            ))

            bot.send_message(
                message.chat.id,
                f"🎬 {title}\nCheck the item's rights before downloading.",
                reply_markup=kb
            )
    except Exception as e:
        print("Public:", e)
        bot.reply_to(message, "Archive search error!")


@bot.callback_query_handler(
    func=lambda call: call.data.startswith(
        ("movie_", "tv_", "person_")
    )
)
def callback(call):
    try:
        bot.answer_callback_query(call.id)

        kind, item_id = call.data.split("_", 1)
        chat_id = call.message.chat.id

        if kind == "movie":
            show_movie(chat_id, item_id)
        elif kind == "tv":
            show_tv(chat_id, item_id)
        elif kind == "person":
            show_actor(chat_id, item_id)

    except Exception as e:
        print("Callback:", e)
        bot.send_message(
            call.message.chat.id,
            "Details error. Try again."
        )


if __name__ == "__main__":
    bot.set_webhook(url=WEBHOOK_URL + "/webhook")
    print("MY CINEMA WEBHOOK READY ❤️")

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
