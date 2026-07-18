/* Video Grabber — the search desk for civic media.
   One query runs YouTube (newest first — a town should mean its latest
   meetings) and the CivicClerk portal (events with video + Zoom links) at
   once. Paste a link to fetch directly at any quality — always mp4 with
   audio, audio-only lands m4a. Weekly schedules fetch while the app is
   open and catch up on launch. Conform and the broadcast re-namer take a
   download the last mile to playout. */

const GrabberPage = (() => {
  const T = toolById("grabber");
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-grabber";

  const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
    "Saturday", "Sunday"];
  const QUALITIES = [["best", "best"], ["2160", "4K"], ["1440", "1440p"],
    ["1080", "1080p"], ["720", "720p"], ["480", "480p"]];

  el.innerHTML = `
  <div class="ws" style="--acc:${T.acc}">
    <div class="mediabar">
      <span class="toolname"><i>Video Grabber</i> · brings the meeting home</span>
      <span class="ytdlp-chip" id="gb-ytdlp" title="the fetch engine — nightly build, checked on every open">yt-dlp —</span>
    </div>
    <div class="ws-body">
      <div class="ws-center" style="overflow-y:auto;padding:16px 22px">

        <div class="gb-hero">
          <div class="tag">find civic media — the portal and the platforms, one search</div>
          <div class="gb-searchrow">
            <input type="text" id="gb-q" spellcheck="false"
              placeholder="town + body — “brookline select board”, “cambridge school committee budget”…">
            <button class="btn primary" id="gb-go">Search</button>
          </div>
          <div class="gb-scope">
            <button class="pb-pill on" id="gb-src-yt" title="YouTube, newest first">youtube</button>
            <button class="pb-pill on" id="gb-src-portal" title="the CivicClerk portal — agendas, video and Zoom recordings">civicclerk portal</button>
            <input type="text" id="gb-tenant" value="brooklinema" spellcheck="false"
              title="the portal tenant — the part before .api.civicclerk.com">
            <select id="gb-days" title="how far back the portal looks">
              <option value="14">last 2 weeks</option>
              <option value="30">last month</option>
              <option value="60" selected>last 2 months</option>
              <option value="180">last 6 months</option>
            </select>
            <span style="flex:1"></span>
            <label class="hint" style="display:flex;gap:6px;align-items:center">fetch at
              <select id="gb-quality">${QUALITIES.map(([v, l]) =>
                `<option value="${v}">${l}</option>`).join("")}</select></label>
          </div>
        </div>

        <div id="gb-results"></div>

        <div class="tag" style="margin-top:22px">or paste a link — yt-dlp speaks zoom, youtube, vimeo and a thousand others</div>
        <div class="gb-direct">
          <input type="text" id="gb-url" placeholder="https://…zoom.us/rec/… or any video URL" spellcheck="false">
          <label class="hint" style="display:flex;gap:5px;align-items:center;white-space:nowrap">
            <input type="checkbox" id="gb-audioonly"> audio only</label>
          <button class="btn" id="gb-fetchurl" style="width:auto">⬇ Fetch</button>
        </div>
        <div class="hint" style="margin-top:5px">every fetch lands as <b>.mp4 with audio</b> at your chosen quality — audio-only lands .m4a</div>

        <div id="gb-jobs"></div>

        <div class="tag" style="margin-top:24px">the bin — fetched recordings</div>
        <div id="gb-library"><div class="hint" style="padding:8px 2px">nothing fetched yet</div></div>
      </div>

      <div class="inspector" id="gb-insp">
        <div class="insp-head"><h2>Grabber</h2></div>

        <div class="insp-sec">
          <span class="tag">on a schedule</span>
          <div id="gb-scheds"><div class="hint">none yet — the archive fills itself once you add one</div></div>
          <div class="field"><label>every</label>
            <select id="gb-s-wd">${WEEKDAYS.map((d, i) =>
              `<option value="${i}" ${i === 3 ? "selected" : ""}>${d}</option>`).join("")}</select>
            <select id="gb-s-hr">${Array.from({ length: 24 }, (_, h) =>
              `<option value="${h}" ${h === 9 ? "selected" : ""}>${String(h).padStart(2, "0")}:00</option>`).join("")}</select>
          </div>
          <div class="field"><label>grab everything from</label>
            <select id="gb-s-days">
              <option value="7" selected>the last week</option>
              <option value="14">the last 2 weeks</option>
              <option value="30">the last month</option>
            </select>
          </div>
          <div class="field"><label>portal + quality</label>
            <input type="text" id="gb-s-tenant" value="brooklinema" spellcheck="false" style="width:110px">
            <select id="gb-s-quality">${QUALITIES.map(([v, l]) =>
              `<option value="${v}">${l}</option>`).join("")}</select>
          </div>
          <button class="btn" id="gb-s-add">Add schedule</button>
          <div class="hint" style="margin-top:6px">runs while the app is open;
            a missed time catches up on the next launch</div>
        </div>

        <div class="insp-sec">
          <span class="tag">conform for air</span>
          <div class="field"><label>preset</label><select id="gb-preset"></select>
            <div class="hint" id="gb-presetnote"></div>
          </div>
          <div class="field"><label>height</label>
            <select id="gb-height">
              <option value="">keep source</option>
              <option value="2160">2160 — 4K</option>
              <option value="1440">1440</option>
              <option value="1080">1080</option>
              <option value="720">720</option>
              <option value="480">480</option>
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
          <span class="tag">broadcast re-namer</span>
          <div class="field"><label>pattern</label>
            <input type="text" id="gb-pattern" value="{title}_{date}" spellcheck="false">
            <div class="hint" id="gb-patternprev">tokens: {title} {date} — spaces and
              brackets become underscores; sidecars travel with the rename</div>
          </div>
        </div>

        <div class="report" id="gb-report"></div>
      </div>
    </div>
  </div>`;

  const S = { presets: [], srcYT: true, srcPortal: true };
  const fmtDur = s => !s ? "" : (s >= 3600
    ? `${Math.floor(s / 3600)}:${String(Math.floor(s % 3600 / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`
    : `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`);
  const fmtDate = d => d && /^\d{8}$/.test(d)
    ? `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}` : (d || "");

  /* ---------- status + chips ---------- */
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
      if (saved) { $("#gb-tenant", el).value = saved; $("#gb-s-tenant", el).value = saved; }
      renderScheds(st.schedules || []);
    } catch (e) { /* the desk still takes pasted links */ }
  }
  function presetNote() {
    const p = S.presets.find(x => x.id === $("#gb-preset", el).value);
    $("#gb-presetnote", el).textContent = !p ? "" :
      `${p.note || ""}${p.encoder ? ` · ${p.encoder}` : ""}${p.hardware ? " (hardware)" : ""}`;
  }

  /* ---------- the search desk ---------- */
  async function find() {
    const q = $("#gb-q", el).value.trim();
    if (q.length < 2) { toast("give the search a couple of words", true); return; }
    const box = $("#gb-results", el);
    const stages = ["asking the portal…", "asking youtube, newest first…",
      "reading the dates…", "still looking — big result pages take a moment…"];
    box.innerHTML = `<div class="gb-sweep"><span class="gb-sweepbar"><i></i></span>
      <span id="gb-sweepmsg">${stages[0]}</span>
      <span class="hint" id="gb-sweepsec" style="margin-left:auto">0s</span></div>`;
    const t0 = Date.now();
    let k = 0;
    const tick = setInterval(() => {
      const m = $("#gb-sweepmsg", box);
      const sec = $("#gb-sweepsec", box);
      if (!m) { clearInterval(tick); return; }
      k = Math.min(k + 1, stages.length - 1);
      m.textContent = stages[k];
      if (sec) sec.textContent = `${Math.round((Date.now() - t0) / 1000)}s`;
    }, 2600);
    try {
      const r = await api("/api/grabber/find", {
        q, youtube: S.srcYT, portal: S.srcPortal,
        tenant: $("#gb-tenant", el).value.trim() || "brooklinema",
        days: +$("#gb-days", el).value,
      });
      patchSession({ tools: { grabber: { tenant: $("#gb-tenant", el).value.trim() } } });
      clearInterval(tick);
      renderResults(r);
    } catch (e) {
      clearInterval(tick);
      box.innerHTML = `<div class="progmsg err" style="padding:10px 2px">${esc(e.message)}</div>`;
    }
  }

  function renderResults(r) {
    const box = $("#gb-results", el);
    const portal = r.portal || [], yt = r.youtube || [];
    const errs = r.errors || {};
    if (!portal.length && !yt.length && !Object.keys(errs).length) {
      box.innerHTML = `<div class="hint" style="padding:10px 2px">nothing found — widen the dates, or try fewer words</div>`;
      return;
    }
    let html = "";
    if (S.srcPortal) {
      html += `<div class="tag" style="margin-top:16px">on the portal — with the zoom recordings</div>`;
      if (errs.portal) html += `<div class="progmsg err">${esc(errs.portal)}</div>`;
      html += portal.length ? portal.map(ev => {
        const vids = ev.links.filter(l => l.videoish);
        return `<div class="gb-event">
          <div class="gb-evhead">
            <span class="gb-evname">${esc(ev.name)}</span>
            <span class="gb-evmeta">${esc((ev.when || "").slice(0, 16).replace("T", " · "))}
              ${ev.category ? " · " + esc(ev.category) : ""}</span>
          </div>
          ${vids.map(l => `<div class="gb-link">
              <span class="badge${/zoom/i.test(l.url) ? " zoom" : ""}">${/zoom/i.test(l.url) ? "zoom" : "video"}</span>
              <span class="gb-lfield" title="found in ${esc(l.field)}">${esc(l.url.length > 66 ? l.url.slice(0, 66) + "…" : l.url)}</span>
              <button class="btn gb-fetch" style="width:auto;padding:3px 12px"
                data-url="${esc(l.url)}" data-name="${esc(ev.name)}">⬇ Fetch</button>
            </div>`).join("")
          || `<div class="hint" style="padding:2px 0 4px">no video link on this event</div>`}
        </div>`;
      }).join("") : (errs.portal ? "" :
        `<div class="hint" style="padding:6px 2px">no matching portal events in that window</div>`);
    }
    if (S.srcYT) {
      html += `<div class="tag" style="margin-top:16px">on youtube — newest first</div>`;
      if (errs.youtube) html += `<div class="progmsg err">${esc(errs.youtube)}</div>`;
      html += yt.length ? yt.map(v => `
        <div class="gb-yt">
          <div class="gb-ytbody">
            <div class="gb-evname">${esc(v.title || v.id)}</div>
            <div class="gb-evmeta">${esc(v.uploader || "")}${v.date ? " · " + fmtDate(v.date) : ""}
              ${v.duration ? " · " + fmtDur(v.duration) : ""}${v.views ? ` · ${(+v.views).toLocaleString()} views` : ""}</div>
          </div>
          <button class="btn" style="width:auto;padding:3px 12px" data-hl="${esc(v.url)}"
            title="read it in Highlighter first — transcript, moments, no download needed">→ Highlighter</button>
          <button class="btn gb-fetch" style="width:auto;padding:3px 12px"
            data-url="${esc(v.url)}" data-name="${esc(v.title || "")}">⬇ Fetch</button>
        </div>`).join("") : (errs.youtube ? "" :
        `<div class="hint" style="padding:6px 2px">youtube came back empty for that</div>`);
    }
    const fetchable = [];
    box.innerHTML = html;
    $$(".gb-fetch", box).forEach(b => { fetchable.push(b);
      b.onclick = () => fetchURL(b.dataset.url, b.dataset.name, b); });
    $$("button[data-hl]", box).forEach(b => b.onclick = () =>
      go("highlighter", { openPath: b.dataset.hl }));
    if (fetchable.length > 1) {
      box.insertAdjacentHTML("afterbegin", `
        <div style="display:flex;gap:8px;align-items:center;margin-top:12px">
          <button class="btn" id="gb-fetchall" style="width:auto">⬇ Fetch all ${fetchable.length}</button>
          <span class="hint">every result below, at the chosen quality — they queue and land in the bin</span>
        </div>`);
      $("#gb-fetchall", box).onclick = () => {
        $("#gb-fetchall", box).disabled = true;
        fetchable.forEach(b => fetchURL(b.dataset.url, b.dataset.name, b));
        toast(`${fetchable.length} fetches queued`);
      };
    }
  }

  /* ---------- fetch + bin ---------- */
  async function fetchURL(url, name, btn, audioOnly) {
    if (!url) return;
    if (btn) btn.disabled = true;
    const quality = audioOnly ? "audio" : $("#gb-quality", el).value;
    try {
      const job = await api("/api/grabber/fetch", { url, name: name || "", quality });
      const p = czProgress($("#gb-jobs", el), {
        label: (name || url).slice(0, 90), acc: "var(--grabber)" });
      watchJob(job.id, j => p.update(j));
      const done = await jobDone(job.id);
      p.finish(done);
      if (btn) btn.disabled = false;
      if (done.status === "done") { toast("fetched — it's in the bin"); loadLibrary(); }
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
          <span class="bname" style="flex:1" title="${esc(r.path)}">${esc(r.name)}</span>
          <span class="bstat">${(r.size / 1e6).toFixed(0)} MB</span>
          <button data-open="${esc(r.path)}" title="find the moments">highlight</button>
          <button data-pub="${esc(r.path)}" title="make the publish kit">publish</button>
          <button data-conv="${esc(r.path)}" title="conform for air with the preset on the right">conform</button>
          <button data-ren="${esc(r.path)}" title="broadcast-safe rename (pattern on the right); sidecars travel too">rename</button>
        </div>`).join("");
      $$("button[data-conv]", box).forEach(b => b.onclick = () => convert(b.dataset.conv, b));
      $$("button[data-open]", box).forEach(b => b.onclick = () =>
        go("highlighter", { openPath: b.dataset.open }));
      $$("button[data-pub]", box).forEach(b => b.onclick = () =>
        go("publisher", { openPath: b.dataset.pub }));
      $$("button[data-ren]", box).forEach(b => b.onclick = () => rename(b.dataset.ren, b));
      patternPreview(rows[0] && rows[0].path);
    } catch (e) { box.innerHTML = `<div class="hint">${esc(e.message)}</div>`; }
  }

  async function patternPreview(path) {
    if (!path) return;
    try {
      const r = await api("/api/grabber/rename", {
        path, pattern: $("#gb-pattern", el).value, preview: true });
      $("#gb-patternprev", el).innerHTML =
        `${esc(r.from.length > 42 ? r.from.slice(0, 42) + "…" : r.from)}<br>→ <b>${esc(r.to)}</b> · sidecars travel too`;
    } catch (e) { /* keep the static hint */ }
  }

  async function rename(path, btn) {
    btn.disabled = true;
    try {
      const r = await api("/api/grabber/rename", {
        path, pattern: $("#gb-pattern", el).value });
      toast(`renamed → ${r.to}`);
      const rep = $("#gb-report", el);
      rep.classList.add("show");
      rep.innerHTML += `<b>renamed</b> ${esc(r.from)}\n   → ${esc(r.to)}${r.sidecars ? ` (+${r.sidecars} sidecars)` : ""}\n`;
      loadLibrary();
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  async function convert(path, btn) {
    btn.disabled = true;
    try {
      const job = await api("/api/grabber/convert", {
        path, preset: $("#gb-preset", el).value,
        height: $("#gb-height", el).value || null,
        fps: $("#gb-fps", el).value || null,
      });
      const p = czProgress($("#gb-jobs", el), {
        label: `conform — ${path.split("/").pop()}`, acc: "var(--grabber)" });
      watchJob(job.id, j => p.update(j));
      const done = await jobDone(job.id);
      p.finish(done);
      btn.disabled = false;
      if (done.status === "done") {
        const rep = $("#gb-report", el);
        rep.classList.add("show");
        rep.innerHTML += `<b>→</b> ${esc(done.result.out)}\n   ${esc(done.result.label)} · ${done.result.hardware ? "hardware" : "software"} encode\n`;
        toast("conformed for air");
        loadLibrary();
      } else if (done.status === "error") toast(done.error, true);
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  /* ---------- schedules ---------- */
  function renderScheds(rows) {
    const box = $("#gb-scheds", el);
    if (!rows.length) {
      box.innerHTML = `<div class="hint">none yet — the archive fills itself once you add one</div>`;
      return;
    }
    box.innerHTML = rows.map(s => `
      <div class="batchrow" style="margin-bottom:6px;flex-wrap:wrap">
        <span class="bname" style="flex:1">${WEEKDAYS[s.weekday]} ${String(s.hour).padStart(2, "0")}:00 ·
          last ${s.days}d · ${esc(s.tenant)} @ ${s.quality}</span>
        <button data-run="${s.id}" title="run it now">▶</button>
        <button data-tog="${s.id}" title="${s.enabled ? "pause" : "resume"}">${s.enabled ? "⏸" : "⏵"}</button>
        <button data-del="${s.id}" title="remove">×</button>
        <span class="hint" style="flex-basis:100%">${s.last_run
          ? `last: ${esc(s.last_run.replace("T", " "))} — ${esc(s.last_note || "")}`
          : "hasn't run yet"}${s.enabled ? "" : " · paused"}</span>
      </div>`).join("");
    $$("button[data-run]", box).forEach(b => b.onclick = async () => {
      b.disabled = true;
      const r = await api("/api/grabber/schedules", { run: b.dataset.run });
      renderScheds(r.schedules); toast("schedule ran — fetches are queueing");
    });
    $$("button[data-tog]", box).forEach(b => b.onclick = async () => {
      const cur = (await api("/api/grabber/schedules")).schedules
        .find(s => s.id === b.dataset.tog);
      const r = await api("/api/grabber/schedules", {
        update: { id: b.dataset.tog, patch: { enabled: !cur.enabled } } });
      renderScheds(r.schedules);
    });
    $$("button[data-del]", box).forEach(b => b.onclick = async () => {
      const r = await api("/api/grabber/schedules", { remove: b.dataset.del });
      renderScheds(r.schedules);
    });
  }

  async function addSchedule() {
    const r = await api("/api/grabber/schedules", { add: {
      weekday: +$("#gb-s-wd", el).value, hour: +$("#gb-s-hr", el).value,
      days: +$("#gb-s-days", el).value,
      tenant: $("#gb-s-tenant", el).value.trim() || "brooklinema",
      quality: $("#gb-s-quality", el).value,
    } });
    renderScheds(r.schedules);
    toast("scheduled — it runs while the app is open");
  }

  /* ---------- wire up ---------- */
  let inited = false;
  function init() {
    $("#gb-go", el).onclick = find;
    $("#gb-q", el).addEventListener("keydown", e => { if (e.key === "Enter") find(); });
    $("#gb-src-yt", el).onclick = () => { S.srcYT = !S.srcYT;
      $("#gb-src-yt", el).classList.toggle("on", S.srcYT); };
    $("#gb-src-portal", el).onclick = () => { S.srcPortal = !S.srcPortal;
      $("#gb-src-portal", el).classList.toggle("on", S.srcPortal); };
    $("#gb-fetchurl", el).onclick = () => {
      const u = $("#gb-url", el).value.trim();
      if (u) { fetchURL(u, "", null, $("#gb-audioonly", el).checked); $("#gb-url", el).value = ""; }
      else toast("paste a link first", true);
    };
    $("#gb-s-add", el).onclick = addSchedule;
    $("#gb-pattern", el).addEventListener("input", () => {
      clearTimeout(S.pt); S.pt = setTimeout(async () => {
        const rows = await api("/api/grabber/library");
        patternPreview(rows[0] && rows[0].path);
      }, 400);
    });
  }

  function onshow(arg) {
    if (!inited) { init(); inited = true; }
    ytdlpCheck();   // every open — the stated deal
    loadStatus();
    loadLibrary();
    if (arg && arg.focusSearch) setTimeout(() => $("#gb-q", el).focus(), 60);
  }

  registerPage("grabber", el, onshow);
  return { onshow };
})();
