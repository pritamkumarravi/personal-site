/**
 * prλtam — Spotify now-playing worker.
 *
 * Ported from saarthak314/site (worker/spotify), extended with this repo's
 * optional shared-key gate. Answers the shape the site's now-playing widget
 * expects:
 *   { playing, progress_ms, played_at, fetched_at,
 *     track: { title, artists[], album, duration_ms, url, art } }
 *
 * Playing → `playing: true` with live `progress_ms`. Nothing playing (or an
 * ad/podcast) → falls back to the most recent track with its `played_at`.
 * Holds the refresh token so the site never does; caches per isolate for 30s
 * and at the edge, refreshing in the background so visitors always get the
 * last good answer fast.
 *
 * Answers GET / and GET /now (same payload).
 *
 * Setup (one-time):
 *   1. Create an app at https://developer.spotify.com/dashboard
 *      → redirect URI: http://127.0.0.1:8765/callback
 *      → scopes needed: user-read-currently-playing user-read-recently-played
 *        (run tools/spotify_auth.py — it prints the refresh token)
 *   2. `npx wrangler secret put` for:
 *        SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REFRESH_TOKEN
 *   3. ALLOWED_ORIGIN is a Wrangler variable (see wrangler.toml), not a secret.
 *      It defaults to the localhost and production site origins below.
 *      ACCESS_KEY is an optional secret gate. A key embedded in the public
 *      site is visible to visitors, so leave it unset for this read-only widget.
 *   4. `npx wrangler deploy` from worker/, then put the URL into
 *      data/site.yaml → spotify.worker.
 */

const TOKEN_URL = "https://accounts.spotify.com/api/token";
const NOW_URL = "https://api.spotify.com/v1/me/player/currently-playing";
const RECENT_URL = "https://api.spotify.com/v1/me/player/recently-played?limit=1";
const CACHE_MS = 30_000;

// Per-isolate caches: good enough for a 30 second window, no storage needed.
let token = { value: null, expiresAt: 0 };
let cached = { body: null, at: 0 };

const EDGE_KEY = "https://now.cache/pritam/now";

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const cors = corsHeaders(request.headers.get("Origin"), env);
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }
    if (request.method !== "GET" || (url.pathname !== "/" && url.pathname !== "/now")) {
      return json({ error: "not found" }, 404, cors);
    }
    // Optional shared-key gate (this repo's addition): the same answer either way.
    if (env.ACCESS_KEY && url.searchParams.get("key") !== env.ACCESS_KEY) {
      return json({ error: "forbidden" }, 401, { ...cors, "cache-control": "no-store" });
    }
    const headers = { ...cors, "cache-control": "public, max-age=30, stale-while-revalidate=600" };
    try {
      // Warm isolate: answer from memory.
      if (cached.body && Date.now() - cached.at <= CACHE_MS) {
        return json(cached.body, 200, headers);
      }
      // Cold isolate: answer from the edge cache if a recent copy exists there,
      // and refresh it in the background so the next visitor gets a fresh one.
      const edge = await edgeCache();
      const hit = edge ? await edge.match(EDGE_KEY) : null;
      if (hit) {
        const body = await hit.json();
        cached = { body, at: Date.now() };
        if (edge) ctx.waitUntil(refresh(env, edge));
        return json(body, 200, headers);
      }
      const body = await nowPlaying(env);
      cached = { body, at: Date.now() };
      if (edge) ctx.waitUntil(storeAtEdge(edge, body));
      return json(body, 200, headers);
    } catch (error) {
      const message = error && error.message ? error.message : String(error);
      return json({ error: message }, 502, { ...cors, "cache-control": "no-store" });
    }
  },
};

async function edgeCache() {
  try {
    return typeof caches !== "undefined" && caches.default ? caches.default : null;
  } catch {
    return null;
  }
}

async function storeAtEdge(edge, body) {
  try {
    await edge.put(
      EDGE_KEY,
      new Response(JSON.stringify(body), {
        headers: { "content-type": "application/json", "cache-control": `public, max-age=${CACHE_MS / 1000}` },
      }),
    );
  } catch {
    // the edge cache is best effort
  }
}

async function refresh(env, edge) {
  try {
    const body = await nowPlaying(env);
    cached = { body, at: Date.now() };
    await storeAtEdge(edge, body);
  } catch {
    // keep serving the last good answer
  }
}

function corsHeaders(origin, env) {
  const allowed = String(env.ALLOWED_ORIGIN || "http://localhost:8000,https://pritamravi.com")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  const wildcard = allowed.includes("*");
  const headers = {
    "access-control-allow-methods": "GET, OPTIONS",
    "access-control-max-age": "86400",
    vary: "Origin",
  };
  if (wildcard) headers["access-control-allow-origin"] = "*";
  else if (origin && allowed.includes(origin)) headers["access-control-allow-origin"] = origin;
  return headers;
}

function json(body, status, headers) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", ...headers },
  });
}

async function accessToken(env) {
  if (token.value && Date.now() < token.expiresAt - 60_000) return token.value;
  for (const name of ["SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REFRESH_TOKEN"]) {
    if (!env[name]) throw new Error(`${name} is not set`);
  }
  const response = await fetch(TOKEN_URL, {
    method: "POST",
    headers: {
      authorization: "Basic " + btoa(`${env.SPOTIFY_CLIENT_ID}:${env.SPOTIFY_CLIENT_SECRET}`),
      "content-type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: env.SPOTIFY_REFRESH_TOKEN,
    }),
  });
  if (!response.ok) throw new Error(`spotify token refresh failed (${response.status})`);
  const data = await response.json();
  token = {
    value: data.access_token,
    expiresAt: Date.now() + (data.expires_in || 3600) * 1000,
  };
  return token.value;
}

async function nowPlaying(env) {
  const headers = { authorization: `Bearer ${await accessToken(env)}` };
  const fetchedAt = new Date().toISOString();
  // Both calls at once: the recent one is only read if nothing is playing.
  const [current, recentPromise] = [await fetch(NOW_URL, { headers }), fetch(RECENT_URL, { headers })];
  if (current.status === 200) {
    const data = await current.json();
    if (data && data.item && data.currently_playing_type === "track") {
      return {
        playing: Boolean(data.is_playing),
        progress_ms: data.progress_ms ?? null,
        played_at: null,
        fetched_at: fetchedAt,
        track: track(data.item),
      };
    }
  } else if (current.status !== 204) {
    if (current.status === 401) token = { value: null, expiresAt: 0 };
    throw new Error(`spotify currently-playing failed (${current.status})`);
  }
  // Nothing playing, or an ad or podcast: fall back to the last track played.
  const recent = await recentPromise;
  if (!recent.ok) throw new Error(`spotify recently-played failed (${recent.status})`);
  const data = await recent.json();
  const item = data.items && data.items[0];
  if (!item || !item.track) {
    return { playing: false, progress_ms: null, played_at: null, fetched_at: fetchedAt, track: null };
  }
  return {
    playing: false,
    progress_ms: null,
    played_at: item.played_at,
    fetched_at: fetchedAt,
    track: track(item.track),
  };
}

function track(item) {
  const images = (item.album && item.album.images) || [];
  return {
    title: item.name,
    artists: (item.artists || []).map((artist) => artist.name),
    album: item.album ? item.album.name : null,
    duration_ms: item.duration_ms,
    url: item.external_urls ? item.external_urls.spotify : null,
    art: images.length ? images[images.length - 1].url : null,
  };
}
