/* BIG Video Grabber — the portal, searched; the recordings, brought home.
   CivicClerk tenant + date range → events (every URL-shaped field in the
   payload is harvested and labeled). Fetch runs through the shared yt-dlp
   nightly (it speaks Zoom), conform runs through the shared encoder presets.
   The tenant is remembered per session — Brookline out of the box. */

const GrabberPage = (() => {
  const T = toolById("grabber");
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-grabber";

  const today = () => new Date().toISOString().slice(0, 10);
  const weeksAgo = n => new Date(Date.now() - n * 7 * 864e5).toISOString().slice(0, 10);

  el.innerHTML = `
  <div class="ws" style="--acc:${T.acc}">
    <div class="mediabar">
      <span class="toolname"><i>BIG Video Grabber</i> · brings the meeting home</span>
      <input type="text" id="gb-tenant" value="brooklinema" spellcheck="false"
        style="flex:0 1 150px;min-width:110px" title="the CivicClerk tenant — the part before .api.civicclerk.com">
      <input type="date" id="gb-from" class="gb-date">
      <input type="date" id="gb-to" class="gb-date">
      <button class="btn" style="width:auto" id="gb-search">Search</button>
      <span class="ytdlp-chip" id="gb-ytdlp" title="the fetch engine — nightly build, checked on every open">yt-dlp —</span>
    </div>
    <div class="ws-body">
      <div class="ws-center" style="overflow-y:auto;padding:16px 20px">
        <div class="tag">meetings found</div>
        <div id="gb-results"><div class="empty-grain" style="padding:26px 4px;color:var(--cream-faint)">
          pick a date range and search — any CivicClerk town works, Brookline is home</div></div>
        <div class="tag" style="margin-top:22px">the bin — fetched recordings</div>
        <div id="gb-library"><div class="hint" style="padding:8px 2px">nothing fetched yet</div></div>
      </div>
      <div class="inspector" id="gb-insp">
        <div class="insp-head"><h2>Grabber</h2></div>

        <div class="insp-sec">
          <span class="tag">conform for air</span>
          <div class="field"><label>preset</label><select id="gb-preset"></select>
            <div class="hint" id="gb-presetnote"></div>
          </div>
          <div class="field"><label>height</label>
            <select id="gb-height">
              <option value="">keep source</option>
              <option value="1080">1080</option>
              <option value="720">720</option>
            </select>
          </div>
          <div class="field"><label>frame rate</label>
            <select id="gb-fps">
              <option value="">conform to source average</option>
              <option value="29.97">29.97 — NTSC broadcast</option>
              <option value="30">30</option>
              <option value="25">25 — PAL</option>
              <option value="59.94">59.94</option>
            </select>
            <div class="hint">Zoom records variable rate; playout wants constant —
              the pass always writes constant frames</div>
          </div>
        </div>

        <div class="insp-sec">
          <span class="tag">fetch a link directly</span>
          <input type="text" id="gb-url" placeholder="https://…zoom.us/rec/… or any video URL" spellcheck="false"
            style="width:100%;background:var(--ink);border:1px solid var(--line);border-radius:7px;padding:6px 9px;font-size:12px;font-family:var(--mono);color:var(--cream)">
          <button class="btn" id="gb-fetchurl" style="margin-top:8px">Fetch URL</button>
          <div class="hint" style="margin-top:6px">for the links a portal doesn't list —
            yt-dlp speaks Zoom, YouTube, Vimeo and a thousand others</div>
        </div>

        <div class="report" id="gb-report"></div>
      </div>
    </div>
  </div>`;

  const S = { presets: [] };

  async function ytdlpCheck() {
    const chip = $("#gb-ytdlp", el);
    try {
      let st = (await api("/api/grabber/ytdlp-check", {})).ytdlp;
      const until = Date.now() + 90000;
      while (["checking", "updating"].includes(st.phase) && Date.now() < until) {
        chip.textContent = "yt-dlp " + (st.phase === "updating" ? "updating…" : "checking…");
        await new Promise(r => setTimeout(r, 900));
        st = (await api("/api/grabber/status")).ytdlp;
      }
      const ok = st.phase === "ok" || st.present;
      const viaProxy = st.proxy && st.proxy.enabled;
      chip.textContent = "yt-dlp " + (st.installed ? `nightly ${st.installed}` : "missing")
        + (viaProxy ? " · webshare" : "");
      chip.classList.toggle("ok", ok);
      chip.classList.toggle("err", !ok);
      chip.title = (st.detail || "") + (viaProxy
        ? ` — fetches ride your Webshare residential proxy (${st.proxy.username_masked})`
        : " — no proxy configured (Settings → fetch network, if YouTube gates fetches)");
    } catch (e) { chip.textContent = "yt-dlp ?"; }
  }

  async function loadStatus() {
    try {
      const st = await api("/api/grabber/status");
      S.presets = st.presets || [];
      const sel = $("#gb-preset", el);
      sel.innerHTML = S.presets.map(p =>
        `<option value="${p.id}" ${p.id === "prores-422" ? "selected" : ""}>${esc(p.label)}${p.available ? "" : " — unavailable"}</option>`).join("");
      presetNote();
      sel.onchange = presetNote;
      const saved = CZ.session.tools?.grabber?.tenant;
      if (saved) $("#gb-tenant", el).value = saved;
    } catch (e) { /* page still works for direct URLs */ }
  }
  function presetNote() {
    const p = S.presets.find(x => x.id === $("#gb-preset", el).value);
    $("#gb-presetnote", el).textContent = !p ? "" :
      `${p.note || ""}${p.encoder ? ` · ${p.encoder}` : ""}${p.hardware ? " (hardware)" : ""}`;
  }

  /* ---------- search ---------- */
  async function search() {
    const box = $("#gb-results", el);
    const tenant = $("#gb-tenant", el).value.trim() || "brooklinema";
    box.innerHTML = `<div class="hint" style="padding:10px 2px">asking ${esc(tenant)}.api.civicclerk.com…</div>`;
    try {
      const r = await api("/api/grabber/search", {
        tenant, from: $("#gb-from", el).value, to: $("#gb-to", el).value,
      });
      patchSession({ tools: { grabber: { tenant } } });
      if (!r.events.length) {
        box.innerHTML = `<div class="hint" style="padding:10px 2px">no events in that range</div>`;
        return;
      }
      box.innerHTML = r.events.map((ev, k) => {
        const vids = ev.links.filter(l => l.videoish);
        const docs = ev.links.length - vids.length;
        return `<div class="gb-event">
          <div class="gb-evhead">
            <span class="gb-evname">${esc(ev.name)}</span>
            <span class="gb-evmeta">${esc((ev.when || "").slice(0, 16).replace("T", " · "))}
              ${ev.category ? " · " + esc(ev.category) : ""}</span>
          </div>
          ${vids.map(l => `<div class="gb-link">
              <span class="gb-lfield" title="found in ${esc(l.field)}">${esc(l.url.length > 74 ? l.url.slice(0, 74) + "…" : l.url)}</span>
              <button class="btn gb-fetch" style="width:auto;padding:3px 12px"
                data-url="${esc(l.url)}" data-name="${esc(ev.name)}">Fetch</button>
            </div>`).join("")
          || `<div class="hint" style="padding:2px 0 4px">no video link on this event${docs ? ` (${docs} document link${docs > 1 ? "s" : ""})` : ""}</div>`}
        </div>`;
      }).join("");
      $$(".gb-fetch", box).forEach(b => b.onclick = () => fetchURL(b.dataset.url, b.dataset.name, b));
      toast(`${r.events.length} events · ${r.with_video} with video`);
    } catch (e) {
      box.innerHTML = `<div class="progmsg err" style="padding:10px 2px">${esc(e.message)}</div>`;
    }
  }

  /* ---------- fetch + library + convert ---------- */
  async function fetchURL(url, name, btn) {
    if (!url) return;
    if (btn) btn.disabled = true;
    try {
      const job = await api("/api/grabber/fetch", { url, name: name || "" });
      toast("fetching — it lands in the bin below");
      const row = document.createElement("div");
      row.className = "batchrow";
      row.innerHTML = `<span class="bname">${esc(name || url)}</span>
        <span class="bstat">queued</span>`;
      $("#gb-library", el).prepend(row);
      watchJob(job.id, j => {
        $(".bstat", row).textContent = j.status === "running"
          ? (j.message || `${Math.round(Math.max(0, j.progress) * 100)}%`) : j.status;
      });
      const done = await jobDone(job.id);
      if (btn) btn.disabled = false;
      if (done.status === "done") { toast("fetched"); loadLibrary(); }
      else if (done.status === "error") { toast(done.error, true); loadLibrary(); }
    } catch (e) { if (btn) btn.disabled = false; toast(e.message, true); }
  }

  async function loadLibrary() {
    const box = $("#gb-library", el);
    try {
      const rows = await api("/api/grabber/library");
      if (!rows.length) {
        box.innerHTML = `<div class="hint" style="padding:8px 2px">nothing fetched yet</div>`;
        return;
      }
      box.innerHTML = rows.map(r => `
        <div class="batchrow" style="margin-top:6px">
          <span class="bname" style="flex:1">${esc(r.name)}</span>
          <span class="bstat">${(r.size / 1e6).toFixed(0)} MB</span>
          <button data-open="${esc(r.path)}" title="open in Highlighter">highlight</button>
          <button data-conv="${esc(r.path)}">conform</button>
        </div>`).join("");
      $$("button[data-conv]", box).forEach(b => b.onclick = () => convert(b.dataset.conv, b));
      $$("button[data-open]", box).forEach(b => b.onclick = () =>
        go("highlighter", { openPath: b.dataset.open }));
    } catch (e) { box.innerHTML = `<div class="hint">${esc(e.message)}</div>`; }
  }

  async function convert(path, btn) {
    btn.disabled = true;
    try {
      const job = await api("/api/grabber/convert", {
        path, preset: $("#gb-preset", el).value,
        height: $("#gb-height", el).value || null,
        fps: $("#gb-fps", el).value || null,
      });
      const row = btn.closest(".batchrow");
      const stat = $(".bstat", row);
      watchJob(job.id, j => {
        stat.textContent = j.status === "running"
          ? `${Math.round(Math.max(0, j.progress) * 100)}% ${j.message || ""}` : j.status;
      });
      const done = await jobDone(job.id);
      btn.disabled = false;
      if (done.status === "done") {
        const rep = $("#gb-report", el);
        rep.classList.add("show");
        rep.innerHTML += `<b>→</b> ${esc(done.result.out)}\n   ${esc(done.result.label)} · ${done.result.hardware ? "hardware" : "software"} encode\n`;
        stat.textContent = "conformed ✓";
        toast("conformed for air");
      } else if (done.status === "error") { stat.textContent = "error"; toast(done.error, true); }
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  /* ---------- wire up ---------- */
  let inited = false;
  function init() {
    $("#gb-from", el).value = weeksAgo(2);
    $("#gb-to", el).value = today();
    $("#gb-search", el).onclick = search;
    $("#gb-fetchurl", el).onclick = () => {
      const u = $("#gb-url", el).value.trim();
      if (u) { fetchURL(u, ""); $("#gb-url", el).value = ""; }
      else toast("paste a link first", true);
    };
    loadStatus();
  }

  function onshow() {
    if (!inited) { init(); inited = true; }
    ytdlpCheck();   // every open — same covenant as Highlighter
    loadLibrary();
  }

  registerPage("grabber", el, onshow);
  return { onshow };
})();
