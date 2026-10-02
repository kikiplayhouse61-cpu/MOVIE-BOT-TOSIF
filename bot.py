import os
import json
import time
import secrets
import string
import requests
from datetime import datetime, timezone

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("7232582251", "0"))

API = f"https://api.telegram.org/bot{TOKEN}"
DB_FILE = "content.json"
USERS_FILE = "users.json"
STATE_FILE = "state.json"

def load_json(filename, default=None):
    if default is None:
        default = {}
    if not os.path.exists(filename):
        return default
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def api(method, data=None):
    try:
        r = requests.post(f"{API}/{method}", data=data or {}, timeout=40)
        return r.json()
    except Exception as e:
        print("Telegram API error:", e)
        return {}

def send_message(chat_id, text, keyboard=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if keyboard:
        data["reply_markup"] = json.dumps({"inline_keyboard": keyboard})
    return api("sendMessage", data)

def send_photo(chat_id, photo_id, caption, keyboard=None):
    data = {"chat_id": chat_id, "photo": photo_id, "caption": caption, "parse_mode": "HTML"}
    if keyboard:
        data["reply_markup"] = json.dumps({"inline_keyboard": keyboard})
    return api("sendPhoto", data)

def random_code():
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(10))

def new_content_code(db):
    while True:
        code = random_code()
        if code not in db:
            return code

def get_bot_username():
    try:
        result = api("getMe")
        return result["result"]["username"]
    except Exception:
        return "movie_ott_all_show_bot"

def register_user(message):
    chat = message.get("chat", {})
    user = message.get("from", {})
    chat_id = str(chat.get("id"))
    if not chat_id:
        return
    users = load_json(USERS_FILE)
    if chat_id not in users:
        users[chat_id] = {
            "id": chat.get("id"),
            "username": user.get("username", ""),
            "first_name": user.get("first_name", ""),
            "joined": datetime.now(timezone.utc).isoformat(),
            "views": 0,
            "clicks": 0
        }
        save_json(USERS_FILE, users)

def show_content(chat_id, code):
    db = load_json(DB_FILE)
    if code not in db:
        send_message(chat_id, "❌ <b>Content unavailable</b>\n\nYe link invalid ya expired hai.")
        return

    item = db[code]
    item["views"] = item.get("views", 0) + 1
    save_json(DB_FILE, db)

    users = load_json(USERS_FILE)
    uid = str(chat_id)
    if uid in users:
        users[uid]["views"] = users[uid].get("views", 0) + 1
        save_json(USERS_FILE, users)

    keyboard = []
    for quality, url in item.get("links", {}).items():
        keyboard.append([{"text": f"▶️ {quality}", "url": url}])

    caption = f"🎬 <b>{item['title']}</b>\n\n👇 <b>Apni quality select karein:</b>"

    if item.get("photo_id"):
        send_photo(chat_id, item["photo_id"], caption, keyboard)
    else:
        send_message(chat_id, caption, keyboard)

def admin_panel(chat_id):
    if chat_id != ADMIN_ID:
        send_message(chat_id, "⛔ Admin only.")
        return
    keyboard = [
        [{"text": "➕ Add Content", "callback_data": "admin_add"},
         {"text": "📚 Content", "callback_data": "admin_content"}],
        [{"text": "📊 Analytics", "callback_data": "admin_analytics"},
         {"text": "👥 Users", "callback_data": "admin_users"}],
        [{"text": "📢 Broadcast", "callback_data": "admin_broadcast"},
         {"text": "🔔 Notification", "callback_data": "admin_notification"}]
    ]
    send_message(chat_id, "👑 <b>ADMIN PANEL</b>\n\nSelect an option:", keyboard)

def analytics(chat_id):
    if chat_id != ADMIN_ID:
        return
    db = load_json(DB_FILE)
    users = load_json(USERS_FILE)
    total_views = sum(item.get("views", 0) for item in db.values())
    total_clicks = sum(user.get("clicks", 0) for user in users.values())
    send_message(
        chat_id,
        "📊 <b>BOT ANALYTICS</b>\n\n"
        f"👥 Total Users: <b>{len(users)}</b>\n"
        f"🎬 Total Content: <b>{len(db)}</b>\n"
        f"👁️ Content Views: <b>{total_views}</b>\n"
        f"🔗 Link Clicks: <b>{total_clicks}</b>"
    )

