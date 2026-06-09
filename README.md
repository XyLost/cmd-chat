# CMD Chat

A lightweight, terminal-based chat app that runs entirely in your command line. No browser, no install — just Python and a one-liner to get started.

Powered by **Cloudflare Workers + KV** on the backend.

```
  ════════════════════════════════════════════════════
  CMD Chat
  User : YourName
  Room : #general
  ════════════════════════════════════════════════════

  [14:32] ✦ YourName joined the room.
  [14:33] You › hey everyone!
  [14:33] Alice › hi there 👋
```

---

## Features

- 💬 Real-time messaging via long-polling
- 🔒 Password-protected rooms
- 🪪 Session tokens — your username is locked to your session, nobody can impersonate you
- 🚦 Rate limiting — prevents spam
- 👑 Master admin controls
- 🔐 All passwords stored as SHA-256 hashes
- 📏 Message length limit (500 chars)
- 🏠 Room creation limit (max 50 rooms / max 5 per user)
- 📢 System messages on join & leave

---

## Quick Start

**1. Download the client**

```bash
curl -o chat.py https://raw.githubusercontent.com/YOUR-NAME/YOUR-REPO/refs/heads/main/GitHub-Files/chat.py
```

**2. Run it**

```bash
python chat.py
```

> **Requirements:** Python 3.7+ and the `requests` library.
> Install requests if needed: `pip install requests`

---

## Usage

When you launch the app, you'll be asked for a username. A session token is automatically created — no password needed.

### General Commands

| Command          | Description                                                |
| ---------------- | ---------------------------------------------------------- |
| `/rooms`         | List all active rooms (🔒 = password protected, 🔓 = open) |
| `/create <name>` | Create a new room (optionally set a password)              |
| `/join <name>`   | Join a room — prompts for password if locked               |
| `/leave`         | Leave the current room                                     |
| `/help`          | Show all available commands                                |
| `exit`           | Quit CMD Chat                                              |

### Examples

```bash
# Create an open room
/create general

# Create a password-protected room
/create secret-room
→ Set a password for #secret-room? (leave blank for open): ••••

# Join an open room
/join general

# Join a password-protected room
/join secret-room
→ 🔒 This room is password-protected.
→ Enter room password: ••••

# List all rooms
/rooms
→   🔓 #general
→   🔒 #secret-room  ← you're here

# Leave current room
/leave
```

---

## Admin Mode

Admin commands are hidden by default. To unlock them, type:

```bash
/admin
→ Master admin password: ••••
→ ✓ Admin mode unlocked
```

Once unlocked, the `[ADMIN]` badge appears next to your username and the following commands become available:

| Command                | Description                                                |
| ---------------------- | ---------------------------------------------------------- |
| `/admin clear <room>`  | Wipe all messages in a room                                |
| `/admin delete <room>` | Permanently delete a room                                  |
| `/admin deleteall`     | Delete ALL rooms (requires typing `DELETE ALL` to confirm) |

### Admin Examples

```bash
# Clear messages in a room
/admin clear general

# Delete a specific room
/admin delete old-room
→ Delete #old-room permanently? (yes/no): yes

# Nuke everything
/admin deleteall
→ Type 'DELETE ALL' to confirm: DELETE ALL
→ Deleted 7 room(s).
```

---

## Self-Hosting (Cloudflare Workers)

Want to run your own server? You'll need a free [Cloudflare](https://cloudflare.com) account.

### 1. Create a KV Namespace

In the Cloudflare dashboard → **Workers & Pages** → **KV** → Create a namespace named `CHAT`.

### 2. Deploy the Worker

- Go to **Workers & Pages** → Create a Worker
- Paste the contents of `CloudFlare-Files/worker.js`
- In **Settings → Variables**, bind your KV namespace:
  - Variable name: `CHAT`
  - KV Namespace: the one you just created

### 3. Set Your Admin Password

Open `worker.js` and replace the placeholder on line 1:

```js
const MASTER_ADMIN_PASSWORD_HASH = "REPLACE_WITH_SHA256_OF_YOUR_ADMIN_PASSWORD";
```

Generate your hash at: https://emn178.github.io/online-tools/sha256.html

Paste the 64-character hex result into the file, then redeploy.

### 4. Point the Client at Your Worker

Open `chat.py` and update the URL on line 8:

```python
WORKER_URL = "https://your-worker-name.your-subdomain.workers.dev"
```

---

## Security Notes

- Usernames are **not** registered — they're tied to a session token valid for 24 hours. After that, the same name can be reused by anyone.
- Room passwords are hashed with SHA-256 before being stored in KV.
- The master admin password hash is stored directly in `worker.js` — keep your worker code private.
- All messages are stored in plain text in Cloudflare KV. Do not share sensitive information.

---

## Project Structure

```
cmd-chat/
├── GitHub-Files/
│   └── chat.py          # Python terminal client
├── CloudFlare-Files/
│   └── worker.js        # Cloudflare Worker (backend)
└── README.md
```

---

## License

MIT — do whatever you want with it.
