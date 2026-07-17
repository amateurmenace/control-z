/* Community Highlighter — the meeting as text, the reel as kept paragraphs.
   Page open kicks the yt-dlp nightly check (the chip says what happened).
   Transcripts arrive free when the fetch found captions; the Scribe pass is
   one click because it's the same app. Detect marks the moments with its
   reasons on every pick; you keep/drop paragraphs; the reel renders from
   exactly what's kept — or leaves as a selects EDL for Resolve. */

const HighlighterPage = (() => {
  const T = toolById("highlighter");
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-highlighter";
  el.innerHTML = `
  <div class="ws" style="--acc:${T.acc}">
    <div class="mediabar">
      <span class="toolname"><i>Community Highlighter</i> · finds the moments</span>
      <input type="text" id="hl-url" placeholder="paste a YouTube / Zoom / video URL — or open a local file below" spellcheck="false">
      <select id="hl-quality" style="background:var(--ink);border:1px solid var(--line);border-radius:7px;padding:6px 8px;font-size:12px">
        <option value="best">best</option><option value="1080">1080p</option>
        <option value="720">720p</option>
      </select>
      <button class="btn" style="width:auto" id="hl-fetch">Fetch</button>
      <span class="ytdlp-chip" id="hl-ytdlp" title="the fetch engine — nightly build, checked on every open">yt-dlp —</span>
    </div>
    <div class="ws-body">
      <div class="ws-center">
        <div id="hl-viewer" style="height:32%;min-height:160px;position:relative"></div>
        <div class="lane" style="padding:7px 12px;display:flex;align-items:center;gap:10px">
          <button class="btn" style="width:auto;padding:5px 15px" id="hl-play" disabled>▶</button>
          <span class="clipmeta" id="hl-time">0:00.0</span>
          <span class="clipmeta" id="hl-name" style="margin-left:6px"></span>
          <span class="clipmeta" id="hl-keptmeta" style="margin-left:auto"></span>
        </div>
        <div class="lane hl-lane"><canvas id="hl-lanecanvas"></canvas></div>
        <div id="hl-transcript" style="flex:1;overflow-y:auto;padding:14px 20px;background:var(--ink);font-size:14px;line-height:1.9">
          <div class="empty-grain" style="padding:36px 8px;color:var(--cream-faint);text-align:center">
            fetch a meeting (or open one from the library) — the video becomes text,
            the text becomes the reel</div>
        </div>
      </div>
      <div class="inspector" id="hl-insp">
        <div class="insp-head"><h2>Highlighter</h2>
          <div class="density"><button data-d="easy">Easy</button><button data-d="studio">Studio</button></div>
        </div>

        <div class="insp-sec">
          <span class="tag">library — fetched meetings</span>
          <div id="hl-library"><div class="hint">nothing fetched yet</div></div>
          <div class="field studio-only"><label>open a local file instead</label>
            <input type="text" id="hl-localpath" placeholder="/path/to/meeting.mp4" spellcheck="false">
          </div>
        </div>

        <div class="insp-sec" id="hl-readsec" style="display:none">
          <span class="tag">the words</span>
          <div class="hint" id="hl-origin" style="margin-bottom:6px"></div>
          <div class="field"><label>scribe model (local, better words + speakers)</label>
            <select id="hl-model">
              <option value="base" selected>base — quick</option>
              <option value="small">small — better</option>
              <option value="large-v3-turbo">large-v3-turbo — best (1.6 GB)</option>
            </select>
          </div>
          <button class="btn" id="hl-transcribe">Upgrade with Scribe</button>
        </div>

        <div class="insp-sec" id="hl-detectsec" style="display:none">
          <span class="tag">find the moments</span>
          <div class="field"><label>reel length target</label>
            <select id="hl-target">
              <option value="30">~30 seconds</option>
              <option value="60">~1 minute</option>
              <option value="90" selected>~90 seconds</option>
              <option value="180">~3 minutes</option>
              <option value="300">~5 minutes</option>
            </select>
          </div>
          <div class="field"><label>your keywords (optional, comma-separated)</label>
            <input type="text" id="hl-keywords" placeholder="crosswalk, zoning, override" spellcheck="false">
          </div>
          <div class="checkrow"><input type="checkbox" id="hl-energy" checked>
            <span>listen for room energy <div class="hint">applause and raised voices score higher</div></span>
          </div>
          <button class="btn primary" id="hl-detect" style="margin-top:10px">Find the moments</button>
          <div class="prog"><i id="hl-detectbar"></i></div>
          <div class="progmsg" id="hl-detectmsg"></div>
        </div>

        <div class="insp-sec" id="hl-reelsec" style="display:none">
          <span class="tag">the reel — kept paragraphs</span>
          <div class="hint" id="hl-reelmeta" style="margin-bottom:6px">nothing kept yet</div>
          <div class="field studio-only"><label>render preset</label>
            <select id="hl-preset">
              <option value="h264" selected>H.264 — social/web</option>
              <option value="prores-422">ProRes 422 — edit master</option>
              <option value="hevc">HEVC — half the size</option>
            </select>
          </div>
          <button class="btn primary" id="hl-render" disabled>Render reel</button>
          <button class="btn" id="hl-edl" disabled>Export selects EDL</button>
          <div class="prog"><i id="hl-reelbar"></i></div>
          <div class="progmsg" id="hl-reelmsg"></div>
        </div>

        <div class="report" id="hl-report"></div>
      </div>
    </div>
  </div>`;

  const S = { path: null, clip: null, t: null, words: [], curWord: -1,
              keep: new Set(), lane: [], picks: [], reasons: new Map() };
  const audio = new Audio();
  let viewer, raf = null;

  /* ---------- yt-dlp chip (the page-open covenant) ---------- */
  async function ytdlpCheck() {
    const chip = $("#hl-ytdlp", el);
    try {
      let st = (await api("/api/highlighter/ytdlp-check", {})).ytdlp;
      chip.textContent = "yt-dlp " + (st.phase === "ok" ? (st.installed || "ready")
        : st.phase === "error" ? "offline" : "checking…");
      const until = Date.now() + 90000;
      while (["checking", "updating"].includes(st.phase) && Date.now() < until) {
        await new Promise(r => setTimeout(r, 900));
        st = (await api("/api/highlighter/status")).ytdlp;
        chip.textContent = "yt-dlp " + (st.phase === "updating" ? "updating…" : "checking…");
      }
      const ok = st.phase === "ok" || st.present;
      chip.textContent = "yt-dlp " + (st.installed ? `nightly ${st.installed}` : "missing");
      chip.classList.toggle("ok", ok);
      chip.classList.toggle("err", !ok);
      chip.title = st.detail || chip.title;
    } catch (e) { chip.textContent = "yt-dlp ?"; }
  }

  /* ---------- library ---------- */
  async function loadLibrary() {
    const box = $("#hl-library", el);
    try {
      const rows = await api("/api/highlighter/library");
      if (!rows.length) {
        box.innerHTML = `<div class="hint">nothing fetched yet — paste a URL above</div>`;
        return;
      }
      box.innerHTML = rows.slice(0, 8).map(r => `
        <button class="lib-row" data-path="${esc(r.path)}" title="${esc(r.title || r.name)}">
          <span class="lname">${esc(r.title || r.name)}</span>
          <span class="lmeta">${r.duration ? fmtTime(r.duration) : ""}
            ${r.transcript ? "· words" : r.captions ? "· captions" : ""}
            ${r.highlights ? "· ★" : ""}</span>
        </button>`).join("");
      $$(".lib-row", box).forEach(b => b.onclick = () => open(b.dataset.path));
    } catch (e) { box.innerHTML = `<div class="hint">${esc(e.message)}</div>`; }
  }

  /* ---------- transcript surface ---------- */
  function keptRanges(pad = 0.3) {
    if (!S.t) return [];
    const idx = [...S.keep].sort((a, b) => a - b);
    const out = [];
    for (const i of idx) {
      const s = S.t.segments[i];
      if (!s) continue;
      const a = Math.max(0, s.start - pad), b = s.end + pad;
      if (out.length && a <= out[out.length - 1].end + 0.8) {
        out[out.length - 1].end = Math.max(out[out.length - 1].end, b);
      } else {
        out.push({ start: a, end: b, label: (s.text || "").slice(0, 40) });
      }
    }
    return out;
  }

  function updateReelMeta() {
    const ranges = keptRanges();
    const total = ranges.reduce((a, r) => a + (r.end - r.start), 0);
    $("#hl-reelmeta", el).textContent = ranges.length
      ? `${S.keep.size} paragraphs → ${ranges.length} cuts · ${total.toFixed(0)}s`
      : "nothing kept yet — click ✓ on a paragraph, or Find the moments";
    $("#hl-keptmeta", el).textContent = ranges.length
      ? `reel: ${ranges.length} cuts · ${total.toFixed(0)}s` : "";
    $("#hl-render", el).disabled = !ranges.length;
    $("#hl-edl", el).disabled = !ranges.length;
    drawLane();
  }

  function renderTranscript() {
    const box = $("#hl-transcript", el);
    S.words = []; S.curWord = -1;
    if (!S.t || !S.t.segments.length) {
      box.innerHTML = `<div class="empty-grain" style="padding:36px 8px;color:var(--cream-faint);text-align:center">
        no words yet — captions weren't found, so run the Scribe pass on the right</div>`;
      return;
    }
    let wi = 0;
    box.innerHTML = S.t.segments.map((seg, si) => {
      const kept = S.keep.has(si);
      const reason = S.reasons.get(si);
      const score = reason ? reason.score : 0;
      let words;
      if (seg.words && seg.words.length) {
        words = seg.words.map(w => {
          S.words.push({ ...w, si });
          return `<span class="sw" data-wi="${wi++}" data-s="${w.s}" data-e="${w.e}">${esc(w.w)}</span>`;
        }).join(" ");
      } else {
        words = esc(seg.text);
      }
      return `<div class="hl-seg${kept ? " kept" : ""}" data-si="${si}"
          style="${score ? `--hlscore:${score}` : ""}">
        <button class="keepbtn" data-si="${si}" title="${kept ? "drop from reel" : "keep in reel"}">${kept ? "✓" : "+"}</button>
        <span class="hl-time">${fmtTime(seg.start)}</span>
        ${seg.speaker ? `<span class="hl-spk">${esc(seg.speaker)}</span>` : ""}
        <span class="hl-text">${words}</span>
        ${reason && reason.reasons.length ? `<span class="hl-why" title="${esc(reason.reasons.join(" · "))}">why</span>` : ""}
      </div>`;
    }).join("");
    $$(".sw", box).forEach(sp => sp.onclick = () => {
      audio.currentTime = parseFloat(sp.dataset.s);
      syncFrame(true);
    });
    $$(".keepbtn", box).forEach(b => b.onclick = () => {
      const si = +b.dataset.si;
      S.keep.has(si) ? S.keep.delete(si) : S.keep.add(si);
      const seg = $(`.hl-seg[data-si="${si}"]`, box);
      seg.classList.toggle("kept", S.keep.has(si));
      b.textContent = S.keep.has(si) ? "✓" : "+";
      updateReelMeta();
    });
    $$(".hl-time", box).forEach((t, k) => t.onclick = () => {
      audio.currentTime = S.t.segments[k].start;
      syncFrame(true);
    });
    updateReelMeta();
  }

  /* ---------- score lane ---------- */
  function drawLane() {
    const c = $("#hl-lanecanvas", el);
    const w = c.clientWidth || c.parentElement.clientWidth || 800;
    c.width = w * devicePixelRatio;
    c.height = 46 * devicePixelRatio;
    const g = c.getContext("2d");
    g.fillStyle = "#0D0D12";
    g.fillRect(0, 0, c.width, c.height);
    const dur = S.clip ? S.clip.nFrames / S.clip.fps
      : (S.t && S.t.segments.length ? S.t.segments[S.t.segments.length - 1].end : 0);
    if (!dur) return;
    const X = t => t / dur * c.width;
    /* scores are measurements — amber, per the covenant */
    for (const s of S.lane) {
      const h = Math.max(2, s.score * 30) * devicePixelRatio;
      g.fillStyle = "rgba(229,168,53,.7)";
      g.fillRect(X(s.start), c.height - h, Math.max(1, X(s.end) - X(s.start)), h);
    }
    for (const r of keptRanges()) {
      g.fillStyle = "rgba(168,181,75,.30)";
      g.fillRect(X(r.start), 0, Math.max(2, X(r.end) - X(r.start)), c.height);
    }
    if (audio.duration) {
      g.fillStyle = "#F5F3EE";
      g.fillRect(X(audio.currentTime), 0, 2, c.height);
    }
  }

  /* ---------- playback sync (scribe's pattern) ---------- */
  function wordAt(t) {
    let lo = 0, hi = S.words.length - 1, best = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (S.words[mid].s <= t) { best = mid; lo = mid + 1; } else hi = mid - 1;
    }
    return best >= 0 && t <= S.words[best].e + 0.35 ? best : -1;
  }
  function syncFrame(force) {
    if (!S.clip) return;
    const i = Math.min(Math.round(audio.currentTime * S.clip.fps), S.clip.nFrames - 1);
    if (force || viewer.i !== i) viewer.show(i);
  }
  function tick() {
    $("#hl-time", el).textContent = fmtTime(audio.currentTime);
    syncFrame(false);
    const wi = wordAt(audio.currentTime);
    if (wi !== S.curWord) {
      const box = $("#hl-transcript", el);
      const prev = $(".sw.cur", box);
      if (prev) prev.classList.remove("cur");
      if (wi >= 0) {
        const sp = $(`.sw[data-wi="${wi}"]`, box);
        if (sp) { sp.classList.add("cur"); if (!audio.paused) sp.scrollIntoView({ block: "nearest" }); }
      }
      S.curWord = wi;
    }
    drawLane();
    if (!audio.paused) raf = requestAnimationFrame(tick);
  }

  /* ---------- open / fetch / detect / render ---------- */
  async function open(path) {
    try {
      const r = await api("/api/media/open", { path, tool: "highlighter" });
      S.path = r.path;
      $("#hl-name", el).innerHTML = `<b>${esc(r.name)}</b>`;
      const v = r.video;
      if (v) {
        S.clip = { path: r.path, nFrames: v.n_frames_estimate || 1, fps: v.fps };
        viewer.setClip(S.clip);
      } else { S.clip = null; viewer.setClip(null); }
      audio.src = `/api/scribe/audio?path=${encodeURIComponent(r.path)}`;
      $("#hl-play", el).disabled = !r.audio_streams;
      S.keep = new Set(); S.lane = []; S.picks = []; S.reasons = new Map(); S.t = null;
      $("#hl-readsec", el).style.display = "";
      $("#hl-detectsec", el).style.display = "";
      $("#hl-reelsec", el).style.display = "";
      const tr = await api("/api/highlighter/transcript", { path: r.path });
      applyTranscript(tr);
    } catch (e) { toast(e.message, true); }
  }

  function applyTranscript(tr) {
    S.t = tr.transcript;
    const origin = $("#hl-origin", el);
    origin.textContent = !S.t
      ? "no words yet — no captions came with this file"
      : tr.origin === "captions"
        ? "words from YouTube captions — instant and free; Scribe hears it better"
        : "words from Scribe — local model, word-accurate";
    if (tr.highlights) {
      S.lane = tr.highlights.lane || [];
      applyPicks(tr.highlights.picks || []);
      $("#hl-detectmsg", el).textContent =
        `${(tr.highlights.picks || []).length} moments marked last time`;
    }
    renderTranscript();
    drawLane();
  }

  function applyPicks(picks) {
    if (!S.t) return;
    S.picks = picks;
    S.reasons = new Map();
    S.keep = new Set();
    S.t.segments.forEach((seg, si) => {
      const mid = (seg.start + seg.end) / 2;
      const hit = picks.find(p => mid >= p.start && mid <= p.end);
      if (hit) {
        S.keep.add(si);
        S.reasons.set(si, { score: hit.score, reasons: hit.reasons || [] });
      }
    });
  }

  async function fetchURL() {
    const url = $("#hl-url", el).value.trim();
    if (!url) { toast("paste a URL first", true); return; }
    const btn = $("#hl-fetch", el);
    btn.disabled = true;
    try {
      const job = await api("/api/highlighter/fetch",
        { url, quality: $("#hl-quality", el).value });
      toast("fetching — watch the queue chip; it lands in the library");
      watchJob(job.id, j => {
        $("#hl-detectmsg", el).textContent = j.message || j.status;
      });
      const done = await jobDone(job.id);
      btn.disabled = false;
      if (done.status === "done") {
        $("#hl-url", el).value = "";
        await loadLibrary();
        open(done.result.path);
        toast(done.result.captions
          ? "fetched — captions came along, the words are already here"
          : "fetched — no captions on this one; run the Scribe pass");
      } else if (done.status === "error") { toast(done.error, true); }
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  async function transcribe() {
    if (!S.path) return;
    const btn = $("#hl-transcribe", el);
    btn.disabled = true;
    try {
      const job = await api("/api/scribe/transcribe", {
        path: S.path, model: $("#hl-model", el).value, diarize: true,
      });
      watchJob(job.id, j => {
        $("#hl-origin", el).textContent = j.message || j.status;
      });
      const done = await jobDone(job.id);
      btn.disabled = false;
      if (done.status === "error") { toast(done.error, true); return; }
      if (done.status === "done") {
        const tr = await api("/api/highlighter/transcript", { path: S.path });
        applyTranscript(tr);
        toast("Scribe pass done — speakers and word timing upgraded");
      }
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  async function detect() {
    if (!S.path) return;
    const btn = $("#hl-detect", el);
    btn.disabled = true;
    $("#hl-detectbar", el).style.width = "8%";
    try {
      const job = await api("/api/highlighter/detect", {
        path: S.path,
        target: parseFloat($("#hl-target", el).value),
        keywords: $("#hl-keywords", el).value,
        energy: $("#hl-energy", el).checked,
      });
      watchJob(job.id, j => {
        $("#hl-detectmsg", el).textContent = j.message || j.status;
        $("#hl-detectbar", el).style.width = j.status === "running" ? "55%" : "8%";
      });
      const done = await jobDone(job.id);
      btn.disabled = false;
      $("#hl-detectbar", el).style.width = done.status === "done" ? "100%" : "0";
      if (done.status === "error") {
        $("#hl-detectmsg", el).textContent = done.error;
        $("#hl-detectmsg", el).classList.add("err");
        return;
      }
      if (done.status !== "done") return;
      $("#hl-detectmsg", el).classList.remove("err");
      S.lane = done.result.lane || [];
      applyPicks(done.result.picks || []);
      renderTranscript();
      toast(`${done.result.picks.length} moments marked — every one says why`);
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  async function renderReel() {
    const ranges = keptRanges();
    if (!ranges.length) return;
    const btn = $("#hl-render", el);
    btn.disabled = true;
    try {
      const job = await api("/api/highlighter/reel", {
        path: S.path, ranges, preset: $("#hl-preset", el).value,
      });
      watchJob(job.id, j => {
        $("#hl-reelmsg", el).textContent = j.message || j.status;
        $("#hl-reelbar", el).style.width = `${Math.max(0, j.progress) * 100}%`;
      });
      const done = await jobDone(job.id);
      btn.disabled = false;
      if (done.status === "done") {
        const rep = $("#hl-report", el);
        rep.classList.add("show");
        rep.innerHTML += `<b>→</b> ${esc(done.result.out)}\n   ${done.result.clips} cuts · ${done.result.duration}s · ${esc(done.result.encoder)}\n`;
        toast("reel rendered");
      } else if (done.status === "error") { toast(done.error, true); }
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  async function exportEDL() {
    const ranges = keptRanges();
    if (!ranges.length) return;
    try {
      const r = await api("/api/scribe/selects", {
        path: S.path,
        selects: ranges.map(x => ({ start: x.start, end: x.end, label: x.label })),
        handles: 0.5,
      });
      const rep = $("#hl-report", el);
      rep.classList.add("show");
      rep.innerHTML += `<b>→</b> ${esc(r.out)}\n   ${r.selects} events · ${esc(r.note)}\n`;
    } catch (e) { toast(e.message, true); }
  }

  /* ---------- wire up ---------- */
  function init() {
    viewer = new Viewer($("#hl-viewer", el), { h: 360 });
    $("#hl-fetch", el).onclick = fetchURL;
    $("#hl-url", el).addEventListener("keydown", e => { if (e.key === "Enter") fetchURL(); });
    $("#hl-localpath", el).addEventListener("keydown", e => {
      if (e.key === "Enter") { const p = e.target.value.trim(); if (p) open(p); }
    });
    $("#hl-play", el).onclick = () => { audio.paused ? audio.play() : audio.pause(); };
    audio.addEventListener("play", () => { $("#hl-play", el).textContent = "⏸"; raf = requestAnimationFrame(tick); });
    audio.addEventListener("pause", () => { $("#hl-play", el).textContent = "▶"; if (raf) cancelAnimationFrame(raf); tick(); });
    audio.addEventListener("seeked", () => tick());
    $("#hl-transcribe", el).onclick = transcribe;
    $("#hl-detect", el).onclick = detect;
    $("#hl-render", el).onclick = renderReel;
    $("#hl-edl", el).onclick = exportEDL;

    const insp = $("#hl-insp", el);
    const dens = $$(".density button", insp);
    function applyDensity(d) {
      insp.classList.toggle("studio", d === "studio");
      dens.forEach(b => b.classList.toggle("on", b.dataset.d === d));
    }
    dens.forEach(b => b.onclick = () => { applyDensity(b.dataset.d); setDensity("highlighter", b.dataset.d); });
    applyDensity(density("highlighter"));

    new MutationObserver(() => { if (!el.classList.contains("active")) stop(); })
      .observe(el, { attributes: true, attributeFilter: ["class"] });
    addEventListener("resize", () => { if (CZ.current === "highlighter") drawLane(); });
  }

  function stop() {
    audio.pause();
    if (raf) { cancelAnimationFrame(raf); raf = null; }
  }

  let inited = false;
  function onshow(arg) {
    if (!inited) { init(); inited = true; }
    Viewer.active = null;   // the audio element owns the clock here
    ytdlpCheck();           // every open — that's the deal, and the chip shows it
    loadLibrary();
    if (arg && arg.openPath) open(arg.openPath);
    if (viewer) viewer.resize();
    drawLane();
  }

  registerPage("highlighter", el, onshow);
  return { onshow };
})();
