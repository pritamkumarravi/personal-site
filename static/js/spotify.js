(function () {
  "use strict";

  /* ---- spotify now playing ----
     Adapted from saarthak314/site.
     The worker (see worker/) answers:
       { playing, progress_ms, played_at, fetched_at,
         track: { title, artists[], album, duration_ms, url, art } }
     When nothing is playing, show the last track with "played Xm ago". The last answer
     is cached in localStorage so the card shows instantly with
     "spotify // syncing" until the fresh answer lands. Two consecutive
     failures show an unavailable state and retry after two minutes; polling
     pauses in background tabs and while the card is off-screen. */
  document.querySelectorAll("[data-now]").forEach((box) => {
    const endpoint = box.dataset.now;
    const content = box.querySelector(".now__content");
    const label = box.querySelector(".now__state");
    if (!endpoint || !content || !label || !window.fetch) return;
    const lower = (value) => String(value || "").trim().toLowerCase();
    const firstArtist = (track) => (track.artists || []).find((name) => typeof name === "string" && name.trim()) || "";
    const clock = (ms) => {
      const seconds = Math.floor(ms / 1000);
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
    let playback = null;
    let ticker = 0;
    let poller = 0;
    let relativeTimer = 0;
    let failures = 0;
    let visible = false;
    const live = box.querySelector(".now__announcement");
    let loading = false;
    const updateProgress = () => {
      if (!state || !playback) return;
      const { data, receivedAt } = state;
      const fetchedAt = Date.parse(data.fetched_at);
      const origin = Number.isFinite(fetchedAt) ? fetchedAt : receivedAt;
      const age = data.playing ? Math.max(0, Date.now() - origin) : 0;
      const position = Math.min(playback.meter.max, data.progress_ms + age);
      const timestamp = clock(position) + " / " + clock(playback.meter.max);
      playback.meter.value = position;
      playback.meter.setAttribute("aria-valuetext", timestamp);
      playback.time.textContent = timestamp;
    };
    const render = () => {
      const data = state && state.data;
      playback = null;
      box.classList.toggle("now--playing", Boolean(data && data.playing));
      if (!data || !data.track) {
        label.textContent = "spotify // no recent track";
        content.textContent = "nothing to display";
        return;
      }
      const track = data.track;
      const played = relativeTime(data.played_at);
      label.textContent = data.playing
        ? "spotify // playing"
        : data.played_at
          ? "spotify // played" + (played ? " " + played : "")
          : "spotify // paused";
      const title = node(track.url ? "a" : "span", "now__title", lower(track.title));
      title.title = title.textContent;
      if (track.url) {
        title.href = track.url;
        title.rel = "noopener";
      }
      const mark = node("span", "now__mark", data.playing ? "▶" : "▷");
      mark.setAttribute("aria-hidden", "true");
      const trackRow = node("div", "now__track", "");
      trackRow.append(mark, title);
      content.replaceChildren(trackRow);

      const duration = track.duration_ms;
      const hasProgress = Number.isFinite(data.progress_ms) && data.progress_ms >= 0 &&
        Number.isFinite(duration) && duration > 0;
      const controls = node("div", "now__playback", "");
      if (hasProgress) {
        const meter = node("progress", "now__meter", "");
        meter.max = duration;
        meter.setAttribute("aria-label", "Playback progress");
        const time = node("span", "now__time", "");
        time.setAttribute("aria-hidden", "true");
        controls.append(meter, time);
        playback = { meter, time };
      }
      if (data.playing || hasProgress) {
        const equalizer = node("span", "now__eq", "");
        equalizer.setAttribute("aria-hidden", "true");
        [..."▂▅▃▇"].forEach((glyph, index) => {
          const bar = node("span", "", glyph);
          bar.style.setProperty("--i", index);
          equalizer.append(bar);
        });
        (hasProgress ? controls : trackRow).append(equalizer);
      }

      const artist = node("span", "now__artist", lower(firstArtist(track)));
      const album = node("span", "now__album", lower(track.album));
      if (artist.textContent || album.textContent) {
        const meta = node("div", "now__meta", "");
        if (artist.textContent) {
          artist.title = artist.textContent;
          meta.append(artist);
        }
        if (artist.textContent && album.textContent) {
          const separator = node("span", "now__separator", "//");
          separator.setAttribute("aria-hidden", "true");
          meta.append(separator);
        }
        if (album.textContent) {
          album.title = album.textContent;
          meta.append(album);
        }
        content.append(meta);
      }
      if (hasProgress) {
        content.append(controls);
        updateProgress();
      }
    };
    const stop = () => {
      window.clearInterval(ticker);
      if (poller) window.clearTimeout(poller);
      if (relativeTimer) window.clearInterval(relativeTimer);
      poller = 0;
      relativeTimer = 0;
      ticker = 0;
    };
    const pollDelay = () => {
      if (failures === 1) return 5000;
      return state && state.data.playing ? 30000 : 120000;
    };
    const schedule = () => {
      if (poller) window.clearTimeout(poller);
      poller = 0;
      if (!visible || document.hidden) return;
      poller = window.setTimeout(load, pollDelay());
      window.clearInterval(ticker);
      ticker = 0;
      if (playback && state?.data.playing) {
        updateProgress();
        ticker = window.setInterval(updateProgress, 1000);
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
      const identity = track ? [track.title, firstArtist(track)].filter(Boolean).join(" — ") : "";
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
        announce(data);
        state = { data, receivedAt: Date.now() };
        failures = 0;
        remember(state.data);
        render();
      } catch {
        failures += 1;
        if (failures >= 2) {
          state = null;
          playback = null;
          box.classList.remove("now--playing");
          label.textContent = "spotify // unavailable";
          content.textContent = "Playback updates will retry shortly.";
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
        state = { data: { ...stored, playing: false }, receivedAt: Date.now() };
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
