/* Community Memory — the record across meetings and years.
 *
 * Highlighter is a microscope; this is the telescope. One page, two views: the
 * record (search the whole corpus + add meetings) and one meeting (its words,
 * its reading, and playback that jumps to any second). Caption-only YouTube
 * meetings play in an embed seeked by postMessage; local files play on the
 * <audio> clock with the canvas frame-server — the same two players Highlighter
 * uses. Every AI surface is labeled and supplements the official record.
 */
const MemoryPage = (() => {
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-memory";
  el.innerHTML = `
  <div class="page-pad wide" style="--acc:var(--memory)">

    <!-- ============ THE RECORD (landing) ============ -->
    <div id="mem-record">
      <div class="hl-hero" style="border-color:var(--memory)">
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
          <h1 style="margin:0">Community Memory</h1>
          <span class="badge synth">beta</span>
        </div>
        <p class="why" style="margin-top:6px;max-width:70ch">
          The record across meetings and years — search every meeting, jump to the
          moment, follow an issue over time. <span class="mark">Supplements the
          official record; it never replaces it.</span>
        </p>
        <div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap">
          <input type="text" id="mem-q" placeholder="Search the record — a phrase, a topic, a street name…"
            style="flex:1;min-width:280px;padding:11px 13px;border:1px solid var(--line);
            border-radius:9px;background:var(--ink-2);font-size:14px;font-family:var(--ui)">
        </div>
        <div id="mem-statline" class="progmsg" style="margin-top:8px"></div>
      </div>

      <div id="mem-results" style="display:none;margin-top:16px"></div>

      <div style="display:grid;grid-template-columns:1.6fr 1fr;gap:16px;margin-top:16px;align-items:start">
        <div class="hl-panel" id="mem-listpanel">
          <span class="tag">the record</span>
          <div id="mem-list"></div>
        </div>
        <div class="hl-panel">
          <span class="tag">add to the record</span>
          <div class="field">
            <label>Meeting URL (YouTube / civic portal) or a local file path</label>
            <input type="text" id="mem-add" placeholder="https://youtube.com/watch?v=…  —or—  /path/to/meeting.mp4">
            <p class="hint">Captions first: published transcripts come straight in. Scribe
              transcribes on-device only when a video has no captions. Local, no account.</p>
          </div>
          <div class="field" style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
            <div><label>Town (optional)</label><input type="text" id="mem-town" placeholder="Brookline"></div>
            <div><label>Body (optional)</label><input type="text" id="mem-body" placeholder="Select Board"></div>
          </div>
          <button class="btn primary" id="mem-addbtn" style="margin-top:10px">Send to the record</button>
          <div class="prog" id="mem-addprog" style="display:none"><i></i></div>
          <div class="progmsg" id="mem-addmsg"></div>
        </div>
      </div>
    </div>

    <!-- ============ ONE MEETING (the long view of a single session) ============ -->
    <div id="mem-meeting" style="display:none">
      <button class="btn" id="mem-back" style="margin-bottom:10px">← the record</button>
      <div style="display:flex;gap:8px;align-items:baseline;flex-wrap:wrap">
        <h1 id="mem-title" style="margin:0;font-size:22px"></h1>
        <span class="badge synth">beta</span>
      </div>
      <div id="mem-meta" class="lmeta" style="font-family:var(--mono);font-size:11px;color:var(--cream-dim);margin-top:4px"></div>
      <div id="mem-origin" class="progmsg" style="margin-top:2px"></div>

      <div style="display:grid;grid-template-columns:1.5fr 1fr;gap:16px;margin-top:14px;align-items:start">
        <div>
          <div class="hl-yt" id="mem-ytbox" style="display:none"><iframe id="mem-ytframe" allow="autoplay"></iframe></div>
          <div id="mem-viewer" style="display:none;background:#0D0D12;border-radius:10px;overflow:hidden;aspect-ratio:16/9"></div>
          <audio id="mem-audio" style="display:none"></audio>
          <div style="display:flex;gap:8px;align-items:center;margin-top:8px">
            <button class="btn" id="mem-play">▶ play</button>
            <span class="progmsg" id="mem-clock" style="margin:0">0:00.0</span>
            <label class="checkrow" style="margin:0 0 0 auto"><input type="checkbox" id="mem-follow"> follow along</label>
          </div>
          <div class="hl-panel" style="margin-top:12px">
            <span class="tag">transcript</span>
            <div id="mem-transcript" style="max-height:360px;overflow:auto"></div>
          </div>
        </div>
        <div id="mem-reading"></div>
      </div>
    </div>
  </div>`;

  /* ------------------------------------------------------------------ */
  const S = { view: "record", id: null, m: null, segs: [], session: false,
              clip: null, sessionTime: 0, ytPlaying: false, pendingSeek: null };
  let viewer = null, raf = 0, inited = false, refreshTimer = 0;
  const audio = () => $("#mem-audio", el);

  // civic meetings run hours — show h:mm:ss, not 173:21 minutes
  function hms(t) {
    t = Math.max(0, t || 0);
    const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = Math.floor(t % 60);
    const p = n => String(n).padStart(2, "0");
    return h ? `${h}:${p(m)}:${p(s)}` : `${m}:${p(s)}`;
  }

  /* ---------------- the record (landing) ---------------- */

  async function loadCorpus() {
    try {
      const d = await api("/api/memory/corpus");
      renderStats(d.stats);
      renderList(d.meetings || []);
      const busy = (d.meetings || []).some(m =>
        ["queued", "transcribing", "analyzing"].includes(m.status));
      clearTimeout(refreshTimer);
      if (busy && CZ.current === "memory")
        refreshTimer = setTimeout(loadCorpus, 2500);
    } catch (e) { toast(e.message, true); }
  }

  function renderStats(s) {
    const hrs = (s.seconds / 3600);
    const bits = [
      `${s.live} in the record`,
      hrs >= 1 ? `${hrs.toFixed(1)} hours` : `${Math.round(s.seconds / 60)} min`,
      `${s.segments} segments`,
    ];
    if (s.towns) bits.push(`${s.towns} town${s.towns > 1 ? "s" : ""}`);
    if (s.bodies) bits.push(`${s.bodies} bodies`);
    bits.push(s.semantic ? "keyword + related language" : "keyword search");
    $("#mem-statline", el).textContent = bits.join(" · ");
  }

  function renderList(meetings) {
    const box = $("#mem-list", el);
    if (!meetings.length) {
      box.innerHTML = `<p class="hint" style="padding:8px 0">The record is empty.
        Paste a meeting URL on the right to begin — a Brookline or Boston meeting
        with captions comes in within seconds.</p>`;
      return;
    }
    box.innerHTML = meetings.map(m => {
      const meta = [m.body, m.town, m.date].filter(Boolean).join(" · ");
      const st = m.status === "live"
        ? `<span class="badge ${m.origin === "captions" ? "" : "hw"}">${m.origin || "read"}</span>`
        : m.status === "no_transcript"
          ? `<span class="stat-chip stat-cancelled">needs transcript</span>`
          : `<span class="stat-chip stat-${m.status === "error" ? "error" : "running"}">${m.status}</span>`;
      const foot = m.status === "error" ? `<div class="progmsg err">${esc(m.error || "failed")}</div>`
        : m.status === "no_transcript" ? `<div class="lmeta" style="color:var(--cream-faint)">${esc(m.error || "no captions yet")}</div>`
          : "";
      return `<div class="batchrow ${m.status === "live" ? "hl-click" : ""}" data-open="${esc(m.id)}"
                style="align-items:center">
        <div>
          <div class="bname" style="font-size:12.5px;color:var(--cream)">${esc(m.title || m.id)}</div>
          <div class="lmeta">${esc(meta) || "&nbsp;"}${m.n_segments ? " · " + m.n_segments + " segments" : ""}</div>
          ${foot}
        </div>
        <span class="bstat">${st}</span>
        <button data-forget="${esc(m.id)}" title="forget this meeting">✕</button>
      </div>`;
    }).join("");
    $$("[data-open]", box).forEach(r => r.onclick = e => {
      if (e.target.dataset.forget !== undefined) return;
      const m = meetings.find(x => x.id === r.dataset.open);
      if (m && m.status === "live") openMeeting(r.dataset.open);
      else if (m && m.status === "no_transcript")
        toast(m.error || "no captions yet — bring the video file in for Scribe", true);
      else toast("still processing — the Queue shows its progress");
    });
    $$("[data-forget]", box).forEach(b => b.onclick = async e => {
      e.stopPropagation();
      await api("/api/memory/forget", { id: b.dataset.forget });
      loadCorpus();
    });
  }

  /* ---------------- cross-corpus search ---------------- */

  let searchTimer = 0;
  function onSearchInput() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(doSearch, 220);
  }
  async function doSearch() {
    const q = $("#mem-q", el).value.trim();
    const box = $("#mem-results", el);
    if (!q) { box.style.display = "none"; box.innerHTML = ""; return; }
    try {
      const d = await api(`/api/memory/search?q=${encodeURIComponent(q)}&limit=60`);
      box.style.display = "";
      if (!d.hits.length) {
        box.innerHTML = `<div class="hl-panel"><span class="tag">no matches</span>
          <p class="hint">Nothing in the record yet for “${esc(q)}”.</p></div>`;
        return;
      }
      box.innerHTML = `<div class="hl-panel"><span class="tag">across the record —
        ${d.hits.length} moment${d.hits.length > 1 ? "s" : ""}</span>
        ${d.hits.map(h => `
          <div class="hl-seg hl-click" data-open="${esc(h.meeting_id)}" data-t="${h.t}"
               style="display:flex;gap:9px;align-items:flex-start;padding:7px 4px">
            <span class="tpill">${hms(h.t)}</span>
            <div style="flex:1">
              <div style="font-size:13px">${esc(h.text)}</div>
              <div class="lmeta">${esc([h.title, h.body, h.date].filter(Boolean).join(" · "))}
                ${h.speaker ? " · " + esc(h.speaker) : ""} ·
                <span style="color:var(--cream-faint)">${h.why}</span></div>
            </div>
          </div>`).join("")}
      </div>`;
      $$("[data-open]", box).forEach(r => r.onclick = () =>
        openMeeting(r.dataset.open, parseFloat(r.dataset.t)));
    } catch (e) { toast(e.message, true); }
  }

  /* ---------------- add to the record ---------------- */

  async function addToRecord() {
    const raw = $("#mem-add", el).value.trim();
    if (!raw) { toast("paste a meeting URL or a file path", true); return; }
    const isUrl = /^https?:\/\//i.test(raw);
    const body = isUrl ? { url: raw } : { path: raw };
    body.town = $("#mem-town", el).value.trim();
    body.body = $("#mem-body", el).value.trim();
    const btn = $("#mem-addbtn", el), prog = $("#mem-addprog", el),
      msg = $("#mem-addmsg", el);
    btn.disabled = true; msg.className = "progmsg";
    try {
      const r = await api("/api/memory/submissions", body);
      if (r.status === "exists") {
        msg.textContent = "already in the record — opening it";
        btn.disabled = false;
        loadCorpus(); openMeeting(r.meeting_id); return;
      }
      prog.style.display = ""; $("i", prog).style.width = "40%";
      msg.textContent = "queued — the Queue tab shows it too";
      $("#mem-add", el).value = "";
      loadCorpus();
      watchJob(r.job.id, j => {
        msg.textContent = j.message || j.status;
        if (typeof j.progress === "number" && j.progress >= 0)
          $("i", prog).style.width = Math.round(j.progress * 100) + "%";
      });
      const done = await jobDone(r.job.id);
      btn.disabled = false; prog.style.display = "none";
      loadCorpus();
      if (done.status !== "done") {
        msg.className = "progmsg err";
        msg.textContent = done.error || "stopped"; return;
      }
      const res = done.result || {};
      msg.textContent = res.status === "exists"
        ? "already in the record (same meeting, different link)"
        : `in the record — ${res.segments} segments · ${res.origin}`;
      if (res.meeting_id && res.status !== "exists") openMeeting(res.meeting_id);
    } catch (e) {
      btn.disabled = false; prog.style.display = "none";
      msg.className = "progmsg err"; msg.textContent = e.message;
    }
  }

  /* ---------------- one meeting ---------------- */

  async function openMeeting(id, seekTo) {
    try {
      const d = await api("/api/memory/meeting", { id });
      S.view = "meeting"; S.id = id; S.m = d.meeting; S.segs = d.transcript.segments;
      $("#mem-record", el).style.display = "none";
      $("#mem-meeting", el).style.display = "";
      const m = d.meeting;
      $("#mem-title", el).textContent = m.title || id;
      $("#mem-meta", el).textContent =
        [m.body, m.town, m.date, m.uploader].filter(Boolean).join("  ·  ")
        + (m.n_speakers ? `  ·  ${m.n_speakers} speakers` : "");
      $("#mem-origin", el).textContent = m.origin === "captions"
        ? "words from the published captions — instant; Scribe hears it better where captions are thin · AI-assisted reading — verify against the official record"
        : m.origin === "scribe"
          ? "words from Scribe — on-device transcription · AI-assisted reading — verify against the official record"
          : "AI-assisted reading — verify against the official record";
      // a jump-to arrives before the player can seek — hold it and apply the
      // moment the player is ready: the embed's onReady (wireSessionClock) for
      // YouTube, the <audio>'s loadedmetadata (openLocal) for local files.
      S.pendingSeek = (typeof seekTo === "number" && !isNaN(seekTo)) ? seekTo : null;
      setupPlayback(m);
      renderTranscript();
      renderReading(m, d.moments);
      showMeeting();
    } catch (e) { toast(e.message, true); }
  }

  function setupPlayback(m) {
    stop();
    S.session = m.source_kind === "youtube" && !!m.video_id;
    $("#mem-ytbox", el).style.display = "none";
    $("#mem-viewer", el).style.display = "none";
    if (S.session) {
      S.clip = null;
      $("#mem-ytbox", el).style.display = "";
      $("#mem-ytframe", el).src =
        `https://www.youtube.com/embed/${encodeURIComponent(m.video_id)}?enablejsapi=1`;
    } else {
      $("#mem-ytframe", el).src = "";   // stop any previous meeting's embed audio
      if (m.media_path) openLocal(m.media_path);
    }
  }

  async function openLocal(path) {
    try {
      const r = await api("/api/media/open", { path, tool: "memory" });
      const v = r.video;
      if (v && viewer) {
        $("#mem-viewer", el).style.display = "";
        S.clip = { path: r.path, nFrames: v.n_frames_estimate || 1, fps: v.fps };
        viewer.setClip(S.clip);
      }
      audio().src = `/api/scribe/audio?path=${encodeURIComponent(r.path)}`;
      if (S.pendingSeek != null) {   // a search jump — apply once the clip has a duration
        const t = S.pendingSeek; S.pendingSeek = null;
        audio().addEventListener("loadedmetadata", () => seek(t, true), { once: true });
      }
    } catch (e) { /* audio-less source: transcript still works */ }
  }

  /* -- playback: two players, one clock (mirrors Highlighter) -- */

  const nowTime = () => S.session ? (S.sessionTime || 0) : audio().currentTime;

  function seek(t, play) {
    if (S.session) {
      const f = $("#mem-ytframe", el);
      try {
        f.contentWindow.postMessage(JSON.stringify(
          { event: "command", func: "seekTo", args: [t, true] }), "*");
        if (play) f.contentWindow.postMessage(JSON.stringify(
          { event: "command", func: "playVideo", args: [] }), "*");
      } catch (e) {}
      S.sessionTime = t; S.ytPlaying = !!play;
      $("#mem-clock", el).textContent = hms(t);
    } else {
      audio().currentTime = t;
      if (play) audio().play();
      syncFrame(true);
    }
    followTranscript();
  }

  function playPause() {
    if (S.session) {
      const f = $("#mem-ytframe", el);
      try {
        f.contentWindow.postMessage(JSON.stringify(
          { event: "command", func: S.ytPlaying ? "pauseVideo" : "playVideo", args: [] }), "*");
      } catch (e) {}
      S.ytPlaying = !S.ytPlaying;
    } else {
      audio().paused ? audio().play() : audio().pause();
    }
  }

  function syncFrame(force) {
    if (!S.clip || !viewer) return;
    const i = Math.min(Math.round(audio().currentTime * S.clip.fps), S.clip.nFrames - 1);
    if (force || viewer.i !== i) viewer.show(i);
  }

  function tick() {
    $("#mem-clock", el).textContent = hms(audio().currentTime);
    syncFrame(false); followTranscript();
    if (!audio().paused) raf = requestAnimationFrame(tick);
  }

  function wireSessionClock() {
    addEventListener("message", e => {
      // anchored: only exact youtube hosts, so youtube.com.evil.com can't spoof
      if (!/^https:\/\/(www\.)?youtube(-nocookie)?\.com$/.test(e.origin)) return;
      let d; try { d = JSON.parse(e.data); } catch (err) { return; }
      if (d.event === "onReady" || d.event === "onStateChange") {
        hello();
        if (S.pendingSeek != null) {   // the jump-to that was waiting on the player
          const t = S.pendingSeek; S.pendingSeek = null;
          seek(t, true);
        }
      }
      const info = d.info || {};
      if (typeof info.currentTime === "number") {
        S.sessionTime = info.currentTime;
        if (typeof info.playerState === "number") S.ytPlaying = info.playerState === 1;
        if (S.session && CZ.current === "memory") {
          $("#mem-clock", el).textContent = hms(S.sessionTime);
          followTranscript();
        }
      }
    });
    $("#mem-ytframe", el).addEventListener("load", () => { S.sessionTime = 0; hello(); });
  }
  function hello() {
    try {
      $("#mem-ytframe", el).contentWindow.postMessage(JSON.stringify(
        { event: "listening", id: "czmem", channel: "widget" }), "*");
    } catch (e) {}
  }

  function stop() {
    if (raf) cancelAnimationFrame(raf), raf = 0;
    try { audio().pause(); } catch (e) {}
  }

  // leaving the tab (rail nav) only hides the page via CSS — the router has no
  // onhide — so pause both players when Memory loses its active class, or a
  // meeting keeps playing audio underneath another tool.
  function pauseAway() {
    stop();
    if (S.session) {
      try {
        $("#mem-ytframe", el).contentWindow.postMessage(JSON.stringify(
          { event: "command", func: "pauseVideo", args: [] }), "*");
      } catch (e) {}
      S.ytPlaying = false;
    }
  }

  /* ---------------- transcript (follow-along) ---------------- */

  function renderTranscript() {
    const box = $("#mem-transcript", el);
    box.innerHTML = S.segs.map((s, i) => `
      <div class="hl-seg hl-click" data-t="${s.start}" data-i="${i}"
           style="padding:5px 4px;border-left:2px solid transparent">
        <span class="tpill" style="margin-right:7px">${hms(s.start)}</span>
        ${s.speaker ? `<b style="font-size:11px;color:var(--cream-dim)">${esc(s.speaker)}:</b> ` : ""}
        <span style="font-size:13px">${esc(s.text)}</span>
      </div>`).join("");
    $$("[data-t]", box).forEach(r => r.onclick = () => seek(parseFloat(r.dataset.t), true));
  }

  let lastNow = -1;
  function followTranscript() {
    if (!S.segs.length) return;
    const t = nowTime();
    if (Math.abs(t - lastNow) < 0.4) return;
    lastNow = t;
    let idx = -1;
    for (let i = 0; i < S.segs.length; i++) {
      if (S.segs[i].start <= t + 0.05) idx = i; else break;
    }
    const box = $("#mem-transcript", el);
    $$(".hl-seg", box).forEach(r => r.classList.remove("now"));
    if (idx >= 0) {
      const row = box.children[idx];
      if (row) {
        row.classList.add("now");
        if ($("#mem-follow", el).checked)
          row.scrollIntoView({ block: "center", behavior: "smooth" });
      }
    }
  }

  /* ---------------- the reading (extractive + labeled generative) ---------------- */

  function renderReading(m, moments) {
    const a = m.analysis || {};
    const panels = [];

    // summary card — labeled by origin, never dressed up as the record
    if (m.summary) {
      const ai = (m.summary_origin || "").startsWith("ai:");
      panels.push(`<div class="hl-panel">
        <span class="tag">${ai ? "ai summary" : "summary"} ${ai
          ? `<span class="badge synth">${esc(m.summary_origin.slice(3))}</span>` : ""}</span>
        <p style="font-size:13px;line-height:1.6">${esc(m.summary)}</p>
        <p class="hint">${ai
          ? "Generated with your key. Verify against the official record."
          : "Sentences quoted from the meeting — no model, no key."}</p>
      </div>`);
    }

    if ((moments || []).length) {
      panels.push(`<div class="hl-panel"><span class="tag">moments</span>
        ${moments.slice(0, 6).map(mo => `
          <div class="hl-seg hl-click" data-t="${mo.start}" style="padding:5px 4px">
            <span class="tpill" style="margin-right:7px">${hms(mo.start)}</span>
            <span style="font-size:12.5px">${esc(mo.text.slice(0, 90))}</span>
            <div class="lmeta">${esc((mo.reasons || []).slice(0, 3).join(" · "))}</div>
          </div>`).join("")}</div>`);
    }

    if ((a.decisions || []).length) {
      panels.push(`<div class="hl-panel"><span class="tag">motions &amp; decisions</span>
        ${a.decisions.slice(0, 8).map(dd => `
          <div class="hl-seg hl-click" data-t="${dd.t}" style="padding:5px 4px">
            <span class="tpill" style="margin-right:7px">${hms(dd.t)}</span>
            <span style="font-size:12.5px">${esc(dd.text.slice(0, 100))}</span>
            ${dd.outcome ? ` <span class="hl-kind hl-kind-money">${esc(dd.outcome)}</span>` : ""}
          </div>`).join("")}</div>`);
    }

    if ((a.topics || []).length) {
      panels.push(`<div class="hl-panel"><span class="tag">topics</span>
        <div style="display:flex;flex-wrap:wrap;gap:6px">
          ${a.topics.slice(0, 12).map(tp =>
        `<span class="tpill hl-click" data-t="${tp.t}" style="background:var(--ink-3);color:var(--cream-dim)">${esc(tp.topic)}</span>`).join("")}
        </div></div>`);
    }

    const ents = a.entities || {};
    const entRows = [];
    [["people", "person"], ["places", "place"], ["organizations", "org"], ["money", "money"]]
      .forEach(([k, cls]) => (ents[k] || []).slice(0, 6).forEach(e =>
        entRows.push(`<span class="hl-kind hl-kind-${cls} hl-click" data-t="${e.t}"
          title="${esc(k)}">${esc(e.name)}</span>`)));
    if (entRows.length) {
      panels.push(`<div class="hl-panel"><span class="tag">named in the meeting</span>
        <div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center">${entRows.join("")}</div>
        <p class="hint">People, places, orgs, and figures the meeting mentioned. Officials only
          are aggregated across meetings; residents stay within their own meeting.</p></div>`);
    }

    if ((a.participation || []).length) {
      panels.push(`<div class="hl-panel"><span class="tag">who spoke</span>
        ${a.participation.slice(0, 8).map(p => `
          <div class="batchrow" style="align-items:center">
            <span class="bname">${esc(p.speaker)}</span>
            <span class="bstat">${Math.round((p.share || 0) * 100)}% · ${p.turns} turns</span>
          </div>`).join("")}</div>`);
    }

    $("#mem-reading", el).innerHTML = panels.join("") || `<div class="hl-panel">
      <span class="tag">reading</span><p class="hint">No reading yet.</p></div>`;
    $$("[data-t]", $("#mem-reading", el)).forEach(r =>
      r.onclick = () => seek(parseFloat(r.dataset.t), true));
  }

  /* ---------------- view switching ---------------- */

  function showMeeting() { S.view = "meeting"; }
  function backToRecord() {
    stop();
    $("#mem-ytframe", el).src = "";
    S.view = "record"; S.session = false; S.clip = null;
    $("#mem-meeting", el).style.display = "none";
    $("#mem-record", el).style.display = "";
    loadCorpus();
  }

  /* ---------------- init / mount ---------------- */

  function init() {
    if (window.Viewer) {
      try { viewer = new Viewer($("#mem-viewer", el), { h: 360 }); } catch (e) { viewer = null; }
    }
    $("#mem-q", el).addEventListener("input", onSearchInput);
    $("#mem-add", el).addEventListener("keydown", e => { if (e.key === "Enter") addToRecord(); });
    $("#mem-addbtn", el).onclick = addToRecord;
    $("#mem-back", el).onclick = backToRecord;
    $("#mem-play", el).onclick = playPause;
    audio().addEventListener("play", () => { $("#mem-play", el).textContent = "⏸ pause"; raf = requestAnimationFrame(tick); });
    audio().addEventListener("pause", () => { $("#mem-play", el).textContent = "▶ play"; if (raf) cancelAnimationFrame(raf); tick(); });
    audio().addEventListener("seeked", () => tick());
    wireSessionClock();
    // the page is shown/hidden by a CSS class the router toggles; watch it so
    // we can pause when the user navigates to another tool
    new MutationObserver(() => {
      if (!el.classList.contains("active")) pauseAway();
    }).observe(el, { attributes: true, attributeFilter: ["class"] });
  }

  function onshow(arg) {
    if (!inited) { init(); inited = true; }
    Viewer.active = null;
    if (arg && arg.openMeeting) { openMeeting(arg.openMeeting, arg.seek); return; }
    backToRecordSilently();
    loadCorpus();
    if (arg && arg.q) { $("#mem-q", el).value = arg.q; doSearch(); }
  }
  function backToRecordSilently() {
    S.view = "record";
    $("#mem-meeting", el).style.display = "none";
    $("#mem-record", el).style.display = "";
  }

  registerPage("memory", el, onshow);
  return { onshow };
})();
