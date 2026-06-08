import requests
import threading
import time
import os
import sys

WORKER_URL = "https://stan-of-her.im-inferno7mm.workers.dev"

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
    print(f"  Room : {ROOM_COLOR}{BOLD}#{state['room']}{RESET}")
    print(f"{CYAN}{'=' * 50}{RESET}\n")


def api_get(path, params=None):
    """GET helper — returns parsed JSON or None on error."""
    try:
        r = requests.get(f"{WORKER_URL}{path}", params=params, timeout=6)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print_msg(f"  {ERROR_COLOR}Network error: {e}{RESET}")
    return None


def api_post(path, body):
    """POST helper — returns True on success."""
    try:
        r = requests.post(f"{WORKER_URL}{path}", json=body, timeout=6)
        return r.status_code == 200
    except Exception as e:
        print_msg(f"  {ERROR_COLOR}Network error: {e}{RESET}")
    return False

# ── Announce join / leave ─────────────────────────────────────────


def announce(action):
    """action: 'joined' or 'left'"""
    api_post("/send", {
        "room": state["room"],
        "user": "__system__",
        "text": f"{state['username']} {action} the room.",
    })

# ── Poll thread ───────────────────────────────────────────────────


def poll_thread():
    while state["running"]:
        if state["room"]:
            data = api_get(
                "/poll", {"room": state["room"], "since": state["last_id"]})
            if data:
                for msg in data:
                    uid = msg["user"]
                    txt = msg["text"]
                    ts = time.strftime(
                        "%H:%M", time.localtime(msg["id"] / 1000))

                    if uid == "__system__":
                        line = f"  {SYS_COLOR}[{ts}] * {txt}{RESET}"
                    elif uid == state["username"]:
                        line = (f"  {TIME_COLOR}[{ts}]{RESET} "
                                f"{MY_COLOR}{BOLD}You{RESET} "
                                f"{MY_COLOR}> {txt}{RESET}")
                    else:
                        c = get_color(uid)
                        line = (f"  {TIME_COLOR}[{ts}]{RESET} "
                                f"{c}{BOLD}{uid}{RESET} "
                                f"{c}> {txt}{RESET}")

                    print_msg(line)
                    state["last_id"] = max(state["last_id"], msg["id"])
        time.sleep(2)

# ── Load room history ─────────────────────────────────────────────


def load_history(room_name):
    msgs = api_get("/poll", {"room": room_name, "since": 0})
    if not msgs:
        print(f"  {SYS_COLOR}Room is empty. Say hello!{RESET}\n")
        return

    print(f"  {SYS_COLOR}--- Last {min(20, len(msgs))} messages ---{RESET}")
    for msg in msgs[-20:]:
        uid = msg["user"]
        txt = msg["text"]
        ts = time.strftime("%H:%M", time.localtime(msg["id"] / 1000))
        if uid == "__system__":
            print(f"  {SYS_COLOR}[{ts}] * {txt}{RESET}")
        elif uid == state["username"]:
            print(
                f"  {TIME_COLOR}[{ts}]{RESET} {MY_COLOR}{BOLD}You{RESET} {MY_COLOR}> {txt}{RESET}")
        else:
            c = get_color(uid)
            print(
                f"  {TIME_COLOR}[{ts}]{RESET} {c}{BOLD}{uid}{RESET} {c}> {txt}{RESET}")

    state["last_id"] = max(m["id"] for m in msgs)
    print(f"  {SYS_COLOR}--- End of history ---{RESET}\n")

# ── Join room ─────────────────────────────────────────────────────


def join_room(room_name, first=False):
    room_name = room_name.strip().lower()
    if not room_name:
        print(f"  {ERROR_COLOR}Room name cannot be empty.{RESET}\n")
        return

    # announce leave from old room
    if state["room"] and not first:
        announce("left")

    state["room"] = room_name
    state["last_id"] = 0

    clear()
    print_header()

    # announce join
    announce("joined")

    load_history(room_name)

# ── Commands ──────────────────────────────────────────────────────


def show_rooms():
    data = api_get("/rooms")
    print(f"\n  {SYS_COLOR}Active rooms:{RESET}")
    if data:
        for rm in data:
            marker = f"  {SYS_COLOR}<-- you are here{RESET}" if rm == state["room"] else ""
            print(f"    {ROOM_COLOR}#{rm}{RESET}{marker}")
    else:
        print(f"    {SYS_COLOR}(none yet){RESET}")
    print()


def show_help():
    print(f"""
  {SYS_COLOR}========== Commands ==========
  /rooms         List active rooms
  /join NAME     Switch to room NAME
  /clear         Clear current room messages
  /help          Show this help
  exit           Quit
  =============================={RESET}
""")

# ── Setup screen (username + room, then help) ─────────────────────


def setup():
    clear()
    print(f"{CYAN}{'=' * 50}{RESET}")
    print(f"  {BOLD}[CMD Chat]{RESET}")
    print(f"{CYAN}{'=' * 50}{RESET}\n")

    # username
    while True:
        username = input("  Enter username: ").strip()
        if username:
            break
        print(f"  {ERROR_COLOR}Username cannot be empty.{RESET}")
    state["username"] = username

    # room
    print()
    while True:
        room = input("  Enter room name: ").strip().lower()
        if room:
            break
        print(f"  {ERROR_COLOR}Room name cannot be empty.{RESET}")

    clear()

    # show help before entering room
    print(f"{CYAN}{'=' * 50}{RESET}")
    print(
        f"  {BOLD}[CMD Chat]  Welcome, {MY_COLOR}{username}{RESET}{BOLD}!{RESET}")
    print(f"{CYAN}{'=' * 50}{RESET}")
    print(f"""
  {SYS_COLOR}========== Commands ==========
  /rooms         List active rooms
  /join NAME     Switch to room NAME
  /clear         Clear current room messages
  /help          Show this help
  exit           Quit
  =============================={RESET}
""")
    input(
        f"  {SYS_COLOR}Press Enter to join {ROOM_COLOR}#{room}{SYS_COLOR}...{RESET}")

    return room

# ── Main ──────────────────────────────────────────────────────────


def main():
    enable_win_colors()

    room = setup()

    # start poll thread before join so we don't miss messages
    threading.Thread(target=poll_thread, daemon=True).start()

    join_room(room, first=True)

    while state["running"]:
        try:
            prompt = (f"  {ROOM_COLOR}#{state['room']}{RESET} "
                      f"{MY_COLOR}{BOLD}{state['username']}{RESET} > ")
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
            announce("left")
            print(f"  {SYS_COLOR}Goodbye! o/{RESET}")

        elif text == "/help":
            show_help()

        elif text == "/rooms":
            show_rooms()

        elif text.startswith("/join "):
            join_room(text[6:])

        elif text == "/clear":
            if api_post("/clear", {"room": state["room"]}):
                state["last_id"] = 0
                print(f"  {SYS_COLOR}Room cleared.{RESET}\n")
            else:
                print(f"  {ERROR_COLOR}Clear failed.{RESET}\n")

        elif text.startswith("/"):
            print(f"  {ERROR_COLOR}Unknown command. Type /help.{RESET}\n")

        else:
            if not api_post("/send", {
                "room": state["room"],
                "user": state["username"],
                "text": text,
            }):
                print(f"  {ERROR_COLOR}Failed to send message.{RESET}\n")


if __name__ == "__main__":
    main()
