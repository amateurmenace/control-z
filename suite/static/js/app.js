/* boot: rail, keyboard, session, websocket. */

(async () => {
  /* ---------- rail ---------- */
  const railTools = $("#rail-tools");
  const railSuite = $("#rail-suite");

  function railItem(page, label, glyph, acc, soon) {
    const b = document.createElement("button");
    b.className = "rail-item";
    b.dataset.page = page;
    b.setAttribute("aria-label", label);
    if (acc) b.style.setProperty("--acc", acc);
    b.innerHTML = `<span class="wire"></span><span class="glyph">${glyph}</span>
      <span>${label}</span>${soon ? `<span class="soon">${soon}</span>` : ""}`;
    b.onclick = () => go(page);
    return b;
  }

  const homeGlyph = `<svg viewBox="0 0 20 20" fill="none">
    <path d="M3.5 9.5 10 3.5l6.5 6v6.5a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1z"
      stroke="var(--cream-dim)" stroke-width="1.6" fill="none"/></svg>`;
  railTools.before(railItem("home", "Home", homeGlyph, null));

  TOOLS.forEach(t => {
    railTools.appendChild(railItem(t.id, t.name, glyphSVG(t.acc, t.ready), t.acc,
      t.ready ? "" : t.when));
  });

  const g = (d) => `<svg viewBox="0 0 20 20" fill="none"><path d="${d}"
    stroke="var(--cream-dim)" stroke-width="1.6" stroke-linecap="round" fill="none"/></svg>`;
  railSuite.appendChild(railItem("queue", "Queue",
    g("M4 6h12M4 10h12M4 14h8"), null));
  railSuite.appendChild(railItem("ofx", "Install OpenFX",
    g("M10 4v8m0 0 3-3m-3 3-3-3M4.5 15.5h11"), null, "v0.4"));
  railSuite.appendChild(railItem("models", "Models",
    g("M10 3.5 16 7v6l-6 3.5L4 13V7zM10 10l6-3M10 10 4 7m6 3v6.5"), null, "v0.4"));
  railSuite.appendChild(railItem("settings", "Settings",
    g("M10 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM10 3v2m0 10v2m7-7h-2M5 10H3m11.9-4.9-1.4 1.4M6.5 13.5l-1.4 1.4m9.8 0-1.4-1.4M6.5 6.5 5.1 5.1"), null, "v0.4"));

  /* queue badge: count of active jobs on the rail */
  setInterval(() => {
    const item = $('.rail-item[data-page="queue"]');
    if (!item) return;
    const n = [...CZ.jobs.values()].filter(j => ["queued", "running"].includes(j.status)).length;
    let b = $(".soon", item);
    if (!b) { b = document.createElement("span"); b.className = "soon"; item.appendChild(b); }
    b.textContent = n ? `${n} active` : "";
    b.style.color = n ? "var(--amber)" : "";
  }, 800);

  /* ---------- keyboard: route to the active viewer ---------- */
  addEventListener("keydown", e => {
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
    const v = Viewer.active;
    if (v && CZ.pages[CZ.current]?.el.contains(v.wrap)) {
      if (v.key(e)) e.preventDefault();
    }
  });

  /* ---------- go ---------- */
  await loadSession();
  connectWS();
  try { CZ.appInfo = await api("/api/app"); } catch (e) {}
  go("home");
})();
