"""
CMD Chat – Python Client
Features:
  ✅ Session Token (register on startup, token sent with every request)
  ✅ Identity forgery prevention (username locked to session)
  ✅ Room passwords (enter when joining/creating locked rooms)
  ✅ Rate limit feedback (shows server error gracefully)
  ✅ Master Admin mode (/admin commands)
  ✅ Message length limit enforced client-side + server error shown
  ✅ System join/leave messages
"""

import requests
import threading
import time
import os
import sys
import getpass

# ── Config ────────────────────────────────────────────────────────
WORKER_URL = "https://stan-of-her.im-inferno7mm.workers.dev"
POLL_INTERVAL = 3
MAX_MSG_LEN = 500

# ── ANSI Colors ───────────────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
USER_COLORS = ["\033[94m", "\033[92m", "\033[93m",
               "\033[95m", "\033[96m", "\033[91m"]
MY_COLOR = "\033[97m"
TIME_COLOR = "\033[90m"
ROOM_COLOR = "\033[33m"
SYS_COLOR = "\033[36m"
ERR_COLOR = "\033[31m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
LOCK_ICON = "🔒"
OPEN_ICON = "🔓"

color_map = {}
color_idx = [0]


def get_color(u):
    if u not in color_map:
        color_map[u] = USER_COLORS[color_idx[0] % len(USER_COLORS)]
        color_idx[0] += 1
    return color_map[u]


def enable_win_colors():
    if sys.platform == "win32":
        import ctypes
        k = ctypes.windll.kernel32
        k.SetConsoleMode(k.GetStdHandle(-11), 7)


# ── State ─────────────────────────────────────────────────────────
state = {
    "username": "",
    "session_token": "",
    "room": "",
    "last_id": 0,
    "running": True,
    "in_input": False,
    "is_admin": False,
}

# ── UI Helpers ────────────────────────────────────────────────────


def clear():
    os.system("cls" if sys.platform == "win32" else "clear")


def print_msg(text):
    print(f"\r{' ' * 80}\r{text}")
    if state["in_input"] and state["room"]:
        print(_prompt(), end="", flush=True)


def _prompt():
    admin_badge = f" {YELLOW}[ADMIN]{RESET}" if state["is_admin"] else ""
    return (f"  {ROOM_COLOR}#{state['room']}{RESET} "
            f"{MY_COLOR}{BOLD}{state['username']}{RESET}{admin_badge} > ")


def print_header():
    admin_badge = f"  {YELLOW}{BOLD}[ADMIN MODE]{RESET}\n" if state["is_admin"] else ""
    print(f"{CYAN}{'═' * 52}{RESET}")
    print(f"  {BOLD}CMD Chat{RESET}")
    print(f"  User : {MY_COLOR}{BOLD}{state['username']}{RESET}")
    if state["room"]:
        print(f"  Room : {ROOM_COLOR}{BOLD}#{state['room']}{RESET}")
    print(f"{CYAN}{'═' * 52}{RESET}")
    if admin_badge:
        print(admin_badge, end="")
    print()

# ── API ───────────────────────────────────────────────────────────


def _headers():
    return {
        "Content-Type": "application/json",
        "X-Session-Token": state["session_token"],
    }


def api_get(path, params=None):
    try:
        r = requests.get(f"{WORKER_URL}{path}", params=params,
                         headers=_headers(), timeout=6)
        if r.status_code == 200:
            return r.json()
        data = r.json() if r.headers.get("Content-Type",
                                         "").startswith("application/json") else {}
        msg = data.get("error", f"HTTP {r.status_code}")
        print_msg(f"  {ERR_COLOR}[!] {msg}{RESET}")
    except Exception as e:
        print_msg(f"  {ERR_COLOR}[!] Network error: {e}{RESET}")
    return None


def api_post(path, body, token_override=None):
    hdrs = _headers()
    if token_override is not None:
        hdrs["X-Session-Token"] = token_override
    try:
        r = requests.post(f"{WORKER_URL}{path}", json=body,
                          headers=hdrs, timeout=6)
        if r.status_code == 200:
            return r.json()
        data = r.json() if r.headers.get("Content-Type",
                                         "").startswith("application/json") else {}
        msg = data.get("error", f"HTTP {r.status_code}")
        print_msg(f"  {ERR_COLOR}[!] {msg}{RESET}")
    except Exception as e:
        print_msg(f"  {ERR_COLOR}[!] Network error: {e}{RESET}")
    return None

