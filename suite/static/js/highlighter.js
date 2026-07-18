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
          <div class="hl-term" id="hl-term" style="display:none"></div>
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
          <div class="hl-sumhead"><span class="mark">AI-Powered Summary</span></div>
          <div class="hl-brief" id="hl-brief"><div class="hint">reading…</div></div>
          <div id="hl-briefrow" style="display:flex;gap:7px;margin-top:10px;flex-wrap:wrap;align-items:center">
            <button class="btn cta" id="hl-report" style="width:auto">Generate Full Report</button>
            <button class="btn" id="hl-aibrief" style="width:auto;display:none">↻ Regenerate</button>
            <select id="hl-lang" style="background:#fff;border:1px solid var(--line);border-radius:7px;padding:5px 8px;font-size:12px">
              ${["Spanish", "Portuguese", "Haitian Creole", "French", "Chinese (Simplified)",
                 "Russian", "Vietnamese", "Arabic", "Korean", "Hindi"].map(l =>
                `<option value="${l}">${l}</option>`).join("")}
            </select>
            <button class="btn" id="hl-trsum" style="width:auto"
              title="translate this summary — your key; lands as a .txt too">Translate summary</button>
          </div>
          <div id="hl-reportout" style="display:none;margin-top:10px;border-top:1px dashed var(--line);padding-top:8px"></div>
        </div>
      </div>

      <div class="hl-pills" id="hl-pills">
        <button class="hl-pill on" data-sec="highlight">Meeting Highlighter</button>
        <button class="hl-pill" data-sec="edit">Highlight Video Editor</button>
        <button class="hl-pill" data-sec="analyze">Meeting Analyzer</button>
        <span class="hl-meta-line" id="hl-metaline"></span>
      </div>

      <!-- HIGHLIGHT -->
      <div id="hl-sec-highlight">
        <div class="hl-grid">
          <div style="display:flex;flex-direction:column;gap:14px;min-width:0">
            <div class="hl-panel" id="hl-agendabox" style="display:none">
              <span class="tag">agenda — the upload's own chapters, clickable</span>
              <div id="hl-agenda" class="hl-results" style="max-height:180px"></div>
            </div>
            <div class="hl-panel">
              <span class="tag">search every word</span>
              <div class="hl-searchrow">
                <input type="text" id="hl-q" placeholder="crosswalk, override, a name…" spellcheck="false">
              </div>
              <div class="hl-spark"><canvas id="hl-sparkline"></canvas></div>
              <div class="hl-results" id="hl-qout"></div>
            </div>
            <div class="hl-panel">
              <span class="tag">transcript — click ✓ to keep a moment for the reel
                <button id="hl-follow" class="chip" style="margin-left:8px;text-transform:none;letter-spacing:0"
                  title="scroll the transcript along with playback">follow</button></span>
              <div class="hl-transcript" id="hl-transcript">
                <div class="empty-grain" style="padding:30px 8px;color:var(--cream-faint);text-align:center">no words yet</div>
              </div>
              <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">
                <button class="btn" id="hl-transcribe" style="width:auto">Upgrade words with Scribe</button>
                <select id="hl-model" style="background:#fff;border:1px solid var(--line);border-radius:7px;padding:5px 8px;font-size:12px">
                  <option value="base">base — quick</option>
                  <option value="small">small — better</option>
                  <option value="large-v3-turbo" selected>large-v3-turbo — best balance</option>
                  <option value="large-v3">large-v3 — most accurate (names)</option>
                </select>
                <button class="btn" id="hl-txt" style="width:auto">Transcript .txt</button>
                <button class="btn" id="hl-srt" style="width:auto">.srt</button>
                <button class="btn" id="hl-trtxt" style="width:auto"
                  title="AI-translate the whole transcript into the language chosen up in the summary card — .srt + .txt land beside the meeting">Translate transcript…</button>
                <button class="btn" id="hl-invsel" style="width:auto"
                  title="select a name in the transcript, then look it up — news, Wikipedia, maps, and your own library">🔍 Investigate selection</button>
              </div>
              <div style="display:flex;gap:8px;margin-top:8px;align-items:center">
                <input type="text" id="hl-hotwords" spellcheck="false" placeholder="names to teach Whisper — auto-filled from this meeting; edit freely"
                  title="people, places and boards from this meeting's own captions/title — Whisper's decoder is biased toward them so proper names land right"
                  style="flex:1;background:#fff;border:1px solid var(--line);border-radius:7px;padding:5px 8px;font-size:12px">
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
                <button class="btn cta bright" id="hl-detect" style="flex:1"
                  title="local scoring — every pick says why, no key needed">✨ Make Highlight Reel</button>
              </div>
              <div style="display:none;margin-bottom:8px" id="hl-aireel-row">
                <button class="btn" id="hl-aireel" style="width:100%"
                  title="generative — the model reads the timestamped transcript with YOUR key and proposes moments; each is validated against the clock">🤖 Make AI Highlight Reel — your key</button>
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
                  <button class="btn" id="hl-askai" style="padding:8px 10px;display:none"
                    title="generative answer grounded in the retrieved passages — your Anthropic key (Settings → AI)">✨ AI</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- EDIT -->
      <div id="hl-sec-edit">
        <div class="hl-nle">
          <div class="hl-toolrow">
            <span class="tag">the reel</span>
            <span class="clipcount" id="hl-clipcount">0 clips</span>
            <span style="flex:1"></span>
            <button class="btn" id="hl-prev">⏮</button>
            <button class="btn" id="hl-playreel">▶ Play reel</button>
            <button class="btn" id="hl-next">⏭</button>
            <button class="btn" id="hl-clear">Clear</button>
            <button class="btn" id="hl-edl">Selects EDL</button>
            <button class="btn cta bright" id="hl-export" style="padding:8px 22px;font-weight:700">Export Video</button>
          </div>
          <div class="hl-timeline" id="hl-timeline">
            <div class="hint" style="padding:20px;color:#8C9086">nothing on the timeline —
              Make Highlights, keep transcript moments, or + Add from the highlights list</div>
          </div>
          <div class="progmsg" id="hl-reelmsg" style="color:#B9BDB2"></div>
        </div>
        <div class="hl-grid" style="padding-top:0">
          <div class="hl-panel">
            <span class="tag">download clips — only the moments you kept</span>
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:4px">
              <select id="hl-quality" title="applies to every download on this page"
                style="background:#fff;border:1px solid var(--line);border-radius:7px;padding:6px 8px;font-size:12px">
                <option value="best">best available</option>
                <option value="2160">4K (2160p)</option>
                <option value="1440">1440p</option>
                <option value="1080" selected>1080p</option>
                <option value="720">720p</option>
                <option value="480">480p</option>
                <option value="audio">audio only</option>
              </select>
              <button class="btn cta bright" id="hl-dlsections" style="flex:1;min-width:200px">⬇ Download highlight clips</button>
            </div>
            <div class="hint" id="hl-dlhint" style="margin-top:6px"></div>
            <div style="display:flex;gap:8px;align-items:center;margin-top:10px;padding-top:8px;border-top:1px dashed var(--line)">
              <button class="btn" id="hl-dlfull" style="width:auto">Download full video</button>
              <span class="hint" id="hl-dlfullhint" style="flex:1">the whole recording — only if you really want all of it</span>
            </div>
            <div class="progmsg" id="hl-dlmsg"></div>
            <div id="hl-dlfiles" style="margin-top:6px"></div>
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
            <div class="checkrow"><input type="checkbox" id="hl-cards">
              <span>title cards <div class="hint">an ink card before each moment —
                the meeting, the moment's words, its timestamp. Context, not decoration.</div></span>
            </div>
            <div class="hint">local file → the reel renders straight from it. URL session →
              download the kept sections first; they stitch into one reel.</div>
            <div class="report" id="hl-report"></div>
          </div>
        </div>
      </div>

      <!-- ANALYZE -->
      <div id="hl-sec-analyze">
        <div class="hl-ana" id="hl-ana"></div>
      </div>
    </div>

    <!-- CLIPS modal: any viz, opened into its moments -->
    <div id="hl-clipsmodal" class="hl-overlay" style="display:none">
      <div class="hl-modal" style="width:min(680px,94vw)">
        <div style="display:flex;align-items:baseline;gap:10px">
          <h2 style="margin:0;font-size:17px" id="hl-cm-title">Moments</h2>
          <span class="hint" id="hl-cm-meta"></span>
          <button class="btn" id="hl-cm-addall" style="margin-left:auto;width:auto;padding:3px 12px">+ all to reel</button>
          <button class="btn" id="hl-cm-close" style="width:auto;padding:3px 12px">✕</button>
        </div>
        <div id="hl-cm-rows" style="max-height:56vh;overflow-y:auto;margin-top:10px"></div>
      </div>
    </div>

    <!-- INVESTIGATE modal: a name, looked up -->
    <div id="hl-invmodal" class="hl-overlay" style="display:none">
      <div class="hl-modal" style="width:min(640px,94vw)">
        <div style="display:flex;align-items:baseline;gap:10px">
          <h2 style="margin:0;font-size:17px">🔍 <span id="hl-inv-q"></span></h2>
          <button class="btn" id="hl-inv-close" style="margin-left:auto;width:auto;padding:3px 12px">✕</button>
        </div>
        <div class="hl-invtabs" id="hl-invtabs">
          <button class="chip on" data-tab="news">News</button>
          <button class="chip" data-tab="wiki">Wikipedia</button>
          <button class="chip" data-tab="maps">Maps</button>
          <button class="chip" data-tab="library">Your library</button>
        </div>
        <div id="hl-inv-body" style="max-height:52vh;overflow-y:auto;margin-top:10px;font-size:13px"></div>
      </div>
    </div>

    <!-- EXPORT VIDEO modal: two doors out -->
    <div id="hl-exportmodal" style="display:none">
      <div class="hl-modal">
        <div style="display:flex;align-items:baseline;gap:10px">
          <h2 style="margin:0;font-size:19px">Export Video</h2>
          <span class="hint" id="hl-exp-meta"></span>
          <button class="btn" id="hl-exp-close" style="margin-left:auto;width:auto;padding:3px 12px">✕</button>
        </div>
        <div class="hl-exp-doors">
          <div class="hl-exp-door" id="hl-exp-sharedoor">
            <h3>🔗 Share a reel link</h3>
            <p>A link to the web player — the reel plays right in the browser
              through YouTube, nothing rendered, nothing uploaded. The clips
              live in the link itself.</p>
            <button class="btn cta" id="hl-exp-share" style="width:100%">Create share link</button>
            <div id="hl-exp-shareout" style="display:none;margin-top:8px">
              <textarea id="hl-exp-url" readonly rows="3" spellcheck="false"
                style="width:100%;font-size:11px;font-family:inherit;border:1px solid var(--line);border-radius:7px;padding:6px;background:#fff;resize:none"></textarea>
              <div style="display:flex;gap:8px;margin-top:6px">
                <button class="btn" id="hl-exp-copy" style="flex:1">📋 Copy URL</button>
                <button class="btn" id="hl-exp-open" style="flex:1">Open player</button>
              </div>
            </div>
            <div class="hint" id="hl-exp-sharenote" style="margin-top:6px"></div>
          </div>
          <div class="hl-exp-door">
            <h3>⬇ Download &amp; edit on this computer</h3>
            <p id="hl-exp-dlwhat">Only the kept spans leave YouTube, then ffmpeg
              cuts them into one MP4 — with title cards if you've checked them.</p>
            <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px">
              <select id="hl-exp-quality" style="background:#fff;border:1px solid var(--line);border-radius:7px;padding:5px 8px;font-size:12px">
                <option value="best">best available</option>
                <option value="1080" selected>1080p</option>
                <option value="720">720p</option>
                <option value="480">480p</option>
              </select>
              <button class="btn cta bright" id="hl-exp-go" style="flex:1">Make the MP4</button>
            </div>
            <div id="hl-exp-stages"></div>
            <div class="hint" style="margin-top:8px">exports run in the background —
              close this and keep working; the card in the corner carries the progress,
              and the Queue holds the file when it's done</div>
          </div>
        </div>
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
      const viaProxy = st.proxy && st.proxy.enabled;
      chip.textContent = "yt-dlp " + (st.installed ? `nightly ${st.installed}` : "missing")
        + (viaProxy ? " · webshare" : "");
      chip.classList.toggle("ok", ok);
      chip.classList.toggle("err", !ok);
      chip.title = (st.detail || "") + (viaProxy
        ? ` — fetches ride your Webshare residential proxy (${st.proxy.username_masked})`
        : " — no proxy configured (Settings → fetch network, if YouTube gates captions)");
    } catch (e) { chip.textContent = "yt-dlp ?"; }
  }

  /* ---------------- landing: finder + library ---------------- */
  async function finder() {
    const box = $("#hl-findout", el);
    const q = $("#hl-findq", el).value.trim();
    if (!q) return;
    // the search rides yt-dlp's own ytsearch — 10-20s is its honest speed,
    // so the wait SHOWS work: staged messages, a sweep bar, elapsed time
    const t0 = Date.now();
    const stages = [
      "asking YouTube's search index…",
      "no API key involved — this is yt-dlp's own crawl…",
      "reading result metadata…",
      "matching civic channels…",
      "nearly there — sorting what came back…",
    ];
    box.innerHTML = `<div class="hl-searching">
      <div class="hl-sweep"><i></i></div>
      <span id="hl-findmsg">${stages[0]}</span>
      <span class="hint" id="hl-findsec" style="margin-left:auto">0s</span>
    </div>`;
    const tick2 = setInterval(() => {
      const s = Math.floor((Date.now() - t0) / 1000);
      const m = $("#hl-findmsg", box);
      const sec = $("#hl-findsec", box);
      if (!m) { clearInterval(tick2); return; }
      m.textContent = stages[Math.min(stages.length - 1, Math.floor(s / 4))];
      sec.textContent = s + "s";
    }, 1000);
    try {
      const r = await api("/api/highlighter/finder", { q });
      clearInterval(tick2);
      box.innerHTML = r.rows.map(v => `
        <div class="hl-result" style="display:flex;gap:8px;align-items:baseline">
          <span style="flex:1">${esc(v.title || v.id)}
            <span style="color:var(--cream-faint);font-size:11px"> · ${esc(v.uploader || "")}
            ${v.duration ? " · " + fmtTime(v.duration) : ""}</span></span>
          <button class="btn cta" style="padding:3px 12px;font-size:11.5px" data-url="${esc(v.url)}">Load</button>
        </div>`).join("") || `<div class="hint">nothing found</div>`;
      $$("button[data-url]", box).forEach(b => b.onclick = () => ingest(b.dataset.url));
    } catch (e) {
      clearInterval(tick2);
      box.innerHTML = `<div class="progmsg err">${esc(e.message)}</div>`;
    }
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
  /* the loading terminal — the web app's sign that everything is in motion */
  function termLine(text, cls) {
    const t = $("#hl-term", el);
    t.style.display = "";
    t.insertAdjacentHTML("beforeend",
      `<div class="tl${cls ? " " + cls : ""}">${text}</div>`);
    t.scrollTop = t.scrollHeight;
  }

  async function ingest(url) {
    if (!url) return;
    const btn = $("#hl-load", el);
    btn.disabled = true;
    btn.textContent = "Reading…";
    const t = $("#hl-term", el);
    t.innerHTML = "";
    termLine(`<b>$</b> highlighter read ${esc(url.slice(0, 70))}`);
    termLine(`<b>$</b> yt-dlp --skip-download --write-subs · watch-page timedtext · racing…`);
    let lastMsg = "";
    try {
      const job = await api("/api/highlighter/ingest", { url });
      const off = watchJob(job.id, j => {
        if (j.message && j.message !== lastMsg) {
          lastMsg = j.message;
          termLine(`  ${esc(j.message)}`);
        }
      });
      const done = await jobDone(job.id);
      off();
      btn.disabled = false;
      btn.textContent = "Load Meeting";
      if (done.status === "error") {
        termLine(`✗ ${esc(done.error || "failed")}`, "err");
        toast(done.error, true);
        return;
      }
      if (done.status !== "done") return;
      const nseg = done.result.transcript?.segments?.length || 0;
      termLine(`✓ ${nseg} segments · brief, entities, agenda computing locally`, "ok");
      termLine(`✓ opening the meeting…`, "ok");
      $("#hl-url", el).value = "";
      if (done.result.captions_note) toast(done.result.captions_note, true);
      setTimeout(() => { t.style.display = "none"; }, 400);
      open(done.result.source);
    } catch (e) {
      btn.disabled = false; btn.textContent = "Load Meeting";
      termLine(`✗ ${esc(e.message)}`, "err");
      toast(e.message, true);
    }
  }

  async function open(source) {
    try {
      S.source = source;
      S.keep = new Set(); S.timeline = []; S.picks = []; S.lane = [];
      S.insight = null; S.curClip = -1; S.sectionFiles = [];
      S.docs = null; S.docsBusy = false; S.xrPos = null;
      renderDlFiles();
      $("#hl-reportout", el).style.display = "none";
      $("#hl-reportout", el).innerHTML = "";
      $("#hl-aibrief", el).style.display = "none";
      llmCheck();
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
  //
  // Local files tick on the <audio> element. URL sessions tick on the
  // embed's own widget messages: send {event:"listening"} and YouTube
  // answers every frame with infoDelivery {currentTime}. One knob —
  // nowTime() — feeds the clock display, the sparkline playhead and the
  // follow-along transcript in both modes.

  const nowTime = () => S.session ? (S.sessionTime || 0) : audio.currentTime;

  function wireSessionClock() {
    const f = $("#hl-ytframe", el);
    const hello = () => {
      try {
        f.contentWindow.postMessage(JSON.stringify(
          { event: "listening", id: "czhl", channel: "widget" }), "*");
      } catch (e) {}
    };
    f.addEventListener("load", () => { S.sessionTime = 0; hello(); });
    addEventListener("message", e => {
      if (!/https:\/\/(www\.)?youtube(-nocookie)?\.com/.test(e.origin)) return;
      let d;
      try { d = JSON.parse(e.data); } catch (err) { return; }
      if (d.event === "onReady") hello();
      const info = d.info || {};
      if (typeof info.currentTime === "number") {
        S.sessionTime = info.currentTime;
        if (typeof info.playerState === "number")
          S.ytPlaying = info.playerState === 1;
        if (S.session && CZ.current === "highlighter") {
          $("#hl-time", el).textContent = fmtTime(S.sessionTime);
          drawSpark();
          followTranscript();
        }
      }
    });
  }

  /* -- follow-along: the transcript scrolls with the meeting ---------- */
  let followOn = false, lastNow = -1;
  function followTranscript() {
    if (!S.t || !S.t.segments.length) return;
    const t = nowTime();
    if (Math.abs(t - lastNow) < 0.4) return;
    lastNow = t;
    const segs = S.t.segments;
    let lo = 0, hi = segs.length - 1, si = 0;
    while (lo <= hi) {                     // binary search the active row
      const mid = (lo + hi) >> 1;
      if (segs[mid].start <= t) { si = mid; lo = mid + 1; } else hi = mid - 1;
    }
    const box = $("#hl-transcript", el);
    const prev = $(".hl-seg.now", box);
    if (prev && +prev.dataset.si === si) return;
    if (prev) prev.classList.remove("now");
    const rowEl = $(`.hl-seg[data-si="${si}"]`, box);
    if (rowEl) {
      rowEl.classList.add("now");
      if (followOn) rowEl.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }
  function seek(t, play) {
    if (S.session) {
      const f = $("#hl-ytframe", el);
      f.contentWindow.postMessage(JSON.stringify(
        { event: "command", func: "seekTo", args: [t, true] }), "*");
      if (play) f.contentWindow.postMessage(JSON.stringify(
        { event: "command", func: "playVideo", args: [] }), "*");
      if (play) S.ytPlaying = true;
      S.sessionTime = t;               // snappy: don't wait for the embed
      $("#hl-time", el).textContent = fmtTime(t);
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
      S.ytPlaying = false;
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
    followTranscript();
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

  let transcriptJob = 0;   // token: a re-render cancels the chunks in flight

  function renderTranscript() {
    const box = $("#hl-transcript", el);
    const job = ++transcriptJob;
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
    const row = (seg, si) => {
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
    };
    // a 7-hour meeting is 8k+ rows — paint the first screenfuls NOW, stream
    // the rest in chunks between frames so the page never freezes
    const CHUNK = 400;
    const segs = S.t.segments;
    box.innerHTML = segs.slice(0, CHUNK).map(row).join("");
    let i = CHUNK;
    (function more() {
      if (job !== transcriptJob || i >= segs.length) return;
      box.insertAdjacentHTML("beforeend",
        segs.slice(i, i + CHUNK).map((s, k) => row(s, i + k)).join(""));
      i += CHUNK;
      requestAnimationFrame(more);
    })();
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
    const spans = mergedSections();
    const dl = $("#hl-dlsections", el);
    dl.textContent = spans.length
      ? `⬇ Download highlight clips (${spans.length} · ${total.toFixed(0)}s)`
      : "⬇ Download highlight clips";
    dl.disabled = !S.session || !spans.length;
    $("#hl-dlhint", el).textContent = S.session
      ? (spans.length
        ? `only these spans leave YouTube — ${spans.length} clip${spans.length === 1 ? "" : "s"}, `
          + `${total.toFixed(0)}s of a ${S.meta?.duration ? fmtTime(S.meta.duration) : "long"} meeting`
        : "keep moments first (✓ in the transcript, or Make Highlights) — then download only those spans")
      : "this source is already local — downloads are for URL sessions";
    const full = $("#hl-dlfull", el);
    full.disabled = !S.session;
    full.textContent = S.meta?.duration
      ? `Download full video (${fmtTime(S.meta.duration)})` : "Download full video";
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
    // with a key, the executive summary writes itself — the web app's way;
    // the extractive read above stands in until it lands (and without a key)
    if (S.llm?.enabled && b.length) aiBrief(true);
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
    // teach Whisper this meeting's names — prefilled, user-editable
    const hw = $("#hl-hotwords", el);
    if (!hw.value || hw.value === S.autoHotwords) {
      hw.value = S.insight.hotwords || "";
      S.autoHotwords = hw.value;
    }
    renderAgenda();
    renderAnalyze();
  }

  function renderAgenda() {
    const items = (S.insight && S.insight.agenda) || [];
    const boxWrap = $("#hl-agendabox", el);
    boxWrap.style.display = items.length ? "" : "none";
    if (!items.length) return;
    $("#hl-agenda", el).innerHTML = items.map(a => `
      <div class="hl-result" style="display:flex;gap:8px;align-items:baseline">
        <span class="tpill" data-t="${a.t}">${fmtTime(a.t)}</span>
        <span style="flex:1">${esc(a.label)}</span>
      </div>`).join("");
    $$("#hl-agenda .tpill", el).forEach(p =>
      p.onclick = () => seek(+p.dataset.t, true));
  }

  function renderAnalyze() {
    const box = $("#hl-ana", el);
    if (!S.insight) { box.innerHTML = ""; return; }
    const I = S.insight;
    const pill = t => `<span class="tpill" data-t="${t}">${fmtTime(t)}</span>`;
    const ent = I.entities || {};
    // the web app's "People, Places & Things" — one card, every row opens
    const merged = [
      ...(ent.people || []).map(r => ({ ...r, kind: "person" })),
      ...(ent.places || []).map(r => ({ ...r, kind: "place" })),
      ...(ent.organizations || []).map(r => ({ ...r, kind: "org" })),
      ...(ent.money || []).map(r => ({ ...r, kind: "money" })),
    ].sort((a, b) => b.count - a.count).slice(0, 18);
    const tmap = I.topic_map || { topics: [], matrix: [], bins: 12 };
    const tmax = Math.max(1, ...tmap.matrix.flat());
    const qTypes = {};
    (I.questions || []).forEach(q => { qTypes[q.type] = (qTypes[q.type] || 0) + 1; });
    const QCOLORS = { budget: "#A97A16", timeline: "#3FA9D0", accountability: "#B0542D",
                      rationale: "#7E5B8E", information: "#1E7F63" };
    const maxTalk = Math.max(...(I.participation || []).map(p => p.seconds), 1);
    box.innerHTML = `
      <div class="hl-panel" style="grid-column:1 / -1"><span class="tag">people, places &amp; things — click a name: play its moments, add them to the reel, or investigate it in the world</span>
        <div class="hl-pptgrid">
        ${merged.map((r, i) => `<div class="hl-entrow">
          <span class="hl-kind hl-kind-${r.kind}">${r.kind}</span>
          <span style="flex:1;overflow:hidden;text-overflow:ellipsis">${esc(r.name)}</span>
          <span class="cnt">×${r.count}</span>
          <button class="btn" data-clips="${esc(r.name)}" title="every moment that says it">clips</button>
          <button class="btn" data-inv="${esc(r.name)}" title="news · Wikipedia · maps · your library">🔍</button>
        </div>`).join("") || `<div class="hint">none found</div>`}
        </div></div>
      <div class="hl-panel"><span class="tag">decisions — motions and outcomes</span>
        ${(I.decisions || []).map(d => `<div class="hl-qrow">
          <span class="hl-outcome ${d.outcome}">${d.outcome}</span>${pill(d.t)}
          ${esc(d.text)}</div>`).join("") || `<div class="hint">no motions detected</div>`}
      </div>
      <div class="hl-panel"><span class="tag">participation tracker — click a speaker for their moments</span>
        ${(I.participation || []).map(p => `<div class="hl-entrow hl-click" data-spk="${esc(p.speaker)}">
          <span style="flex:0 0 110px;overflow:hidden;text-overflow:ellipsis">${esc(p.speaker)}</span>
          <span class="hl-bar" style="width:${(p.seconds / maxTalk * 100).toFixed(0)}%"></span>
          <span class="cnt">${fmtTime(p.seconds)} · ${p.turns} turns</span></div>`).join("")
        || `<div class="hint">no speaker labels — run the Scribe pass with speakers on</div>`}
      </div>
      <div class="hl-panel" style="grid-column:1 / -1"><span class="tag">topic coverage map — which topics got airtime when; click a cell to open those moments</span>
        <div class="hl-tmap" style="grid-template-columns:110px repeat(${tmap.bins},1fr)">
          ${tmap.topics.map((name, ti) => `
            <span class="hl-tmap-label" title="${esc(name)}">${esc(name)}</span>
            ${tmap.matrix[ti].map((v, bi) => `<button class="hl-tmap-cell" data-topic="${esc(name)}"
              data-bin="${bi}" style="--a:${(v / tmax).toFixed(2)}" title="${esc(name)} · ${v} mention${v === 1 ? "" : "s"}"></button>`).join("")}
          `).join("") || `<div class="hint">nothing recurred enough to map</div>`}
        </div>
      </div>
      <div class="hl-panel" style="grid-column:1 / -1"><span class="tag">framing — eight civic lenses, counted from the meeting's own words; click a lens for its moments</span>
        ${(I.framing?.total) ? (I.framing.lenses || []).map((l, li) => `
          <div class="hl-entrow hl-click hl-lensrow" data-lens="${li}" ${l.count ? "" : 'style="opacity:.45"'}>
            <span style="flex:0 0 116px;display:flex;align-items:center;gap:7px">
              <i style="width:9px;height:9px;border-radius:2px;background:${l.color};display:inline-block"></i>${l.lens}</span>
            <span class="hl-bar" style="width:${Math.max(1, l.share * 100).toFixed(0)}%;background:${l.color}"></span>
            <span class="cnt">×${l.count} · ${l.drift === "rising" ? "↑ rising" : l.drift === "fading" ? "↓ fading" : "steady"}</span>
          </div>`).join("")
        : `<div class="hint">no lens vocabulary detected — unusual for a public meeting</div>`}
        <div class="hint" style="margin-top:5px">a sentence can carry more than one lens — that's how meetings talk; drift compares the meeting's halves</div>
      </div>
      <div class="hl-panel"><span class="tag">question flow — ${(I.questions || []).length} asked; click a type</span>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin:6px 0 8px">
          ${Object.entries(qTypes).map(([k, n]) => `<button class="chip" data-qtype="${k}"
            style="border-color:${QCOLORS[k] || "var(--line)"}">${k} · ${n}</button>`).join("")}
        </div>
        ${(I.questions || []).slice(0, 12).map(q => `<div class="hl-qrow">
          <span class="hl-qtype">${q.type}</span>${pill(q.t)}${esc(q.text)}</div>`).join("")
        || `<div class="hint">no questions detected</div>`}
      </div>
      <div class="hl-panel"><span class="tag">moments of disagreement — tension words, counted; ▶ plays each</span>
        ${(I.disagreements || []).map(d => `<div class="hl-qrow hl-disrow">
          ${pill(d.t)}<span style="flex:1">${d.speaker ? `<b>${esc(d.speaker)}:</b> ` : ""}${esc(d.text)}
          <span class="hint">${(d.words || []).join(" · ")}</span></span></div>`).join("")
        || `<div class="hint">no pushback vocabulary detected</div>`}
      </div>
      <div class="hl-panel" style="grid-column:1 / -1"><span class="tag">cross-reference network — names that share a sentence are connected; thicker line = more often; drag nodes, click a line for the moments together</span>
        <div id="hl-xrwrap" style="position:relative"></div>
        <div class="hint" style="display:flex;gap:14px;margin-top:4px">
          <span><i style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#1E7F63"></i> person</span>
          <span><i style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#3E6C8E"></i> place</span>
          <span><i style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#7E5B8E"></i> organization</span>
          <span><i style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A97A16"></i> keyword</span>
        </div>
      </div>
      <div class="hl-panel" style="grid-column:1 / -1"><span class="tag">relevant documents — the town portal's own paper (CivicClerk, read by BIG Video Grabber's reader)</span>
        <div style="display:flex;gap:8px;align-items:center;margin:6px 0;flex-wrap:wrap">
          <input type="text" id="hl-doctenant" spellcheck="false" title="the part before .api.civicclerk.com"
            style="width:150px;background:#fff;border:1px solid var(--line);border-radius:7px;padding:5px 9px;font-size:12.5px">
          <button class="btn" id="hl-docfind" style="width:auto;padding:5px 14px">Find documents</button>
          <span class="hint" id="hl-docmsg"></span>
        </div>
        <div id="hl-docs"></div>
      </div>
      <div class="hl-panel"><span class="tag">recurring topics</span>
        ${(I.topics || []).map(t => `<div class="hl-entrow hl-click" data-clips="${esc(t.topic)}">${pill(t.t)}
          <span>${esc(t.topic)}</span><span class="cnt">×${t.count}</span></div>`).join("")
        || `<div class="hint">nothing recurred enough</div>`}
      </div>
      <div class="hl-panel"><span class="tag">meeting pace — words per minute, counted
          ${I.pace?.wpm_avg ? `<span style="text-transform:none;letter-spacing:0">· avg ${I.pace.wpm_avg}</span>` : ""}</span>
        <div class="hl-spark" style="height:64px"><canvas id="hl-pacechart" data-click="seek"></canvas></div>
      </div>
      <div class="hl-panel"><span class="tag">discussion dynamics — questions · decisions · tension, counted</span>
        <div class="hl-spark" style="height:84px"><canvas id="hl-dynchart" data-click="seek"></canvas></div>
        <div class="hint" style="display:flex;gap:14px;margin-top:4px">
          <span><i style="display:inline-block;width:9px;height:9px;background:#3FA9D0;border-radius:2px"></i> questions</span>
          <span><i style="display:inline-block;width:9px;height:9px;background:#1E7F63;border-radius:2px"></i> decisions</span>
          <span><i style="display:inline-block;width:9px;height:9px;background:#B0542D;border-radius:2px"></i> tension</span>
        </div>
      </div>`;
    $$("#hl-ana .tpill", box).forEach(p => p.onclick = () => seek(+p.dataset.t, true));
    // every viz opens: clips buttons, investigate, speakers, topic cells, q-types
    $$("button[data-clips], .hl-entrow[data-clips]", box).forEach(b => b.onclick = () => {
      const q = b.dataset.clips;
      clipsModal(`"${q}" — every mention`, segsWith(q));
    });
    $$("button[data-inv]", box).forEach(b => b.onclick = () => investigate(b.dataset.inv));
    $$(".hl-entrow[data-spk]", box).forEach(r => r.onclick = () => {
      const spk = r.dataset.spk;
      clipsModal(`${spk} — their moments`, (S.t?.segments || [])
        .filter(s => s.speaker === spk)
        .map(s => ({ t: s.start, end: s.end, text: s.text })));
    });
    $$(".hl-tmap-cell", box).forEach(c => c.onclick = () => {
      const topic = c.dataset.topic;
      const tm = S.insight.topic_map;
      const binW = (tm.duration || 1) / tm.bins;
      const a = +c.dataset.bin * binW, b2 = a + binW;
      const rows = segsWith(topic).filter(r => r.t >= a && r.t < b2);
      clipsModal(`"${topic}" · ${fmtTime(a)}–${fmtTime(b2)}`, rows);
    });
    $$("button[data-qtype]", box).forEach(b => b.onclick = () => {
      const k = b.dataset.qtype;
      clipsModal(`${k} questions`, (S.insight.questions || [])
        .filter(q => q.type === k)
        .map(q => ({ t: q.t, text: q.text, speaker: q.speaker })));
    });
    $$(".hl-disrow", box).forEach((r, i) => r.onclick = e => {
      if (e.target.closest(".tpill")) return;
      const d = (S.insight.disagreements || [])[i];
      if (d) seek(d.t, true);
    });
    $$(".hl-lensrow", box).forEach(r => r.onclick = () => {
      const l = (S.insight.framing?.lenses || [])[+r.dataset.lens];
      if (!l) return;
      if (!l.count) { toast(`no ${l.lens} vocabulary in this meeting`); return; }
      clipsModal(`${l.lens} framing — ${l.count} counted mention${l.count === 1 ? "" : "s"}`, l.moments);
    });
    renderCrossref();
    const ten = $("#hl-doctenant", box);
    ten.value = localStorage.getItem("cz-doc-tenant") || "brooklinema";
    $("#hl-docfind", box).onclick = () => loadDocuments(true);
    if (S.docs) renderDocuments();
    else loadDocuments(false);
    drawCharts();
  }

  /* -- cross-reference network: an SVG you can rearrange, every line a
        door into its moments. Static ring layout, no physics — the graph
        holds still unless you move it. ---------------------------------- */
  const XR_COLORS = { person: "#1E7F63", place: "#3E6C8E",
                      org: "#7E5B8E", keyword: "#A97A16" };
  function renderCrossref() {
    const wrap = $("#hl-xrwrap", el);
    if (!wrap) return;
    const xr = S.insight?.crossref;
    if (!xr || (xr.nodes || []).length < 3) {
      wrap.innerHTML = `<div class="hint">not enough connected names to draw a network</div>`;
      return;
    }
    const W = 700, H = 420, cx = W / 2, cy = H / 2 + 8;
    if (!S.xrPos || S.xrPos.length !== xr.nodes.length) {
      // most-connected nodes take the inner ring
      const deg = xr.nodes.map((_, i) =>
        xr.edges.reduce((n, e) => n + (e.a === i || e.b === i ? e.count : 0), 0));
      const order = xr.nodes.map((_, i) => i).sort((a, b) => deg[b] - deg[a]);
      S.xrPos = new Array(xr.nodes.length);
      order.forEach((ni, rank) => {
        const ring = rank < 5 ? 88 : 165;
        const slot = rank < 5 ? rank / Math.min(5, order.length)
                              : (rank - 5) / Math.max(1, order.length - 5);
        const ang = slot * 2 * Math.PI - Math.PI / 2 + (rank < 5 ? 0 : 0.3);
        S.xrPos[ni] = { x: cx + Math.cos(ang) * ring * 1.55,
                        y: cy + Math.sin(ang) * ring };
      });
    }
    const P = S.xrPos;
    const maxC = Math.max(...xr.edges.map(e => e.count), 1);
    wrap.innerHTML = `<svg id="hl-xref" viewBox="0 0 ${W} ${H}"
        style="width:100%;max-height:440px;display:block">
      ${xr.edges.map((e, i) => `<line data-edge="${i}"
        x1="${P[e.a].x}" y1="${P[e.a].y}" x2="${P[e.b].x}" y2="${P[e.b].y}"
        stroke="var(--line)" stroke-width="${(1 + 4 * e.count / maxC).toFixed(1)}"
        style="cursor:pointer" />`).join("")}
      ${xr.nodes.map((n, i) => `<g data-node="${i}" style="cursor:grab">
        <circle cx="${P[i].x}" cy="${P[i].y}" r="${Math.min(11, 5 + n.count / 3).toFixed(1)}"
          fill="${XR_COLORS[n.kind] || "#7E7D75"}" />
        <text x="${P[i].x}" y="${P[i].y - Math.min(11, 5 + n.count / 3) - 4}"
          text-anchor="middle" font-size="11" fill="var(--cream)"
          style="pointer-events:none">${esc(n.name)}</text></g>`).join("")}
    </svg>`;
    const svg = $("#hl-xref", wrap);
    const pt = ev => {
      const p = svg.createSVGPoint();
      p.x = ev.clientX; p.y = ev.clientY;
      return p.matrixTransform(svg.getScreenCTM().inverse());
    };
    const lines = $$("line[data-edge]", svg);
    let drag = -1, moved = false;
    // drag moves attributes in place — the svg is never rebuilt mid-drag
    const moveNode = i => {
      const g = $(`g[data-node="${i}"]`, svg);
      const c = $("circle", g), t = $("text", g);
      c.setAttribute("cx", P[i].x); c.setAttribute("cy", P[i].y);
      t.setAttribute("x", P[i].x);
      t.setAttribute("y", P[i].y - (+c.getAttribute("r")) - 4);
      lines.forEach((ln, li) => {
        const e = xr.edges[li];
        if (e.a === i) { ln.setAttribute("x1", P[i].x); ln.setAttribute("y1", P[i].y); }
        if (e.b === i) { ln.setAttribute("x2", P[i].x); ln.setAttribute("y2", P[i].y); }
      });
    };
    $$("g[data-node]", svg).forEach(g => {
      g.onmousedown = ev => { drag = +g.dataset.node; moved = false; ev.preventDefault(); };
      g.onmouseenter = () => lines.forEach((ln, i) => {
        const e = xr.edges[i];
        ln.setAttribute("stroke",
          e.a === +g.dataset.node || e.b === +g.dataset.node ? "var(--amber)" : "var(--line)");
      });
      g.onmouseleave = () => lines.forEach(ln => ln.setAttribute("stroke", "var(--line)"));
    });
    svg.onmousemove = ev => {
      if (drag < 0) return;
      moved = true;
      const p = pt(ev);
      P[drag] = { x: Math.max(16, Math.min(W - 16, p.x)),
                  y: Math.max(20, Math.min(H - 10, p.y)) };
      moveNode(drag);
    };
    svg.onmouseup = () => {
      if (drag >= 0 && !moved) {
        const n = xr.nodes[drag];
        clipsModal(`"${n.name}" — every mention`, segsWith(n.name));
      }
      drag = -1;
    };
    svg.onmouseleave = () => { drag = -1; };
    $$("line[data-edge]", svg).forEach(ln => ln.onclick = () => {
      const e = xr.edges[+ln.dataset.edge];
      clipsModal(`${xr.nodes[e.a].name} + ${xr.nodes[e.b].name} — ${e.count} sentence${e.count === 1 ? "" : "s"} together`,
        e.moments);
    });
  }

  /* -- relevant documents: the town's own portal, read around this
        meeting's date. Found by date + name match — no model involved. -- */
  async function loadDocuments(fresh) {
    const msg = $("#hl-docmsg", el);
    if (!msg) return;
    if (S.docsBusy || (S.docs && !fresh)) return;
    S.docsBusy = true;
    const tenant = ($("#hl-doctenant", el).value.trim() || "brooklinema").toLowerCase();
    localStorage.setItem("cz-doc-tenant", tenant);
    msg.textContent = `reading the ${tenant} portal…`;
    try {
      S.docs = await api("/api/highlighter/documents", { path: S.source, tenant });
      msg.textContent = "";
      renderDocuments();
    } catch (e) {
      msg.textContent = e.message;
      $("#hl-docs", el).innerHTML = "";
    } finally { S.docsBusy = false; }
  }

  const DOC_ICONS = { "agenda": "📋", "agenda packet": "🗂", "minutes": "📝",
                      "agenda | html": "📋" };
  function renderDocuments() {
    const box = $("#hl-docs", el);
    if (!box || !S.docs) return;
    const evs = S.docs.events || [];
    if (!evs.length) {
      box.innerHTML = `<div class="hint">the ${esc(S.docs.tenant)} portal lists nothing
        within ±${S.docs.window_days} days of ${esc(S.docs.around)} that matches this
        meeting's name — try another tenant, or the meeting may not be a CivicClerk town</div>`;
      return;
    }
    box.innerHTML = evs.map(ev => `
      <div style="padding:7px 0;border-bottom:1px dashed var(--line)">
        <div style="display:flex;gap:8px;align-items:baseline;flex-wrap:wrap">
          <b>${esc(ev.name)}</b>
          <span class="hint">${esc((ev.when || "").slice(0, 10))}${ev.category ? " · " + esc(ev.category) : ""}</span>
          ${ev.score ? `<span class="cnt" title="title words in common">match ×${ev.score}</span>` : ""}
        </div>
        ${(ev.files || []).map(f => `
          <a href="${esc(f.url)}" target="_blank" rel="noopener" class="hl-docrow"
             style="display:flex;gap:8px;align-items:center;padding:3px 0 3px 12px;text-decoration:none;color:inherit">
            <span>${DOC_ICONS[(f.type || "").toLowerCase()] || "📄"}</span>
            <span style="flex:1">${esc(f.name)}</span>
            <span class="hint">${esc(f.type)} · opens the portal's PDF ↗</span>
          </a>`).join("") || `<div class="hint" style="padding-left:12px">no published files on this event</div>`}
      </div>`).join("");
  }

  /* -- the shape of the meeting: two canvases, counted not modeled ----- */
  function drawBins(c, draw) {
    if (!c || !c.clientWidth) return;
    c.width = c.clientWidth * devicePixelRatio;
    c.height = c.clientHeight * devicePixelRatio;
    const g = c.getContext("2d");
    g.clearRect(0, 0, c.width, c.height);
    g.fillStyle = "rgba(0,0,0,.05)";
    g.fillRect(0, 0, c.width, c.height);
    draw(g, c.width, c.height);
  }

  function drawCharts() {
    const I = S.insight;
    if (!I) return;
    const dur = I.pace?.duration || 1;
    const seekAt = e => {
      const r = e.target.getBoundingClientRect();
      seek((e.clientX - r.left) / r.width * dur, true);
    };
    const pc = $("#hl-pacechart", el);
    if (pc && I.pace?.bins?.length) {
      drawBins(pc, (g, W, H) => {
        const bins = I.pace.bins, mx = Math.max(...bins, 1), bw = W / bins.length;
        g.fillStyle = "rgba(169,122,22,.75)";
        bins.forEach((v, b) => {
          const h = v / mx * (H - 6);
          if (h > 0) g.fillRect(b * bw + 1, H - h, bw - 2, h);
        });
      });
      pc.onclick = seekAt;
    }
    const dc = $("#hl-dynchart", el);
    if (dc && I.dynamics?.lanes) {
      drawBins(dc, (g, W, H) => {
        const L = I.dynamics.lanes;
        const lanes = [["questions", "#3FA9D0"], ["decisions", "#1E7F63"],
                       ["tension", "#B0542D"]];
        const laneH = H / lanes.length;
        lanes.forEach(([k, color], li) => {
          const bins = L[k] || [], mx = Math.max(...bins, 1), bw = W / bins.length;
          g.fillStyle = color;
          bins.forEach((v, b) => {
            const h = v / mx * (laneH - 4);
            if (h > 0) g.fillRect(b * bw + 1, laneH * (li + 1) - h, bw - 2, h);
          });
        });
      });
      dc.onclick = seekAt;
    }
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
    const nt = nowTime();
    if (nt > 0) {
      g.fillStyle = "#23261D";
      g.fillRect(nt / dur * c.width, 0, 2, c.height);
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
        ${S.session ? `<button class="add" data-dl="${k}"
          title="download just this span (${(p.end - p.start).toFixed(0)}s) at the chosen quality">↓ clip</button>` : ""}
        <button class="add${inTl ? " in" : ""}" data-k="${k}">${inTl ? "✓ in reel" : "+ Add"}</button>
      </div>`;
    }).join("");
    $$(".tpill", box).forEach(p => p.onclick = () => seek(+p.dataset.t, true));
    $$("button[data-dl]", box).forEach(b => b.onclick = () => {
      const p = S.picks[+b.dataset.dl];
      download(true, [{ start: p.start, end: p.end }]);
      toast(`fetching ${fmtTime(p.start)}–${fmtTime(p.end)} — watch the Edit tab for progress`);
    });
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
        <div class="cfx">
          <button data-nud="${k}|start|-0.5" title="in point 0.5s earlier">◂in</button>
          <button data-nud="${k}|start|0.5" title="in point 0.5s later">in▸</button>
          <select data-spd="${k}" title="playback speed — rendered into the export">
            ${[0.5, 1, 1.5, 2].map(s => `<option value="${s}"${(c.speed || 1) === s ? " selected" : ""}>${s}×</option>`).join("")}
          </select>
          <label title="0.35s fade in/out on this clip — rendered into the export">
            <input type="checkbox" data-fade="${k}"${c.fade ? " checked" : ""}>fade</label>
          <button data-nud="${k}|end|-0.5" title="out point 0.5s earlier">◂out</button>
          <button data-nud="${k}|end|0.5" title="out point 0.5s later">out▸</button>
        </div>
      </div>`).join("");
    $$("[data-nud]", box).forEach(b => b.onclick = () => {
      const [k, e2, d] = b.dataset.nud.split("|");
      const c = S.timeline[+k];
      c[e2] = Math.max(0, c[e2] + parseFloat(d));
      if (c.end <= c.start) c.end = c.start + 0.5;
      renderTimeline();
    });
    $$("select[data-spd]", box).forEach(s => s.onchange = () => {
      S.timeline[+s.dataset.spd].speed = parseFloat(s.value);
      updateMetaLine();
    });
    $$("input[data-fade]", box).forEach(f => f.onchange = () => {
      S.timeline[+f.dataset.fade].fade = f.checked;
    });
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

  function renderDlFiles() {
    const box = $("#hl-dlfiles", el);
    const files = S.sectionFiles || [];
    box.innerHTML = files.map(f => {
      const name = f.split("/").pop();
      return `<div style="display:flex;gap:8px;align-items:center;font-size:12px;padding:3px 0">
        <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
          title="${esc(f)}">🎬 ${esc(name)}</span>
        <button class="btn" style="width:auto;padding:2px 10px;font-size:11px" data-reveal="${esc(f)}">Reveal</button>
      </div>`;
    }).join("");
    $$("button[data-reveal]", box).forEach(b => b.onclick = async () => {
      try { await api("/api/media/reveal", { path: b.dataset.reveal }); }
      catch (e) { toast(e.message, true); }
    });
  }

  async function download(sectionsOnly, spans) {
    const url = S.meta?.url;
    if (!url) { toast("this source has no URL — it's already a local file", true); return; }
    const sections = sectionsOnly ? (spans || mergedSections()) : null;
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
        const landed = done.result.paths || [done.result.path];
        S.sectionFiles = [...new Set([...(S.sectionFiles || []), ...landed])];
        renderDlFiles();
        toast(`${landed.length} clip${landed.length === 1 ? "" : "s"} landed — Export reel stitches them`);
      } else {
        toast("full video downloaded — opening the local copy");
        open(done.result.path);
      }
    } catch (e) { toast(e.message, true); }
  }

  /* ---------------- Export Video: two doors out ---------------- */
  const PLAYER_BASE = "https://community-highlighter.onrender.com/";

  function shareLink() {
    // the web player's whole contract lives in the URL: video id, clip
    // spans, labels — nothing is uploaded, nothing is stored anywhere
    const clips = S.timeline.map(c =>
      `${Math.round(c.start)}-${Math.round(c.end)}`).join(",");
    const titles = S.timeline.map(c =>
      (c.label || "").replace(/\|/g, "/")).join("|");
    return `${PLAYER_BASE}?mode=play&v=${encodeURIComponent(ytId())}`
      + `&clips=${clips}&titles=${encodeURIComponent(titles)}&labels=on`;
  }

  function openExportModal() {
    if (!S.timeline.length) { toast("the timeline is empty — keep some moments first", true); return; }
    const total = S.timeline.reduce((a, c) => a + (c.end - c.start), 0);
    $("#hl-exp-meta", el).textContent =
      `${S.timeline.length} clip${S.timeline.length === 1 ? "" : "s"} · ${total.toFixed(0)}s`;
    const canShare = S.session && !!ytId();
    const door = $("#hl-exp-sharedoor", el);
    door.style.opacity = canShare ? "" : ".45";
    $("#hl-exp-share", el).disabled = !canShare;
    $("#hl-exp-sharenote", el).textContent = canShare
      ? "plays through the public web player — anyone with the link can watch"
      : "share links need a YouTube source — this is a local file, use the MP4 door";
    $("#hl-exp-shareout", el).style.display = "none";
    $("#hl-exp-dlwhat", el).textContent = S.session
      ? "Only the kept spans leave YouTube, then ffmpeg cuts them into one MP4 — with title cards if you've checked them."
      : "The reel renders straight from the local file — with title cards if you've checked them.";
    $("#hl-exp-stages", el).innerHTML = "";
    $("#hl-exportmodal", el).style.display = "";
  }

  function stageRow(n, label) {
    const box = $("#hl-exp-stages", el);
    box.insertAdjacentHTML("beforeend",
      `<div class="hl-stage" id="hl-stage-${n}"><b>${label}</b><span>queued</span></div>`);
    const row = $(`#hl-stage-${n}`, el);
    return {
      set: (msg, cls) => {
        $("span", row).textContent = msg;
        row.className = "hl-stage" + (cls ? " " + cls : "");
      },
    };
  }

  async function makeMp4() {
    const go = $("#hl-exp-go", el);
    go.disabled = true;
    const preset = $("#hl-preset", el).value;
    const wantCards = $("#hl-cards", el).checked;
    const title = S.meta?.title || $("#hl-title", el).textContent || "";
    $("#hl-exp-stages", el).innerHTML = "";
    try {
      let files = null;
      if (S.session) {
        const spans = mergedSections();
        const s1 = stageRow(1, `1 · Download ${spans.length} clip${spans.length === 1 ? "" : "s"} from YouTube`);
        // a span that already landed as [start-end].mp4 never re-downloads
        const match = s => (S.sectionFiles || []).find(f =>
          f.includes(`[${Math.floor(s.start)}-${Math.floor(s.end)}]`));
        if (spans.every(s => match(s))) {
          files = spans.map(match);
          s1.set(`✓ all ${files.length} clips already on disk — nothing re-downloads`, "ok");
        } else {
          const job = await api("/api/highlighter/fetch", {
            url: S.meta?.url, quality: $("#hl-exp-quality", el).value, sections: spans });
          watchJob(job.id, j => s1.set(j.status === "running"
            ? `${Math.round(Math.max(0, j.progress) * 100)}% — ${j.message || "fetching"}` : j.status));
          const done = await jobDone(job.id);
          if (done.status !== "done") { s1.set(done.error || done.status, "err"); go.disabled = false; return; }
          files = done.result.paths || [done.result.path];
          S.sectionFiles = [...new Set([...(S.sectionFiles || []), ...files])];
          renderDlFiles();
          s1.set(`✓ ${files.length} clips landed — only ${spans.reduce((a, s) => a + s.end - s.start, 0).toFixed(0)}s left YouTube`, "ok");
        }
      }
      const s2 = stageRow(2, `${S.session ? "2" : "1"} · Cut the MP4 with ffmpeg${wantCards ? " (+ title cards)" : ""}`);
      let job2;
      if (S.session) {
        const spanCards = wantCards ? files.map(f => {
          const m = f.match(/\[(\d+)-(\d+)\]\.\w+$/);
          const a = m ? +m[1] : 0, b = m ? +m[2] : 1e9;
          const hit = S.timeline.find(c => c.start >= a - 1 && c.start <= b + 1);
          return { label: hit?.label || "", t: a };
        }) : null;
        const fileFx = files.map(f => {
          const m = f.match(/\[(\d+)-(\d+)\]\.\w+$/);
          const a = m ? +m[1] : 0, b2 = m ? +m[2] : 1e9;
          const hit = S.timeline.find(c => c.start >= a - 1 && c.start <= b2 + 1);
          return { speed: hit?.speed || 1, fade: !!hit?.fade };
        });
        job2 = await api("/api/highlighter/stitch", {
          files, preset, cards: spanCards, title, fx: fileFx });
      } else {
        job2 = await api("/api/highlighter/reel", {
          path: S.source, preset, cards: wantCards, title,
          ranges: S.timeline.map(c => ({ start: c.start, end: c.end,
                                         label: c.label || "",
                                         speed: c.speed || 1,
                                         fade: !!c.fade })) });
      }
      watchJob(job2.id, j => s2.set(j.status === "running"
        ? `${Math.round(Math.max(0, j.progress) * 100)}% — ${j.message || "cutting"}` : j.status));
      const done2 = await jobDone(job2.id);
      if (done2.status !== "done") { s2.set(done2.error || done2.status, "err"); go.disabled = false; return; }
      const r = done2.result;
      s2.set(`✓ ${r.clips} cuts${r.cards ? ` · ${r.cards} title cards` : ""} · ${r.duration}s · ${r.encoder}`, "ok");
      const s3 = stageRow(3, "✓ Your video");
      s3.set(r.out.split("/").pop());
      $("#hl-exp-stages", el).insertAdjacentHTML("beforeend",
        `<button class="btn" id="hl-exp-reveal" style="width:auto;margin-top:6px">Reveal in Finder</button>`);
      $("#hl-exp-reveal", el).onclick = () => api("/api/media/reveal", { path: r.out }).catch(e => toast(e.message, true));
      const rep = $("#hl-report", el);
      rep.classList.add("show");
      rep.innerHTML += `<b>→</b> ${esc(r.out)}\n   ${r.clips} cuts · ${r.duration}s · ${esc(r.encoder)}\n`;
      toast("video exported");
    } catch (e) { toast(e.message, true); }
    go.disabled = false;
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

  /* ---------------- the generative upgrade (your key) ---------------- */
  async function llmCheck() {
    try { S.llm = await api("/api/settings/llm"); } catch (e) { S.llm = null; }
    const on = !!(S.llm && S.llm.enabled);
    $("#hl-trsum", el).style.display = on ? "" : "none";
    $("#hl-trtxt", el).style.display = on ? "" : "none";
    $("#hl-askai", el).style.display = on ? "" : "none";
    $("#hl-aireel-row", el).style.display = on ? "" : "none";
  }

  async function aiReel() {
    const btn = $("#hl-aireel", el);
    btn.disabled = true;
    try {
      const job = await api("/api/highlighter/ai-reel", {
        path: S.source, target: parseFloat($("#hl-target", el).value) });
      watchJob(job.id, j => { $("#hl-detectmsg", el).textContent = j.message || j.status; });
      const done = await jobDone(job.id);
      btn.disabled = false;
      if (done.status === "error") { $("#hl-detectmsg", el).textContent = done.error; toast(done.error, true); return; }
      if (done.status !== "done") return;
      S.lane = [];
      applyPicks(done.result.picks || [], true);
      renderTranscript();
      renderHighlights();
      drawSpark();
      $("#hl-origin", el).textContent = `· picks are generative (${esc((done.result.origin || "").replace("ai:", ""))}, your key) — timestamps validated locally`;
      toast(`${done.result.picks.length} AI moments — top 5 are on the timeline`);
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  // [MM:SS] / [H:MM:SS] in generated prose become the same clickable pills
  // the extractive brief wears — every AI claim stays checkable
  function linkifyTimes(text) {
    return esc(text).replace(/\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]/g,
      (m, a, b, c) => {
        const t = c ? (+a * 3600 + +b * 60 + +c) : (+a * 60 + +b);
        return `<span class="tpill" data-t="${t}">${c ? a + ":" + b + ":" + c : a + ":" + b}</span>`;
      });
  }

  async function aiBrief(auto) {
    const btn = $("#hl-aibrief", el);
    const box = $("#hl-brief", el);
    const src = S.source;
    btn.disabled = true;
    if (!auto) box.insertAdjacentHTML("afterbegin",
      `<div class="hint" id="hl-briefwip">rewriting the executive summary…</div>`);
    else box.insertAdjacentHTML("afterbegin",
      `<div class="hint" id="hl-briefwip">✍ writing the executive summary — ${esc(S.llm?.model || "your key")}…</div>`);
    try {
      const job = await api("/api/highlighter/ai-brief",
        { path: src, fresh: !auto });
      const done = await jobDone(job.id);
      btn.disabled = false;
      if (S.source !== src) return;   // user moved on to another meeting
      $("#hl-briefwip", el)?.remove();
      if (done.status !== "done") {
        box.insertAdjacentHTML("afterbegin",
          `<div class="hint">${esc(done.error || "stopped")} — the extractive read below stands</div>`);
        return;
      }
      box.innerHTML = done.result.text.split(/\n+/).map(p =>
        `<p>${linkifyTimes(p.replace(/^#+\s*/, "").replace(/\*\*/g, ""))}</p>`).join("");
      $$(".tpill", box).forEach(p => p.onclick = () => seek(+p.dataset.t, true));
      $("#hl-aibrief", el).style.display = "";
    } catch (e) {
      btn.disabled = false;
      $("#hl-briefwip", el)?.remove();
      if (!auto) toast(e.message, true);
    }
  }

  async function askAI() {
    const q = $("#hl-askq", el).value.trim();
    if (!q || !S.source) return;
    const log = $("#hl-chatlog", el);
    log.innerHTML += `<div class="hl-msg q">${esc(q)}</div>`;
    $("#hl-askq", el).value = "";
    log.scrollTop = log.scrollHeight;
    const holder = document.createElement("div");
    holder.className = "hl-msg a";
    holder.innerHTML = `<span class="hint">asking with your key…</span>`;
    log.appendChild(holder);
    try {
      const job = await api("/api/highlighter/ai-ask", { path: S.source, q });
      const done = await jobDone(job.id);
      if (done.status !== "done") { holder.innerHTML = esc(done.error || "stopped"); return; }
      holder.innerHTML = `<div class="hint" style="margin-bottom:3px">generative — ${esc(done.result.model)}, your key</div>`
        + done.result.text.split(/\n+/).map(p => `<div style="margin-bottom:4px">${linkifyTimes(p)}</div>`).join("");
      $$(".tpill", holder).forEach(p => p.onclick = () => seek(+p.dataset.t, true));
      log.scrollTop = log.scrollHeight;
    } catch (e) { holder.innerHTML = esc(e.message); }
  }

  /* ---------------- full report + translate ---------------- */
  async function fullReport(fresh) {
    const btn = $("#hl-report", el);
    const out = $("#hl-reportout", el);
    btn.disabled = true;
    out.style.display = "";
    out.innerHTML = `<div class="hint">writing the report…</div>`;
    try {
      const job = await api("/api/highlighter/report", { path: S.source, fresh: !!fresh });
      watchJob(job.id, j => { if (j.status === "running") out.innerHTML = `<div class="hint">${esc(j.message || "working")}</div>`; });
      const done = await jobDone(job.id);
      btn.disabled = false;
      if (done.status !== "done") { out.innerHTML = `<div class="hint">${esc(done.error || "stopped")}</div>`; return; }
      const r = done.result;
      out.innerHTML = `
        <div style="display:flex;gap:7px;flex-wrap:wrap;margin-bottom:8px">
          <button class="btn cta" data-rev="${esc(r.pdf)}" style="width:auto">📄 Reveal PDF</button>
          <button class="btn" data-rev="${esc(r.md)}" style="width:auto">Reveal .md</button>
          <button class="btn" id="hl-rep-fresh" style="width:auto">↻ Regenerate</button>
        </div>
        <div class="hl-brief hl-reporttext">${r.text.split(/\n+/).map(p => {
          const s = p.replace(/\*\*/g, "");
          if (s.startsWith("## ")) return `<p><b>${linkifyTimes(s.slice(3))}</b></p>`;
          if (s.startsWith("# ")) return `<p><b style="font-size:15px">${linkifyTimes(s.slice(2))}</b></p>`;
          if (s.startsWith("- ")) return `<p style="padding-left:12px">· ${linkifyTimes(s.slice(2))}</p>`;
          return `<p>${linkifyTimes(s)}</p>`;
        }).join("")}</div>`;
      $$("button[data-rev]", out).forEach(b => b.onclick = () =>
        api("/api/media/reveal", { path: b.dataset.rev }).catch(e => toast(e.message, true)));
      $("#hl-rep-fresh", out).onclick = () => fullReport(true);
      $$(".tpill", out).forEach(p => p.onclick = () => seek(+p.dataset.t, true));
      toast("full report written — markdown + PDF beside the meeting");
    } catch (e) { btn.disabled = false; out.innerHTML = `<div class="hint">${esc(e.message)}</div>`; }
  }

  async function translate(what) {
    const lang = $("#hl-lang", el).value;
    const btn = $(what === "summary" ? "#hl-trsum" : "#hl-trtxt", el);
    btn.disabled = true;
    try {
      const job = await api("/api/highlighter/translate", { path: S.source, what, lang });
      watchJob(job.id, j => { $("#hl-detectmsg", el).textContent = j.message || j.status; });
      const done = await jobDone(job.id);
      btn.disabled = false;
      if (done.status !== "done") { toast(done.error || "stopped", true); return; }
      if (what === "summary") {
        const box = $("#hl-brief", el);
        box.insertAdjacentHTML("beforeend",
          `<div style="border-top:1px dashed var(--line);margin-top:8px;padding-top:8px">
            <div class="hint" style="margin-bottom:4px">${esc(lang)} — also saved as a .txt</div>
            ${done.result.text.split(/\n+/).map(p => `<p>${linkifyTimes(p)}</p>`).join("")}</div>`);
        $$(".tpill", box).forEach(p => p.onclick = () => seek(+p.dataset.t, true));
      } else {
        toast(`transcript in ${lang} — .srt and .txt landed beside the meeting`);
      }
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  /* ---------------- the clips modal: any viz, opened into moments -------- */
  function clipsModal(title, rows) {
    // rows: [{t, end?, text, speaker?}]
    $("#hl-cm-title", el).textContent = title;
    $("#hl-cm-meta", el).textContent = `${rows.length} moment${rows.length === 1 ? "" : "s"}`;
    const box = $("#hl-cm-rows", el);
    box.innerHTML = rows.map((r, i) => `
      <div class="hl-cmrow">
        <span class="tpill" data-t="${r.t}">${fmtTime(r.t)}</span>
        <span style="flex:1">${r.speaker ? `<b>${esc(r.speaker)}:</b> ` : ""}${esc((r.text || "").slice(0, 140))}</span>
        <button class="btn" data-play="${i}" title="play this moment">▶</button>
        <button class="btn" data-add="${i}" title="add to the reel">+</button>
      </div>`).join("") || `<div class="hint">nothing matched</div>`;
    $$(".tpill", box).forEach(p => p.onclick = () => seek(+p.dataset.t, true));
    $$("button[data-play]", box).forEach(b => b.onclick = () => {
      const r = rows[+b.dataset.play];
      seek(r.t, true);
    });
    $$("button[data-add]", box).forEach(b => b.onclick = () => {
      const r = rows[+b.dataset.add];
      addToTimeline({ start: Math.max(0, r.t - 0.3), end: (r.end || r.t + 12) + 0.3,
                      label: (r.text || "").slice(0, 60) });
      renderTimeline();
      toast("added to the reel");
    });
    $("#hl-cm-addall", el).onclick = () => {
      rows.slice(0, 12).forEach(r => addToTimeline({
        start: Math.max(0, r.t - 0.3), end: (r.end || r.t + 12) + 0.3,
        label: (r.text || "").slice(0, 60) }, true));
      renderTimeline();
      toast(`${Math.min(rows.length, 12)} moments on the reel`);
    };
    $("#hl-clipsmodal", el).style.display = "";
  }

  const segsWith = q => (S.t?.segments || [])
    .filter(s => (s.text || "").toLowerCase().includes(q.toLowerCase()))
    .map(s => ({ t: s.start, end: s.end, text: s.text, speaker: s.speaker }));

  /* ---------------- investigate: a name, looked up ---------------- */
  async function investigate(q) {
    q = (q || "").trim();
    if (!q) { toast("select or click a name first", true); return; }
    $("#hl-inv-q", el).textContent = q;
    $("#hl-invmodal", el).style.display = "";
    invTab("news", q);
  }

  async function invTab(tab, q) {
    $$("#hl-invtabs .chip", el).forEach(c => c.classList.toggle("on", c.dataset.tab === tab));
    const body = $("#hl-inv-body", el);
    body.innerHTML = `<div class="hint">looking up…</div>`;
    try {
      if (tab === "news") {
        const r = await api("/api/highlighter/investigate", { q });
        body.innerHTML = r.rows.map(n => `
          <div class="hl-cmrow"><span style="flex:1"><a href="${esc(n.link)}" target="_blank" rel="noopener">${esc(n.title)}</a>
            <span class="hint">${esc(n.source)} · ${esc(n.date)}</span></span></div>`).join("")
          || `<div class="hint">no recent news found</div>`;
      } else if (tab === "wiki") {
        const resp = await fetch("https://en.wikipedia.org/api/rest_v1/page/summary/"
          + encodeURIComponent(q.replace(/ /g, "_")));
        if (!resp.ok) throw new Error("no Wikipedia page by that exact name");
        const w = await resp.json();
        body.innerHTML = `
          ${w.thumbnail ? `<img src="${esc(w.thumbnail.source)}" style="float:right;max-width:120px;border-radius:8px;margin:0 0 8px 10px">` : ""}
          <p><b>${esc(w.title)}</b>${w.description ? ` — ${esc(w.description)}` : ""}</p>
          <p style="margin-top:6px">${esc(w.extract || "")}</p>
          <p style="margin-top:8px"><a href="${esc(w.content_urls?.desktop?.page || "#")}" target="_blank" rel="noopener">Read on Wikipedia ↗</a></p>`;
      } else if (tab === "maps") {
        const enc = encodeURIComponent(q);
        body.innerHTML = `
          <p class="hint" style="margin-bottom:8px">maps open in your browser — the map services don't allow embedding</p>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <a class="btn cta" style="width:auto;text-decoration:none" href="https://www.google.com/maps/search/${enc}" target="_blank" rel="noopener">Google Maps ↗</a>
            <a class="btn" style="width:auto;text-decoration:none" href="https://www.openstreetmap.org/search?query=${enc}" target="_blank" rel="noopener">OpenStreetMap ↗</a>
            <a class="btn" style="width:auto;text-decoration:none" href="https://news.google.com/search?q=${enc}" target="_blank" rel="noopener">Google News ↗</a>
          </div>`;
      } else if (tab === "library") {
        const r = await api("/api/highlighter/mentions", { q, path: S.source });
        body.innerHTML = `<p class="hint" style="margin-bottom:6px">every other meeting on this machine that says "${esc(q)}" — the desktop's own knowledge base</p>`
          + (r.rows.map(m => `
          <div class="hl-cmrow"><span style="flex:1"><b>${esc(m.title)}</b>
            <span class="hint">×${m.count}${m.t != null ? " · first at " + fmtTime(m.t) : ""}</span></span>
            <button class="btn" data-open="${esc(m.source)}" style="width:auto">Open</button></div>`).join("")
          || `<div class="hint">no other meeting in your library mentions it yet</div>`);
        $$("button[data-open]", body).forEach(b => b.onclick = () => {
          $("#hl-invmodal", el).style.display = "none";
          open(b.dataset.open);
        });
      }
    } catch (e) { body.innerHTML = `<div class="hint">${esc(e.message)}</div>`; }
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
        path: S.source, model: $("#hl-model", el).value, diarize: true,
        hotwords: $("#hl-hotwords", el).value.trim() });
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
    // all three sections live on one page now — the pills are anchors
    $$("#hl-pills .hl-pill", el).forEach(p =>
      p.classList.toggle("on", p.dataset.sec === name));
    if (name === "highlight") {
      $("#hl-loaded", el).scrollTo({ top: 0, behavior: "smooth" });
    } else {
      $(`#hl-sec-${name}`, el).scrollIntoView({ behavior: "smooth",
                                                block: "start" });
    }
    drawSpark();
    drawCharts();
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

    // one listener owns every transcript row — 8k rows never mean 8k handlers
    $("#hl-transcript", el).addEventListener("click", e => {
      const keep = e.target.closest(".keepbtn");
      if (keep) { toggleKeep(+keep.dataset.si); return; }
      const tEl = e.target.closest(".hl-time");
      if (tEl) seek(+tEl.dataset.t, true);
    });
    $("#hl-follow", el).onclick = () => {
      followOn = !followOn;
      $("#hl-follow", el).classList.toggle("on", followOn);
      if (followOn) { lastNow = -1; followTranscript(); }
    };
    wireSessionClock();

    $("#hl-detect", el).onclick = detect;
    $("#hl-q", el).addEventListener("input", searchTranscript);
    $("#hl-transcribe", el).onclick = transcribe;
    $("#hl-txt", el).onclick = exportTxt;
    $("#hl-srt", el).onclick = exportSrt;
    $("#hl-askgo", el).onclick = askMeeting;
    $("#hl-askq", el).addEventListener("keydown", e => { if (e.key === "Enter") askMeeting(); });
    $("#hl-aibrief", el).onclick = () => aiBrief(false);
    $("#hl-askai", el).onclick = askAI;
    $("#hl-report", el).onclick = () => fullReport(false);
    $("#hl-trsum", el).onclick = () => translate("summary");
    $("#hl-trtxt", el).onclick = () => translate("transcript");
    $("#hl-invsel", el).onclick = () => {
      const sel = String(window.getSelection() || "").trim();
      investigate(sel || $("#hl-q", el).value.trim());
    };
    $("#hl-cm-close", el).onclick = () => { $("#hl-clipsmodal", el).style.display = "none"; };
    $("#hl-clipsmodal", el).onclick = e => {
      if (e.target.id === "hl-clipsmodal") e.target.style.display = "none";
    };
    $("#hl-inv-close", el).onclick = () => { $("#hl-invmodal", el).style.display = "none"; };
    $("#hl-invmodal", el).onclick = e => {
      if (e.target.id === "hl-invmodal") e.target.style.display = "none";
    };
    $$("#hl-invtabs .chip", el).forEach(c => c.onclick = () =>
      invTab(c.dataset.tab, $("#hl-inv-q", el).textContent));

    // transport keys, NLE muscle memory: space play/pause, arrows ±5s —
    // never while typing in a field
    addEventListener("keydown", e => {
      if (CZ.current !== "highlighter" || !S.source) return;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
      if (e.code === "Space") {
        e.preventDefault();
        if (S.session) {
          // the embed owns its clock; we track only our last command
          const f = $("#hl-ytframe", el);
          f.contentWindow.postMessage(JSON.stringify({ event: "command",
            func: S.ytPlaying ? "pauseVideo" : "playVideo", args: [] }), "*");
          S.ytPlaying = !S.ytPlaying;
        } else audio.paused ? audio.play() : audio.pause();
      } else if (!S.session && (e.key === "ArrowLeft" || e.key === "ArrowRight")) {
        e.preventDefault();
        seek(Math.max(0, audio.currentTime + (e.key === "ArrowLeft" ? -5 : 5)),
             !audio.paused);
      }
    });

    $("#hl-prev", el).onclick = () => playClip(Math.max(0, S.curClip - 1), false);
    $("#hl-next", el).onclick = () => playClip(Math.min(S.timeline.length - 1, S.curClip + 1), false);
    $("#hl-playreel", el).onclick = () => playClip(0, true);
    $("#hl-clear", el).onclick = () => { S.timeline = []; S.keep = new Set(); renderTimeline(); renderTranscript(); renderHighlights(); };
    $("#hl-export", el).onclick = openExportModal;
    $("#hl-edl", el).onclick = exportEDL;
    $("#hl-aireel", el).onclick = aiReel;

    // the export modal's own wiring
    $("#hl-exp-close", el).onclick = () => { $("#hl-exportmodal", el).style.display = "none"; };
    $("#hl-exportmodal", el).onclick = e => {
      if (e.target.id === "hl-exportmodal") $("#hl-exportmodal", el).style.display = "none";
    };
    $("#hl-exp-share", el).onclick = () => {
      const url = shareLink();
      $("#hl-exp-shareout", el).style.display = "";
      $("#hl-exp-url", el).value = url;
      $("#hl-exp-sharenote", el).textContent = "✓ link created — the clips live in the URL itself, nothing was uploaded";
    };
    $("#hl-exp-copy", el).onclick = async () => {
      try { await navigator.clipboard.writeText($("#hl-exp-url", el).value); toast("link copied"); }
      catch (e) { $("#hl-exp-url", el).select(); toast("copy blocked — the URL is selected, ⌘C copies it", true); }
    };
    $("#hl-exp-open", el).onclick = () => window.open($("#hl-exp-url", el).value, "_blank");
    $("#hl-exp-go", el).onclick = makeMp4;
    $("#hl-dlfull", el).onclick = () => download(false);
    $("#hl-dlsections", el).onclick = () => download(true);

    new MutationObserver(() => { if (!el.classList.contains("active")) stop(); })
      .observe(el, { attributes: true, attributeFilter: ["class"] });
    addEventListener("resize", () => {
      if (CZ.current !== "highlighter") return;
      drawSpark();
      drawCharts();
    });
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
