import requests
import threading
import time
import os
import sys

WORKER_URL = "https://stan-of-her.im-inferno7mm.workers.dev/"

RESET = "\033[0m"
BOLD = "\033[1m"
USER_COLORS = ["\033[94m", "\033[92m", "\033[93m",
               "\033[95m", "\033[96m", "\033[91m"]
MY_COLOR = "\033[97m"
TIME_COLOR = "\033[90m"
ROOM_COLOR = "\033[33m"
SYS_COLOR = "\033[36m"
ERROR_COLOR = "\033[31m"

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
        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7)


state = {"username": "", "room": "general",
         "last_id": 0, "running": True, "in_input": False}


def print_msg(text):
    print(f"\r{' '*70}\r{text}")
    if state["in_input"]:
        print(
            f"  {ROOM_COLOR}#{state['room']}{RESET} {MY_COLOR}{BOLD}{state['username']}{RESET} ▶ ", end="", flush=True)


def poll_thread():
    while state["running"]:
        try:
            r = requests.get(f"{WORKER_URL}/poll",
                             params={"room": state["room"], "since": state["last_id"]}, timeout=5)
            if r.status_code == 200:
                for msg in r.json():
                    uid, txt = msg["user"], msg["text"]
                    ts = time.strftime("%H:%M", time.localtime(msg["id"]/1000))
                    if uid == state["username"]:
                        line = f"  {TIME_COLOR}[{ts}]{RESET} {MY_COLOR}{BOLD}شما{RESET} {MY_COLOR}◀ {txt}{RESET}"
                    else:
                        c = get_color(uid)
                        line = f"  {TIME_COLOR}[{ts}]{RESET} {c}{BOLD}{uid}{RESET} {c}▶ {txt}{RESET}"
                    print_msg(line)
                    state["last_id"] = max(state["last_id"], msg["id"])
        except:
            pass
        time.sleep(2)


def join_room(room_name):
    if not room_name.strip():
        print(f"  {ERROR_COLOR}نام اتاق خالیه.{RESET}\n")
        return
    state["room"] = room_name.strip().lower()
    state["last_id"] = 0
    try:
        r = requests.get(f"{WORKER_URL}/poll",
                         params={"room": state["room"], "since": 0}, timeout=5)
        msgs = r.json()
        os.system("cls" if sys.platform == "win32" else "clear")
        print_header()
        print(
            f"  {SYS_COLOR}وارد اتاق {ROOM_COLOR}#{state['room']}{SYS_COLOR} شدی.{RESET}\n")
        if msgs:
            print(f"  {SYS_COLOR}--- پیام‌های اخیر ---{RESET}")
            for msg in msgs[-20:]:
                uid, txt = msg["user"], msg["text"]
                ts = time.strftime("%H:%M", time.localtime(msg["id"]/1000))
                if uid == state["username"]:
                    line = f"  {TIME_COLOR}[{ts}]{RESET} {MY_COLOR}{BOLD}شما{RESET} {MY_COLOR}◀ {txt}{RESET}"
                else:
                    c = get_color(uid)
                    line = f"  {TIME_COLOR}[{ts}]{RESET} {c}{BOLD}{uid}{RESET} {c}▶ {txt}{RESET}"
                print(line)
            state["last_id"] = max(m["id"] for m in msgs)
            print(f"  {SYS_COLOR}--- پایان ---{RESET}\n")
        else:
            print(f"  {SYS_COLOR}اتاق خالیه!{RESET}\n")
    except Exception as e:
        print(f"  {ERROR_COLOR}خطا: {e}{RESET}\n")


def show_rooms():
    try:
        rooms = requests.get(f"{WORKER_URL}/rooms", timeout=5).json()
        print(f"\n  {SYS_COLOR}اتاق‌های فعال:{RESET}")
        for rm in (rooms or ["(هنوز خالیه)"]):
            m = " ◄" if rm == state["room"] else ""
            print(f"    {ROOM_COLOR}#{rm}{RESET}{m}")
        print()
    except:
        print(f"  {ERROR_COLOR}خطا در گرفتن لیست.{RESET}\n")


def show_help():
    print(f"""
  {SYS_COLOR}══════════ دستورات ══════════
  /rooms       لیست اتاق‌ها
  /join NAME   رفتن به اتاق NAME
  /clear       پاک کردن اتاق فعلی
  /help        این راهنما
  exit         خروج
  ════════════════════════════{RESET}
""")


def print_header():
    print(f"\033[96m{'═'*50}{RESET}")
    print(f"  {BOLD}🟠 CMD Chat  |  github.com/YOUR-NAME/cmd-chat{RESET}")
    print(
        f"  کاربر: {MY_COLOR}{BOLD}{state['username']}{RESET}   اتاق: {ROOM_COLOR}{BOLD}#{state['room']}{RESET}")
    print(f"\033[96m{'═'*50}{RESET}")
    print(f"  {SYS_COLOR}/help برای راهنما{RESET}\n")


def main():
    enable_win_colors()
    os.system("cls" if sys.platform == "win32" else "clear")
    print(f"\033[96m{'═'*50}{RESET}")
    print(f"  {BOLD}🟠 CMD Chat{RESET}")
    print(f"\033[96m{'═'*50}{RESET}\n")

    username = input("  نام کاربری: ").strip()
    if not username:
        print("خالیه!")
        sys.exit(1)
    state["username"] = username

    print(f"\n  {SYS_COLOR}اتاق پیش‌فرض: {ROOM_COLOR}#general{RESET}")
    ri = input("  اسم اتاق (اینتر برای general): ").strip().lower()
    if ri:
        state["room"] = ri

    os.system("cls" if sys.platform == "win32" else "clear")
    print_header()

    # لود پیام‌های اخیر
    join_room(state["room"])

    threading.Thread(target=poll_thread, daemon=True).start()

    while state["running"]:
        try:
            state["in_input"] = True
            text = input(
                f"  {ROOM_COLOR}#{state['room']}{RESET} {MY_COLOR}{BOLD}{state['username']}{RESET} ▶ ").strip()
            state["in_input"] = False
        except (KeyboardInterrupt, EOFError):
            state["running"] = False
            print(f"\n  {SYS_COLOR}خداحافظ! 👋{RESET}")
            break

        if not text:
            continue
        if text == "exit":
            state["running"] = False
            print(f"  {SYS_COLOR}خداحافظ! 👋{RESET}")
            break
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
                print(f"  {SYS_COLOR}پاک شد.{RESET}\n")
            except:
                print(f"  {ERROR_COLOR}خطا.{RESET}\n")
        elif text.startswith("/"):
            print(f"  {ERROR_COLOR}دستور نامعلوم.{RESET}\n")
        else:
            try:
                requests.post(f"{WORKER_URL}/send",
                              json={"room": state["room"], "user": state["username"], "text": text}, timeout=5)
            except Exception as e:
                print(f"  {ERROR_COLOR}⚠ خطا: {e}{RESET}\n")


if __name__ == "__main__":
    main()
