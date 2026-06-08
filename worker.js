export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const headers = {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    };

    if (request.method === "OPTIONS") return new Response(null, { headers });

    // POST /send   body: { room, user, text }
    if (request.method === "POST" && url.pathname === "/send") {
      let body;
      try {
        body = await request.json();
      } catch {
        return new Response(JSON.stringify({ error: "bad json" }), {
          status: 400,
          headers,
        });
      }

      const { room, user, text } = body;
      if (
        !room ||
        !user ||
        text === undefined ||
        text === null ||
        text === ""
      ) {
        return new Response(
          JSON.stringify({ error: "room/user/text required" }),
          { status: 400, headers },
        );
      }

      const key = `room:${room}`;
      const msg = { id: Date.now(), user, text: String(text) };

      const raw = await env.CHAT.get(key);
      const msgs = raw ? JSON.parse(raw) : [];
      msgs.push(msg);
      if (msgs.length > 300) msgs.splice(0, msgs.length - 300);
      await env.CHAT.put(key, JSON.stringify(msgs));

      // update room list
      const roomsRaw = await env.CHAT.get("rooms");
      const rooms = roomsRaw ? JSON.parse(roomsRaw) : [];
      if (!rooms.includes(room)) {
        rooms.push(room);
        await env.CHAT.put("rooms", JSON.stringify(rooms));
      }

      return new Response(JSON.stringify({ ok: true }), { headers });
    }

    // GET /poll?room=ROOM&since=ID
    if (request.method === "GET" && url.pathname === "/poll") {
      const room = url.searchParams.get("room");
      const since = parseInt(url.searchParams.get("since") || "0");
      if (!room)
        return new Response(JSON.stringify({ error: "room required" }), {
          status: 400,
          headers,
        });

      const raw = await env.CHAT.get(`room:${room}`);
      const msgs = raw ? JSON.parse(raw) : [];
      const newMsgs = msgs.filter((m) => m.id > since);
      return new Response(JSON.stringify(newMsgs), { headers });
    }

    // GET /rooms
    if (request.method === "GET" && url.pathname === "/rooms") {
      const raw = await env.CHAT.get("rooms");
      const rooms = raw ? JSON.parse(raw) : [];
      return new Response(JSON.stringify(rooms), { headers });
    }

    // POST /clear   body: { room }
    if (request.method === "POST" && url.pathname === "/clear") {
      let body;
      try {
        body = await request.json();
      } catch {
        return new Response(JSON.stringify({ error: "bad json" }), {
          status: 400,
          headers,
        });
      }
      const { room } = body;
      if (!room)
        return new Response(JSON.stringify({ error: "room required" }), {
          status: 400,
          headers,
        });
      await env.CHAT.delete(`room:${room}`);
      return new Response(JSON.stringify({ ok: true }), { headers });
    }

    return new Response(JSON.stringify({ error: "not found" }), {
      status: 404,
      headers,
    });
  },
};
