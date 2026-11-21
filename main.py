
import os
import sqlite3
import requests
import telebot
from flask import Flask, request

# SETTINGS
BOT_TOKEN = os.getenv("BOT_TOKEN")
TMDB_KEY = os.getenv("TMDB_KEY")
BASE_URL = os.getenv("RENDER_EXTERNAL_URL")

if not BOT_TOKEN or not TMDB_KEY or not BASE_URL:
    raise ValueError("BOT_TOKEN, TMDB_KEY, RENDER_EXTERNAL_URL required")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

TMDB = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/w500"

# FILE DATABASE
db = sqlite3.connect("movies.db", check_same_thread=False)
db.execute("""
CREATE TABLE IF NOT EXISTS files (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 chat_id INTEGER,
 title TEXT,
 file_id TEXT,
 kind TEXT
)
""")
db.commit()


def tmdb(path, params=None):
    p = params or {}
    p["api_key"] = TMDB_KEY
    r = requests.get(TMDB + path, params=p, timeout=20)
    r.raise_for_status()
    return r.json()


def movie_info(movie_id):
    m = tmdb(f"/movie/{movie_id}", {"append_to_response": "credits,videos"})
    poster = IMG + m["poster_path"] if m.get("poster_path") else None

    text = (
        f"🎬 <b>{m.get('title')}</b>\n"
        f"⭐ Rating: {m.get('vote_average', 'N/A')}/10\n"
        f"📅 Release: {m.get('release_date', 'N/A')}\n\n"
        f"📖 <b>Story:</b>\n{m.get('overview') or 'No story available'}\n\n"
    )

    cast = m.get("credits", {}).get("cast", [])[:5]
    if cast:
        text += "🎭 <b>Cast:</b>\n"
        text += ", ".join(x["name"] for x in cast)

    trailer = None
    for v in m.get("videos", {}).get("results", []):
        if v["site"] == "YouTube" and v["type"] == "Trailer":
            trailer = "https://youtube.com/watch?v=" + v["key"]
            break

    if trailer:
        text += f"\n\n▶️ <a href='{trailer}'>Watch Trailer</a>"

    if poster:
        bot.send_photo(
            CURRENT_CHAT[0], poster,
            caption=text, parse_mode="HTML"
        )
    else:
        bot.send_message(CURRENT_CHAT[0], text, parse_mode="HTML")


CURRENT_CHAT = [None]


def show_movies(chat_id, results):
    if not results:
        bot.send_message(chat_id, "❌ Movies not found.")
        return

    markup = telebot.types.InlineKeyboardMarkup()
    for m in results[:10]:
        name = m.get("title") or m.get("name")
        year = (m.get("release_date") or m.get("first_air_date") or "")[:4]
        markup.add(telebot.types.InlineKeyboardButton(
            f"🎬 {name} ({year})",
            callback_data=f"movie_{m['id']}"
        ))

    bot.send_message(chat_id, "🎬 Select a movie:", reply_markup=markup)


@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        "🎬 <b>WELCOME TO MY CINEMA BOT ❤️</b>\n\n"
        "/search Premalu - Search movies\n"
        "/trending - Trending movies\n"
        "/latest - Latest movies\n"
        "/lang ml Premalu - Language search\n"
        "/advanced ml 2024 - Advanced search\n"
        "/actor Fahadh Faasil - Actor search\n"
        "/tv Stranger Things - TV search\n"
        "/where Premalu - Legal streaming search\n"
        "/file_search Premalu - Search group files",
        parse_mode="HTML"
    )


@bot.message_handler(commands=["search"])
def search(message):
    q = message.text.replace("/search", "", 1).strip()
    if not q:
        return bot.reply_to(message, "Use: /search Premalu")
    data = tmdb("/search/movie", {"query": q})
    show_movies(message.chat.id, data.get("results", []))


@bot.message_handler(commands=["trending"])
def trending(message):
    data = tmdb("/trending/movie/week")
    show_movies(message.chat.id, data.get("results", []))


@bot.message_handler(commands=["latest"])
def latest(message):
    data = tmdb("/movie/now_playing")
    show_movies(message.chat.id, data.get("results", []))


@bot.message_handler(commands=["lang"])
def lang(message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return bot.reply_to(message, "Use: /lang ml Premalu")

    codes = {"ml": "ml", "ta": "ta", "hi": "hi", "en": "en"}
    code = codes.get(parts[1].lower())
    if not code:
        return bot.reply_to(message, "Use ml, ta, hi or en.")

    data = tmdb("/search/movie", {
        "query": parts[2], "language": code
    })
    results = [
        x for x in data.get("results", [])
        if x.get("original_language") == code
    ]
    show_movies(message.chat.id, results)


@bot.message_handler(commands=["advanced"])
def advanced(message):
    parts = message.text.split()
    if len(parts) < 3:
        return bot.reply_to(message, "Use: /advanced ml 2024")

    data = tmdb("/discover/movie", {
        "with_original_language": parts[1],
        "primary_release_year": parts[2],
        "sort_by": "popularity.desc"
    })
    show_movies(message.chat.id, data.get("results", []))


@bot.message_handler(commands=["actor"])
def actor(message):
    q = message.text.replace("/actor", "", 1).strip()
    if not q:
        return bot.reply_to(message, "Use: /actor Fahadh Faasil")

    data = tmdb("/search/person", {"query": q})
    markup = telebot.types.InlineKeyboardMarkup()
    for p in data.get("results", [])[:8]:
        markup.add(telebot.types.InlineKeyboardButton(
            p["name"], callback_data=f"person_{p['id']}"
        ))
    bot.send_message(message.chat.id, "🎭 Select actor:", reply_markup=markup)


@bot.message_handler(commands=["tv"])
def tv(message):
    q = message.text.replace("/tv", "", 1).strip()
    if not q:
        return bot.reply_to(message, "Use: /tv Stranger Things")

    data = tmdb("/search/tv", {"query": q})
    markup = telebot.types.InlineKeyboardMarkup()
    for x in data.get("results", [])[:10]:
        markup.add(telebot.types.InlineKeyboardButton(
            x["name"], callback_data=f"tv_{x['id']}"
        ))
    bot.send_message(message.chat.id, "📺 Select TV series:", reply_markup=markup)


@bot.message_handler(commands=["where"])
def where(message):
    q = message.text.replace("/where", "", 1).strip()
    if not q:
        return bot.reply_to(message, "Use: /where Premalu")

    from urllib.parse import quote
    url = "https://www.justwatch.com/in/search?q=" + quote(q)
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(
        "Find legal streaming options", url=url
    ))
    bot.send_message(
        message.chat.id,
        "🎬 Check official streaming availability:",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("movie_"))
