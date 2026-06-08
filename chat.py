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
    "room": "general",
    "last_id": 0,
    "running": True,
    "in_input": False,
}

# ── Helpers ───────────────────────────────────────────────────────


def clear():
    os.system("cls" if sys.platform == "win32" else "clear")


def print_msg(text):
    """Print a message, redrawing the input prompt if needed."""
    print(f"\r{' ' * 70}\r{text}")
    if state["in_input"]:
        prompt = (f"  {ROOM_COLOR}#{state['room']}{RESET} "
                  f"{MY_COLOR}{BOLD}{state['username']}{RESET} > ")
        print(prompt, end="", flush=True)


def print_header():
    print(f"{CYAN}{'=' * 50}{RESET}")
    print(f"  {BOLD}[CMD Chat]{RESET}")
    print(f"  User: {MY_COLOR}{BOLD}{state['username']}{RESET}   "
          f"Room: {ROOM_COLOR}{BOLD}#{state['room']}{RESET}")
    print(f"{CYAN}{'=' * 50}{RESET}")
    print(f"  {SYS_COLOR}Type /help for commands{RESET}\n")

# ── Poll thread ───────────────────────────────────────────────────


def poll_thread():
    while state["running"]:
        try:
            r = requests.get(
                f"{WORKER_URL}/poll",
                params={"room": state["room"], "since": state["last_id"]},
                timeout=5,
            )
            if r.status_code == 200:
                for msg in r.json():
                    uid = msg["user"]
                    txt = msg["text"]
                    ts = time.strftime(
                        "%H:%M", time.localtime(msg["id"] / 1000))

                    if uid == state["username"]:
                        line = (f"  {TIME_COLOR}[{ts}]{RESET} "
                                f"{MY_COLOR}{BOLD}You{RESET} "
                                f"{MY_COLOR}< {txt}{RESET}")
                    else:
                        c = get_color(uid)
                        line = (f"  {TIME_COLOR}[{ts}]{RESET} "
                                f"{c}{BOLD}{uid}{RESET} "
                                f"{c}> {txt}{RESET}")

                    print_msg(line)
                    state["last_id"] = max(state["last_id"], msg["id"])
        except Exception:
            pass
        time.sleep(2)

# ── Join room ─────────────────────────────────────────────────────


def join_room(room_name):
    room_name = room_name.strip().lower()
    if not room_name:
        print(f"  {ERROR_COLOR}Room name cannot be empty.{RESET}\n")
        return

    state["room"] = room_name
    state["last_id"] = 0

    try:
        r = requests.get(f"{WORKER_URL}/poll",
                         params={"room": room_name, "since": 0}, timeout=5)
        msgs = r.json() if r.status_code == 200 else []
    except Exception as e:
        msgs = []
        print(f"  {ERROR_COLOR}Could not load history: {e}{RESET}\n")

    clear()
    print_header()
    print(f"  {SYS_COLOR}Joined room {ROOM_COLOR}#{room_name}{RESET}\n")

    if msgs:
        print(f"  {SYS_COLOR}--- Last {min(20, len(msgs))} messages ---{RESET}")
        for msg in msgs[-20:]:
            uid = msg["user"]
            txt = msg["text"]
            ts = time.strftime("%H:%M", time.localtime(msg["id"] / 1000))
            if uid == state["username"]:
                print(
                    f"  {TIME_COLOR}[{ts}]{RESET} {MY_COLOR}{BOLD}You{RESET} {MY_COLOR}< {txt}{RESET}")
            else:
                c = get_color(uid)
                print(
                    f"  {TIME_COLOR}[{ts}]{RESET} {c}{BOLD}{uid}{RESET} {c}> {txt}{RESET}")
        state["last_id"] = max(m["id"] for m in msgs)
        print(f"  {SYS_COLOR}--- End of history ---{RESET}\n")
    else:
        print(f"  {SYS_COLOR}Room is empty. Say hello!{RESET}\n")

# ── Commands ──────────────────────────────────────────────────────


def show_rooms():
    try:
        rooms = requests.get(f"{WORKER_URL}/rooms", timeout=5).json()
        print(f"\n  {SYS_COLOR}Active rooms:{RESET}")
        for rm in (rooms if rooms else ["(none yet)"]):
            marker = " <-- you are here" if rm == state["room"] else ""
            print(f"    {ROOM_COLOR}#{rm}{RESET}{marker}")
        print()
    except Exception:
        print(f"  {ERROR_COLOR}Could not fetch room list.{RESET}\n")


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


def send(text):
    try:
        requests.post(
            f"{WORKER_URL}/send",
            json={"room": state["room"],
                  "user": state["username"], "text": text},
            timeout=5,
        )
    except Exception as e:
        print(f"  {ERROR_COLOR}Send error: {e}{RESET}\n")

# ── Main ──────────────────────────────────────────────────────────


def main():
    enable_win_colors()
    clear()

    print(f"{CYAN}{'=' * 50}{RESET}")
    print(f"  {BOLD}[CMD Chat]{RESET}")
    print(f"{CYAN}{'=' * 50}{RESET}\n")

    # --- get username ---
    while True:
        username = input("  Username: ").strip()
        if username:
            break
        print(f"  {ERROR_COLOR}Username cannot be empty.{RESET}")
    state["username"] = username

    # --- get room ---
    print(f"\n  {SYS_COLOR}Default room: {ROOM_COLOR}#general{RESET}")
    ri = input("  Room name (Enter for general): ").strip().lower()
    if ri:
        state["room"] = ri

    # --- start polling thread ---
    threading.Thread(target=poll_thread, daemon=True).start()

    # --- load room history ---
    join_room(state["room"])

    # --- main loop ---
    while state["running"]:
        try:
            prompt = (f"  {ROOM_COLOR}#{state['room']}{RESET} "
                      f"{MY_COLOR}{BOLD}{state['username']}{RESET} > ")
            state["in_input"] = True
            text = input(prompt).strip()
            state["in_input"] = False
        except (KeyboardInterrupt, EOFError):
            state["running"] = False
            print(f"\n  {SYS_COLOR}Goodbye! o/{RESET}")
            break

        if not text:
            continue

        if text == "exit":
            state["running"] = False
            print(f"  {SYS_COLOR}Goodbye! o/{RESET}")

        elif text == "/help":
            show_help()

        elif text == "/rooms":
            show_rooms()

        elif text.startswith("/join "):
            join_room(text[6:])

        elif text == "/clear":
            try:
                requests.post(f"{WORKER_URL}/clear",
                              json={"room": state["room"]}, timeout=5)
                state["last_id"] = 0
                print(f"  {SYS_COLOR}Room cleared.{RESET}\n")
            except Exception:
                print(f"  {ERROR_COLOR}Clear failed.{RESET}\n")

        elif text.startswith("/"):
            print(f"  {ERROR_COLOR}Unknown command. Type /help.{RESET}\n")

        else:
            send(text)


if __name__ == "__main__":
    main()
