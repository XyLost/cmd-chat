import requests
import threading
import time
import os
import sys

WORKER_URL = "https://stan-of-her.im-inferno7mm.workers.dev"
POLL_INTERVAL = 3

# ── Colors ────────────────────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
USER_COLORS = ["\033[94m", "\033[92m", "\033[93m",
               "\033[95m", "\033[96m", "\033[91m"]
MY_COLOR = "\033[97m"
TIME_COLOR = "\033[90m"
ROOM_COLOR = "\033[33m"
SYS_COLOR = "\033[36m"
ERROR_COLOR = "\033[31m"
CYAN = "\033[96m"

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
    "room": "",
    "last_id": 0,
    "running": True,
    "in_input": False,
}

# ── Helpers ───────────────────────────────────────────────────────


def clear():
    os.system("cls" if sys.platform == "win32" else "clear")


def print_msg(text):
    print(f"\r{' ' * 70}\r{text}")
    if state["in_input"] and state["room"]:
        prompt = (f"  {ROOM_COLOR}#{state['room']}{RESET} "
                  f"{MY_COLOR}{BOLD}{state['username']}{RESET} > ")
        print(prompt, end="", flush=True)


def print_header():
    print(f"{CYAN}{'=' * 50}{RESET}")
    print(f"  {BOLD}[CMD Chat]{RESET}")
    print(f"  User : {MY_COLOR}{BOLD}{state['username']}{RESET}")
    if state["room"]:
        print(f"  Room : {ROOM_COLOR}{BOLD}#{state['room']}{RESET}")
    print(f"{CYAN}{'=' * 50}{RESET}\n")


def api_get(path, params=None):
    try:
        r = requests.get(f"{WORKER_URL}{path}", params=params, timeout=6)
        if r.status_code == 200:
            return r.json()
        else:
            print_msg(
                f"  {ERROR_COLOR}[GET {path}] status {r.status_code}{RESET}")
    except Exception as e:
        print_msg(f"  {ERROR_COLOR}[GET {path}] {e}{RESET}")
    return None


def api_post(path, body):
    try:
        r = requests.post(f"{WORKER_URL}{path}", json=body, timeout=6)
        if r.status_code == 200:
            return True
        else:
            print_msg(
                f"  {ERROR_COLOR}[POST {path}] status {r.status_code}{RESET}")
    except Exception as e:
        print_msg(f"  {ERROR_COLOR}[POST {path}] {e}{RESET}")
    return False


def announce(action):
    api_post("/send", {
        "room": state["room"],
        "user": "__system__",
        "text": f"{state['username']} {action} the room.",
    })


def fmt(msg):
    uid = msg["user"]
    txt = msg["text"]
    ts = time.strftime("%H:%M", time.localtime(msg["id"] / 1000))
    if uid == "__system__":
        return f"  {SYS_COLOR}[{ts}] * {txt}{RESET}"
    elif uid == state["username"]:
        return (f"  {TIME_COLOR}[{ts}]{RESET} "
                f"{MY_COLOR}{BOLD}You{RESET} "
                f"{MY_COLOR}> {txt}{RESET}")
    else:
        c = get_color(uid)
        return (f"  {TIME_COLOR}[{ts}]{RESET} "
                f"{c}{BOLD}{uid}{RESET} "
                f"{c}> {txt}{RESET}")

# ── Poll thread ───────────────────────────────────────────────────


def poll_thread():
    while state["running"]:
        if state["room"]:
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
    print(f"  {SYS_COLOR}--- Last {min(20, len(msgs))} messages ---{RESET}")
    for msg in msgs[-20:]:
        print(fmt(msg))
    state["last_id"] = max(m["id"] for m in msgs)
    print(f"  {SYS_COLOR}--- End of history ---{RESET}\n")

# ── Join / Create room ────────────────────────────────────────────


def join_room(room_name, first=False):
    room_name = room_name.strip().lower()
    if not room_name:
        print(f"  {ERROR_COLOR}Room name cannot be empty.{RESET}\n")
        return

    if state["room"] and not first:
        announce("left")

    state["room"] = room_name
    state["last_id"] = 0

    clear()
    print_header()
    announce("joined")
    load_history()