def content_list(chat_id):
    if chat_id != ADMIN_ID:
        return
    db = load_json(DB_FILE)
    if not db:
        send_message(chat_id, "📭 No content saved.")
        return
    text = "📚 <b>CONTENT MANAGER</b>\n\n"
    for code, item in db.items():
        text += f"🎬 <b>{item['title']}</b>\n🔐 Code: <code>{code}</code>\n👁️ Views: {item.get('views', 0)}\n\n"
    send_message(chat_id, text)

def start_add(chat_id):
    if chat_id != ADMIN_ID:
        send_message(chat_id, "⛔ Admin only.")
        return
    states = load_json(STATE_FILE)
    states[str(chat_id)] = {"step": "photo"}
    save_json(STATE_FILE, states)
    send_message(chat_id, "➕ <b>NEW CONTENT</b>\n\nStep 1/5\n🖼️ Poster photo bhejo.")

def process_add(message):
    chat_id = message["chat"]["id"]
    if chat_id != ADMIN_ID:
        return False

    states = load_json(STATE_FILE)
    key = str(chat_id)
    if key not in states:
        return False

    state = states[key]
    step = state["step"]

    if step == "photo":
        if "photo" not in message:
            send_message(chat_id, "❌ Poster photo bhejo.")
            return True
        state["photo_id"] = message["photo"][-1]["file_id"]
        state["step"] = "title"
        save_json(STATE_FILE, states)
        send_message(chat_id, "✅ Photo received.\n\nStep 2/5\n🎬 Movie / Show title bhejo.")
        return True

    if step == "title":
        text = message.get("text", "").strip()
        if not text:
            send_message(chat_id, "❌ Title bhejo.")
            return True
        state["title"] = text
        state["step"] = "480p"
        save_json(STATE_FILE, states)
        send_message(chat_id, "Step 3/5\n🔗 480p link bhejo.\nNahi hai to <code>skip</code>.")
        return True

    if step == "480p":
        text = message.get("text", "").strip()
        state["links"] = {}
        if text.lower() != "skip" and text:
            state["links"]["480p"] = text
        state["step"] = "720p"
        save_json(STATE_FILE, states)
        send_message(chat_id, "Step 4/5\n🔗 720p link bhejo.\nNahi hai to <code>skip</code>.")
        return True

    if step == "720p":
        text = message.get("text", "").strip()
        if text.lower() != "skip" and text:
            state["links"]["720p"] = text
        state["step"] = "1080p"
        save_json(STATE_FILE, states)
        send_message(chat_id, "Step 5/5\n🔗 1080p link bhejo.\nNahi hai to <code>skip</code>.")
        return True

    if step == "1080p":
        text = message.get("text", "").strip()
        if text.lower() != "skip" and text:
            state["links"]["1080p"] = text

        db = load_json(DB_FILE)
        code = new_content_code(db)
        db[code] = {
            "title": state["title"],
            "photo_id": state["photo_id"],
            "links": state["links"],
            "views": 0,
            "created": datetime.now(timezone.utc).isoformat()
        }
        save_json(DB_FILE, db)

        del states[key]
        save_json(STATE_FILE, states)

        link = f"https://t.me/{get_bot_username()}?start={code}"
        send_message(
            chat_id,
            "✅ <b>CONTENT SAVED</b>\n\n"
            f"🎬 <b>{state['title']}</b>\n"
            f"🔐 Code: <code>{code}</code>\n\n"
            "🔗 <b>User Link:</b>\n"
            f"{link}\n\n"
            "Is link ko channel post ke button mein use karo."
        )
        return True

    return False

def start_broadcast(chat_id):
    if chat_id != ADMIN_ID:
        return
    states = load_json(STATE_FILE)
    states[str(chat_id)] = {"step": "broadcast"}
    save_json(STATE_FILE, states)
    send_message(chat_id, "📢 <b>BROADCAST</b>\n\nAb text ya photo bhejo. /cancel se cancel kar sakte ho.")

