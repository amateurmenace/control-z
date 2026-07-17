/* Community Highlighter — the web app's shape, the suite's local engine.

   Landing: paste a URL (or drop/browse a local clip) → the meeting is READ
   before any video moves: captions seed the transcript, the brief/entities/
   questions come from insight.py, and preview plays through a YouTube embed.
   Three sections, like the web app: Highlight · Edit · Analyze.
   Downloads are smart — the whole recording, or only the kept sections.
   Every AI-shaped card says which kind of local reading it got: the brief is
   extractive, ask is retrieval. Nothing leaves the machine but the fetch. */

const HighlighterPage = (() => {
  const T = toolById("highlighter");
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-highlighter";

  const REEL_STYLES = [
    ["decisions", "Decisions", "motion,vote,approved,carries,unanimous,adopted,resolution"],
    ["comments", "Public comment", "public comment,resident,neighbor,petition,speak"],
    ["controversial", "Controversial", "oppose,concern,disagree,objection,problem,frustrated,unacceptable"],
    ["budget", "Budget", "budget,million,thousand,funding,dollar,tax,cost,fee"],
    ["actions", "Actions", "next steps,follow up,action item,directed,will bring,report back"],
    ["everything", "Everything", ""],
  ];

  el.innerHTML = `
  <div class="ws" style="--acc:${T.acc}">
    <div class="mediabar">
      <span class="toolname"><i>Community Highlighter</i> · finds the moments</span>
      <span class="clipmeta" id="hl-title" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"></span>
      <button class="btn" style="width:auto;display:none" id="hl-back">← meetings</button>
      <span class="ytdlp-chip" id="hl-ytdlp" title="the fetch engine — nightly build, checked on every open">yt-dlp —</span>
    </div>

    <!-- ================= LANDING ================= -->
    <div id="hl-landing" style="overflow-y:auto;flex:1">
      <div style="padding:22px 24px;max-width:1100px">
        <div class="hl-hero">
          <div class="tag">community highlighter · via BIG</div>
          <h1 style="margin-top:6px">Turn long public meetings into
            <span class="mark">useful moments</span> in minutes.</h1>
          <p style="color:var(--cream-dim);margin-top:6px;font-size:13.5px">
            Every resident deserves to know what was decided and why. Paste a link —
            the meeting becomes readable before a single frame downloads.</p>
          <div class="hl-urlrow">
            <input type="text" id="hl-url" placeholder="Paste a YouTube / meeting URL here" spellcheck="false">
            <button class="btn cta" id="hl-load">Load Meeting</button>
          </div>
          <div style="display:flex;gap:12px;align-items:center;margin-top:12px;flex-wrap:wrap">
            <div id="hl-drop" style="flex:1;min-width:260px;border:2px dashed var(--line);border-radius:10px;
                 padding:13px 16px;text-align:center;color:var(--cream-dim);font-size:12.5px">
              …or drag a local clip here
              <button class="browse-btn" id="hl-browse" style="margin:0 0 0 10px;padding:5px 16px">Browse…</button>
            </div>
          </div>
        </div>

        <div class="hl-cards">
          <div class="hl-card"><h2><span class="nub" style="background:var(--hl-cta)"></span>Search &amp; Highlight</h2>
            <p>Search every word said. The brief, the entities, and the marked moments
              come from the transcript itself — extractive and time-stamped, with reasons.</p></div>
          <div class="hl-card"><h2><span class="nub" style="background:var(--highlighter)"></span>Edit</h2>
            <p>Kept moments land on a timeline: reorder, trim, preview, then render the
              reel locally — or download only those sections of the video.</p></div>
          <div class="hl-card"><h2><span class="nub" style="background:var(--grabber)"></span>Analyze &amp; Discover</h2>
            <p>Decisions with outcomes, who spoke, question flow, topics, money.
              Everything clickable, everything sourced to its moment.</p></div>
        </div>

        <div class="hl-panel" style="margin-top:18px">
          <span class="tag">civic meeting finder</span>
          <div class="hl-searchrow">
            <input type="text" id="hl-findq" placeholder="town + board — “brookline select board”, “cambridge school committee”…" spellcheck="false">
            <button class="btn cta" id="hl-findgo" style="padding:8px 16px">Search</button>
          </div>
          <div id="hl-findout" class="hl-results"></div>
        </div>

        <div class="hl-panel" style="margin-top:14px">
          <span class="tag">your meetings</span>
          <div id="hl-library"><div class="hint">nothing yet — load a URL above, and it lands here readable</div></div>
        </div>
      </div>
    </div>

    <!-- ================= LOADED ================= -->
    <div id="hl-loaded" style="display:none;flex-direction:column;flex:1;min-height:0;overflow-y:auto">
      <div style="display:flex;gap:14px;padding:14px 20px 0;align-items:stretch;flex-wrap:wrap">
        <div style="flex:1.3;min-width:380px">
          <div id="hl-viewer" style="height:300px;position:relative;display:none;border-radius:10px;overflow:hidden"></div>
          <div class="hl-yt" id="hl-ytbox" style="display:none"><iframe id="hl-ytframe" allow="autoplay"></iframe></div>
          <div class="lane" style="padding:7px 10px;display:flex;align-items:center;gap:10px;background:none">
            <button class="btn" style="width:auto;padding:5px 15px" id="hl-play">▶</button>
            <span class="clipmeta" id="hl-time">0:00.0</span>
            <span class="clipmeta" id="hl-srcmode" style="margin-left:auto"></span>
          </div>
        </div>
        <div style="flex:1;min-width:320px" class="hl-panel">
          <span class="tag">executive brief — extractive, the meeting's own sentences</span>
          <div class="hl-brief" id="hl-brief"><div class="hint">reading…</div></div>
        </div>
      </div>

      <div class="hl-pills" id="hl-pills">
        <button class="hl-pill on" data-sec="highlight">Highlight</button>
        <button class="hl-pill" data-sec="edit">Edit</button>
        <button class="hl-pill" data-sec="analyze">Analyze</button>
        <span class="hl-meta-line" id="hl-metaline"></span>
      </div>

      <!-- HIGHLIGHT -->
      <div id="hl-sec-highlight">
        <div class="hl-grid">
          <div style="display:flex;flex-direction:column;gap:14px;min-width:0">
            <div class="hl-panel">
              <span class="tag">search every word</span>
              <div class="hl-searchrow">
                <input type="text" id="hl-q" placeholder="crosswalk, override, a name…" spellcheck="false">
              </div>
              <div class="hl-spark"><canvas id="hl-sparkline"></canvas></div>
              <div class="hl-results" id="hl-qout"></div>
            </div>
            <div class="hl-panel">
              <span class="tag">transcript — click ✓ to keep a moment for the reel</span>
              <div class="hl-transcript" id="hl-transcript">
                <div class="empty-grain" style="padding:30px 8px;color:var(--cream-faint);text-align:center">no words yet</div>
              </div>
              <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">
                <button class="btn" id="hl-transcribe" style="width:auto">Upgrade words with Scribe</button>
                <select id="hl-model" style="background:#fff;border:1px solid var(--line);border-radius:7px;padding:5px 8px;font-size:12px">
                  <option value="base" selected>base — quick</option>
                  <option value="small">small — better</option>
                  <option value="large-v3-turbo">large-v3-turbo — best</option>
                </select>
                <button class="btn" id="hl-txt" style="width:auto">Transcript .txt</button>
                <button class="btn" id="hl-srt" style="width:auto">.srt</button>
                <button class="btn" id="hl-gtranslate" style="width:auto"
                  title="copies the transcript, opens Google Translate — the honest free path for any language">Google Translate…</button>
              </div>
            </div>
          </div>
          <div style="display:flex;flex-direction:column;gap:14px;min-width:0">
            <div class="hl-panel">
              <span class="tag">the moments <span id="hl-origin" style="text-transform:none;letter-spacing:0"></span></span>
              <div class="hl-styles" id="hl-stylerow" style="margin-bottom:8px"></div>
              <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px">
                <select id="hl-target" style="background:#fff;border:1px solid var(--line);border-radius:7px;padding:5px 8px;font-size:12px">
                  <option value="60">~1 minute</option>
                  <option value="90" selected>~90 seconds</option>
                  <option value="180">~3 minutes</option>
                  <option value="300">~5 minutes</option>
                </select>
                <button class="btn cta bright" id="hl-detect" style="flex:1">Make Highlights</button>
              </div>
              <div class="progmsg" id="hl-detectmsg"></div>
              <div class="hl-hilist" id="hl-hilist"><div class="hint">pick a style and Make Highlights —
                every pick will say why it was chosen</div></div>
            </div>
            <div class="hl-panel">
              <span class="tag">word cloud</span>
              <div class="hl-cloud" id="hl-cloud"><div class="hint">reading…</div></div>
            </div>
            <div class="hl-panel">
              <span class="tag">ask the meeting — retrieval, points at what was said</span>
              <div class="hl-chat">
                <div class="hl-chatlog" id="hl-chatlog"></div>
                <div class="hl-suggest" id="hl-suggest"></div>
                <div class="hl-searchrow">
                  <input type="text" id="hl-askq" placeholder="What happened with the crosswalk?" spellcheck="false">
                  <button class="btn cta" id="hl-askgo" style="padding:8px 14px">Ask</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- EDIT -->
      <div id="hl-sec-edit" style="display:none">
        <div class="hl-nle">
          <div class="hl-toolrow">
            <span class="tag">the reel</span>
            <span class="clipcount" id="hl-clipcount">0 clips</span>
            <span style="flex:1"></span>
            <button class="btn" id="hl-prev">⏮</button>
            <button class="btn" id="hl-playreel">▶ Play reel</button>
            <button class="btn" id="hl-next">⏭</button>
            <button class="btn" id="hl-clear">Clear</button>
            <button class="btn cta" id="hl-export">Export reel</button>
            <button class="btn" id="hl-edl">Selects EDL</button>
          </div>
          <div class="hl-timeline" id="hl-timeline">
            <div class="hint" style="padding:20px;color:#8C9086">nothing on the timeline —
              Make Highlights, keep transcript moments, or + Add from the highlights list</div>
          </div>
          <div class="progmsg" id="hl-reelmsg" style="color:#B9BDB2"></div>
        </div>
        <div class="hl-grid" style="padding-top:0">
          <div class="hl-panel">
            <span class="tag">smart download — get only what you need</span>
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:4px">
              <select id="hl-quality" style="background:#fff;border:1px solid var(--line);border-radius:7px;padding:6px 8px;font-size:12px">
                <option value="1080" selected>1080p</option>
                <option value="720">720p</option>
                <option value="best">best</option>
              </select>
              <button class="btn" id="hl-dlfull" style="width:auto">Download full video</button>
              <button class="btn cta" id="hl-dlsections" style="width:auto">Download kept sections only</button>
            </div>
            <div class="hint" id="hl-dlhint" style="margin-top:6px"></div>
            <div class="progmsg" id="hl-dlmsg"></div>
          </div>
          <div class="hl-panel">
            <span class="tag">render</span>
            <div class="field"><label>preset</label>
              <select id="hl-preset">
                <option value="h264" selected>H.264 — social/web</option>
                <option value="prores-422">ProRes 422 — edit master</option>
                <option value="hevc">HEVC — half the size</option>
              </select>
            </div>
            <div class="hint">local file → the reel renders straight from it. URL session →
              download the kept sections first; they stitch into one reel.</div>
            <div class="report" id="hl-report"></div>
          </div>
        </div>
      </div>

      <!-- ANALYZE -->
      <div id="hl-sec-analyze" style="display:none">
        <div class="hl-ana" id="hl-ana"></div>
      </div>
    </div>
  </div>`;

  /* ---------------- state ---------------- */
  const S = {
    source: null, session: false, meta: null, clip: null,
    t: null, origin: null, lane: [], picks: [], keep: new Set(),
    timeline: [], curClip: -1, insight: null, ytReady: false,
    playTimer: null, words: [], curWord: -1,
  };
  const audio = new Audio();
  let viewer = null, raf = null;

  const ytId = () => (S.meta && S.meta.id) || (S.source || "").split("/").pop();

  /* ---------------- yt-dlp chip ---------------- */
  async function ytdlpCheck() {
    const chip = $("#hl-ytdlp", el);
    try {
      let st = (await api("/api/highlighter/ytdlp-check", {})).ytdlp;
      const until = Date.now() + 90000;
      while (["checking", "updating"].includes(st.phase) && Date.now() < until) {
        chip.textContent = "yt-dlp " + (st.phase === "updating" ? "updating…" : "checking…");
        await new Promise(r => setTimeout(r, 900));
        st = (await api("/api/highlighter/status")).ytdlp;
      }
      const ok = st.phase === "ok" || st.present;
      chip.textContent = "yt-dlp " + (st.installed ? `nightly ${st.installed}` : "missing");
      chip.classList.toggle("ok", ok);
      chip.classList.toggle("err", !ok);
      chip.title = st.detail || chip.title;
    } catch (e) { chip.textContent = "yt-dlp ?"; }
  }

  /* ---------------- landing: finder + library ---------------- */
  async function finder() {
    const box = $("#hl-findout", el);
    const q = $("#hl-findq", el).value.trim();
    if (!q) return;
    box.innerHTML = `<div class="hint" style="padding:8px 2px">searching…</div>`;
    try {
      const r = await api("/api/highlighter/finder", { q });
      box.innerHTML = r.rows.map(v => `
        <div class="hl-result" style="display:flex;gap:8px;align-items:baseline">
          <span style="flex:1">${esc(v.title || v.id)}
            <span style="color:var(--cream-faint);font-size:11px"> · ${esc(v.uploader || "")}
            ${v.duration ? " · " + fmtTime(v.duration) : ""}</span></span>
          <button class="btn cta" style="padding:3px 12px;font-size:11.5px" data-url="${esc(v.url)}">Load</button>
        </div>`).join("") || `<div class="hint">nothing found</div>`;
      $$("button[data-url]", box).forEach(b => b.onclick = () => ingest(b.dataset.url));
    } catch (e) { box.innerHTML = `<div class="progmsg err">${esc(e.message)}</div>`; }
  }

  async function loadLibrary() {
    const box = $("#hl-library", el);
    try {
      const r = await api("/api/highlighter/library");
      const meet = (r.meetings || []).map(m => `
        <button class="lib-row" data-src="${esc(m.source)}">
          <span class="lname">▸ ${esc(m.title)}</span>
          <span class="lmeta">${m.duration ? fmtTime(m.duration) : ""} ${m.transcript ? "· read" : ""} · URL session</span>
        </button>`).join("");
      const vids = (r.videos || []).map(v => `
        <button class="lib-row" data-src="${esc(v.path)}">
          <span class="lname">${esc(v.title || v.name)}</span>
          <span class="lmeta">${v.duration ? fmtTime(v.duration) : ""}
            ${v.transcript ? "· words" : v.captions ? "· captions" : ""}
            ${v.highlights ? "· ★" : ""} · local file</span>
        </button>`).join("");
      box.innerHTML = (meet + vids) ||
        `<div class="hint">nothing yet — load a URL above, and it lands here readable</div>`;
      $$(".lib-row", box).forEach(b => b.onclick = () => open(b.dataset.src));
    } catch (e) { box.innerHTML = `<div class="hint">${esc(e.message)}</div>`; }
  }

  /* ---------------- ingest / open ---------------- */
  async function ingest(url) {
    if (!url) return;
    const btn = $("#hl-load", el);
    btn.disabled = true;
    btn.textContent = "Reading…";
    try {
      const job = await api("/api/highlighter/ingest", { url });
      const done = await jobDone(job.id);
      btn.disabled = false;
      btn.textContent = "Load Meeting";
      if (done.status === "error") { toast(done.error, true); return; }
      if (done.status !== "done") return;
      $("#hl-url", el).value = "";
      if (done.result.captions_note) toast(done.result.captions_note, true);
      open(done.result.source);
    } catch (e) { btn.disabled = false; btn.textContent = "Load Meeting"; toast(e.message, true); }
  }

  async function open(source) {
    try {
      S.source = source;
      S.keep = new Set(); S.timeline = []; S.picks = []; S.lane = [];
      S.insight = null; S.curClip = -1;
      const tr = await api("/api/highlighter/transcript", { path: source });
      S.session = tr.session;
      S.meta = tr.meta;
      $("#hl-landing", el).style.display = "none";
      $("#hl-loaded", el).style.display = "flex";
      $("#hl-back", el).style.display = "";
      if (S.session) {
        S.clip = null;
        $("#hl-viewer", el).style.display = "none";
        $("#hl-ytbox", el).style.display = "";
        $("#hl-ytframe", el).src =
          `https://www.youtube.com/embed/${encodeURIComponent(ytId())}?enablejsapi=1`;
        $("#hl-srcmode", el).textContent = "streaming preview — nothing downloaded yet";
        $("#hl-title", el).textContent = S.meta?.title || "";
      } else {
        const r = await api("/api/media/open", { path: source, tool: "highlighter" });
        $("#hl-ytbox", el).style.display = "none";
        $("#hl-viewer", el).style.display = "";
        const v = r.video;
        S.clip = v ? { path: r.path, nFrames: v.n_frames_estimate || 1, fps: v.fps } : null;
        viewer.setClip(S.clip);
        audio.src = `/api/scribe/audio?path=${encodeURIComponent(r.path)}`;
        $("#hl-srcmode", el).textContent = "local file — everything works offline";
        $("#hl-title", el).textContent = r.name;
      }
      applyTranscript(tr);
      loadInsight();
      showSec("highlight");
    } catch (e) { toast(e.message, true); }
  }

  function backToLanding() {
    stop();
    $("#hl-ytframe", el).src = "";
    $("#hl-landing", el).style.display = "";
    $("#hl-loaded", el).style.display = "none";
    $("#hl-back", el).style.display = "none";
    $("#hl-title", el).textContent = "";
    S.source = null;
    loadLibrary();
  }

  /* ---------------- playback (two players, one clock) ---------------- */
  function seek(t, play) {
    if (S.session) {
      const f = $("#hl-ytframe", el);
      f.contentWindow.postMessage(JSON.stringify(
        { event: "command", func: "seekTo", args: [t, true] }), "*");
      if (play) f.contentWindow.postMessage(JSON.stringify(
        { event: "command", func: "playVideo", args: [] }), "*");
    } else {
      audio.currentTime = t;
      if (play) audio.play();
      syncFrame(true);
    }
  }
  function pause() {
    if (S.session) {
      $("#hl-ytframe", el).contentWindow.postMessage(JSON.stringify(
        { event: "command", func: "pauseVideo", args: [] }), "*");
    } else audio.pause();
  }
  function syncFrame(force) {
    if (!S.clip || !viewer) return;
    const i = Math.min(Math.round(audio.currentTime * S.clip.fps), S.clip.nFrames - 1);
    if (force || viewer.i !== i) viewer.show(i);
  }
  function tick() {
    $("#hl-time", el).textContent = fmtTime(audio.currentTime);
    syncFrame(false);
    drawSpark();
    if (!audio.paused) raf = requestAnimationFrame(tick);
  }

  /* ---------------- transcript ---------------- */
  function applyTranscript(tr) {
    S.t = tr.transcript;
    S.origin = tr.origin;
    $("#hl-origin", el).textContent = !S.t ? "· no words yet"
      : tr.origin === "captions" ? "· words from captions (instant); Scribe hears it better"
      : "· words from Scribe — local model";
    if (tr.highlights) {
      S.lane = tr.highlights.lane || [];
      applyPicks(tr.highlights.picks || [], false);
    }
    renderTranscript();
    renderHighlights();
    renderTimeline();
  }

  function renderTranscript() {
    const box = $("#hl-transcript", el);
    if (!S.t || !S.t.segments.length) {
      box.innerHTML = `<div class="empty-grain" style="padding:30px 8px;color:var(--cream-faint);text-align:center">
        no words yet — ${S.session ? "this URL had no captions; download it, then run Scribe"
                                   : "run the Scribe pass below"}</div>`;
      return;
    }
    const reasons = new Map();
    S.t.segments.forEach((seg, si) => {
      const mid = (seg.start + seg.end) / 2;
      const hit = S.picks.find(p => mid >= p.start && mid <= p.end);
      if (hit) reasons.set(si, hit);
    });
    box.innerHTML = S.t.segments.map((seg, si) => {
      const kept = S.keep.has(si);
      const hit = reasons.get(si);
      return `<div class="hl-seg${kept ? " kept" : ""}" data-si="${si}"
          style="${hit ? `--hlscore:${hit.score}` : ""}">
        <button class="keepbtn" data-si="${si}">${kept ? "✓" : "+"}</button>
        <span class="hl-time" data-t="${seg.start}">${fmtTime(seg.start)}</span>
        ${seg.speaker ? `<span class="hl-spk">${esc(seg.speaker)}</span>` : ""}
        <span class="hl-text">${esc(seg.text)}</span>
        ${hit && hit.reasons?.length ? `<span class="hl-why" title="${esc(hit.reasons.join(" · "))}">why</span>` : ""}
      </div>`;
    }).join("");
    $$(".keepbtn", box).forEach(b => b.onclick = () => toggleKeep(+b.dataset.si));
    $$(".hl-time", box).forEach(tEl => tEl.onclick = () => seek(+tEl.dataset.t, true));
    updateMetaLine();
  }

  function toggleKeep(si) {
    S.keep.has(si) ? S.keep.delete(si) : S.keep.add(si);
    const seg = S.t.segments[si];
    if (S.keep.has(si)) {
      addToTimeline({ start: Math.max(0, seg.start - 0.3), end: seg.end + 0.3,
                      label: (seg.text || "").slice(0, 60), si });
    } else {
      S.timeline = S.timeline.filter(c => c.si !== si);
      renderTimeline();
    }
    const row = $(`.hl-seg[data-si="${si}"]`, el);
    if (row) {
      row.classList.toggle("kept", S.keep.has(si));
      $(".keepbtn", row).textContent = S.keep.has(si) ? "✓" : "+";
    }
    updateMetaLine();
  }

  function updateMetaLine() {
    const total = S.timeline.reduce((a, c) => a + (c.end - c.start), 0);
    $("#hl-metaline", el).textContent = S.timeline.length
      ? `reel: ${S.timeline.length} clip${S.timeline.length === 1 ? "" : "s"} · ${total.toFixed(0)}s` : "";
    $("#hl-clipcount", el).textContent =
      `${S.timeline.length} clip${S.timeline.length === 1 ? "" : "s"} · ${total.toFixed(0)}s`;
    $("#hl-dlhint", el).textContent = S.session
      ? (S.timeline.length
        ? `kept sections = ${S.timeline.length} spans, ${total.toFixed(0)}s — a fraction of the meeting`
        : "keep moments first, then download only those spans")
      : "this source is already local — downloads are for URL sessions";
  }

  /* ---------------- insight (brief, cloud, analyze) ---------------- */
  async function loadInsight() {
    $("#hl-brief", el).innerHTML = `<div class="hint">reading…</div>`;
    $("#hl-cloud", el).innerHTML = `<div class="hint">reading…</div>`;
    try {
      S.insight = await api("/api/highlighter/insight", { path: S.source });
    } catch (e) {
      $("#hl-brief", el).innerHTML = `<div class="hint">${esc(e.message)}</div>`;
      $("#hl-cloud", el).innerHTML = "";
      $("#hl-ana", el).innerHTML = `<div class="hint" style="padding:0 2px">${esc(e.message)}</div>`;
      renderSuggestions([]);
      return;
    }
    const b = S.insight.brief || [];
    $("#hl-brief", el).innerHTML = b.length
      ? b.map(x => `<p><span class="tpill" data-t="${x.t}">${fmtTime(x.t)}</span>${esc(x.text)}</p>`).join("")
      : `<div class="hint">not enough words for a brief yet</div>`;
    $$("#hl-brief .tpill", el).forEach(p => p.onclick = () => seek(+p.dataset.t, true));
    const wf = S.insight.wordfreq || [];
    const maxc = Math.max(...wf.map(w => w.count), 1);
    $("#hl-cloud", el).innerHTML = wf.length ? wf.map((w, i) =>
      `<button style="font-size:${(11 + 15 * Math.sqrt(w.count / maxc)).toFixed(1)}px"
        class="${i < 3 ? "hot" : ""}" data-w="${esc(w.word)}">${esc(w.word)}</button>`).join(" ")
      : `<div class="hint">no words yet</div>`;
    $$("#hl-cloud button", el).forEach(btn => btn.onclick = () => {
      $("#hl-q", el).value = btn.dataset.w;
      searchTranscript();
    });
    renderSuggestions((S.insight.topics || []).slice(0, 3)
      .map(t => `What was said about ${t.topic}?`));
    renderAnalyze();
  }

  function renderAnalyze() {
    const box = $("#hl-ana", el);
    if (!S.insight) { box.innerHTML = ""; return; }
    const I = S.insight;
    const pill = t => `<span class="tpill" data-t="${t}">${fmtTime(t)}</span>`;
    const ent = I.entities || {};
    const entCard = (title, rows) => `
      <div class="hl-panel"><span class="tag">${title}</span>
        ${(rows || []).map(r => `<div class="hl-entrow">${pill(r.t)}
          <span>${esc(r.name)}</span><span class="cnt">×${r.count}</span></div>`).join("")
        || `<div class="hint">none found</div>`}</div>`;
    const maxTalk = Math.max(...(I.participation || []).map(p => p.seconds), 1);
    box.innerHTML = `
      <div class="hl-panel"><span class="tag">decisions — motions and outcomes</span>
        ${(I.decisions || []).map(d => `<div class="hl-qrow">
          <span class="hl-outcome ${d.outcome}">${d.outcome}</span>${pill(d.t)}
          ${esc(d.text)}</div>`).join("") || `<div class="hint">no motions detected</div>`}
      </div>
      ${entCard("people", ent.people)}
      ${entCard("places", ent.places)}
      ${entCard("organizations", ent.organizations)}
      ${entCard("money", ent.money)}
      <div class="hl-panel"><span class="tag">who spoke — needs the Scribe pass</span>
        ${(I.participation || []).map(p => `<div class="hl-entrow">
          <span style="flex:0 0 110px;overflow:hidden;text-overflow:ellipsis">${esc(p.speaker)}</span>
          <span class="hl-bar" style="width:${(p.seconds / maxTalk * 100).toFixed(0)}%"></span>
          <span class="cnt">${fmtTime(p.seconds)} · ${p.turns} turns</span></div>`).join("")
        || `<div class="hint">no speaker labels — run the Scribe pass with speakers on</div>`}
      </div>
      <div class="hl-panel"><span class="tag">question flow</span>
        ${(I.questions || []).map(q => `<div class="hl-qrow">
          <span class="hl-qtype">${q.type}</span>${pill(q.t)}${esc(q.text)}</div>`).join("")
        || `<div class="hint">no questions detected</div>`}
      </div>
      <div class="hl-panel"><span class="tag">recurring topics</span>
        ${(I.topics || []).map(t => `<div class="hl-entrow">${pill(t.t)}
          <span>${esc(t.topic)}</span><span class="cnt">×${t.count}</span></div>`).join("")
        || `<div class="hint">nothing recurred enough</div>`}
      </div>`;
    $$("#hl-ana .tpill", box).forEach(p => p.onclick = () => seek(+p.dataset.t, true));
  }

  /* ---------------- search + sparkline ---------------- */
  function searchTranscript() {
    const q = $("#hl-q", el).value.trim().toLowerCase();
    const out = $("#hl-qout", el);
    drawSpark();
    if (!q || !S.t) { out.innerHTML = ""; return; }
    const hits = [];
    S.t.segments.forEach(s => {
      const low = (s.text || "").toLowerCase();
      if (low.includes(q)) hits.push(s);
    });
    out.innerHTML = hits.slice(0, 40).map(s => `
      <div class="hl-result"><span class="tpill" data-t="${s.start}">${fmtTime(s.start)}</span>
        ${esc(s.text).replace(new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "ig"),
                              m => `<em>${m}</em>`)}</div>`).join("")
      || `<div class="hint" style="padding:6px 2px">no matches — the cloud shows the words that ARE here</div>`;
    $$(".tpill", out).forEach(p => p.onclick = () => seek(+p.dataset.t, true));
  }

  function drawSpark() {
    const c = $("#hl-sparkline", el);
    if (!c || !c.clientWidth) return;
    c.width = c.clientWidth * devicePixelRatio;
    c.height = 44 * devicePixelRatio;
    const g = c.getContext("2d");
    g.clearRect(0, 0, c.width, c.height);
    g.fillStyle = "rgba(0,0,0,.05)";
    g.fillRect(0, 0, c.width, c.height);
    if (!S.t || !S.t.segments.length) return;
    const dur = S.t.segments[S.t.segments.length - 1].end || 1;
    const q = $("#hl-q", el).value.trim().toLowerCase();
    const bins = new Float32Array(50);
    S.t.segments.forEach(s => {
      const w = q ? ((s.text || "").toLowerCase().split(q).length - 1)
                  : (S.lane.find(l => l.start === s.start)?.score || 0);
      if (w > 0) bins[Math.min(49, s.start / dur * 50 | 0)] += w;
    });
    const mx = Math.max(...bins, 0.001);
    const bw = c.width / 50;
    g.fillStyle = q ? "rgba(34,197,94,.85)" : "rgba(169,122,22,.7)";
    for (let b = 0; b < 50; b++) {
      const h = bins[b] / mx * (c.height - 6);
      if (h > 0) g.fillRect(b * bw + 1, c.height - h, bw - 2, h);
    }
    if (!S.session && audio.duration) {
      g.fillStyle = "#23261D";
      g.fillRect(audio.currentTime / dur * c.width, 0, 2, c.height);
    }
  }

  /* ---------------- highlights + picks ---------------- */
  function styleKeywords() {
    return $(".hl-styles .chip.on", el)?.dataset.k || "";
  }

  async function detect() {
    if (!S.source) return;
    const btn = $("#hl-detect", el);
    btn.disabled = true;
    try {
      const job = await api("/api/highlighter/detect", {
        path: S.source, target: parseFloat($("#hl-target", el).value),
        keywords: styleKeywords(), energy: !S.session,
      });
      watchJob(job.id, j => { $("#hl-detectmsg", el).textContent = j.message || j.status; });
      const done = await jobDone(job.id);
      btn.disabled = false;
      if (done.status === "error") { $("#hl-detectmsg", el).textContent = done.error; return; }
      if (done.status !== "done") return;
      S.lane = done.result.lane || [];
      applyPicks(done.result.picks || [], true);
      renderTranscript();
      renderHighlights();
      drawSpark();
      toast(`${done.result.picks.length} moments — top 5 are on the timeline, each says why`);
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  function applyPicks(picks, autoload) {
    S.picks = picks;
    if (autoload) {
      S.timeline = [];
      S.keep = new Set();
      picks.slice(0, 5).forEach(p => addToTimeline({
        start: p.start, end: p.end,
        label: (p.text || p.reasons?.[0] || "moment").slice(0, 60) }, true));
    }
    renderTimeline();
  }

  function renderHighlights() {
    const box = $("#hl-hilist", el);
    if (!S.picks.length) {
      box.innerHTML = `<div class="hint">pick a style and Make Highlights —
        every pick will say why it was chosen</div>`;
      return;
    }
    box.innerHTML = S.picks.map((p, k) => {
      const inTl = S.timeline.some(c => Math.abs(c.start - p.start) < 0.5);
      return `<div class="hl-hirow">
        <span class="tpill" data-t="${p.start}">${fmtTime(p.start)}</span>
        <span style="flex:1">${esc((p.text || "").slice(0, 90))}
          <span class="hl-why" title="${esc((p.reasons || []).join(" · "))}">why</span></span>
        <button class="add${inTl ? " in" : ""}" data-k="${k}">${inTl ? "✓ in reel" : "+ Add"}</button>
      </div>`;
    }).join("");
    $$(".tpill", box).forEach(p => p.onclick = () => seek(+p.dataset.t, true));
    $$("button.add", box).forEach(b => b.onclick = () => {
      const p = S.picks[+b.dataset.k];
      const inTl = S.timeline.some(c => Math.abs(c.start - p.start) < 0.5);
      if (inTl) S.timeline = S.timeline.filter(c => Math.abs(c.start - p.start) >= 0.5);
      else addToTimeline({ start: p.start, end: p.end, label: (p.text || "").slice(0, 60) }, true);
      renderTimeline();
      renderHighlights();
    });
  }

  /* ---------------- timeline (the dark NLE strip) ---------------- */
  function addToTimeline(clip, silent) {
    S.timeline.push({ ...clip });
    S.timeline.sort((a, b) => a.start - b.start);
    if (!silent) renderTimeline();
    else updateMetaLine();
  }

  function renderTimeline() {
    const box = $("#hl-timeline", el);
    if (!S.timeline.length) {
      box.innerHTML = `<div class="hint" style="padding:20px;color:#8C9086">nothing on the timeline —
        Make Highlights, keep transcript moments, or + Add from the highlights list</div>`;
      updateMetaLine();
      return;
    }
    const vid = S.session ? ytId() : null;
    box.innerHTML = S.timeline.map((c, k) => `
      <div class="hl-clip${k === S.curClip ? " playing" : ""}" draggable="true" data-k="${k}">
        <button class="rm" data-k="${k}">×</button>
        <img src="${S.session
          ? `https://i.ytimg.com/vi/${encodeURIComponent(vid)}/mqdefault.jpg`
          : frameURL(S.source, Math.round(c.start * (S.clip?.fps || 30)), 120)}"
          loading="lazy" onerror="this.style.visibility='hidden'">
        <div class="ctitle">${esc(c.label || "clip")}</div>
        <div class="cmeta"><span>${fmtTime(c.start)}–${fmtTime(c.end)}</span>
          <span>${(c.end - c.start).toFixed(1)}s</span></div>
        <div class="trim">
          <input data-k="${k}" data-e="start" value="${c.start.toFixed(1)}" spellcheck="false" title="in point (s)">
          <input data-k="${k}" data-e="end" value="${c.end.toFixed(1)}" spellcheck="false" title="out point (s)">
        </div>
      </div>`).join("");
    $$(".hl-clip", box).forEach(clipEl => {
      clipEl.addEventListener("dragstart", e => {
        clipEl.classList.add("dragging");
        e.dataTransfer.setData("text/clip", clipEl.dataset.k);
      });
      clipEl.addEventListener("dragend", () => clipEl.classList.remove("dragging"));
      clipEl.addEventListener("dragover", e => e.preventDefault());
      clipEl.addEventListener("drop", e => {
        e.preventDefault();
        const from = +e.dataTransfer.getData("text/clip");
        const to = +clipEl.dataset.k;
        if (Number.isNaN(from) || from === to) return;
        const [moved] = S.timeline.splice(from, 1);
        S.timeline.splice(to, 0, moved);
        renderTimeline();
      });
      clipEl.onclick = e => {
        if (["INPUT", "BUTTON"].includes(e.target.tagName)) return;
        playClip(+clipEl.dataset.k, false);
      };
    });
    $$(".rm", box).forEach(b => b.onclick = () => {
      S.timeline.splice(+b.dataset.k, 1);
      renderTimeline();
      renderHighlights();
    });
    $$(".trim input", box).forEach(inp => inp.onchange = () => {
      const c = S.timeline[+inp.dataset.k];
      const v = parseFloat(inp.value);
      if (!Number.isNaN(v)) c[inp.dataset.e] = Math.max(0, v);
      if (c.end <= c.start) c.end = c.start + 0.5;
      renderTimeline();
    });
    updateMetaLine();
  }

  function playClip(k, thenNext) {
    if (k < 0 || k >= S.timeline.length) { S.curClip = -1; renderTimeline(); return; }
    S.curClip = k;
    const c = S.timeline[k];
    renderTimeline();
    seek(c.start, true);
    clearTimeout(S.playTimer);
    S.playTimer = setTimeout(() => {
      if (thenNext) playClip(k + 1, true);
      else pause();
    }, Math.max(200, (c.end - c.start) * 1000));
  }

  /* ---------------- downloads + render ---------------- */
  function mergedSections() {
    const spans = S.timeline.map(c => ({ start: c.start, end: c.end }))
      .sort((a, b) => a.start - b.start);
    const out = [];
    for (const s of spans) {
      if (out.length && s.start <= out[out.length - 1].end + 1.0) {
        out[out.length - 1].end = Math.max(out[out.length - 1].end, s.end);
      } else out.push({ ...s });
    }
    return out;
  }

  async function download(sectionsOnly) {
    const url = S.meta?.url;
    if (!url) { toast("this source has no URL — it's already a local file", true); return; }
    const sections = sectionsOnly ? mergedSections() : null;
    if (sectionsOnly && !sections.length) { toast("keep some moments first", true); return; }
    try {
      const job = await api("/api/highlighter/fetch", {
        url, quality: $("#hl-quality", el).value, sections });
      watchJob(job.id, j => {
        $("#hl-dlmsg", el).textContent = j.status === "running"
          ? `${Math.round(Math.max(0, j.progress) * 100)}% ${j.message || ""}` : (j.message || j.status);
      });
      const done = await jobDone(job.id);
      if (done.status === "error") { toast(done.error, true); return; }
      if (done.status !== "done") return;
      loadLibrary();
      if (sectionsOnly) {
        S.sectionFiles = done.result.paths || [done.result.path];
        toast(`${S.sectionFiles.length} section clips landed — Export reel now stitches them`);
      } else {
        toast("full video downloaded — opening the local copy");
        open(done.result.path);
      }
    } catch (e) { toast(e.message, true); }
  }

  async function exportReel() {
    if (!S.timeline.length) { toast("the timeline is empty", true); return; }
    const preset = $("#hl-preset", el).value;
    try {
      let job;
      if (!S.session) {
        job = await api("/api/highlighter/reel", {
          path: S.source, preset,
          ranges: S.timeline.map(c => ({ start: c.start, end: c.end })) });
      } else if (S.sectionFiles && S.sectionFiles.length) {
        job = await api("/api/highlighter/stitch", { files: S.sectionFiles, preset });
      } else {
        toast("URL session — download the kept sections first, then export", true);
        return;
      }
      watchJob(job.id, j => {
        $("#hl-reelmsg", el).textContent = j.message ||
          `${Math.round(Math.max(0, j.progress) * 100)}%`;
      });
      const done = await jobDone(job.id);
      if (done.status === "done") {
        const rep = $("#hl-report", el);
        rep.classList.add("show");
        rep.innerHTML += `<b>→</b> ${esc(done.result.out)}\n   ${done.result.clips} cuts · ${done.result.duration}s · ${esc(done.result.encoder)}\n`;
        toast("reel rendered");
      } else if (done.status === "error") toast(done.error, true);
    } catch (e) { toast(e.message, true); }
  }

  async function exportEDL() {
    if (S.session) { toast("EDLs reference a local source — download first", true); return; }
    if (!S.timeline.length) { toast("the timeline is empty", true); return; }
    try {
      const r = await api("/api/scribe/selects", {
        path: S.source, handles: 0.5,
        selects: S.timeline.map(c => ({ start: c.start, end: c.end, label: c.label || "" })) });
      const rep = $("#hl-report", el);
      rep.classList.add("show");
      rep.innerHTML += `<b>→</b> ${esc(r.out)}\n   ${r.selects} events · ${esc(r.note)}\n`;
      toast("selects EDL written");
    } catch (e) { toast(e.message, true); }
  }

  /* ---------------- ask the meeting ---------------- */
  function renderSuggestions(list) {
    const box = $("#hl-suggest", el);
    const items = list || [];
    box.innerHTML = items.map(s => `<button>${esc(s)}</button>`).join("");
    $$("button", box).forEach(b => b.onclick = () => {
      $("#hl-askq", el).value = b.textContent;
      askMeeting();
    });
  }

  async function askMeeting() {
    const q = $("#hl-askq", el).value.trim();
    if (!q || !S.source) return;
    const log = $("#hl-chatlog", el);
    log.innerHTML += `<div class="hl-msg q">${esc(q)}</div>`;
    $("#hl-askq", el).value = "";
    log.scrollTop = log.scrollHeight;
    try {
      const r = await api("/api/highlighter/ask", { path: S.source, q });
      const body = r.passages.length
        ? r.passages.map(p => `<div style="margin-bottom:6px">
            <span class="tpill" data-t="${p.t}">${fmtTime(p.t)}</span>
            ${p.speaker ? `<b>${esc(p.speaker)}:</b> ` : ""}${esc(p.text)}</div>`).join("")
        : esc(r.note || "nothing matched");
      log.innerHTML += `<div class="hl-msg a">${body}</div>`;
      $$(".tpill", log).forEach(p => p.onclick = () => seek(+p.dataset.t, true));
      renderSuggestions(r.suggestions || []);
      log.scrollTop = log.scrollHeight;
    } catch (e) {
      log.innerHTML += `<div class="hl-msg a">${esc(e.message)}</div>`;
    }
  }

  /* ---------------- transcript exports ---------------- */
  function downloadText(name, text) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  }
  const srtTime = t => {
    const h = String(Math.floor(t / 3600)).padStart(2, "0");
    const m = String(Math.floor(t / 60) % 60).padStart(2, "0");
    const s = String(Math.floor(t % 60)).padStart(2, "0");
    const ms = String(Math.round(t % 1 * 1000)).padStart(3, "0");
    return `${h}:${m}:${s},${ms}`;
  };
  function exportTxt() {
    if (!S.t) return;
    downloadText("transcript.txt", S.t.segments.map(s =>
      `[${fmtTime(s.start)}]${s.speaker ? " " + s.speaker + ":" : ""} ${s.text}`).join("\n"));
  }
  function exportSrt() {
    if (!S.t) return;
    downloadText("transcript.srt", S.t.segments.map((s, i) =>
      `${i + 1}\n${srtTime(s.start)} --> ${srtTime(s.end)}\n${s.text}\n`).join("\n"));
  }
  async function gTranslate() {
    if (!S.t) return;
    const text = S.t.segments.map(s => s.text).join("\n");
    try { await navigator.clipboard.writeText(text); } catch (e) {}
    window.open("https://translate.google.com/", "_blank");
    toast("transcript copied — paste it into Google Translate (free, any language)");
  }

  /* ---------------- scribe upgrade ---------------- */
  async function transcribe() {
    if (S.session) { toast("Scribe needs the audio — download the video first", true); return; }
    const btn = $("#hl-transcribe", el);
    btn.disabled = true;
    try {
      const job = await api("/api/scribe/transcribe", {
        path: S.source, model: $("#hl-model", el).value, diarize: true });
      watchJob(job.id, j => { $("#hl-detectmsg", el).textContent = j.message || j.status; });
      const done = await jobDone(job.id);
      btn.disabled = false;
      if (done.status === "error") { toast(done.error, true); return; }
      if (done.status === "done") {
        const tr = await api("/api/highlighter/transcript", { path: S.source });
        applyTranscript(tr);
        loadInsight();
        toast("Scribe pass done — words, timing and speakers upgraded");
      }
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  /* ---------------- sections nav ---------------- */
  function showSec(name) {
    ["highlight", "edit", "analyze"].forEach(s => {
      $(`#hl-sec-${s}`, el).style.display = s === name ? "" : "none";
    });
    $$("#hl-pills .hl-pill", el).forEach(p =>
      p.classList.toggle("on", p.dataset.sec === name));
    if (name === "highlight") drawSpark();
  }

  /* ---------------- wire up ---------------- */
  let inited = false;
  function init() {
    viewer = new Viewer($("#hl-viewer", el), { h: 360 });
    viewer.onOpen = p => open(p);

    $("#hl-load", el).onclick = () => {
      const u = $("#hl-url", el).value.trim();
      if (u.startsWith("http")) ingest(u);
      else if (u) open(u);           // a pasted local path works too
      else toast("paste a URL first", true);
    };
    $("#hl-url", el).addEventListener("keydown", e => { if (e.key === "Enter") $("#hl-load", el).click(); });
    $("#hl-browse", el).onclick = e => { e.stopPropagation(); browseForPath(p => open(p)); };
    wireDropZone($("#hl-drop", el), p => open(p));
    wireDropZone($("#hl-landing", el), p => open(p));
    $("#hl-back", el).onclick = backToLanding;
    $("#hl-findgo", el).onclick = finder;
    $("#hl-findq", el).addEventListener("keydown", e => { if (e.key === "Enter") finder(); });

    $("#hl-play", el).onclick = () => {
      if (S.session) { seek(0, true); return; }
      audio.paused ? audio.play() : audio.pause();
    };
    audio.addEventListener("play", () => { $("#hl-play", el).textContent = "⏸"; raf = requestAnimationFrame(tick); });
    audio.addEventListener("pause", () => { $("#hl-play", el).textContent = "▶"; if (raf) cancelAnimationFrame(raf); tick(); });

    $$("#hl-pills .hl-pill", el).forEach(p => p.onclick = () => showSec(p.dataset.sec));

    const styleRow = $("#hl-stylerow", el);
    styleRow.innerHTML = REEL_STYLES.map(([id, label, kw], i) =>
      `<span class="chip${i === 0 ? " on" : ""}" data-id="${id}" data-k="${esc(kw)}">${label}</span>`).join("");
    $$(".chip", styleRow).forEach(c => c.onclick = () => {
      $$(".chip", styleRow).forEach(x => x.classList.remove("on"));
      c.classList.add("on");
    });

    $("#hl-detect", el).onclick = detect;
    $("#hl-q", el).addEventListener("input", searchTranscript);
    $("#hl-transcribe", el).onclick = transcribe;
    $("#hl-txt", el).onclick = exportTxt;
    $("#hl-srt", el).onclick = exportSrt;
    $("#hl-gtranslate", el).onclick = gTranslate;
    $("#hl-askgo", el).onclick = askMeeting;
    $("#hl-askq", el).addEventListener("keydown", e => { if (e.key === "Enter") askMeeting(); });

    $("#hl-prev", el).onclick = () => playClip(Math.max(0, S.curClip - 1), false);
    $("#hl-next", el).onclick = () => playClip(Math.min(S.timeline.length - 1, S.curClip + 1), false);
    $("#hl-playreel", el).onclick = () => playClip(0, true);
    $("#hl-clear", el).onclick = () => { S.timeline = []; S.keep = new Set(); renderTimeline(); renderTranscript(); renderHighlights(); };
    $("#hl-export", el).onclick = exportReel;
    $("#hl-edl", el).onclick = exportEDL;
    $("#hl-dlfull", el).onclick = () => download(false);
    $("#hl-dlsections", el).onclick = () => download(true);

    new MutationObserver(() => { if (!el.classList.contains("active")) stop(); })
      .observe(el, { attributes: true, attributeFilter: ["class"] });
    addEventListener("resize", () => { if (CZ.current === "highlighter") drawSpark(); });
  }

  function stop() {
    audio.pause();
    clearTimeout(S.playTimer);
    if (raf) { cancelAnimationFrame(raf); raf = null; }
  }

  function onshow(arg) {
    if (!inited) { init(); inited = true; }
    Viewer.active = null;
    ytdlpCheck();      // every open — that's the deal, and the chip shows it
    loadLibrary();
    if (arg && arg.openPath) open(arg.openPath);
  }

  registerPage("highlighter", el, onshow);
  return { onshow };
})();
