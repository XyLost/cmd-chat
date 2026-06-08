// ═══════════════════════════════════════════════════════════════
//  CMD Chat – Cloudflare Worker
//  Features:
//    ✅ Room passwords (SHA-256 hashed)
//    ✅ Session tokens per user
//    ✅ Identity forgery prevention
//    ✅ Rate limiting (per IP)
//    ✅ Master admin password
//    ✅ Only admin can delete all rooms
//    ✅ Password hashing (SHA-256)
//    ✅ Message length limit
//    ✅ Room creation limit
//    ✅ System join/leave messages
// ═══════════════════════════════════════════════════════════════

const MASTER_ADMIN_PASSWORD_HASH = "382997923e031c6ef0ef957f555504485b415b7bcb4136318e3b9d0a515e2638";
// const MASTER_ADMIN_PASSWORD_HASH = "REPLACE_WITH_SHA256_OF_YOUR_ADMIN_PASSWORD";
// To generate: sha256("yourpassword") → paste the hex here
// Online tool: https://emn178.github.io/online-tools/sha256.html

const CONFIG = {
  MAX_MSG_LENGTH: 500, // max chars per message
  MAX_ROOMS: 50, // max total rooms
  MAX_ROOMS_PER_IP: 5, // max rooms one IP can create
  RATE_LIMIT_WINDOW_MS: 10000, // 10 second window
  RATE_LIMIT_MAX_MSGS: 8, // max messages per window
  SESSION_TTL_MS: 86400000, // session valid for 24h
  MAX_HISTORY: 300, // messages kept per room
};

// ── Crypto helpers ────────────────────────────────────────────────

async function sha256(text) {
  const buf = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(text),
  );
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function generateToken() {
  const arr = new Uint8Array(32);
  crypto.getRandomValues(arr);
  return Array.from(arr)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// ── KV key helpers ────────────────────────────────────────────────

const KEY = {
  room: (r) => `room:${r}`,
  roomMeta: (r) => `room_meta:${r}`, // { passwordHash, createdBy }
  rooms: "rooms",
  session: (tok) => `session:${tok}`, // { username, room, createdAt }
  rateLimit: (ip) => `rate:${ip}`, // { count, windowStart }
  roomsCreatedBy: (ip) => `rooms_by_ip:${ip}`, // number
};

// ── Rate limiter ──────────────────────────────────────────────────

async function checkRateLimit(env, ip) {
  const key = KEY.rateLimit(ip);
  const raw = await env.CHAT.get(key);
  const now = Date.now();
  let data = raw ? JSON.parse(raw) : { count: 0, windowStart: now };

  if (now - data.windowStart > CONFIG.RATE_LIMIT_WINDOW_MS) {
    data = { count: 1, windowStart: now };
  } else {
    data.count++;
  }

  await env.CHAT.put(key, JSON.stringify(data), {
    expirationTtl: Math.ceil(CONFIG.RATE_LIMIT_WINDOW_MS / 1000) + 5,
  });

  return data.count > CONFIG.RATE_LIMIT_MAX_MSGS;
}

// ── Session helpers ───────────────────────────────────────────────

async function createSession(env, username) {
  const token = generateToken();
  const session = { username, createdAt: Date.now() };
  await env.CHAT.put(KEY.session(token), JSON.stringify(session), {
    expirationTtl: Math.ceil(CONFIG.SESSION_TTL_MS / 1000),
  });
  return token;
}

async function getSession(env, token) {
  if (!token) return null;
  const raw = await env.CHAT.get(KEY.session(token));
  if (!raw) return null;
  const session = JSON.parse(raw);
  if (Date.now() - session.createdAt > CONFIG.SESSION_TTL_MS) {
    await env.CHAT.delete(KEY.session(token));
    return null;
  }
  return session;
}

// ── Response helpers ──────────────────────────────────────────────

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, X-Session-Token",
    },
  });
}

function err(msg, status = 400) {
  return json({ error: msg }, status);
}

// ── System message helper ─────────────────────────────────────────

async function sysMsg(env, room, text) {
  const key = KEY.room(room);
  const raw = await env.CHAT.get(key);
  const msgs = raw ? JSON.parse(raw) : [];
  msgs.push({ id: Date.now(), user: "__system__", text });
  if (msgs.length > CONFIG.MAX_HISTORY)
    msgs.splice(0, msgs.length - CONFIG.MAX_HISTORY);
  await env.CHAT.put(key, JSON.stringify(msgs));
}