def movie_callback(call):
    movie_id = call.data.split("_")[1]
    CURRENT_CHAT[0] = call.message.chat.id
    try:
        movie_info(movie_id)
    except Exception:
        bot.send_message(call.message.chat.id, "Movie details unavailable.")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("tv_"))
def tv_callback(call):
    try:
        x = tmdb("/tv/" + call.data.split("_")[1])
        text = (
            f"📺 <b>{x.get('name')}</b>\n"
            f"⭐ Rating: {x.get('vote_average')}/10\n"
            f"📅 First aired: {x.get('first_air_date')}\n\n"
            f"{x.get('overview') or ''}"
        )
        if x.get("poster_path"):
            bot.send_photo(
                call.message.chat.id, IMG + x["poster_path"],
                caption=text, parse_mode="HTML"
            )
        else:
            bot.send_message(call.message.chat.id, text, parse_mode="HTML")
    except Exception:
        bot.send_message(call.message.chat.id, "TV details unavailable.")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("person_"))
def person_callback(call):
    try:
        p = tmdb("/person/" + call.data.split("_")[1],
                 {"append_to_response": "combined_credits"})
        movies = p.get("combined_credits", {}).get("cast", [])[:10]
        bot.send_message(
            call.message.chat.id,
            "🎭 <b>" + p["name"] + "</b>\n\n" +
            "\n".join(
                "• " + (x.get("title") or x.get("name", ""))
                for x in movies
            ),
            parse_mode="HTML"
        )
    except Exception:
        bot.send_message(call.message.chat.id, "Actor details unavailable.")
    bot.answer_callback_query(call.id)


# SAVE MOVIE FILES SENT TO GROUP
@bot.message_handler(
    content_types=["video", "document", "audio", "animation"]
)
def save_group_file(message):
    if message.chat.type not in ["group", "supergroup"]:
        return

    title = message.caption or ""

    if message.video:
        file_id = message.video.file_id
        kind = "video"
        title = title or "video"
    elif message.document:
        file_id = message.document.file_id
        kind = "document"
        title = title or message.document.file_name or "file"
    elif message.audio:
        file_id = message.audio.file_id
        kind = "audio"
        title = title or message.audio.file_name or "audio"
    else:
        file_id = message.animation.file_id
        kind = "animation"
        title = title or "animation"

    db.execute(
        "INSERT INTO files(chat_id,title,file_id,kind) VALUES(?,?,?,?)",
        (message.chat.id, title.lower(), file_id, kind)
    )
    db.commit()
    bot.reply_to(message, "✅ File saved in movie search index!")


def search_group_files(message, query):
    rows = db.execute(
        "SELECT file_id,kind,title FROM files "
        "WHERE chat_id=? AND title LIKE ? LIMIT 5",
        (message.chat.id, "%" + query.lower() + "%")
    ).fetchall()

    if not rows:
        bot.reply_to(message, "❌ File not found. Upload it to this group first.")
        return

    for file_id, kind, title in rows:
        caption = "🎬 " + title
        if kind == "video":
            bot.send_video(message.chat.id, file_id, caption=caption)
        elif kind == "audio":
            bot.send_audio(message.chat.id, file_id, caption=caption)
        elif kind == "animation":
            bot.send_animation(message.chat.id, file_id, caption=caption)
        else:
            bot.send_document(message.chat.id, file_id, caption=caption)


@bot.message_handler(commands=["file_search"])
def file_search(message):
    q = message.text.replace("/file_search", "", 1).strip()
    if not q:
        return bot.reply_to(message, "Use: /file_search Premalu")
    search_group_files(message, q)


# SEARCH FILES WHEN A NAME IS TYPED IN THE GROUP
@bot.message_handler(
    func=lambda m: m.chat.type in ["group", "supergroup"]
    and bool(m.text) and not m.text.startswith("/")
)
def group_text_search(message):
    search_group_files(message, message.text.strip())


# WEBHOOK
@app.route("/", methods=["GET"])
def home():
    return "My Cinema Bot is running!"


@app.route("/webhook", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        update = telebot.types.Update.de_json(
            request.get_data().decode("utf-8")
        )
        bot.process_new_updates([update])
        return "OK", 200
    return "Invalid", 403


bot.set_webhook(url=BASE_URL.rstrip("/") + "/webhook")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
