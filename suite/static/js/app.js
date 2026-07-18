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

  TOOLS.filter(t => t.group !== "community").forEach(t => {
    railTools.appendChild(railItem(t.id, t.name, glyphSVG(t.acc, t.ready), t.acc,
      t.ready ? "" : t.when));
  });
  // the Resolve resources live with the tools — they ARE the toolkit
  railTools.appendChild(railItem("davinci", "DaVinci Tools",
    `<svg viewBox="0 0 20 20" fill="none"><path d="M4 5.5h12v9H4zM4 8h12M7.5 5.5V8m5-2.5V8m-6 4h7"
      stroke="var(--cream-dim)" stroke-width="1.6" stroke-linecap="round" fill="none"/></svg>`, null));

  /* the community pair: their own header, square glyphs, a tinted corner —
     the visual line between "the workbench" and "the apps BIG brought" */
  const railCommunity = $("#rail-community");
  TOOLS.filter(t => t.group === "community").forEach(t => {
    const item = railItem(t.id, t.name, glyphSVG(t.acc, t.ready, true), t.acc, "");
    item.classList.add("community");
    item.title = t.long || t.name;
    railCommunity.appendChild(item);
  });

  const g = (d) => `<svg viewBox="0 0 20 20" fill="none"><path d="${d}"
    stroke="var(--cream-dim)" stroke-width="1.6" stroke-linecap="round" fill="none"/></svg>`;
  railSuite.appendChild(railItem("queue", "Queue",
    g("M4 6h12M4 10h12M4 14h8"), null));
  railSuite.appendChild(railItem("ofx", "Install OpenFX",
    g("M10 4v8m0 0 3-3m-3 3-3-3M4.5 15.5h11"), null));
  railSuite.appendChild(railItem("models", "Models",
    g("M10 3.5 16 7v6l-6 3.5L4 13V7zM10 10l6-3M10 10 4 7m6 3v6.5"), null));
  railSuite.appendChild(railItem("settings", "Settings",
    g("M10 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM10 3v2m0 10v2m7-7h-2M5 10H3m11.9-4.9-1.4 1.4M6.5 13.5l-1.4 1.4m9.8 0-1.4-1.4M6.5 6.5 5.1 5.1"), null));
  railSuite.appendChild(railItem("about", "About",
    g("M10 17a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM10 9v4.5M10 6.4v.2"), null));

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

  /* ---------- job toasts: every queued thing, live, bottom-right ---------- */
  const jt = document.createElement("div");
  jt.id = "jobtoasts";
  document.body.appendChild(jt);
  window.JobToasts = {
    onJob(j) {
      let card = jt.querySelector(`[data-jid="${j.id}"]`);
      const active = ["queued", "running"].includes(j.status);
      if (!card && !active) return;          // never resurrect finished jobs
      if (!card) {
        jt.insertAdjacentHTML("beforeend", `
          <div class="jt-card" data-jid="${j.id}">
            <div class="jt-label"></div>
            <div class="jt-bar"><i></i></div>
            <div class="jt-msg"></div>
          </div>`);
        card = jt.querySelector(`[data-jid="${j.id}"]`);
        card.onclick = () => go("queue");
      }
      $(".jt-label", card).textContent = j.label || j.kind || "job";
      const pct = Math.round(Math.max(0, j.progress || 0) * 100);
      $(".jt-bar i", card).style.width = (active ? pct : 100) + "%";
      $(".jt-msg", card).textContent = j.status === "queued" ? "queued"
        : j.status === "running" ? `${pct}% — ${j.message || "working"}`
        : (j.message || j.status);
      card.classList.toggle("done", j.status === "done");
      card.classList.toggle("err", ["error", "cancelled"].includes(j.status));
      if (!active) setTimeout(() => card.remove(), 7000);
    },
  };

  /* ---------- keyboard: route to the active viewer ---------- */
  addEventListener("keydown", e => {
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
    const v = Viewer.active;
    if (v && CZ.pages[CZ.current]?.el.contains(v.wrap)) {
      if (v.key(e)) e.preventDefault();
    }
  });

  /* ---------- ⌘K: jump anywhere ---------- */
  const DESTS = [
    ...TOOLS.filter(t => t.ready).map(t => ({
      id: t.id, label: t.long || t.name, hint: t.one || t.verb || "" })),
    { id: "home", label: "Home", hint: "the three doors" },
    { id: "davinci", label: "DaVinci Tools", hint: "grades · node tree · fusion templates" },
    { id: "ofx", label: "Install OpenFX", hint: "the plugins, into Resolve" },
    { id: "queue", label: "Queue", hint: "every job, live" },
    { id: "models", label: "Models", hint: "what's downloaded" },
    { id: "settings", label: "Settings", hint: "proxy · AI · caches" },
    { id: "about", label: "About", hint: "the covenant" },
  ];
  const pal = document.createElement("div");
  pal.id = "palette";
  pal.innerHTML = `<div class="pal-box">
    <input id="pal-q" placeholder="jump to a tool… (esc closes)" spellcheck="false" autocomplete="off">
    <div id="pal-list"></div></div>`;
  pal.style.display = "none";
  document.body.appendChild(pal);
  let palSel = 0;
  function palRender() {
    const q = $("#pal-q", pal).value.trim().toLowerCase();
    const hits = DESTS.filter(d => !q || d.label.toLowerCase().includes(q)
      || d.id.includes(q) || (d.hint || "").toLowerCase().includes(q));
    palSel = Math.min(palSel, Math.max(0, hits.length - 1));
    $("#pal-list", pal).innerHTML = hits.map((d, i) =>
      `<button class="pal-row${i === palSel ? " sel" : ""}" data-id="${d.id}">
        <b>${d.label}</b><span>${d.hint || ""}</span></button>`).join("")
      || `<div class="pal-row" style="opacity:.6">nothing called that</div>`;
    $$(".pal-row[data-id]", pal).forEach(b => b.onclick = () => { palClose(); go(b.dataset.id); });
    return hits;
  }
  function palOpen() {
    pal.style.display = "";
    $("#pal-q", pal).value = "";
    palSel = 0;
    palRender();
    $("#pal-q", pal).focus();
  }
  function palClose() { pal.style.display = "none"; }
  pal.onclick = e => { if (e.target === pal) palClose(); };
  $("#pal-q", pal).addEventListener("input", () => { palSel = 0; palRender(); });
  $("#pal-q", pal).addEventListener("keydown", e => {
    const hits = DESTS.filter(d => { const q = $("#pal-q", pal).value.trim().toLowerCase();
      return !q || d.label.toLowerCase().includes(q) || d.id.includes(q)
        || (d.hint || "").toLowerCase().includes(q); });
    if (e.key === "Escape") palClose();
    else if (e.key === "ArrowDown") { e.preventDefault(); palSel = Math.min(palSel + 1, hits.length - 1); palRender(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); palSel = Math.max(palSel - 1, 0); palRender(); }
    else if (e.key === "Enter" && hits[palSel]) { palClose(); go(hits[palSel].id); }
  });
  addEventListener("keydown", e => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      pal.style.display === "none" ? palOpen() : palClose();
    }
  });

  /* ---------- go ---------- */
  await loadSession();
  connectWS();
  try { CZ.appInfo = await api("/api/app"); } catch (e) {}
  /* deep links: /#kb opens the Library, /#clear opens Clear — shareable,
     and how the site's slide captures find each room */
  const dest = (location.hash || "").slice(1);
  go(CZ.pages[dest] ? dest : "home");
  addEventListener("hashchange", () => {
    const d = (location.hash || "").slice(1);
    if (CZ.pages[d]) go(d);
  });
})();