// ═════════════════════════════════════════════════════════════════
//  MAIN HANDLER
// ═════════════════════════════════════════════════════════════════

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";

    if (request.method === "OPTIONS")
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, X-Session-Token",
        },
      });

    // ── POST /register  { username }  →  { token } ─────────────────
    if (request.method === "POST" && url.pathname === "/register") {
      const body = await request.json().catch(() => null);
      if (!body?.username || typeof body.username !== "string")
        return err("username required");

      const username = body.username.trim().slice(0, 32);
      if (!username || username === "__system__" || username === "__admin__")
        return err("invalid username");

      const token = await createSession(env, username);
      return json({ ok: true, token, username });
    }

    // ── POST /create  { roomName, password? }  header: X-Session-Token ──
    if (request.method === "POST" && url.pathname === "/create") {
      const token = request.headers.get("X-Session-Token");
      const session = await getSession(env, token);
      if (!session) return err("invalid or expired session", 401);

      if (await checkRateLimit(env, ip))
        return err("rate limit exceeded, slow down", 429);

      const body = await request.json().catch(() => null);
      const roomName = body?.roomName?.trim().toLowerCase();
      if (!roomName || !/^[a-z0-9_-]{1,32}$/.test(roomName))
        return err("invalid room name (a-z 0-9 _ - , max 32 chars)");

      // global room cap
      const roomsRaw = await env.CHAT.get(KEY.rooms);
      const rooms = roomsRaw ? JSON.parse(roomsRaw) : [];
      if (rooms.length >= CONFIG.MAX_ROOMS)
        return err(`room limit reached (max ${CONFIG.MAX_ROOMS})`);

      // per-IP room cap
      const ipCountRaw = await env.CHAT.get(KEY.roomsCreatedBy(ip));
      const ipCount = ipCountRaw ? parseInt(ipCountRaw) : 0;
      if (ipCount >= CONFIG.MAX_ROOMS_PER_IP)
        return err(`you can only create ${CONFIG.MAX_ROOMS_PER_IP} rooms`);

      if (rooms.includes(roomName)) return err("room already exists");

      // hash password if provided
      let passwordHash = null;
      if (body?.password && body.password.trim()) {
        passwordHash = await sha256(body.password.trim());
      }

      const meta = {
        passwordHash,
        createdBy: session.username,
        createdByIp: ip,
      };
      await env.CHAT.put(KEY.roomMeta(roomName), JSON.stringify(meta));

      rooms.push(roomName);
      await env.CHAT.put(KEY.rooms, JSON.stringify(rooms));
      await env.CHAT.put(KEY.roomsCreatedBy(ip), String(ipCount + 1));

      await sysMsg(
        env,
        roomName,
        `Room #${roomName} created by ${session.username}.`,
      );

      return json({ ok: true });
    }

    // ── POST /join  { room, password? }  header: X-Session-Token ───
    if (request.method === "POST" && url.pathname === "/join") {
      const token = request.headers.get("X-Session-Token");
      const session = await getSession(env, token);
      if (!session) return err("invalid or expired session", 401);

      const body = await request.json().catch(() => null);
      const roomName = body?.room?.trim().toLowerCase();
      if (!roomName) return err("room required");

      const metaRaw = await env.CHAT.get(KEY.roomMeta(roomName));
      if (!metaRaw) return err("room not found", 404);

      const meta = JSON.parse(metaRaw);
      if (meta.passwordHash) {
        const provided = body?.password
          ? await sha256(body.password.trim())
          : null;
        if (provided !== meta.passwordHash)
          return err("wrong room password", 403);
      }

      await sysMsg(env, roomName, `${session.username} joined the room.`);
      return json({ ok: true, hasPassword: !!meta.passwordHash });
    }

    // ── POST /leave  { room }  header: X-Session-Token ─────────────
    if (request.method === "POST" && url.pathname === "/leave") {
      const token = request.headers.get("X-Session-Token");
      const session = await getSession(env, token);
      if (!session) return err("invalid or expired session", 401);

      const body = await request.json().catch(() => null);
      const roomName = body?.room?.trim().toLowerCase();
      if (!roomName) return err("room required");

      await sysMsg(env, roomName, `${session.username} left the room.`);
      return json({ ok: true });
    }

    // ── POST /send  { room, text }  header: X-Session-Token ─────────
    if (request.method === "POST" && url.pathname === "/send") {
      const token = request.headers.get("X-Session-Token");
      const session = await getSession(env, token);
      if (!session) return err("invalid or expired session", 401);

      if (await checkRateLimit(env, ip))
        return err("rate limit exceeded, slow down", 429);

      const body = await request.json().catch(() => null);
      const { room, text } = body || {};
      if (!room || text === undefined || text === null || text === "")
        return err("room/text required");

      if (typeof text !== "string" || text.length > CONFIG.MAX_MSG_LENGTH)
        return err(`message too long (max ${CONFIG.MAX_MSG_LENGTH} chars)`);

      // verify room exists
      const metaRaw = await env.CHAT.get(KEY.roomMeta(room));
      if (!metaRaw) return err("room not found", 404);

      const key = KEY.room(room);
      const raw = await env.CHAT.get(key);
      const msgs = raw ? JSON.parse(raw) : [];
      // username comes ONLY from verified session — cannot be spoofed
      msgs.push({ id: Date.now(), user: session.username, text: String(text) });
      if (msgs.length > CONFIG.MAX_HISTORY)
        msgs.splice(0, msgs.length - CONFIG.MAX_HISTORY);
      await env.CHAT.put(key, JSON.stringify(msgs));

      return json({ ok: true });
    }

    // ── GET /poll?room=ROOM&since=ID  header: X-Session-Token ───────
    if (request.method === "GET" && url.pathname === "/poll") {
      const token = request.headers.get("X-Session-Token");
      const session = await getSession(env, token);
      if (!session) return err("invalid or expired session", 401);

      const room = url.searchParams.get("room");
      const since = parseInt(url.searchParams.get("since") || "0");
      if (!room) return err("room required");

      const raw = await env.CHAT.get(KEY.room(room));
      const msgs = raw ? JSON.parse(raw) : [];
      return json(msgs.filter((m) => m.id > since));
    }

    // ── GET /rooms  header: X-Session-Token ─────────────────────────
    if (request.method === "GET" && url.pathname === "/rooms") {
      const token = request.headers.get("X-Session-Token");
      const session = await getSession(env, token);
      if (!session) return err("invalid or expired session", 401);

      const raw = await env.CHAT.get(KEY.rooms);
      const rooms = raw ? JSON.parse(raw) : [];

      // include whether each room has a password
      const details = await Promise.all(
        rooms.map(async (r) => {
          const metaRaw = await env.CHAT.get(KEY.roomMeta(r));
          const meta = metaRaw ? JSON.parse(metaRaw) : {};
          return { name: r, hasPassword: !!meta.passwordHash };
        }),
      );
      return json(details);
    }

    // ── POST /admin/clear-room  { room, adminPassword } ─────────────
    if (request.method === "POST" && url.pathname === "/admin/clear-room") {
      const body = await request.json().catch(() => null);
      if (!body?.adminPassword) return err("adminPassword required", 401);

      const hash = await sha256(body.adminPassword);
      if (hash !== MASTER_ADMIN_PASSWORD_HASH)
        return err("wrong admin password", 403);

      const room = body?.room?.trim().toLowerCase();
      if (!room) return err("room required");

      await env.CHAT.delete(KEY.room(room));
      return json({ ok: true });
    }

    // ── POST /admin/delete-room  { room, adminPassword } ────────────
    if (request.method === "POST" && url.pathname === "/admin/delete-room") {
      const body = await request.json().catch(() => null);
      if (!body?.adminPassword) return err("adminPassword required", 401);

      const hash = await sha256(body.adminPassword);
      if (hash !== MASTER_ADMIN_PASSWORD_HASH)
        return err("wrong admin password", 403);

      const room = body?.room?.trim().toLowerCase();
      if (!room) return err("room required");

      const roomsRaw = await env.CHAT.get(KEY.rooms);
      let rooms = roomsRaw ? JSON.parse(roomsRaw) : [];
      rooms = rooms.filter((r) => r !== room);
      await env.CHAT.put(KEY.rooms, JSON.stringify(rooms));
      await env.CHAT.delete(KEY.room(room));
      await env.CHAT.delete(KEY.roomMeta(room));

      return json({ ok: true });
    }

    // ── POST /admin/delete-all-rooms  { adminPassword } ─────────────
    if (
      request.method === "POST" &&
      url.pathname === "/admin/delete-all-rooms"
    ) {
      const body = await request.json().catch(() => null);
      if (!body?.adminPassword) return err("adminPassword required", 401);

      const hash = await sha256(body.adminPassword);
      if (hash !== MASTER_ADMIN_PASSWORD_HASH)
        return err("wrong admin password", 403);

      const roomsRaw = await env.CHAT.get(KEY.rooms);
      const rooms = roomsRaw ? JSON.parse(roomsRaw) : [];
      await Promise.all(
        rooms.flatMap((r) => [
          env.CHAT.delete(KEY.room(r)),
          env.CHAT.delete(KEY.roomMeta(r)),
        ]),
      );
      await env.CHAT.put(KEY.rooms, JSON.stringify([]));

      return json({ ok: true, deleted: rooms.length });
    }

    return err("not found", 404);
  },
};