# ── Registration ──────────────────────────────────────────────────


def register(username):
    """Register with the server and get a session token."""
    try:
        r = requests.post(f"{WORKER_URL}/register",
                          json={"username": username}, timeout=6)
        if r.status_code == 200:
            data = r.json()
            return data.get("token"), data.get("username")
        data = r.json()
        print(
            f"  {ERR_COLOR}[!] {data.get('error', 'Registration failed')}{RESET}")
    except Exception as e:
        print(f"  {ERR_COLOR}[!] Network error: {e}{RESET}")
    return None, None

# ── Poll thread ───────────────────────────────────────────────────


def poll_thread():
    while state["running"]:
        if state["room"] and state["session_token"]:
            data = api_get(
                "/poll", {"room": state["room"], "since": state["last_id"]})
            if data:
                for msg in data:
                    print_msg(fmt(msg))
                    state["last_id"] = max(state["last_id"], msg["id"])
        time.sleep(POLL_INTERVAL)


def load_history():
    msgs = api_get("/poll", {"room": state["room"], "since": 0})
    if not msgs:
        print(f"  {SYS_COLOR}Room is empty. Say hello!{RESET}\n")
        return
    print(f"  {SYS_COLOR}─── Last {min(20, len(msgs))} messages ───{RESET}")
    for msg in msgs[-20:]:
        print(fmt(msg))
    state["last_id"] = max(m["id"] for m in msgs)
    print(f"  {SYS_COLOR}─── End of history ──────{RESET}\n")


def fmt(msg):
    uid = msg["user"]
    txt = msg["text"]
    ts = time.strftime("%H:%M", time.localtime(msg["id"] / 1000))
    if uid == "__system__":
        return f"  {SYS_COLOR}[{ts}] ✦ {txt}{RESET}"
    elif uid == state["username"]:
        return (f"  {TIME_COLOR}[{ts}]{RESET} "
                f"{MY_COLOR}{BOLD}You{RESET} {MY_COLOR}› {txt}{RESET}")
    else:
        c = get_color(uid)
        return (f"  {TIME_COLOR}[{ts}]{RESET} "
                f"{c}{BOLD}{uid}{RESET} {c}› {txt}{RESET}")

# ── Room actions ──────────────────────────────────────────────────


def join_room(room_name, password=None):
    room_name = room_name.strip().lower()
    if not room_name:
        print(f"  {ERR_COLOR}Room name cannot be empty.{RESET}\n")
        return

    body = {"room": room_name}
    if password:
        body["password"] = password

    result = api_post("/join", body)
    if not result:
        return  # error already printed

    if state["room"]:
        api_post("/leave", {"room": state["room"]})

    state["room"] = room_name
    state["last_id"] = 0
    clear()
    print_header()
    load_history()


def join_room_interactive(room_name, has_password=False):
    """Join, asking for password if needed."""
    password = None
    if has_password:
        print(f"  {LOCK_ICON} {YELLOW}This room is password-protected.{RESET}")
        password = getpass.getpass("  Enter room password: ")
    join_room(room_name, password)


def create_room(room_name):
    room_name = room_name.strip().lower()
    if not room_name:
        print(f"  {ERR_COLOR}Room name cannot be empty.{RESET}\n")
        return

    want_pw = input(
        f"  Set a password for #{room_name}? (leave blank for open): ").strip()
    body = {"roomName": room_name}
    if want_pw:
        body["password"] = want_pw

    result = api_post("/create", body)
    if not result:
        return

    if state["room"]:
        api_post("/leave", {"room": state["room"]})

    state["room"] = room_name
    state["last_id"] = 0
    clear()
    print_header()
    icon = LOCK_ICON if want_pw else OPEN_ICON
    print(
        f"  {SYS_COLOR}Room {ROOM_COLOR}#{room_name}{SYS_COLOR} created {icon}{RESET}")
    if want_pw:
        print(f"  {YELLOW}Password protected. Share the password privately.{RESET}")
    else:
        print(
            f"  {SYS_COLOR}Others can join with:{RESET} {CYAN}/join {room_name}{RESET}")
    print()
    load_history()

# ── Commands ──────────────────────────────────────────────────────


def show_rooms():
    data = api_get("/rooms")
    print(f"\n  {SYS_COLOR}Active rooms:{RESET}")
    if data:
        for rm in data:
            name = rm["name"]
            icon = LOCK_ICON if rm.get("hasPassword") else OPEN_ICON
            here = f"  {SYS_COLOR}← you're here{RESET}" if name == state["room"] else ""
            print(f"    {icon} {ROOM_COLOR}#{name}{RESET}{here}")
    else:
        print(f"    {SYS_COLOR}(no rooms yet){RESET}")
    print()


