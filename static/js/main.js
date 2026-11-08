/* prλtam — site behaviours. Vanilla JS, no dependencies.
   Everything here is progressive enhancement: the site is fully
   readable with JavaScript disabled. */

(function () {
  "use strict";

  /* ---- copy buttons on code blocks ---- */
  document.querySelectorAll(".codehilite pre").forEach(function (pre) {
    var btn = document.createElement("button");
    btn.className = "copy-btn";
    btn.type = "button";
    btn.textContent = "Copy code";
    var reset;
    btn.addEventListener("click", async function () {
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(pre.textContent);
        } else {
          var input = document.createElement("textarea");
          input.value = pre.textContent;
          document.body.appendChild(input);
          input.select();
          try {
            if (!document.execCommand("copy")) throw new Error("Clipboard unavailable");
          } finally {
            input.remove();
            btn.focus();
          }
        }
        btn.textContent = "Copied";
      } catch {
        btn.textContent = "Copy failed";
      }
      clearTimeout(reset);
      reset = setTimeout(function () { btn.textContent = "Copy code"; }, 1600);
    });
    pre.before(btn);
  });

  var toc = document.querySelector("details.toc");
  if (toc) {
    var desktopContents = window.matchMedia("(min-width: 66.25rem)");
    var syncContents = function () { toc.open = desktopContents.matches; };
    syncContents();
    desktopContents.addEventListener("change", syncContents);
  }

  /* ---- reading progress (article pages) ---- */
  var bar = document.getElementById("progress-bar");
  if (bar) {
    var ticking = false;
    var update = function () {
      var doc = document.documentElement;
      var max = doc.scrollHeight - window.innerHeight;
      var pct = max > 0 ? Math.min(1, window.scrollY / max) : 0;
      bar.style.width = (pct * 100).toFixed(2) + "%";
      ticking = false;
    };
    window.addEventListener("scroll", function () {
      if (!ticking) {
        ticking = true;
        window.requestAnimationFrame(update);
      }
    }, { passive: true });
    update();
  }

  /* ---- table-of-contents scrollspy ---- */
  if (toc && "IntersectionObserver" in window) {
    var links = Array.prototype.slice.call(toc.querySelectorAll("a[href^='#']"));
    var byId = {};
    links.forEach(function (a) { byId[a.getAttribute("href").slice(1)] = a; });
    var headings = Object.keys(byId)
      .map(function (id) { return document.getElementById(id); })
      .filter(Boolean);
    if (headings.length) {
      var active = null;
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            if (active) active.classList.remove("active");
            active = byId[entry.target.id];
            if (active) active.classList.add("active");
          }
        });
      }, { rootMargin: "-15% 0px -70% 0px" });
      headings.forEach(function (h) { observer.observe(h); });
    }
  }
})();
