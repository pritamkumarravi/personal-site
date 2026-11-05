(function () {
  "use strict";

  /* ---- spotify now playing ----
     Ported from saarthak314/site (design + behaviour preserved).
     The worker (see worker/) answers:
       { playing, progress_ms, played_at, fetched_at,
         track: { title, artists[], album, duration_ms, url, art } }
     Playing → live meter + clock + equalizer; paused → ▷ and no meter;
     nothing playing → the last track with "played Xm ago". The last answer
     is cached in localStorage so the card shows instantly with
     "spotify // syncing" until the fresh answer lands. Two consecutive
     failures show an unavailable state and retry after two minutes; polling
     pauses in background tabs and while the card is off-screen. */
  document.querySelectorAll("[data-now]").forEach((box) => {
    const endpoint = box.dataset.now;
    const pre = box.querySelector(".now__pre");
    const label = box.querySelector(".now__state");
    if (!endpoint || !pre || !label || !window.fetch) return;
    const cells = 8;
    const lower = (value) => String(value || "").toLowerCase();
    const clock = (ms) => {
      const seconds = Math.max(0, Math.floor(ms / 1000));
      return Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0");
    };
    const relativeTime = (iso, now = Date.now()) => {
      if (typeof iso !== "string" || !iso.trim()) return null;
      const playedAt = Date.parse(iso);
      if (!Number.isFinite(playedAt)) return null;
      const minutes = Math.max(0, Math.floor((now - playedAt) / 60000));
      if (minutes < 1) return "just now";
      if (minutes < 60) return minutes + "m ago";
      const hours = Math.floor(minutes / 60);
      if (hours < 24) return hours + "h ago";
      const days = Math.floor(hours / 24);
      if (days < 7) return days + "d ago";
      if (days < 30) return Math.floor(days / 7) + "w ago";
      const months = Math.floor(days / 30);
      if (months < 12) return months + "mo ago";
      return Math.floor(months / 12) + "y ago";
    };
    const node = (tag, className, text) => {
      const element = document.createElement(tag);
      if (className) element.className = className;
      element.textContent = text;
      return element;
    };
    let state = null;
    let meter = null;
    let timeLabel = null;
    let ticker = 0;
    let poller = 0;
    let relativeTimer = 0;
    let failures = 0;
    let visible = false;
    const live = box.querySelector(".now__announcement");
    let loading = false;
    let boundaryRefreshRequested = false;

    const trackIdentity = (data) => {
      const track = data && data.track;
      return track ? [track.url || "", track.title || "", (track.artists || []).join(", ")].join("\u0000") : "";
    };

    const elapsed = () => {
      if (!state || !state.data.playing || state.data.progress_ms == null) return 0;
      const duration = state.data.track.duration_ms || 0;
      const fetchedAt = Date.parse(state.data.fetched_at);
      const origin = Number.isFinite(fetchedAt) ? fetchedAt : state.receivedAt;
      return Math.min(duration, Math.max(0, state.data.progress_ms + Date.now() - origin));
    };
    const tick = () => {
      if (!state || !meter) return;
      const duration = state.data.track.duration_ms || 0;
      const done = elapsed();
      const filled = duration ? Math.round((done / duration) * cells) : 0;
      meter.textContent = "▓".repeat(filled) + "░".repeat(cells - filled);
      timeLabel.textContent = " " + clock(done) + " / " + clock(duration) + " ";
      if (duration && done >= duration && !boundaryRefreshRequested &&
          !loading && visible && !document.hidden) {
        boundaryRefreshRequested = true;
        load();
      }
    };
    const render = () => {
      const data = state && state.data;
      meter = null;
      box.classList.toggle("now--playing", Boolean(data && data.playing));
      if (!data || !data.track) {
        label.textContent = "spotify // no recent track";
        pre.textContent = "nothing to display";
        return;
      }
      const track = data.track;
      pre.replaceChildren();
      const played = relativeTime(data.played_at);
      label.textContent = data.playing
        ? "spotify // playing"
        : data.played_at
          ? "spotify // played" + (played ? " " + played : "")
          : "spotify // paused";
      const title = node(track.url ? "a" : "span", "now__title", lower(track.title));
      if (track.url) {
        title.href = track.url;
        title.rel = "noopener";
      }
      const mark = node("span", "now__mark", data.playing ? "▶ " : "▷ ");
      mark.setAttribute("aria-hidden", "true");
      pre.append(mark, title, "\n");
      const artist = lower((track.artists || []).find((name) => String(name || "").trim()));
      const album = lower(track.album);
      const metadata = [artist, album].filter(Boolean).join(" // ");
      if (metadata) pre.append("  ", node("span", "now__meta", metadata));
      if (data.playing && data.progress_ms != null && track.duration_ms) {
        meter = node("span", "now__meter", "");
        timeLabel = node("span", "", "");
        const eq = node("span", "now__eq", "");
        meter.setAttribute("aria-hidden", "true");
        eq.setAttribute("aria-hidden", "true");
        "▂▅▃▇".split("").forEach((glyph, index) => {
          const bar = node("span", "", glyph);
          bar.style.setProperty("--i", index);
          eq.append(bar);
        });
        pre.append("\n  ", meter, timeLabel, eq);
        tick();
      }
    };
    const stop = () => {
      if (ticker) window.clearInterval(ticker);
      if (poller) window.clearTimeout(poller);
      if (relativeTimer) window.clearInterval(relativeTimer);
      ticker = 0;
      poller = 0;
      relativeTimer = 0;
    };
    const pollDelay = () => {
      if (failures === 1) return 5000;
      return state && state.data.playing ? 30000 : 120000;
    };
    const schedule = () => {
      if (poller) window.clearTimeout(poller);
      poller = 0;
      if (!visible || document.hidden) return;
      const playing = Boolean(state && state.data.playing);
      poller = window.setTimeout(load, pollDelay());
      if (playing && !ticker) ticker = window.setInterval(tick, 1000);
      if (!playing && ticker) {
        window.clearInterval(ticker);
        ticker = 0;
      }
      if (state && state.data.track && state.data.played_at) {
        if (!relativeTimer) relativeTimer = window.setInterval(updatePlayedLabel, 60000);
      } else if (relativeTimer) {
        window.clearInterval(relativeTimer);
        relativeTimer = 0;
      }
    };
    const updatePlayedLabel = () => {
      if (!state || state.data.playing || !state.data.played_at) return;
      const elapsed = relativeTime(state.data.played_at);
      label.textContent = "spotify // played" + (elapsed ? " " + elapsed : "");
    };
    const announce = (data) => {
      const track = data.track;
      const identity = track ? [track.title, (track.artists || []).join(", ")].join(" — ") : "";
      const mode = data.playing ? "playing" : data.played_at ? "recently played" : "paused";
      const message = identity ? identity + ", " + mode : "No recent Spotify track";
      if (live.textContent !== message) live.textContent = message;
    };
    const storageKey = "pritam.now";
    const remember = (data) => {
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(data));
      } catch {
        // storage can be full or disabled; the block still works without it
      }
    };
    const load = async () => {
      if (loading || !visible || document.hidden) return;
      loading = true;
      if (poller) window.clearTimeout(poller);
      poller = 0;
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 10000);
      try {
        const response = await fetch(endpoint, { mode: "cors", signal: controller.signal });
        if (!response.ok) throw new Error(String(response.status));
        const data = await response.json();
        const previous = state && state.data;
        if (
          previous &&
          (trackIdentity(previous) !== trackIdentity(data) ||
            Boolean(previous.playing) !== Boolean(data.playing) ||
            (Number.isFinite(data.progress_ms) &&
              Number.isFinite(previous.progress_ms) &&
              data.progress_ms < previous.progress_ms - 1000))
        ) {
          boundaryRefreshRequested = false;
        }
        announce(data);
        state = { data, receivedAt: Date.now() };
        failures = 0;
        remember(state.data);
        render();
      } catch {
        failures += 1;
        if (failures >= 2) {
          state = null;
          meter = null;
          boundaryRefreshRequested = false;
          box.classList.remove("now--playing");
          label.textContent = "spotify // unavailable";
          pre.textContent = "Playback updates will retry shortly.";
          if (failures === 2) live.textContent = "Spotify is unavailable";
        }
      } finally {
        window.clearTimeout(timeout);
        loading = false;
        schedule();
      }
    };
    const sync = () => {
      if (visible && !document.hidden) {
        if (!state || Date.now() - state.receivedAt >= pollDelay()) load();
        else schedule();
      } else {
        stop();
      }
    };
    // Show the last known track at once; the fresh answer replaces it.
    try {
      const stored = JSON.parse(window.localStorage.getItem(storageKey) || "null");
      if (stored && stored.track && !state) {
        state = { data: { ...stored, playing: false, progress_ms: null }, receivedAt: Date.now() };
        render();
        label.textContent = "spotify // syncing";
        state = null;
      }
    } catch {
      // ignore unreadable storage
    }
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            visible = entry.isIntersecting;
          });
          sync();
        },
        { rootMargin: "120px 0px" },
      ).observe(box);
    } else {
      visible = true;
      sync();
    }
    document.addEventListener("visibilitychange", sync);
  });
})();