def show_help():
    in_room = state["room"] != ""
    admin_cmds = """
  /admin clear <room>   Clear room messages
  /admin delete <room>  Delete a room permanently
  /admin deleteall      Delete ALL rooms""" if state["is_admin"] else ""

    room_cmds = """
  /join <name>          Join a room (asks for password if needed)
  /create <name>        Create a new room
  /rooms                List all active rooms
  /leave                Leave current room""" if in_room else """
  /join <name>          Join a room
  /create <name>        Create a new room
  /rooms                List all rooms"""

    print(f"""
  {SYS_COLOR}════════════ Commands ════════════{room_cmds}{admin_cmds}
  /help                 Show this help
  exit                  Quit
  ══════════════════════════════════{RESET}
""")


def admin_mode():
    """Unlock admin commands for this session."""
    if state["is_admin"]:
        print(f"  {YELLOW}Already in admin mode.{RESET}\n")
        return
    pw = getpass.getpass("  Master admin password: ")
    # We validate indirectly: send a harmless admin call and see if 403 comes back
    # Using /admin/delete-room with a dummy room to test the password
    r = api_post("/admin/clear-room",
                 {"room": "__test_auth__", "adminPassword": pw})
    # If error says "room not found" → password was correct
    # If error says "wrong admin password" → rejected
    # We need to check the raw response, so do it manually:
    try:
        raw = requests.post(f"{WORKER_URL}/admin/clear-room",
                            json={"room": "__test_auth_room__",
                                  "adminPassword": pw},
                            timeout=6)
        data = raw.json()
        if raw.status_code in (200, 404) or data.get("error") == "room not found":
            state["is_admin"] = True
            state["admin_password"] = pw
            print(f"  {GREEN}{BOLD}Admin mode unlocked ✓{RESET}\n")
        else:
            print(f"  {ERR_COLOR}Wrong password.{RESET}\n")
    except Exception as e:
        print(f"  {ERR_COLOR}Error: {e}{RESET}\n")


def admin_clear(room):
    if not state.get("admin_password"):
        print(f"  {ERR_COLOR}Not in admin mode. Use /admin first.{RESET}\n")
        return
    result = api_post("/admin/clear-room",
                      {"room": room, "adminPassword": state["admin_password"]})
    if result:
        print(f"  {GREEN}Room #{room} cleared.{RESET}\n")


def admin_delete(room):
    if not state.get("admin_password"):
        print(f"  {ERR_COLOR}Not in admin mode. Use /admin first.{RESET}\n")
        return
    confirm = input(
        f"  {ERR_COLOR}Delete #{room} permanently? (yes/no): {RESET}").strip()
    if confirm.lower() != "yes":
        print(f"  {SYS_COLOR}Cancelled.{RESET}\n")
        return
    result = api_post("/admin/delete-room",
                      {"room": room, "adminPassword": state["admin_password"]})
    if result:
        if state["room"] == room:
            state["room"] = ""
            state["last_id"] = 0
        print(f"  {GREEN}Room #{room} deleted.{RESET}\n")


def admin_deleteall():
    if not state.get("admin_password"):
        print(f"  {ERR_COLOR}Not in admin mode. Use /admin first.{RESET}\n")
        return
    confirm = input(
        f"  {ERR_COLOR}Delete ALL rooms? Type 'DELETE ALL' to confirm: {RESET}").strip()
    if confirm != "DELETE ALL":
        print(f"  {SYS_COLOR}Cancelled.{RESET}\n")
        return
    result = api_post("/admin/delete-all-rooms",
                      {"adminPassword": state["admin_password"]})
    if result:
        deleted = result.get("deleted", "?")
        state["room"] = ""
        state["last_id"] = 0
        print(f"  {GREEN}Deleted {deleted} room(s).{RESET}\n")

# ── Lobby ─────────────────────────────────────────────────────────


def lobby():
    clear()
    print_header()
    show_help()
    data = api_get("/rooms")
    if data:
        print(f"  {SYS_COLOR}Available rooms:{RESET}")
        for rm in data:
            icon = LOCK_ICON if rm.get("hasPassword") else OPEN_ICON
            print(f"    {icon} {ROOM_COLOR}#{rm['name']}{RESET}")
        print()