def create_room(room_name):
    room_name = room_name.strip().lower()
    if not room_name:
        print(f"  {ERROR_COLOR}Room name cannot be empty.{RESET}\n")
        return

    # check if room already exists
    existing = api_get("/rooms")
    if existing and room_name in existing:
        print(
            f"  {ERROR_COLOR}Room #{room_name} already exists. Use /join {room_name}{RESET}\n")
        return

    # join it (first send creates it in KV)
    if state["room"]:
        announce("left")

    state["room"] = room_name
    state["last_id"] = 0

    clear()
    print_header()
    # send a system message to register the room
    announce("created")
    print(f"  {SYS_COLOR}Room {ROOM_COLOR}#{room_name}{SYS_COLOR} created! Others can join with:{RESET}")
    print(f"  {CYAN}/join {room_name}{RESET}\n")

# ── Commands ──────────────────────────────────────────────────────


def show_rooms():
    data = api_get("/rooms")
    print(f"\n  {SYS_COLOR}Active rooms:{RESET}")
    if data:
        for rm in data:
            here = f"  {SYS_COLOR}<-- you{RESET}" if rm == state["room"] else ""
            print(f"    {ROOM_COLOR}#{rm}{RESET}{here}")
    else:
        print(f"    {SYS_COLOR}(none yet){RESET}")
    print()


def show_help():
    in_room = state["room"] != ""
    room_commands = f"""
  /join NAME     Join an existing room
  /create NAME   Create a new room""" if not in_room else f"""
  /join NAME     Switch to another room
  /create NAME   Create a new room
  /rooms         List all active rooms
  /clear         Clear current room messages"""

    print(f"""
  {SYS_COLOR}========== Commands =========={room_commands}
  /help          Show this help
  exit           Quit
  =============================={RESET}
""")

# ── Lobby screen (no room) ────────────────────────────────────────


def lobby():
    """Screen shown when user is logged in but not in any room."""
    clear()
    print_header()
    show_help()

    # show existing rooms
    data = api_get("/rooms")
    if data:
        print(f"  {SYS_COLOR}Active rooms you can join:{RESET}")
        for rm in data:
            print(f"    {ROOM_COLOR}#{rm}{RESET}")
        print()

# ── Setup screen ──────────────────────────────────────────────────


def setup():
    clear()
    print(f"{CYAN}{'=' * 50}{RESET}")
    print(f"  {BOLD}[CMD Chat]{RESET}")
    print(f"{CYAN}{'=' * 50}{RESET}\n")

    while True:
        username = input("  Enter username: ").strip()
        if username:
            break
        print(f"  {ERROR_COLOR}Username cannot be empty.{RESET}")
    state["username"] = username

# ── Main ──────────────────────────────────────────────────────────


def main():
    enable_win_colors()
    setup()

    threading.Thread(target=poll_thread, daemon=True).start()

    # show lobby (no room yet)
    lobby()

    while state["running"]:
        try:
            if state["room"]:
                prompt = (f"  {ROOM_COLOR}#{state['room']}{RESET} "
                          f"{MY_COLOR}{BOLD}{state['username']}{RESET} > ")
            else:
                prompt = f"  {MY_COLOR}{BOLD}{state['username']}{RESET} > "

            state["in_input"] = True
            text = input(prompt).strip()
            state["in_input"] = False

        except (KeyboardInterrupt, EOFError):
            state["running"] = False
            if state["room"]:
                announce("left")
            print(f"\n  {SYS_COLOR}Goodbye! o/{RESET}")
            break

        if not text:
            continue

        if text == "exit":
            state["running"] = False
            if state["room"]:
                announce("left")
            print(f"  {SYS_COLOR}Goodbye! o/{RESET}")

        elif text == "/help":
            show_help()

        elif text == "/rooms":
            show_rooms()

        elif text.startswith("/join "):
            join_room(text[6:])

        elif text.startswith("/create "):
            create_room(text[8:])

        elif text == "/clear":
            if not state["room"]:
                print(f"  {ERROR_COLOR}You are not in a room.{RESET}\n")
            elif api_post("/clear", {"room": state["room"]}):
                state["last_id"] = 0
                print(f"  {SYS_COLOR}Room cleared.{RESET}\n")
            else:
                print(f"  {ERROR_COLOR}Clear failed.{RESET}\n")

        elif text.startswith("/"):
            print(f"  {ERROR_COLOR}Unknown command. Type /help.{RESET}\n")

        else:
            if not state["room"]:
                print(
                    f"  {ERROR_COLOR}You are not in a room. Use /create NAME or /join NAME first.{RESET}\n")
            else:
                api_post("/send", {
                    "room": state["room"],
                    "user": state["username"],
                    "text": text,
                })


if __name__ == "__main__":
    main()