def process_broadcast(message):
    chat_id = message["chat"]["id"]
    if chat_id != ADMIN_ID:
        return False

    states = load_json(STATE_FILE)
    key = str(chat_id)
    if key not in states or states[key].get("step") != "broadcast":
        return False

    users = load_json(USERS_FILE)
    sent = 0
    failed = 0

    for uid in users:
        try:
            if "photo" in message:
                result = send_photo(int(uid), message["photo"][-1]["file_id"], message.get("caption", ""))
            else:
                result = send_message(int(uid), message.get("text", ""))

            if result.get("ok"):
                sent += 1
            else:
                failed += 1
            time.sleep(0.05)
        except Exception:
            failed += 1

    del states[key]
    save_json(STATE_FILE, states)
    send_message(chat_id, f"✅ <b>Broadcast completed</b>\n\n📤 Sent: {sent}\n❌ Failed: {failed}")
    return True

def handle_callback(update):
    callback = update["callback_query"]
    chat_id = callback["message"]["chat"]["id"]
    data = callback.get("data", "")

    api("answerCallbackQuery", {"callback_query_id": callback["id"]})

    if chat_id != ADMIN_ID:
        return

    if data == "admin_add":
        start_add(chat_id)
    elif data == "admin_analytics":
        analytics(chat_id)
    elif data == "admin_content":
        content_list(chat_id)
    elif data == "admin_users":
        users = load_json(USERS_FILE)
        send_message(chat_id, f"👥 <b>Total Users:</b> {len(users)}")
    elif data == "admin_broadcast":
        start_broadcast(chat_id)
    elif data == "admin_notification":
        send_message(chat_id, "🔔 Notification system ready.\n\nUse /broadcast to send a notification.")

def handle_message(message):
    register_user(message)
    chat_id = message["chat"]["id"]

    if process_broadcast(message):
        return
    if process_add(message):
        return

    text = message.get("text", "").strip()

    if text == "/admin":
        admin_panel(chat_id)
        return
    if text == "/add":
        start_add(chat_id)
        return
    if text == "/broadcast":
        start_broadcast(chat_id)
        return
    if text == "/analytics":
        analytics(chat_id)
        return
    if text == "/list":
        content_list(chat_id)
        return
    if text == "/cancel":
        if chat_id == ADMIN_ID:
            states = load_json(STATE_FILE)
            states.pop(str(chat_id), None)
            save_json(STATE_FILE, states)
            send_message(chat_id, "❌ Cancelled.")
        return
    if text == "/id":
        send_message(chat_id, f"🆔 Your Telegram ID:\n<code>{chat_id}</code>")
        return
    if text.startswith("/delete "):
        if chat_id != ADMIN_ID:
            send_message(chat_id, "⛔ Admin only.")
            return
        code = text.split(maxsplit=1)[1]
        db = load_json(DB_FILE)
        if code not in db:
            send_message(chat_id, "❌ Content not found.")
            return
        title = db[code]["title"]
        del db[code]
        save_json(DB_FILE, db)
        send_message(chat_id, f"🗑️ Deleted:\n<b>{title}</b>")
        return
    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        if len(parts) == 1:
            send_message(chat_id, "👋 <b>Welcome!</b>\n\nChannel se mila hua content link open karein.")
        else:
            show_content(chat_id, parts[1].strip())
        return

def main():
    if not TOKEN:
        print("❌ BOT_TOKEN missing")
        return
    if not ADMIN_ID:
        print("❌ ADMIN_ID missing")
        return

    print("🤖 Bot started...")
    offset = None

    while True:
        try:
            result = api("getUpdates", {"timeout": 30, "offset": offset})
            if result.get("ok"):
                for update in result.get("result", []):
                    offset = update["update_id"] + 1
                    if "message" in update:
                        handle_message(update["message"])
                    elif "callback_query" in update:
                        handle_callback(update)
        except Exception as e:
            print("Error:", e)
            time.sleep(3)

if __name__ == "__main__":
    main()