# ── Setup ─────────────────────────────────────────────────────────


def setup():
    clear()
    print(f"{CYAN}{'═' * 52}{RESET}")
    print(f"  {BOLD}CMD Chat{RESET}")
    print(f"{CYAN}{'═' * 52}{RESET}\n")
    print(f"  {SYS_COLOR}Connecting to server...{RESET}")

    while True:
        username = input("\n  Choose a username: ").strip()
        if not username:
            print(f"  {ERR_COLOR}Username cannot be empty.{RESET}")
            continue
        print(f"  {SYS_COLOR}Registering...{RESET}", end="", flush=True)
        token, confirmed_name = register(username)
        if token:
            state["username"] = confirmed_name
            state["session_token"] = token
            print(
                f"\r  {GREEN}Logged in as {BOLD}{confirmed_name}{RESET} ✓{' ' * 20}")
            break
        print(f"\r  {ERR_COLOR}Try a different username.{RESET}{' ' * 20}")

# ── Main loop ─────────────────────────────────────────────────────


def main():
    enable_win_colors()
    setup()

    threading.Thread(target=poll_thread, daemon=True).start()
    lobby()

    while state["running"]:
        try:
            if state["room"]:
                prompt = _prompt()
            else:
                admin_badge = f" {YELLOW}[ADMIN]{RESET}" if state["is_admin"] else ""
                prompt = f"  {MY_COLOR}{BOLD}{state['username']}{RESET}{admin_badge} > "

            state["in_input"] = True
            text = input(prompt).strip()
            state["in_input"] = False

        except (KeyboardInterrupt, EOFError):
            state["running"] = False
            if state["room"]:
                api_post("/leave", {"room": state["room"]})
            print(f"\n  {SYS_COLOR}Goodbye! o/{RESET}")
            break

        if not text:
            continue

        # ── exit ──────────────────────────────────────────────────
        if text == "exit":
            state["running"] = False
            if state["room"]:
                api_post("/leave", {"room": state["room"]})
            print(f"  {SYS_COLOR}Goodbye! o/{RESET}")

        # ── /help ─────────────────────────────────────────────────
        elif text == "/help":
            show_help()

        # ── /rooms ───────────────────────────────────────────────
        elif text == "/rooms":
            show_rooms()

        # ── /join ────────────────────────────────────────────────
        elif text.startswith("/join "):
            rname = text[6:].strip().lower()
            # check if it has password
            rooms_data = api_get("/rooms")
            has_pw = False
            if rooms_data:
                for rm in rooms_data:
                    if rm["name"] == rname:
                        has_pw = rm.get("hasPassword", False)
                        break
            join_room_interactive(rname, has_pw)

        # ── /create ──────────────────────────────────────────────
        elif text.startswith("/create "):
            create_room(text[8:])

        # ── /leave ───────────────────────────────────────────────
        elif text == "/leave":
            if not state["room"]:
                print(f"  {ERR_COLOR}You are not in a room.{RESET}\n")
            else:
                api_post("/leave", {"room": state["room"]})
                state["room"] = ""
                state["last_id"] = 0
                lobby()

        # ── /admin ───────────────────────────────────────────────
        elif text == "/admin":
            admin_mode()

        elif text.startswith("/admin "):
            parts = text.split()
            if not state["is_admin"]:
                print(
                    f"  {ERR_COLOR}Use /admin to unlock admin mode first.{RESET}\n")
            elif len(parts) == 3 and parts[1] == "clear":
                admin_clear(parts[2])
            elif len(parts) == 3 and parts[1] == "delete":
                admin_delete(parts[2])
            elif len(parts) == 2 and parts[1] == "deleteall":
                admin_deleteall()
            else:
                print(f"  {ERR_COLOR}Unknown admin command. Use /help.{RESET}\n")

        # ── unknown command ───────────────────────────────────────
        elif text.startswith("/"):
            print(f"  {ERR_COLOR}Unknown command. Type /help.{RESET}\n")

        # ── message ───────────────────────────────────────────────
        else:
            if not state["room"]:
                print(
                    f"  {ERR_COLOR}Not in a room. Use /create or /join first.{RESET}\n")
            elif len(text) > MAX_MSG_LEN:
                print(
                    f"  {ERR_COLOR}Message too long ({len(text)}/{MAX_MSG_LEN} chars).{RESET}\n")
            else:
                api_post("/send", {"room": state["room"], "text": text})


if __name__ == "__main__":
    main()
