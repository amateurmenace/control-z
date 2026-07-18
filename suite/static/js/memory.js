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
          <button class="btn" id="mem-bell" title="resurfacings on your threads"
            style="margin-left:auto;display:none">🔔 <span id="mem-bell-n">0</span></button>
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
          <button class="btn" id="mem-analyticsbtn"
            title="the record as charts — topics, framing and names over time">📊 Analytics</button>
          <button class="btn" id="mem-officialsbtn"
            title="every official's roll-call record, read from the record">⬡ The votes</button>
          <button class="btn" id="mem-publishbtn"
            title="press the public edition and hand off the deploy">⬆ Publish the record</button>
        </div>
        <div id="mem-statline" class="progmsg" style="margin-top:8px"></div>
        <div id="mem-publishwrap" style="margin-top:10px"></div>
      </div>

      <div id="mem-results" style="display:none;margin-top:16px"></div>

      <!-- the long view: issues tracked across the record, and the threads
           following them (the telescope's landing) -->
      <div style="display:grid;grid-template-columns:1.6fr 1fr;gap:16px;margin-top:16px;align-items:start">
        <div class="hl-panel" id="mem-issuepanel">
          <div style="display:flex;align-items:baseline;gap:8px">
            <span class="tag">the long view — issues across the record</span>
            <button class="btn" id="mem-rebuild" style="margin-left:auto;font-size:11px;padding:3px 8px"
              title="re-cluster the whole record into issues">↻ rebuild</button>
          </div>
          <div id="mem-issuelist"></div>
          <div id="mem-candidates" style="margin-top:8px"></div>
        </div>
        <div class="hl-panel" id="mem-threadpanel">
          <span class="tag">still watching</span>
          <div id="mem-threads"></div>
          <div id="mem-digestwrap" style="display:none;margin-top:8px">
            <button class="btn" id="mem-digest" style="font-size:11px;padding:4px 9px">⧉ copy the digest</button>
            <p class="hint" style="margin-top:6px">A plain roundup of your threads —
              nothing sent anywhere, yours to paste where you like.</p>
          </div>
        </div>
      </div>

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

    <!-- ============ ONE ISSUE (the long view across meetings) ============ -->
    <div id="mem-issue" style="display:none">
      <button class="btn" id="mem-ibackbtn" style="margin-bottom:10px">← the record</button>
      <div style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap">
        <h1 id="mem-iname" style="margin:0;font-size:22px"></h1>
        <span class="badge synth">beta</span>
        <button class="btn primary" id="mem-followbtn" style="margin-left:auto">☆ follow this issue</button>
      </div>
      <div id="mem-ioverview" class="progmsg" style="margin-top:4px"></div>
      <div id="mem-idisclose" class="lmeta" style="color:var(--cream-faint);margin-top:2px"></div>
      <div id="mem-ialiases" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px"></div>
      <div id="mem-idelta"></div>

      <div class="hl-panel" style="margin-top:14px">
        <span class="tag">the timeline — every meeting this issue touched</span>
        <div id="mem-timeline" style="overflow-x:auto;padding:10px 2px 4px"></div>
      </div>
      <div id="mem-iledger"></div>
      <div id="mem-ipaper"></div>
      <div id="mem-iappearances"></div>
    </div>

    <!-- ============ THE VOTES (per-official roll-call records) ============ -->
    <div id="mem-officials" style="display:none">
      <button class="btn" id="mem-offbackbtn" style="margin-bottom:10px">← the record</button>
      <div class="hl-hero" style="border-color:var(--memory)">
        <div style="display:flex;align-items:center;gap:10px">
          <h1 style="margin:0">The people's votes</h1>
          <span class="badge synth">beta</span>
        </div>
        <p class="why" style="margin-top:6px;max-width:70ch">
          Every roll call the record has read, by member — officials only, by
          construction: a roll call is the board voting. Each cell lands the tape
          on the moment. Read from the transcript; verify against the official
          minutes.</p>
      </div>
      <div id="mem-offbody" style="margin-top:16px"></div>
    </div>

    <!-- ==== ANALYTICS (lane A hook — the Library's charts, moved in;
         drawn by the shared czAnalytics engine) ==== -->
    <div id="mem-analytics" style="display:none">
      <button class="btn" id="mem-anbackbtn" style="margin-bottom:10px">← the record</button>
      <div class="hl-hero" style="border-color:var(--memory)">
        <div style="display:flex;align-items:center;gap:10px">
          <h1 style="margin:0">The record, drawn</h1>
          <span class="badge synth">beta</span>
        </div>
        <p class="why" style="margin-top:6px;max-width:70ch">
          Every meeting on this machine as one picture — topics over time,
          civic framing, the names that keep appearing. Every mark opens its
          receipts, and every receipt can join the reel timeline.
        </p>
      </div>
      <div id="mem-anbody" style="margin-top:16px"></div>
    </div>
  </div>`;

  /* ------------------------------------------------------------------ */
  const S = { view: "record", id: null, m: null, segs: [], session: false,
              clip: null, sessionTime: 0, ytPlaying: false, pendingSeek: null,
              iid: null, issue: null };
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
      box.innerHTML = `<div class="hl-panel">
        <div style="display:flex;align-items:baseline;gap:8px">
          <span class="tag">across the record —
            ${d.hits.length} moment${d.hits.length > 1 ? "s" : ""}</span>
          <button class="btn" id="mem-mint" style="margin-left:auto;font-size:11px;padding:3px 9px"
            title="follow this as an issue — you'll be told when it resurfaces">☆ follow this</button>
        </div>
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
            ${window.czTray ? czTray.btnHTML({ source: "vid:" + h.meeting_id,
              start: Math.max(0, h.t - 2), end: h.t + 12,
              label: (h.text || "").slice(0, 80),
              title: (h.title || "").slice(0, 60) }) : ""}
          </div>`).join("")}
      </div>`;
      $$("[data-open]", box).forEach(r => r.onclick = () =>
        openMeeting(r.dataset.open, parseFloat(r.dataset.t)));
      const mint = $("#mem-mint", box);
      if (mint) mint.onclick = () => mintFromSearch(q);
    } catch (e) { toast(e.message, true); }
  }

  async function mintFromSearch(q) {
    try {
      const r = await api("/api/memory/thread/mint", { q });
      toast(r.attached
        ? `following “${r.name}” — it was already on the record`
        : `following “${r.name}” — a new thread from your search`);
      openIssue(r.issue_id);
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
      hideAllViews();
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

    // the town's paper + the roll calls — the vote ledger and the documents,
    // with a control to fetch the town's paper from its portal (a job).
    panels.push(`<div class="hl-panel" id="mem-docsvotes">
      <div style="display:flex;align-items:baseline;gap:8px">
        <span class="tag">the town's paper &amp; the roll calls</span>
        <button class="btn" id="mem-fetchdocs" style="margin-left:auto;font-size:11px;padding:3px 8px"
          title="pull this meeting's agenda, minutes and packet from the town portal">⬇ fetch the paper</button>
      </div>
      <div id="mem-dvbody"><p class="hint">Fetch the town's agenda, minutes and packet —
        they interleave on the record and give the roll call its roster.</p></div>
    </div>`);

    $("#mem-reading", el).innerHTML = panels.join("") || `<div class="hl-panel">
      <span class="tag">reading</span><p class="hint">No reading yet.</p></div>`;
    $$("[data-t]", $("#mem-reading", el)).forEach(r =>
      r.onclick = () => seek(parseFloat(r.dataset.t), true));
    const fb = $("#mem-fetchdocs", el);
    if (fb) fb.onclick = () => fetchDocuments(m.id);
    loadDocsVotes(m.id);
  }

  async function loadDocsVotes(mid) {
    try {
      const d = await api("/api/memory/meeting/documents", { id: mid });
      const box = $("#mem-dvbody", el); if (!box) return;
      const votes = d.votes || [], docs = d.documents || [];
      if (!votes.length && !docs.length) return;   // keep the invite prompt
      const vhtml = votes.length ? `<div style="margin-bottom:8px">
        ${votes.map(v => `<div style="border:1px solid var(--line);border-radius:7px;margin-top:6px;overflow:hidden">
          <div class="hl-seg hl-click" data-t="${v.t}" style="padding:6px 9px;background:var(--ink-3);font-size:12px">
            <span class="tpill" style="margin-right:6px">${hms(v.t)}</span>${esc((v.motion || "").slice(0, 80))}
            <span class="hl-kind hl-kind-money" style="margin-left:5px">${esc(v.tally || "")} ${esc(v.outcome || "")}</span></div>
          <div style="display:flex;flex-wrap:wrap;gap:5px 10px;padding:6px 9px">
            ${(v.roll || []).map(r => `<span style="font-size:11.5px">${esc(r.name)} ${RC(r.vote)}</span>`).join("")}</div>
        </div>`).join("")}</div>` : "";
      const dhtml = docs.length ? docs.map(dc => `<div style="padding:5px 4px;border-left:2px solid var(--amber);padding-left:9px;margin-top:5px">
        ${dc.url ? `<a href="${esc(dc.url)}" target="_blank" rel="noopener" style="color:var(--memory);font-weight:600">📄 ${esc(dc.kind || "document")} — ${esc((dc.title || "").slice(0, 50))}</a>`
          : `<b>📄 ${esc(dc.kind || "document")}</b>`}
        <span class="lmeta" style="margin-left:6px">${dc.pages || 0} pp · ${dc.n_chunks || 0} chunks</span></div>`).join("") : "";
      box.innerHTML = vhtml + dhtml;
      $$("[data-t]", box).forEach(r => r.onclick = () => seek(parseFloat(r.dataset.t), true));
    } catch (e) { /* the paper is optional — the reading stands without it */ }
  }

  /* ---------------- the long view: issues + threads ---------------- */

  async function loadIssues() {
    try {
      const d = await api("/api/memory/issues");
      renderIssues(d.issues || [], d.candidates || []);
    } catch (e) { /* the panel stays empty; search & the record still work */ }
  }

  function issueRow(i, cand) {
    const span = [i.first_seen, i.last_seen].filter(Boolean);
    const spanTxt = span.length === 2 && span[0] !== span[1]
      ? `${span[0]} → ${span[1]}` : (span[0] || "");
    return `<div class="batchrow hl-click" data-issue="${esc(i.id)}" style="align-items:center">
      <div>
        <div class="bname" style="font-size:12.5px;color:var(--cream)">${esc(i.name)}
          ${cand ? '<span class="stat-chip stat-cancelled" style="margin-left:6px">candidate</span>' : ""}</div>
        <div class="lmeta">${i.n_meetings} meeting${i.n_meetings !== 1 ? "s" : ""} ·
          ${i.n_segments} moment${i.n_segments !== 1 ? "s" : ""}${spanTxt ? " · " + esc(spanTxt) : ""}</div>
      </div>
      ${cand ? "" : `<button data-follow="${esc(i.id)}" data-on="${i.following ? 1 : 0}"
        title="${i.following ? "following" : "follow this issue"}"
        style="background:none;border:none;cursor:pointer;font-size:15px;line-height:1;
        color:${i.following ? "var(--memory)" : "var(--cream-dim)"}">${i.following ? "★" : "☆"}</button>`}
    </div>`;
  }

  function renderIssues(list, candidates) {
    const box = $("#mem-issuelist", el);
    if (!list.length) {
      box.innerHTML = `<p class="hint" style="padding:6px 0">No issues drawn yet.
        Once a couple of meetings are in the record, press <b>↻ rebuild</b> to draw
        the long view — or “follow this” on any search to start a thread.</p>`;
    } else {
      box.innerHTML = list.map(i => issueRow(i)).join("");
      $$("[data-issue]", box).forEach(r => r.onclick = e => {
        if (e.target.dataset.follow !== undefined) return;
        openIssue(r.dataset.issue);
      });
      $$("[data-follow]", box).forEach(b => b.onclick = async e => {
        e.stopPropagation();
        await toggleFollow(b.dataset.follow, b.dataset.on !== "1");
        loadIssues(); loadThreads();
      });
    }
    const cbox = $("#mem-candidates", el);
    if (candidates && candidates.length) {
      cbox.innerHTML = `<details><summary class="hint" style="cursor:pointer">
        ${candidates.length} candidate issue${candidates.length > 1 ? "s" : ""} — new
        topics a steward can promote, rename, or discard</summary>
        <div style="margin-top:6px">${candidates.map(i => issueRow(i, true)).join("")}</div></details>`;
      $$("[data-issue]", cbox).forEach(r => r.onclick = () => openIssue(r.dataset.issue));
    } else cbox.innerHTML = "";
  }

  async function toggleFollow(iid, on) {
    try { await api("/api/memory/thread", { issue_id: iid, follow: on }); }
    catch (e) { toast(e.message, true); }
  }

  async function loadThreads() {
    try {
      const d = await api("/api/memory/threads");
      renderThreads(d.threads || [], d.unseen || 0);
    } catch (e) { /* threads are additive — silence is fine */ }
  }

  function renderThreads(threads, unseen) {
    const bell = $("#mem-bell", el);
    if (unseen > 0) { bell.style.display = ""; $("#mem-bell-n", el).textContent = unseen; }
    else bell.style.display = "none";
    $("#mem-digestwrap", el).style.display = threads.length ? "" : "none";
    const box = $("#mem-threads", el);
    if (!threads.length) {
      box.innerHTML = `<p class="hint" style="padding:6px 0">Not following anything yet.
        Tap ☆ on an issue, or “follow this” on a search — Memory will note it when the
        issue resurfaces on a new agenda.</p>`;
      return;
    }
    box.innerHTML = threads.map(t => `
      <div class="batchrow hl-click" data-issue="${esc(t.issue_id)}" style="align-items:center">
        <div>
          <div class="bname" style="font-size:12.5px">${esc(t.name)}</div>
          <div class="lmeta">${t.n_meetings} appearance${t.n_meetings !== 1 ? "s" : ""}${
            t.last_seen ? " · last " + esc(t.last_seen) : ""}</div>
        </div>
        ${t.unseen ? `<span class="stat-chip stat-running">${t.unseen} new</span>`
          : `<span class="lmeta">watching</span>`}
      </div>`).join("");
    $$("[data-issue]", box).forEach(r => r.onclick = () => openIssue(r.dataset.issue));
  }

  async function ackNotifications() {
    try { await api("/api/memory/thread/ack", {}); loadThreads(); } catch (e) {}
  }

  async function rebuildIssues() {
    const btn = $("#mem-rebuild", el);
    btn.disabled = true; const was = btn.textContent; btn.textContent = "↻ drawing…";
    try {
      const r = await api("/api/memory/issues/rebuild", {});
      watchJob(r.job.id, j => { if (j.message) btn.textContent = "↻ " + j.message.slice(0, 22); });
      await jobDone(r.job.id);
      loadIssues();
      toast("the long view is redrawn");
    } catch (e) { toast(e.message, true); }
    btn.disabled = false; btn.textContent = was;
  }

  async function copyDigest() {
    try {
      const d = await api("/api/memory/digest");
      await navigator.clipboard.writeText(d.markdown || "");
      toast("the digest is on your clipboard — paste it anywhere");
    } catch (e) { toast("couldn't copy — " + e.message, true); }
  }

  /* ---------------- one issue (the long view across meetings) ---------------- */

  async function openIssue(id) {
    try {
      const d = await api("/api/memory/issue", { id });
      stop(); $("#mem-ytframe", el).src = "";       // leave any playing meeting
      S.view = "issue"; S.iid = id; S.issue = d.issue; S.session = false;
      hideAllViews();
      $("#mem-issue", el).style.display = "";
      const i = d.issue;
      $("#mem-iname", el).textContent = i.name;
      $("#mem-ioverview", el).textContent = d.overview || "";
      $("#mem-idisclose", el).textContent =
        ((i.name_origin || "").startsWith("ai:")
          ? "Issue named by " + i.name_origin.slice(3) + " · "
          : "Named from the record's own words · ")
        + "officials-only aggregation — residents stay within their meeting · "
        + "supplements the official record, never replaces it.";
      renderFollow(i.following);
      const chips = [];
      (i.aliases || []).slice(0, 10).forEach(a =>
        chips.push(`<span class="tpill" style="background:var(--ink-3);color:var(--cream-dim)">${esc(a)}</span>`));
      (i.related || []).slice(0, 8).forEach(a =>
        chips.push(`<span class="tpill" style="background:var(--ink-2);color:var(--cream-faint)" title="in this issue's vocabulary">${esc(a)}</span>`));
      $("#mem-ialiases", el).innerHTML = chips.join("");
      $("#mem-idelta", el).innerHTML = d.latest_delta
        ? `<div class="hl-panel" style="margin-top:12px;border-color:var(--memory)">
            <span class="tag">what changed, last time</span>
            <p style="font-size:13px;line-height:1.6">${esc(d.latest_delta)}</p>
            <p class="hint">The delta on a resurfacing — generative with your key, extractive otherwise. Verify against the official record.</p></div>`
        : "";
      renderTimeline(d.timeline || []);
      renderLedger(d.ledger || []);
      renderPaper(d.paper || []);
      renderAppearances(d.timeline || []);
      try { el.querySelector(".page-pad").scrollTop = 0; } catch (e) {}
    } catch (e) { toast(e.message, true); }
  }

  const RC = v => {
    const c = { yes: "var(--forest)", no: "var(--memory)", abstain: "var(--cream-faint)" }[v] || "var(--cream-dim)";
    const t = { yes: "aye", no: "no", abstain: "abs" }[v] || esc(v);
    return `<span style="font:600 9.5px var(--mono);text-transform:uppercase;color:${c};border:1px solid var(--line);border-radius:4px;padding:0 4px">${t}</span>`;
  };

  function renderLedger(ledger) {
    const box = $("#mem-iledger", el);
    if (!ledger.length) { box.innerHTML = ""; return; }
    box.innerHTML = `<div class="hl-panel" style="margin-top:14px">
      <span class="tag">the vote ledger — roll calls on this issue, read from the record</span>
      ${ledger.map(v => `
        <div style="border:1px solid var(--line);border-radius:8px;margin-top:8px;overflow:hidden">
          <div class="hl-seg hl-click" data-open="${esc(v.meeting_id)}" data-t="${v.t}"
            style="padding:7px 10px;background:var(--ink-3);font-size:12.5px">
            <span class="tpill" style="margin-right:6px">${esc(v.date || "")}</span>
            ${esc((v.motion || "").slice(0, 90))}
            <span class="hl-kind hl-kind-money" style="margin-left:6px">${esc(v.tally || "")} ${esc(v.outcome || "")}</span>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:6px 12px;padding:8px 10px">
            ${(v.roll || []).map(r => `<span class="hl-click" data-open="${esc(v.meeting_id)}" data-t="${r.t || v.t}"
              style="font-size:12px;cursor:pointer">${esc(r.name)} ${RC(r.vote)}</span>`).join("")}
          </div>
        </div>`).join("")}
      <p class="hint" style="margin-top:8px">Roll calls are read from the transcript and may mishear a name — verify against the official minutes.</p>
    </div>`;
    $$("[data-open]", box).forEach(r => r.onclick = () =>
      openMeeting(r.dataset.open, parseFloat(r.dataset.t || 0)));
  }

  function renderPaper(paper) {
    const box = $("#mem-ipaper", el);
    if (!paper.length) { box.innerHTML = ""; return; }
    box.innerHTML = `<div class="hl-panel" style="margin-top:14px">
      <span class="tag">the town's paper — documents linked to this issue</span>
      ${paper.map(d => `
        <div style="padding:7px 4px;border-left:2px solid var(--amber);padding-left:10px;margin-top:6px">
          ${d.url ? `<a href="${esc(d.url)}" target="_blank" rel="noopener" style="font-weight:600;color:var(--memory)">📄 ${esc(d.kind || "document")} — ${esc((d.title || "").slice(0, 60))}</a>`
            : `<b>📄 ${esc(d.kind || "document")}</b>`}
          <span class="lmeta" style="margin-left:6px">${esc(d.date || "")} · ${d.n} cite${d.n !== 1 ? "s" : ""}</span>
          ${(d.cites || []).slice(0, 3).map(c => `<div class="lmeta" style="margin-left:14px;color:var(--cream-dim)">p.${c.page} · ${esc((c.text || "").slice(0, 90))}</div>`).join("")}
        </div>`).join("")}
    </div>`;
  }

  function renderFollow(on) {
    const b = $("#mem-followbtn", el);
    b.textContent = on ? "★ following" : "☆ follow this issue";
    b.classList.toggle("primary", !on);
    b.onclick = async () => { await toggleFollow(S.iid, !on); renderFollow(!on); loadThreads(); };
  }

  function renderTimeline(nodes) {
    const box = $("#mem-timeline", el);
    if (!nodes.length) { box.innerHTML = `<p class="hint">No appearances yet.</p>`; return; }
    box.innerHTML = `<div style="display:flex;align-items:stretch;min-width:min-content">
      ${nodes.map((n, idx) => timelineNode(n, idx, nodes.length)).join("")}</div>`;
    $$("[data-open]", box).forEach(r => r.onclick = () =>
      openMeeting(r.dataset.open, parseFloat(r.dataset.t || 0)));
  }

  function timelineNode(n, idx, total) {
    const beads = (n.beads || []).slice(0, 5);
    const miles = (n.milestones || []);
    const docs = (n.documents || []);
    const nVotes = miles.filter(m => m.kind === "vote").length;
    const tags = [];
    if (nVotes) tags.push(`<span style="color:var(--memory)">${nVotes} ⬡ vote${nVotes > 1 ? "s" : ""}</span>`);
    if (docs.length) tags.push(`<span style="color:var(--amber)">${docs.length} 📄</span>`);
    return `<div style="min-width:210px;max-width:240px;flex:0 0 auto;padding:0 12px;position:relative">
      <div style="position:absolute;top:8px;left:0;right:0;height:2px;background:var(--line)"></div>
      ${idx === 0 ? `<div style="position:absolute;top:8px;left:0;width:50%;height:2px;background:var(--ink-2)"></div>` : ""}
      ${idx === total - 1 ? `<div style="position:absolute;top:8px;right:0;width:50%;height:2px;background:var(--ink-2)"></div>` : ""}
      <div style="text-align:center;position:relative">
        <span style="display:inline-block;width:13px;height:13px;border-radius:50%;background:var(--memory);border:3px solid var(--ink);position:relative;z-index:1"></span>
      </div>
      <div style="text-align:center;margin-top:6px">
        <div class="lmeta" style="color:var(--cream)">${esc(n.date || "undated")}</div>
        <div style="font-size:11.5px;color:var(--cream-dim);margin-top:2px">${esc((n.body || n.title || "").slice(0, 42))}</div>
        <div class="lmeta">${n.n} moment${n.n !== 1 ? "s" : ""}${tags.length ? " · " + tags.join(" · ") : ""}</div>
      </div>
      <div style="margin-top:8px;display:flex;flex-direction:column;gap:4px">
        ${beads.map(b => `<div class="hl-seg hl-click" data-open="${esc(n.meeting_id)}" data-t="${b.t}"
            style="padding:4px 6px;border-radius:6px;background:var(--ink-2);font-size:11px">
            <span class="tpill" style="margin-right:5px">${hms(b.t)}</span>${esc((b.text || "").slice(0, 52))}</div>`).join("")}
        ${miles.map(m => `<div class="hl-seg hl-click" data-open="${esc(n.meeting_id)}" data-t="${m.t}"
            style="padding:4px 6px;border-radius:6px;background:var(--ink-3);font-size:11px;border-left:2px solid var(--memory)">
            ${m.kind === "vote" ? "⬡" : "◆"} <span class="tpill" style="margin-right:5px">${hms(m.t)}</span>${esc((m.text || "").slice(0, 42))}
            ${m.tally ? ` <span class="tpill" style="margin-left:3px">${esc(m.tally)}</span>` : ""}
            ${m.outcome ? ` <span class="hl-kind hl-kind-money">${esc(m.outcome)}</span>` : ""}</div>`).join("")}
        ${docs.map(d => `<div style="padding:4px 6px;border-radius:6px;background:var(--ink-2);font-size:11px;border-left:2px solid var(--amber)">
            ${d.url ? `<a href="${esc(d.url)}" target="_blank" rel="noopener" style="color:var(--cream)">📄 ${esc((d.kind || "doc"))}</a>` : `📄 ${esc(d.kind || "doc")}`}
            ${d.cites && d.cites[0] ? ` <span class="lmeta">p.${d.cites[0].page}</span>` : ""}</div>`).join("")}
      </div>
    </div>`;
  }

  function renderAppearances(nodes) {
    const box = $("#mem-iappearances", el);
    box.innerHTML = nodes.map(n => `
      <div class="hl-panel" style="margin-top:12px">
        <span class="tag">${esc(n.date || "undated")} — ${esc(n.title || n.meeting_id)} ·
          ${n.n} moment${n.n !== 1 ? "s" : ""}</span>
        ${(n.beads || []).map(b => `
          <div class="hl-seg hl-click" data-open="${esc(n.meeting_id)}" data-t="${b.t}" style="padding:5px 4px">
            <span class="tpill" style="margin-right:7px">${hms(b.t)}</span>
            ${b.speaker ? `<b style="font-size:11px;color:var(--cream-dim)">${esc(b.speaker)}:</b> ` : ""}
            <span style="font-size:12.5px">${esc(b.text)}</span>
            ${b.why === "related" ? ` <span class="lmeta" style="color:var(--cream-faint)">· related language</span>` : ""}
            ${window.czTray ? czTray.btnHTML({ source: "vid:" + n.meeting_id,
              start: Math.max(0, b.t - 2), end: b.t + 12,
              label: (b.text || "").slice(0, 80),
              title: (n.title || n.meeting_id || "").slice(0, 60) }) : ""}
          </div>`).join("")}
      </div>`).join("");
    $$("[data-open]", box).forEach(r => r.onclick = () =>
      openMeeting(r.dataset.open, parseFloat(r.dataset.t)));
  }

  /* ---------------- view switching ---------------- */

  function showMeeting() { S.view = "meeting"; }
  function hideAllViews() {
    $("#mem-record", el).style.display = "none";
    $("#mem-meeting", el).style.display = "none";
    $("#mem-issue", el).style.display = "none";
    $("#mem-analytics", el).style.display = "none";
    $("#mem-officials", el).style.display = "none";
  }
  function openAnalytics() {
    stop();
    S.view = "analytics";
    hideAllViews();
    $("#mem-analytics", el).style.display = "";
    czAnalytics.renderInto($("#mem-anbody", el), {});
  }

  async function openOfficials() {
    stop(); $("#mem-ytframe", el).src = "";
    S.view = "officials"; hideAllViews();
    $("#mem-officials", el).style.display = "";
    const box = $("#mem-offbody", el);
    box.innerHTML = `<p class="hint">reading the roll calls…</p>`;
    try {
      const d = await api("/api/memory/officials");
      const offs = d.officials || [];
      if (!offs.length) { box.innerHTML = `<p class="hint">No roll calls on the record yet. Fetch a meeting's documents, then re-read its votes.</p>`; return; }
      box.innerHTML = `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px">
        ${offs.map(o => `<div class="hl-panel">
          <div style="display:flex;justify-content:space-between;align-items:baseline">
            <b style="font-size:16px">${esc(o.name)}</b>
            <span class="lmeta">${esc(o.town || "")}</span></div>
          <div style="display:flex;gap:6px;align-items:center;margin:8px 0;flex-wrap:wrap">
            ${RC("yes")} ${o.yes} · ${RC("no")} ${o.no} · ${RC("abstain")} ${o.abstain}
            <span class="lmeta" style="margin-left:auto">${o.total} recorded votes</span></div>
          <div style="display:flex;flex-wrap:wrap;gap:4px">
            ${(o.votes || []).slice(0, 30).map(v => `<span class="hl-click" data-open="${esc(v.meeting_id)}" data-t="${v.t || 0}"
              title="${esc((v.motion || "").slice(0, 80))}" style="cursor:pointer">${RC(v.vote)}</span>`).join("")}
          </div></div>`).join("")}
      </div>`;
      $$("[data-open]", box).forEach(r => r.onclick = () =>
        openMeeting(r.dataset.open, parseFloat(r.dataset.t || 0)));
    } catch (e) { box.innerHTML = `<p class="hint">${esc(e.message)}</p>`; }
  }

  async function publishRecord() {
    const wrap = $("#mem-publishwrap", el);
    const btn = $("#mem-publishbtn", el);
    btn.disabled = true;
    try {
      const r = await api("/api/memory/publish", {});
      const p = czProgress(wrap, { label: "pressing the public edition…", acc: "var(--memory)" });
      watchJob(r.job.id, j => p.update(j));
      const done = await jobDone(r.job.id);
      p.finish(done);
      if (done.status === "error") { toast(done.error, true); btn.disabled = false; return; }
      const res = done.result || {};
      const added = (res.meetings_added || []);
      const deltas = Object.entries(res.count_deltas || {})
        .map(([k, v]) => `${v > 0 ? "+" : ""}${v} ${k}`).join(" · ");
      wrap.innerHTML = `<div class="hl-panel" style="border-color:var(--memory)">
        <span class="tag">edition pressed — ${esc(res.edition_date || "")} · ${res.meetings} meetings · ${res.issues} issues</span>
        <p style="font-size:13px;margin-top:6px">
          ${res.changed ? "" : "No change since the last pressing — "}${added.length ? `${added.length} meeting(s) added. ` : ""}${deltas ? esc(deltas) + ". " : ""}
          Fingerprint <code>${esc(res.corpus_hash || "")}</code>${res.prev_hash && res.prev_hash !== res.corpus_hash ? ` (was ${esc(res.prev_hash)})` : ""}.
          ${res.budget_busts ? `<span style="color:var(--memory)">⚠ ${res.budget_busts} budget bust(s).</span>` : ""}</p>
        <p class="hint">Now push it live (the desk never deploys itself):</p>
        <pre style="background:var(--ink-3);padding:10px;border-radius:8px;overflow:auto;font-size:11px;user-select:all">git worktree add /tmp/ghp -B gh-pages origin/gh-pages
cp -R site/docs/app /tmp/ghp/app
cd /tmp/ghp && git add app && git commit -m "Deploy: the record, ${esc(res.edition_date || "")}" && git push origin gh-pages
cd - && git worktree remove /tmp/ghp --force && git branch -D gh-pages
# then poll https://control-z.org/app/ until it serves the new pressing</pre></div>`;
      toast("edition pressed — the push ritual is ready to copy");
    } catch (e) { toast(e.message, true); }
    btn.disabled = false;
  }

  async function fetchDocuments(mid) {
    const host = $("#mem-reading", el);
    try {
      const r = await api("/api/memory/documents/fetch", { id: mid });
      const p = czProgress(host, { label: "fetching the town's paper…", acc: "var(--memory)" });
      watchJob(r.job.id, j => p.update(j));
      const done = await jobDone(r.job.id);
      p.finish(done);
      if (done.status === "error") { toast(done.error, true); return; }
      const res = done.result || {};
      const n = (res.documents || []).filter(d => !d.error).length;
      toast(n ? `${n} document(s) linked · ${res.votes || 0} roll call(s) re-read` : (res.note || "no matching documents found"));
      if (S.view === "meeting" && S.id === mid) loadDocsVotes(mid);
    } catch (e) { toast(e.message, true); }
  }
  function backToRecord() {
    stop();
    $("#mem-ytframe", el).src = "";
    S.view = "record"; S.session = false; S.clip = null;
    hideAllViews();
    $("#mem-record", el).style.display = "";
    loadCorpus(); loadIssues(); loadThreads();
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
    $("#mem-ibackbtn", el).onclick = backToRecord;
    $("#mem-analyticsbtn", el).onclick = openAnalytics;
    $("#mem-anbackbtn", el).onclick = backToRecord;
    $("#mem-officialsbtn", el).onclick = openOfficials;
    $("#mem-offbackbtn", el).onclick = backToRecord;
    $("#mem-publishbtn", el).onclick = publishRecord;
    $("#mem-rebuild", el).onclick = rebuildIssues;
    $("#mem-bell", el).onclick = ackNotifications;
    $("#mem-digest", el).onclick = copyDigest;
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
    if (arg && arg.openIssue) { openIssue(arg.openIssue); return; }
    backToRecordSilently();
    loadCorpus(); loadIssues(); loadThreads();
    if (arg && arg.q) { $("#mem-q", el).value = arg.q; doSearch(); }
  }
  function backToRecordSilently() {
    S.view = "record";
    hideAllViews();
    $("#mem-record", el).style.display = "";
  }

  registerPage("memory", el, onshow);
  return { onshow };
})();
