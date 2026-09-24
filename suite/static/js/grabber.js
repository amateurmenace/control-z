/* Video Grabber — the search desk for civic media.
   One query runs YouTube (newest first — a town should mean its latest
   meetings) and the CivicClerk portal (events with video + Zoom links) at
   once. Fetch shows what a video really offers (each quality, with its
   size) before a byte moves — always mp4 with audio, audio-only lands
   m4a. Weekly schedules fetch while the app is open and catch up on
   launch. Conform and the broadcast re-namer take a download the last
   mile to playout. */

const GrabberPage = (() => {
  const T = toolById("grabber");
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-grabber";

  const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
    "Saturday", "Sunday"];
  // ceilings, not promises: each takes the best the video has at or under
  // it (the chooser shows what a given video really resolves to)
  const QUALITIES = [["best", "best available"], ["2160", "up to 4K"],
    ["1440", "up to 1440p"], ["1080", "up to 1080p"], ["720", "up to 720p"],
    ["480", "up to 480p"]];

  el.innerHTML = `
  <div class="ws" style="--acc:${T.acc}">
    <div class="mediabar">
      <span class="toolname"><i>Video Grabber</i><span class="tn-sub"> · brings the meeting home</span></span>
      <span class="ytdlp-chip" id="gb-ytdlp" title="the fetch engine — nightly build, checked on every open">yt-dlp —</span>
    </div>
    <div class="ws-body">
      <div class="ws-center" style="overflow-y:auto;padding:16px 22px">

        <div class="gb-hero">
          <div class="gb-herohead">
            <h2>Bring a meeting home</h2>
            <p>Search the town's portal and YouTube at once — or paste any video link.</p>
          </div>
          <div class="gb-entry">
            <span class="gb-entrylabel">find a meeting</span>
            <div class="gb-searchrow">
              <input type="text" id="gb-q" spellcheck="false"
                placeholder="town + board — “brookline select board”, “cambridge school committee budget”…">
              <button class="btn primary" id="gb-go" type="button">Search</button>
            </div>
            <div class="gb-scope">
              <button class="pb-pill on" id="gb-src-yt" type="button" title="YouTube, newest first">youtube</button>
              <button class="pb-pill on" id="gb-src-portal" type="button" title="the CivicClerk portal — agendas, video and Zoom recordings">civicclerk portal</button>
              <input type="text" id="gb-tenant" value="brooklinema" spellcheck="false" aria-label="portal tenant"
                title="the portal tenant — the part before .api.civicclerk.com">
              <select id="gb-days" title="how far back the portal looks" aria-label="how far back">
                <option value="14">last 2 weeks</option>
                <option value="30">last month</option>
                <option value="60" selected>last 2 months</option>
                <option value="180">last 6 months</option>
              </select>
            </div>
          </div>
          <div class="gb-or" aria-hidden="true"><span>or</span></div>
          <div class="gb-entry">
            <span class="gb-entrylabel">paste a link — YouTube, Zoom, Vimeo and a thousand more</span>
            <div class="gb-searchrow">
              <input type="text" id="gb-url" placeholder="https://…" spellcheck="false" aria-label="video link">
              <button class="btn gb-fetchbtn" id="gb-fetchurl" type="button">⬇ Fetch…</button>
            </div>
            <div class="gb-entryhint">You'll see every quality it comes in, with its size, before anything downloads.
              Video lands as .mp4 (h264 — plays everywhere); captions come along separately.</div>
          </div>
        </div>

        <div class="gb-strip">
          <div id="gb-where"></div>
          <div id="gb-proxy"></div>
        </div>

        <div id="gb-results"></div>
        <div id="gb-jobs"></div>

        <div class="gb-binhead">
          <h3>The bin</h3>
          <span class="hint">everything you've fetched — send any of it down the line: Highlighter
            finds the moments, Publisher makes the posts</span>
        </div>
        <div id="gb-library"><div class="hint" style="padding:8px 2px">nothing fetched yet</div></div>
      </div>

      <div class="inspector" id="gb-insp">
        <div class="insp-head"><h2>Grabber</h2></div>

        <div class="insp-sec">
          <span class="tag">the fetch engine</span>
          <div class="hint" id="gb-engine" style="line-height:1.55">checking yt-dlp…</div>
          <button class="btn" id="gb-ytupdate" style="margin-top:8px">Check for yt-dlp update</button>
          <div class="hint" id="gb-jsrt" style="margin-top:8px;line-height:1.5"></div>
        </div>

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
  const fmtAgo = ts => {
    if (!ts) return "never";
    const s = Math.max(0, Date.now() / 1000 - ts);
    return s < 90 ? "just now" : s < 5400 ? `${Math.round(s / 60)} min ago`
      : s < 172800 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} days ago`;
  };
  async function ytdlpCheck(force) {
    const chip = $("#gb-ytdlp", el);
    const eng = $("#gb-engine", el);
    const btn = $("#gb-ytupdate", el);
    btn.disabled = true;
    try {
      let st = (await api("/api/grabber/ytdlp-check", { force: !!force })).ytdlp;
      const until = Date.now() + 120000;
      while (["checking", "updating"].includes(st.phase) && Date.now() < until) {
        chip.textContent = "yt-dlp " + (st.phase === "updating" ? "updating…" : "checking…");
        eng.textContent = st.detail || "checking GitHub for tonight's build…";
        btn.textContent = st.phase === "updating" ? "updating…" : "checking…";
        await new Promise(r => setTimeout(r, 900));
        st = (await api("/api/grabber/status")).ytdlp;
      }
      const ok = st.phase === "ok" || st.present;
      const viaProxy = st.proxy && st.proxy.enabled;
      const day = st.installed ? st.installed.split(".").slice(0, 3).join(".") : "";
      chip.textContent = "yt-dlp " + (day || "missing") + (viaProxy ? " · proxy on" : "");
      chip.classList.toggle("ok", ok);
      chip.classList.toggle("err", !ok);
      chip.title = (st.installed ? `nightly ${st.installed} — ` : "") + (st.detail || "") + (viaProxy
        ? " — YouTube requests ride the proxy" : " — fetching directly from this computer");
      const state = st.phase === "error" ? "couldn't check"
        : /current/i.test(st.detail || "") ? "current" : (st.detail || "");
      eng.innerHTML = `<div class="gb-engline"><span class="gb-engdot${st.phase === "error" ? " err" : ok ? " ok" : ""}"></span>
          <b>${day ? `yt-dlp ${esc(day)}` : "yt-dlp isn't installed yet"}</b>
          <span class="gb-engstate">${esc(state)}</span></div>
        <div class="gb-engsub">checked ${fmtAgo(st.checked_at)} — the downloader updates nightly,
          because YouTube changes weekly</div>`;
      const rt = st.js_runtime;
      $("#gb-jsrt", el).innerHTML = rt
        ? `✓ YouTube's JavaScript checks: solved with <b>${esc(rt.name)}</b>`
        : `⚠ No JavaScript runtime found — YouTube may offer fewer qualities and fail more often.
           <a href="#" id="gb-getdeno">Install the free helper (Deno) in Settings</a>.`;
      const gd = $("#gb-getdeno", el);
      if (gd) gd.onclick = e => { e.preventDefault(); go("settings", { section: "runtimes" }); };
      if (force) toast(st.phase === "error" ? (st.detail || "couldn't check") : (st.detail || "yt-dlp is current"),
                       st.phase === "error");
    } catch (e) { chip.textContent = "yt-dlp ?"; eng.textContent = e.message; }
    btn.disabled = false;
    btn.textContent = "Check for yt-dlp update";
  }

  /* ---------- where downloads go: shown, choosable, confirmed once ---------- */
  let whereRow = null, proxyCard = null, dl = { path: "", confirmed: false },
      asking = null;
  async function loadWhere() {
    try { dl = await api("/api/settings/downloads"); } catch (e) {}
    return dl.path;
  }
  /* the first fetch asks, once: here, or somewhere you pick. "Fetch all N"
     shares the one question (asking) instead of stacking N of them. */
  function confirmFolder() {
    // set synchronously, so every concurrent caller shares this one promise
    if (asking) return asking;
    asking = (async () => {
      if (!dl.confirmed) await loadWhere();  // fresh truth, not a guess
      return dl.confirmed ? true : askFolder();
    })().finally(() => { asking = null; });
    return asking;
  }
  function askFolder() {
    return new Promise(resolve => {
      let chosen = false;
      const m = czModal({
        title: "Where should downloads go?", width: 520,
        onClose: () => resolve(chosen),
        html: `<p class="cz-lede">Videos you fetch are saved to your <b>Downloads</b> folder,
            in a folder of their own:</p>
          <div class="cz-loc" style="margin-top:10px"><code class="cz-loc-path">${esc(
            (CZ.appInfo && CZ.appInfo.home && dl.path.startsWith(CZ.appInfo.home))
              ? "~" + dl.path.slice(CZ.appInfo.home.length) : dl.path)}</code></div>
          <p class="hint" style="margin-top:8px">Captions and a small info file ride along beside each
            video. You can change this any time — it's shown right on the Grabber page.</p>
          <div class="cz-row" style="margin-top:14px">
            <button class="btn primary" id="gb-cf-ok" style="width:auto;--acc:var(--grabber);color:#fff">Use this folder</button>
            <button class="btn" id="gb-cf-pick" style="width:auto">Choose a different folder…</button>
          </div>`,
      });
      $("#gb-cf-ok", m.box).onclick = async () => {
        try { dl = await api("/api/settings/downloads", { path: "" }); chosen = true; } catch (e) { toast(e.message, true); }
        whereRow && whereRow.refresh();
        m.close();
      };
      $("#gb-cf-pick", m.box).onclick = async () => {
        const p = await pickFolder(dl.path);
        if (!p) return;
        try { dl = await api("/api/settings/downloads", { path: p }); chosen = true; }
        catch (e) { toast(e.message, true); return; }
        whereRow && whereRow.refresh();
        m.close();
      };
    });
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
      const ytErr = (r.errors || {}).youtube;
      if (ytErr && czBlocked(ytErr) && proxyCard) proxyCard.nudge(ytErr);
    } catch (e) {
      clearInterval(tick);
      box.innerHTML = `<div class="progmsg err" style="padding:10px 2px">${esc(e.message)}</div>`;
      if (czBlocked(e.message) && proxyCard) proxyCard.nudge(e.message);
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
                data-url="${esc(l.url)}" data-name="${esc(ev.name)}">⬇ Fetch…</button>
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
            title="read it in Highlighter first — transcript, moments, no download needed">Read in Highlighter</button>
          <button class="btn gb-fetch" style="width:auto;padding:3px 12px"
            data-url="${esc(v.url)}" data-name="${esc(v.title || "")}">⬇ Fetch…</button>
        </div>`).join("") : (errs.youtube ? "" :
        `<div class="hint" style="padding:6px 2px">youtube came back empty for that</div>`);
    }
    const fetchable = [];
    box.innerHTML = html;
    $$(".gb-fetch", box).forEach(b => { fetchable.push(b);
      b.onclick = () => chooseAndFetch(b.dataset.url, b.dataset.name, b); });
    $$("button[data-hl]", box).forEach(b => b.onclick = () =>
      go("highlighter", { openPath: b.dataset.hl }));
    if (fetchable.length > 1) {
      // many at once skips the chooser (N popups for N results would be a
      // punishment) — so the ceiling sits right here, beside the button
      const pref = lastQuality();
      box.insertAdjacentHTML("afterbegin", `
        <div style="display:flex;gap:8px;align-items:center;margin-top:12px;flex-wrap:wrap">
          <button class="btn" id="gb-fetchall" style="width:auto">⬇ Fetch all ${fetchable.length}</button>
          <label class="hint" style="display:flex;gap:6px;align-items:center">at
            <select id="gb-allq">${[...QUALITIES, ["audio", "audio only"]].map(([v, l]) =>
              `<option value="${v}" ${v === pref ? "selected" : ""}>${l}</option>`).join("")}</select></label>
          <span class="hint">— the best each one has at or under that; they queue and land in the bin</span>
        </div>`);
      $("#gb-fetchall", box).onclick = () => {
        $("#gb-fetchall", box).disabled = true;
        const q = $("#gb-allq", box).value;
        fetchable.forEach(b => fetchURL(b.dataset.url, b.dataset.name, b, q));
        toast(`${fetchable.length} fetches queued`);
      };
    }
  }

  /* ---------- the quality chooser: see what a video offers, then fetch ----------
     A single Fetch asks first. The check reads the video's real ladder in a
     few seconds — each rung resolved to the file you'd actually get, with
     its size — and audio only lives here too. Your last pick is remembered
     and pre-selected, landed on this video's ladder. */
  const QPREF = "cz-gb-quality";
  function lastQuality() {
    try { return localStorage.getItem(QPREF) || "best"; } catch (e) { return "best"; }
  }
  function rememberQuality(q) { try { localStorage.setItem(QPREF, q); } catch (e) {} }
  const aboutSize = b => b == null ? "size unknown" : b < 1e6 ? "under 1 MB"
    : b >= 1e9 ? `about ${(b / 1e9).toFixed(1)} GB` : `about ${Math.round(b / 1e6)} MB`;
  const tilde = p => (CZ.appInfo && CZ.appInfo.home && p.startsWith(CZ.appInfo.home))
    ? "~" + p.slice(CZ.appInfo.home.length) : p;
  const hms = t => {                     // 3:53 · 4:02:17 — a running time
    t = Math.round(t);
    const h = Math.floor(t / 3600), m = Math.floor(t % 3600 / 60), x = t % 60;
    const p2 = n => String(n).padStart(2, "0");
    return h ? `${h}:${p2(m)}:${p2(x)}` : `${m}:${p2(x)}`;
  };
  const qLabel = q => q === "audio" ? "audio only"
    : (QUALITIES.find(([v]) => v === q) || [q, q])[1];

  // the remembered pick on THIS ladder: audio stays audio, "best" is the
  // top, a number is the tallest rung at or under it
  function preselect(opts, want) {
    const vids = opts.map((o, i) => [o, i]).filter(([o]) => o.quality !== "audio");
    if (want === "audio") {
      const i = opts.findIndex(o => o.quality === "audio");
      if (i >= 0) return i;
    }
    if (!vids.length) return 0;
    if (want === "best" || want === "audio") return vids[0][1];
    const fit = vids.find(([o]) => !o.height || o.height <= +want);
    return (fit || vids[vids.length - 1])[1];
  }

  function chooseQuality(url, name) {
    return new Promise(resolve => {
      let answer = null;
      const m = czModal({ title: "Choose a quality", width: 540,
                          onClose: () => resolve(answer) });
      const box = m.box;
      if (!dl.path) loadWhere();
      const take = (q, remember) => {
        answer = q;
        if (remember) rememberQuality(q);
        m.close();
      };
      const pref = lastQuality();
      // captions come only with a video fetch — not audio only, not Zoom
      const where = caps => dl.path
        ? `<div class="hint gb-qc-where">lands in <code>${esc(tilde(dl.path))}</code>${
            caps ? " · a video brings its captions along" : ""}</div>` : "";
      const actions = go => `<div class="gb-qc-actions">
          <button class="btn" type="button" data-x>Cancel</button>
          <button class="btn primary gb-qc-go" type="button">${go || "⬇ Fetch"}</button></div>`;
      const wire = () => {
        $("[data-x]", box).onclick = () => m.close();
        const go = $(".gb-qc-go", box);
        box.onkeydown = e => {
          if (e.key === "Enter" && !e.target.matches("button")) { e.preventDefault(); go.click(); }
        };
        return go;
      };
      // a list of rungs → radio rows; the button names the pick and its size
      const list = (opts, sel) => {
        box.insertAdjacentHTML("beforeend", `
          <div class="gb-qc-list" role="radiogroup" aria-label="quality">
            ${opts.map((o, i) => `<label class="gb-qc-opt">
              <input type="radio" name="gb-qc" data-i="${i}" ${i === sel ? "checked" : ""}>
              <span class="gb-qc-label">${esc(o.label)}</span>
              <span class="gb-qc-kind">${o.quality === "audio" ? ".m4a" : ".mp4"}</span>
              <span class="gb-qc-size">${o.bytes === undefined ? "" : aboutSize(o.bytes)}</span>
            </label>`).join("")}
          </div>`);
      };
      const finish = (opts, remember) => {
        const go = wire();
        const sync = () => {
          const o = opts[+$("input[name=gb-qc]:checked", box).dataset.i];
          go.onclick = () => take(o.quality, remember);
          go.textContent = `⬇ Fetch ${o.label}` + (o.bytes ? ` · ${aboutSize(o.bytes).replace("about ", "~").replace("under ", "<")}` : "");
        };
        $$("input[name=gb-qc]", box).forEach(r => r.onchange = sync);
        sync();
        setTimeout(() => { const r = $("input[name=gb-qc]:checked", box); if (r) r.focus(); }, 30);
      };

      box.innerHTML = `
        <div class="gb-qc-title">${esc(name || url)}</div>
        <div class="gb-qc-wait" role="status"><span class="gb-qc-spin"></span>checking what this video offers — a few seconds…</div>
        <div class="gb-qc-actions">
          <button class="btn" type="button" data-x>Cancel</button>
          <button class="btn gb-qc-skip" type="button" title="skip the check — the fetch takes the best it has at or under this">Don't wait — fetch ${esc(qLabel(pref))}</button></div>`;
      $("[data-x]", box).onclick = () => m.close();
      $(".gb-qc-skip", box).onclick = () => take(pref, false);

      api("/api/grabber/probe", { url }).then(info => {
        if (!box.isConnected) return;             // closed while it checked
        if (info.kind === "zoom") {
          box.innerHTML = `<div class="gb-qc-title">${esc(name || "Zoom recording")}</div>
            <p class="cz-lede" style="margin-top:8px">Zoom shares a recording exactly as it was
              recorded — one version, so there's nothing to choose.</p>
            ${where(false)}${actions("⬇ Fetch the recording")}`;
          wire().onclick = () => take("best", false);
          return;
        }
        const opts = info.options || [];
        if (!opts.length) { fallback(""); return; }
        const top = opts.find(o => o.quality !== "audio");
        const meta = [info.uploader, info.duration ? hms(info.duration) : ""].filter(Boolean);
        box.innerHTML = `
          <div class="gb-qc-title">${esc(info.title || name || url)}</div>
          ${meta.length ? `<div class="hint">${meta.map(esc).join(" · ")}</div>` : ""}
          ${info.live ? `<div class="cz-note">This is <b>live right now</b> — a fetch records until the stream ends.</div>` : ""}`;
        list(opts, preselect(opts, pref));
        if (top && top.height && info.max_height > top.height) {
          box.insertAdjacentHTML("beforeend", `<div class="hint" style="margin-top:8px">It also exists up to
            ${info.max_height >= 2160 ? "4K" : info.max_height + "p"}, but only in VP9/AV1 — codecs QuickTime and many
            editors can't open. Fetches stay h264 so every file plays everywhere.</div>`);
        }
        box.insertAdjacentHTML("beforeend", where(true) + actions());
        finish(opts, true);
      }).catch(e => { if (box.isConnected) fallback(e.message); });

      // the check failed or the site won't say: the ceilings, no sizes
      function fallback(msg) {
        const blocked = !!msg && czBlocked(msg);
        const opts = [...QUALITIES, ["audio", "audio only"]].map(([v, l]) =>
          ({ quality: v, label: l, bytes: undefined, height: +v || 0 }));
        box.innerHTML = `<div class="gb-qc-title">${esc(name || url)}</div>
          ${msg ? `<div class="progmsg err" style="margin-top:8px">${esc(msg)}</div>` : ""}
          <p class="hint" style="margin-top:8px">${blocked
            ? "YouTube is refusing this computer right now — close this, turn on the proxy (just under the link box), and fetch again."
            : "It didn't say what it offers — pick a ceiling, and the fetch takes the best it has at or under it."}</p>`;
        list(opts, Math.max(0, opts.findIndex(o => o.quality === pref)));
        box.insertAdjacentHTML("beforeend", where(true) + actions());
        finish(opts, true);
        if (blocked && proxyCard) proxyCard.nudge(msg);
      }
    });
  }

  // one video: ask, then fetch — a dismissed chooser fetches nothing
  async function chooseAndFetch(url, name, btn, onStarted) {
    if (btn) btn.disabled = true;
    const q = await chooseQuality(url, name);
    if (btn) btn.disabled = false;
    if (q) fetchURL(url, name, btn, q, onStarted);
  }

  /* ---------- fetch + bin ---------- */
  async function fetchURL(url, name, btn, quality, onStarted) {
    if (!url) return;
    if (!(await confirmFolder())) { toast("pick where downloads go first", true); return; }
    if (btn) btn.disabled = true;
    try {
      const job = await api("/api/grabber/fetch", { url, name: name || "",
                                                    quality: quality || "best" });
      if (onStarted) onStarted();
      const p = czProgress($("#gb-jobs", el), {
        label: (name || url).slice(0, 90), acc: "var(--grabber)" });
      watchJob(job.id, j => p.update(j));
      const done = await jobDone(job.id);
      p.finish(done);
      if (btn) btn.disabled = false;
      if (done.status === "done") {
        const cap = (done.result || {}).captions || {};
        toast(cap.captions === "failed"
          ? "fetched — the video is safe; its captions didn't come (see the bin)"
          : "fetched — it's in the bin");
        if (cap.blocked && proxyCard) proxyCard.nudge(cap.note);
        loadLibrary();
      } else if (done.status === "error") {
        toast(done.error, true);
        if (czBlocked(done.error) && proxyCard) proxyCard.nudge(done.error);
        loadLibrary();
      }
    } catch (e) { if (btn) btn.disabled = false; toast(e.message, true); }
  }

  async function fetchCaptions(path, btn) {
    btn.disabled = true;
    try {
      const job = await api("/api/grabber/captions", { path });
      const p = czProgress($("#gb-jobs", el), {
        label: `captions — ${path.split("/").pop()}`.slice(0, 90), acc: "var(--grabber)" });
      watchJob(job.id, j => p.update(j));
      const done = await jobDone(job.id);
      p.finish(done);
      if (done.status === "error") {
        toast(done.error, true);
        if (czBlocked(done.error) && proxyCard) proxyCard.nudge(done.error);
      } else if (done.status === "done") toast(done.message || "captions ✓");
      loadLibrary();
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  async function loadLibrary() {
    const box = $("#gb-library", el);
    try {
      const rows = await api("/api/grabber/library");
      if (!rows.length) {
        box.innerHTML = `<div class="hint" style="padding:8px 2px">nothing fetched yet —
          search above, or paste a link</div>`;
        return;
      }
      const words = r => r.transcript ? `<span class="badge" style="color:var(--ok);border-color:var(--ok)" title="a transcript is beside it">words ✓</span>`
        : r.captions ? `<span class="badge" style="color:var(--ok);border-color:var(--ok)" title="YouTube's captions are beside it — Highlighter reads them instantly">captions ✓</span>`
        : `<span class="badge warn" title="no words yet — fetch YouTube's captions, or let Scribe transcribe it">no captions</span>`;
      // one row per recording: its title in full, one clear way onward
      // (the next app), and the housekeeping as quiet text beside the facts
      box.innerHTML = rows.map(r => `
        <div class="gb-binrow">
          <span class="bname" title="${esc(r.path)}">${esc(r.title || r.name)}</span>
          <div class="gb-binacts">${czNextHTML("grabber", r.path, { isFile: true })}</div>
          <div class="gb-binsub">
            <span class="gb-binmeta">${(r.size / 1e6).toFixed(0)} MB${r.duration ? " · " + fmtDur(r.duration) : ""}${r.section ? " · section clip" : ""}</span>
            ${words(r)} ${r.highlights ? `<span class="badge" title="moments already picked">★ moments</span>` : ""}
            <span class="gb-binmore">
              ${!r.captions && !r.transcript && r.url ? `<button type="button" data-cap="${esc(r.path)}"
                title="fetch YouTube's captions for this file — no re-download">get captions</button>` : ""}
              <button type="button" data-conv="${esc(r.path)}" title="conform for air with the preset on the right">conform for air</button>
              <button type="button" data-ren="${esc(r.path)}" title="broadcast-safe rename (pattern on the right); sidecars travel too">rename</button>
              <button type="button" data-rev="${esc(r.path)}" title="show it in Finder">show in Finder</button>
            </span>
          </div>
        </div>`).join("");
      $$("button[data-conv]", box).forEach(b => b.onclick = () => convert(b.dataset.conv, b));
      $$("button[data-cap]", box).forEach(b => b.onclick = () => fetchCaptions(b.dataset.cap, b));
      $$("button[data-ren]", box).forEach(b => b.onclick = () => rename(b.dataset.ren, b));
      $$("button[data-rev]", box).forEach(b => b.onclick = () =>
        api("/api/media/reveal", { path: b.dataset.rev }).catch(e => toast(e.message, true)));
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
    whereRow = czLocRow($("#gb-where", el), {
      label: "Downloads go to",
      load: loadWhere,
      save: async p => { dl = await api("/api/settings/downloads", { path: p }); return dl.path; },
    });
    proxyCard = czProxyCard($("#gb-proxy", el));
    $("#gb-ytupdate", el).onclick = () => ytdlpCheck(true);
    $("#gb-go", el).onclick = find;
    $("#gb-q", el).addEventListener("keydown", e => { if (e.key === "Enter") find(); });
    $("#gb-src-yt", el).onclick = () => { S.srcYT = !S.srcYT;
      $("#gb-src-yt", el).classList.toggle("on", S.srcYT); };
    $("#gb-src-portal", el).onclick = () => { S.srcPortal = !S.srcPortal;
      $("#gb-src-portal", el).classList.toggle("on", S.srcPortal); };
    $("#gb-fetchurl", el).onclick = () => {
      const u = $("#gb-url", el).value.trim();
      // the link stays in the box until the fetch is really queued — a
      // dismissed chooser or folder prompt shouldn't eat what was pasted
      if (u) chooseAndFetch(u, "", $("#gb-fetchurl", el),
                            () => { $("#gb-url", el).value = ""; });
      else toast("paste a link first", true);
    };
    $("#gb-url", el).addEventListener("keydown", e => {
      if (e.key === "Enter") $("#gb-fetchurl", el).click(); });
    $("#gb-s-add", el).onclick = addSchedule;
    $("#gb-pattern", el).addEventListener("input", () => {
      clearTimeout(S.pt); S.pt = setTimeout(async () => {
        const rows = await api("/api/grabber/library");
        patternPreview(rows[0] && rows[0].path);
      }, 400);
    });
  }

  function onshow(arg) {
    const first = !inited;
    if (!inited) { init(); inited = true; }
    ytdlpCheck();   // every open — the stated deal
    loadStatus();
    loadLibrary();
    if (!first) { whereRow.refresh(); proxyCard.refresh(); }
    if (arg && arg.focusSearch) setTimeout(() => $("#gb-q", el).focus(), 60);
  }

  /* back to a fresh desk: no query, no results, no half-pasted link.
     Fetches already running keep going (the Queue and the corner cards
     carry them); the bin is the disk, so it stays. */
  function reset() {
    $("#gb-q", el).value = "";
    $("#gb-url", el).value = "";
    $("#gb-results", el).innerHTML = "";
    $("#gb-jobs", el).innerHTML = "";
    const rep = $("#gb-report", el);
    rep.innerHTML = ""; rep.classList.remove("show");
    S.srcYT = S.srcPortal = true;
    $("#gb-src-yt", el).classList.add("on");
    $("#gb-src-portal", el).classList.add("on");
    if (inited) { loadLibrary(); proxyCard.refresh(); }
  }

  registerPage("grabber", el, onshow, { reset });
  return { onshow };
})();
