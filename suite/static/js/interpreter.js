/* Community Interpreter — a meeting's captions, in the languages your
   town speaks.

   Open any meeting Highlighter has read. Pick languages (seven ride the
   panel, Simple English first-class); one queue job writes timed subtitle
   files (.srt + .vtt) beside the meeting. Every track says it's AI and
   which engine made it; every line takes one tap to flag for a fluent
   reviewer, and a correction rewrites the track in place. The page walks
   it as three steps — choose, check, download — and says at the top what
   it's for and what you get. */

const InterpreterPage = (() => {
  const T = toolById("interpreter");
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-interpreter";

  el.innerHTML = `
  <div class="ws" style="--acc:${T.acc}">
    <div class="mediabar">
      <span class="toolname"><i>Community Interpreter</i> · carries it across</span>
      <span class="beta-chip" title="beta — AI translation; every track says so, every line takes one tap to flag">beta</span>
      <span class="clipmeta" id="itp-title" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"></span>
      <button class="btn" id="itp-back" style="width:auto;display:none">← meetings</button>
    </div>
    <div class="ws-body">
      <div class="ws-center" id="itp-center" style="overflow-y:auto;padding:18px 22px 40px"></div>
      <div class="inspector">
        <div class="insp-head"><h2>Interpreter</h2></div>
        <div class="insp-sec">
          <span class="tag">the translation engine</span>
          <div class="hint" id="itp-engine" style="line-height:1.55">—</div>
        </div>
        <div class="insp-sec" id="itp-glossbox">
          <span class="tag">your town's word list</span>
          <div class="hint">names that must never be translated, and the right words for civic
            terms — used on every translation</div>
          <div id="itp-gloss"></div>
        </div>
        <div class="insp-sec">
          <span class="tag">lines waiting for a reviewer <span id="itp-qcount"></span></span>
          <div class="hint">flagged lines from every language and meeting — a fluent speaker fixes them here</div>
          <div id="itp-queue"></div>
        </div>
        <div class="report" id="itp-report"></div>
      </div>
    </div>
  </div>`;

  const S = { source: null, meta: null, video: null, langs: {}, nSeg: 0,
              origin: null, session: false, status: null, selected: new Set(),
              view: null, cues: [], glossary: null, glossLang: "es",
              town: "brookline", queue: [], url: null };

  const fmtT = t => { t = Math.max(0, Math.floor(t)); return t >= 3600
    ? `${Math.floor(t / 3600)}:${String(Math.floor(t % 3600 / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`
    : `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`; };
  const L = code => (S.status ? S.status.languages : []).find(l => l.code === code);
  const trackURL = (code, fmt, dl) => `/api/interpreter/track?path=${encodeURIComponent(S.source)}` +
    `&lang=${code}&fmt=${fmt || "vtt"}${dl ? "&dl=1" : ""}&r=${(S.langs[code] || {}).created || 0}`;

  /* the engine, in one sentence and one button */
  function engineHTML() {
    const eng = S.status && S.status.engine;
    if (!eng) return "";
    if (eng.engine) return `<div class="itp-eng ok">✓ ${esc(eng.sentence)}</div>`;
    return `<div class="itp-eng need">
      <b>Translation needs an engine.</b> The simplest is an AI key (Anthropic, OpenAI or Google
      Gemini — Gemini has a free tier); only this meeting's words are sent, only when you press Translate.
      <div class="cz-row"><button class="btn primary" id="itp-addkey" style="width:auto;color:#fff">🔑 Add an AI key</button>
        <span class="hint">or install an on-device model by hand (Models page) — no key at all</span></div>
    </div>`;
  }
  function wireEngine(box) {
    const b = $("#itp-addkey", box);
    if (b) b.onclick = async () => {
      if (await czKeyModal({ feature: "Translating captions" })) { await loadStatus(); S.source ? renderMain() : shelf(); }
    };
  }

  /* ---------- the landing: what this is, how it goes, what to open ---------- */
  async function shelf() {
    S.source = null;
    $("#itp-title", el).textContent = "";
    $("#itp-back", el).style.display = "none";
    const box = $("#itp-center", el);
    box.innerHTML = `
      <div class="cz-hero" style="--acc:${T.acc}">
        <div class="tag">community interpreter</div>
        <h1>Your meeting's captions, <span class="mark">in the languages your town speaks</span>.</h1>
        <p>Interpreter translates a meeting's captions into Spanish, Simple English, Chinese,
          Portuguese, Haitian Creole, Vietnamese and Russian, and saves them as subtitle files —
          upload them to YouTube, play them on your channel, or post them with the video. The
          translations are AI and say so; any line can be flagged for a fluent neighbor to fix,
          and the fix goes straight into the file.</p>
        <div class="cz-how">
          <div class="cz-how-step"><span class="cz-how-n">1</span><b>Pick a meeting</b>
            one that has words — read it in Highlighter first</div>
          <div class="cz-how-step"><span class="cz-how-n">2</span><b>Choose languages</b>
            as many as you like — one job does them all</div>
          <div class="cz-how-step"><span class="cz-how-n">3</span><b>Check the lines</b>
            watch it with subtitles on; flag anything that reads wrong</div>
          <div class="cz-how-step"><span class="cz-how-n">4</span><b>Download subtitles</b>
            .srt for YouTube, .vtt for web players — timed to the video</div>
        </div>
        <div class="cz-outs">${(S.status ? S.status.languages : []).map(l =>
          `<span class="cz-out" title="${esc(l.english)}">${esc(l.name)}</span>`).join("")}
          <span class="cz-out">.srt</span><span class="cz-out">.vtt</span></div>
      </div>
      <div style="margin-top:14px">${engineHTML()}</div>
      <div class="tag" style="margin-top:18px">meetings with words — newest first</div>
      <div id="itp-shelf" class="cz-shelf"><div class="hint">looking…</div></div>
      <div class="cz-pick">
        <input type="text" id="itp-path" spellcheck="false"
          placeholder="…or paste a path — a video file with its transcript, or a Highlighter meeting folder">
        <button class="btn" id="itp-open" style="width:auto">Open</button>
        <button class="btn" id="itp-browse" style="width:auto">Browse…</button>
      </div>`;
    wireEngine(box);
    $("#itp-open", box).onclick = () => open($("#itp-path", box).value.trim());
    $("#itp-path", box).addEventListener("keydown", e => {
      if (e.key === "Enter") open($("#itp-path", box).value.trim()); });
    $("#itp-browse", box).onclick = () => browseForPath(open);
    let rows = [];
    try { rows = (await api("/api/interpreter/library")).rows || []; } catch (e) {}
    if (S.source) return;   // an open beat us here — never clobber it
    const sh = $("#itp-shelf", box);
    if (!sh) return;
    sh.innerHTML = rows.length ? rows.slice(0, 24).map(r => `
      <button class="cz-shelf-item" style="--acc:${T.acc}" data-open="${esc(r.source)}">
        <b title="${esc(r.title)}">${esc(r.title)}</b>
        <span>${r.duration ? fmtT(r.duration) + " · " : ""}${r.video ? "video on this computer" : "words only"}</span>
      </button>`).join("")
      : `<div class="hint">none yet — read a meeting in <a href="#" data-go="highlighter">Highlighter</a> and it appears here</div>`;
    $$("[data-open]", sh).forEach(b => b.onclick = () => open(b.dataset.open));
    $$("[data-go]", sh).forEach(a => a.onclick = e => { e.preventDefault(); go(a.dataset.go); });
  }

  /* ---------- open ---------- */
  async function open(path) {
    if (!path) return;
    const box = $("#itp-center", el);
    box.innerHTML = `<div class="hint" style="padding:16px 2px">reading the meeting…</div>`;
    try {
      const r = await api("/api/interpreter/open", { path });
      S.source = r.source; S.meta = r.meta; S.video = r.video;
      S.langs = r.languages; S.nSeg = r.n_segments; S.origin = r.origin;
      S.session = r.session; S.url = r.url || null;
      S.view = Object.keys(S.langs).find(c => S.langs[c].has) || null;
      S.cues = [];
      $("#itp-title", el).textContent = S.meta.title || "";
      $("#itp-back", el).style.display = "";
      renderMain();
      if (S.view) loadCues(S.view);
    } catch (e) {
      box.innerHTML = `<div class="cz-step current" style="--acc:${T.acc};max-width:640px">
        <div class="cz-step-head"><span class="cz-step-num">!</span><h2>Can't open this one yet</h2></div>
        <div class="cz-step-sub">${esc(e.message)}</div>
        <div class="cz-row"><button class="btn" id="itp-hl" style="width:auto">Open it in Highlighter</button>
          <button class="btn" id="itp-back2" style="width:auto">← back</button></div></div>`;
      $("#itp-hl", box).onclick = () => go("highlighter", { openPath: path });
      $("#itp-back2", box).onclick = shelf;
    }
  }

  /* ---------- the loaded view: three steps ---------- */
  function langCard(l) {
    const st = S.langs[l.code] || {};
    const on = S.selected.has(l.code);
    const state = st.has ? (st.stale ? "out of date — the words changed" : "✓ done") : "not yet";
    return `<button class="itp-lang${on ? " on" : ""}${st.has ? (st.stale ? " stale" : " has") : ""}"
      data-lang="${l.code}" aria-pressed="${on}"
      aria-label="${esc(l.english)} — ${state}${on ? ", selected" : ""}">
      <span class="itp-lname">${esc(l.name)}</span>
      <span class="itp-leng">${esc(l.english)}</span>
      <span class="itp-lstate">${state}${st.n_flags ? ` · ⚑ ${st.n_flags}` : ""}</span>
    </button>`;
  }

  function provenanceHTML(code) {
    const st = S.langs[code] || {};
    if (!st.has) return "";
    const g = st.glossary || {};
    const where = st.engine === "local" ? " — on-device" : " (your key)";
    const bits = [
      `<b>AI translation — beta</b>`,
      esc(st.model || "?") + where,
      `word list ${esc(g.town || "?")} v${g.version ?? "?"}`,
      esc(st.review || "unreviewed"),
    ];
    if (st.n_fallback) bits.push(`${st.n_fallback} lines kept in English`);
    if (st.n_miss) bits.push(`${st.n_miss} word-list misses`);
    if (st.n_corrected) bits.push(`✓ ${st.n_corrected} corrected`);
    return `<div class="itp-prov">${bits.join(" · ")}</div>`;
  }

  function renderMain() {
    const box = $("#itp-center", el);
    const langs = S.status ? S.status.languages : [];
    const nSel = S.selected.size;
    const engineOK = S.status && S.status.engine.engine;
    const avail = langs.filter(l => (S.langs[l.code] || {}).has);

    const player = S.video ? `
      <video id="itp-video" controls preload="metadata" crossorigin="anonymous"
        style="width:100%;max-height:380px;background:#000;border-radius:9px;margin-top:10px">
        <source src="/api/interpreter/media?path=${encodeURIComponent(S.video)}">
        <track kind="subtitles" label="English (original)" srclang="en" src="${trackURL("en")}">
        ${avail.map(l => `<track kind="subtitles" label="${esc(l.name)}" srclang="${esc(l.srclang)}"
          src="${trackURL(l.code)}">`).join("")}
      </video>`
      : `<div class="itp-novideo">No video on this computer — the subtitles still write and
          export. ${S.url ? `<button class="btn" id="itp-getvid" style="width:auto;margin-left:6px">⬇ Download it to watch them play</button>
          <div id="itp-getprog"></div>` : ""}</div>`;

    box.innerHTML = `
      <div class="pb-kithead">
        <div style="min-width:0">
          <div class="tag">subtitles in other languages</div>
          <h1 style="font-size:21px;margin-top:3px">${esc(S.meta.title)}</h1>
          <div class="hint">${S.nSeg} lines · words from ${esc(S.origin || "the transcript")}${S.meta.duration ? ` · ${fmtT(S.meta.duration)}` : ""}</div>
        </div>
        <div class="pb-kitacts">${czNextHTML("interpreter", S.source, { isFile: !S.session })}</div>
      </div>
      ${engineOK ? "" : `<div style="margin-top:12px">${engineHTML()}</div>`}

      <div class="cz-step ${avail.length ? "done" : "current"}" style="--acc:${T.acc}">
        <div class="cz-step-head"><span class="cz-step-num">${avail.length ? "✓" : "1"}</span>
          <h2>Choose languages</h2>
          <span class="cz-step-state">${avail.length} of ${langs.length} done</span></div>
        <div class="cz-step-sub">Tap every language you want, then Translate. Languages already done
          are marked ✓ — pick them again only to redo them.</div>
        <div class="itp-langs">${langs.map(langCard).join("")}</div>
        <div class="cz-row">
          <button class="btn primary cz-bigbtn" id="itp-run" style="color:#fff" ${nSel ? "" : "disabled"}>
            ${nSel ? `▶ Translate ${nSel} language${nSel === 1 ? "" : "s"}` : "Pick at least one language"}</button>
          <label class="hint" style="display:flex;align-items:center;gap:5px">
            <input type="checkbox" id="itp-fresh"> redo ones already done</label>
          <span class="hint" id="itp-jobstat"></span>
        </div>
        <div id="itp-prog"></div>
      </div>

      <div class="cz-step ${avail.length ? "current" : ""}" style="--acc:${T.acc}">
        <div class="cz-step-head"><span class="cz-step-num">2</span><h2>Watch and check</h2></div>
        <div class="cz-step-sub">${avail.length ? `Pick a language to read it line by line. Click a line to
          jump the video there; tap ⚑ on anything that reads wrong — it goes to the reviewer list on the right.`
          : "Once a language is translated, it shows up here to read and check."}</div>
        ${player}
        ${avail.length ? `
        <div class="chips" style="margin:10px 0 6px">
          ${avail.map(l => `<button class="chip${S.view === l.code ? " on" : ""}" data-view="${l.code}"
            aria-pressed="${S.view === l.code}" aria-label="read the ${esc(l.english)} subtitles"
            style="${S.view === l.code ? `border-color:${T.acc};background:${T.acc};color:#fff` : ""}">${esc(l.name)}</button>`).join("")}
        </div>
        <div id="itp-prov">${S.view ? provenanceHTML(S.view) : ""}</div>
        <div id="itp-cues" class="itp-cues"></div>` : ""}
      </div>

      <div class="cz-step ${avail.length ? "" : ""}" style="--acc:${T.acc}">
        <div class="cz-step-head"><span class="cz-step-num">3</span><h2>Download the subtitles</h2></div>
        <div class="cz-step-sub">Each language is two files, timed to the video. <b>.srt</b> — upload it on
          YouTube (Subtitles → Add language → Upload file). <b>.vtt</b> — for web players and most
          playout systems. They're also saved beside the meeting.</div>
        ${avail.length ? avail.map(l => `<div class="batchrow"><span class="bname">${esc(l.name)} <span class="hint" style="display:inline">${esc(l.english)}</span></span>
          <span class="bstat">
            <a href="${trackURL(l.code, "srt", 1)}" class="itp-dl">⇩ .srt</a>
            <a href="${trackURL(l.code, "vtt", 1)}" class="itp-dl">⇩ .vtt</a>
          </span>
          <button data-rev="${l.code}">Show in Finder</button></div>`).join("")
          : `<div class="hint" style="margin-top:6px">nothing to download yet</div>`}
      </div>`;

    wireEngine(box);
    $$("[data-lang]", box).forEach(b => b.onclick = () => {
      const c = b.dataset.lang;
      S.selected.has(c) ? S.selected.delete(c) : S.selected.add(c);
      renderMain();
    });
    $$("[data-view]", box).forEach(b => b.onclick = () => setView(b.dataset.view));
    $$("[data-rev]", box).forEach(b => b.onclick = () =>
      api("/api/media/reveal", { path: trackPathGuess(b.dataset.rev) })
        .catch(e => toast(e.message, true)));
    $("#itp-run", box).onclick = translateJob;
    const gv = $("#itp-getvid", box);
    if (gv) gv.onclick = fetchVideo;
    renderCues();
  }

  async function fetchVideo() {
    const b = $("#itp-getvid", el);
    b.disabled = true;
    try {
      const job = await api("/api/highlighter/fetch", { url: S.url, quality: "720" });
      const p = czProgress($("#itp-getprog", el), { label: "downloading the recording", acc: T.acc });
      watchJob(job.id, j => p.update(j));
      const done = await jobDone(job.id);
      p.finish(done);
      if (done.status === "done") open(S.source);
      else { b.disabled = false; if (done.status === "error") toast(done.error, true); }
    } catch (e) { b.disabled = false; toast(e.message, true); }
  }

  /* the srt lands beside the source — same shape the server writes */
  function trackPathGuess(code) {
    const base = S.session ? `${S.source}/meeting` : S.source.replace(/\.[^.]+$/, "");
    return `${base}.translated.${code}.srt`;
  }

  async function setView(code) {
    S.view = code;
    await loadCues(code);
    const prov = $("#itp-prov", el);
    if (prov) prov.innerHTML = provenanceHTML(code);
    $$("[data-view]", el).forEach(b => {
      const on = b.dataset.view === code;
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", String(on));
      b.style.borderColor = on ? T.acc : "";
      b.style.background = on ? T.acc : "";
      b.style.color = on ? "#fff" : "";
    });
    const video = $("#itp-video", el);
    if (video) {
      const want = (L(code) || {}).srclang;
      [...video.textTracks].forEach(t => {
        t.mode = t.language === want ? "showing" : "disabled";
      });
    }
  }

  async function loadCues(code) {
    try {
      S.cues = (await api("/api/interpreter/cues", { path: S.source, lang: code })).cues;
    } catch (e) { S.cues = []; }
    renderCues();
  }

  function renderCues() {
    const box = $("#itp-cues", el);
    if (!box) return;
    if (!S.cues.length) {
      box.innerHTML = `<div class="hint" style="padding:12px">no lines yet</div>`;
      return;
    }
    box.innerHTML = S.cues.map((c, i) => {
      const badges = [
        c.fallback ? `<span class="badge" title="the model dropped this line — the English stayed, honestly">kept in English</span>` : "",
        c.miss ? `<span class="badge" title="word-list terms lost in this line">word list: ${esc(c.miss.join(", "))}</span>` : "",
        c.corrected ? `<span class="badge" title="a reviewer corrected this line">✓ corrected</span>` : "",
      ].join("");
      return `<div data-cue="${i}" class="itp-cue${c.flag ? " flagged" : ""}" title="click to jump the video here">
        <span class="itp-cuet">${fmtT(c.start)}</span>
        <span style="flex:1;font-size:13px">${esc(c.text)}
          <span class="itp-cuesrc">${esc(c.src || "")}</span>
          ${badges}</span>
        <button data-flag="${i}" aria-pressed="${!!c.flag}"
          aria-label="${c.flag ? `unflag line ${i + 1}` : `flag line ${i + 1} for review`}"
          title="${c.flag ? "flagged — tap to unflag" : "flag this line for a reviewer"}"
          class="itp-flag">⚑</button>
      </div>`;
    }).join("");
    $$("[data-cue]", box).forEach(row => row.onclick = e => {
      if (e.target.dataset.flag !== undefined) return;
      const c = S.cues[+row.dataset.cue];
      const video = $("#itp-video", el);
      if (video && c) { video.currentTime = c.start; video.play().catch(() => {}); }
    });
    $$("[data-flag]", box).forEach(b => b.onclick = async e => {
      e.stopPropagation();
      const i = +b.dataset.flag;
      const on = !S.cues[i].flag;
      try {
        const r = await api("/api/interpreter/flag",
          { path: S.source, lang: S.view, i, on });
        if (on) S.cues[i].flag = { note: "" }; else delete S.cues[i].flag;
        (S.langs[S.view] || {}).n_flags = r.n_flags;
        renderCues();
        loadQueue();
        toast(on ? "flagged — it's in the reviewer list" : "unflagged");
      } catch (err) { toast(err.message, true); }
    });
  }

  /* ---------- the job ---------- */
  async function translateJob() {
    const langs = [...S.selected];
    try {
      const job = await api("/api/interpreter/translate",
        { path: S.source, langs, town: S.town,
          fresh: $("#itp-fresh", el) ? $("#itp-fresh", el).checked : false });
      const p = czProgress($("#itp-prog", el), {
        label: `translating ${langs.length} language${langs.length === 1 ? "" : "s"}`, acc: T.acc });
      watchJob(job.id, j => p.update(j));
      const done = await jobDone(job.id);
      p.finish(done);
      if (done.status === "done") {
        toast("subtitles written — check them before they air");
        S.selected.clear();
        open(S.source);
      } else if (done.status === "error") toast(done.error, true);
    } catch (e) { toast(e.message, true); }
  }

  /* ---------- inspector: engine, glossary, queue ---------- */
  async function loadStatus() {
    try {
      S.status = await api("/api/interpreter/status");
      const eng = $("#itp-engine", el);
      eng.innerHTML = S.status.engine.engine
        ? esc(S.status.engine.sentence)
        : `no engine yet — <a href="#" id="itp-eng-key">add an AI key</a>, or install an on-device
           model by hand (Models page). The page still reads existing subtitles and the reviewer list.`;
      const k = $("#itp-eng-key", el);
      if (k) k.onclick = async e => { e.preventDefault();
        if (await czKeyModal({ feature: "Translating captions" })) { await loadStatus(); S.source ? renderMain() : shelf(); } };
      $("#itp-qcount", el).textContent =
        S.status.queue_open ? `· ${S.status.queue_open} open` : "";
      if (!S.glossary) loadGlossary(S.town);
    } catch (e) { /* the page still opens tracks */ }
  }

  async function loadGlossary(town) {
    try {
      const r = await api(`/api/interpreter/glossary?town=${encodeURIComponent(town)}`);
      S.glossary = r.glossary; S.town = r.glossary.town;
      renderGlossary(r.towns || []);
    } catch (e) { $("#itp-gloss", el).innerHTML = `<div class="hint">${esc(e.message)}</div>`; }
  }

  function renderGlossary(towns) {
    const g = S.glossary;
    const box = $("#itp-gloss", el);
    const langs = S.status ? S.status.languages : [];
    const terms = Object.keys(g.terms || {});
    const rows = terms.map(t => {
      const r = (g.terms[t] || {})[S.glossLang] || {};
      const vetted = r.status === "vetted";
      return `<div style="display:flex;gap:5px;align-items:center;margin-top:4px">
        <span style="font-size:11px;flex:0 0 34%;color:var(--cream-dim);overflow:hidden;text-overflow:ellipsis" title="${esc(t)}">${esc(t)}</span>
        <input type="text" data-term="${esc(t)}" value="${esc(r.text || "")}" placeholder="—"
          style="flex:1;min-width:0;background:#fff;border:1px solid var(--line);border-radius:5px;padding:3px 6px;font-size:11px;color:var(--cream)">
        <button data-vet="${esc(t)}" title="${vetted ? "checked by a fluent reviewer" : "a suggestion — not yet checked"}"
          style="background:none;border:1px solid var(--line);border-radius:5px;cursor:pointer;font-size:10px;padding:2px 5px;
          color:${vetted ? "var(--ok, #7BA05B)" : "var(--cream-dim)"}">${vetted ? "checked" : "sugg."}</button>
      </div>`;
    }).join("");
    box.innerHTML = `
      <div class="field"><label>town</label>
        <select id="itp-town">${towns.map(t =>
          `<option value="${esc(t.town)}" ${t.town === g.town ? "selected" : ""}>${esc(t.label)}${t.edited ? " ·edited" : ""}</option>`).join("")}
        </select> <span class="hint" style="display:inline">v${g.version}</span></div>
      <div class="field"><label>never translate <span class="hint" style="display:inline">one per line — names, places</span></label>
        <textarea id="itp-keep" rows="4" spellcheck="false"
          style="font-size:11px;font-family:var(--mono)">${esc((g.keep || []).join("\n"))}</textarea></div>
      <div class="field"><label>civic terms, in
        <select id="itp-glang" style="width:auto">${langs.map(l =>
          `<option value="${l.code}" ${l.code === S.glossLang ? "selected" : ""}>${esc(l.name)}</option>`).join("")}
        </select></label>
        ${rows || `<div class="hint">no terms yet</div>`}
        <div style="display:flex;gap:5px;margin-top:6px">
          <input type="text" id="itp-newterm" placeholder="English term"
            style="flex:0 0 34%;min-width:0;background:#fff;border:1px solid var(--line);border-radius:5px;padding:3px 6px;font-size:11px;color:var(--cream)">
          <input type="text" id="itp-newrender" placeholder="in ${esc((L(S.glossLang) || {}).name || "")}"
            style="flex:1;min-width:0;background:#fff;border:1px solid var(--line);border-radius:5px;padding:3px 6px;font-size:11px;color:var(--cream)">
          <button class="btn" id="itp-addterm" style="width:auto;padding:3px 8px">+</button>
        </div>
      </div>
      <button class="btn" id="itp-glosssave" style="margin-top:6px">Save the word list</button>
      <div class="hint" style="margin-top:4px">the next translation uses it</div>`;

    $("#itp-town", box).onchange = e => loadGlossary(e.target.value);
    $("#itp-glang", box).onchange = e => { S.glossLang = e.target.value; renderGlossary(towns); };
    $$("input[data-term]", box).forEach(x => x.onchange = () => {
      const t = x.dataset.term;
      const slot = (g.terms[t] = g.terms[t] || {});
      if (x.value.trim()) slot[S.glossLang] = { text: x.value.trim(),
        status: (slot[S.glossLang] || {}).status === "vetted" ? "vetted" : "suggested" };
      else delete slot[S.glossLang];
    });
    $$("button[data-vet]", box).forEach(b => b.onclick = () => {
      const t = b.dataset.vet;
      const r = (g.terms[t] || {})[S.glossLang];
      if (!r || !r.text) { toast("write the translation first, then mark it checked", true); return; }
      r.status = r.status === "vetted" ? "suggested" : "vetted";
      renderGlossary(towns);
    });
    $("#itp-addterm", box).onclick = () => {
      const t = $("#itp-newterm", box).value.trim();
      const r = $("#itp-newrender", box).value.trim();
      if (!t) { toast("write the English term first", true); return; }
      g.terms[t] = g.terms[t] || {};
      if (r) g.terms[t][S.glossLang] = { text: r, status: "suggested" };
      renderGlossary(towns);
    };
    $("#itp-glosssave", box).onclick = async () => {
      g.keep = $("#itp-keep", box).value.split("\n").map(s => s.trim()).filter(Boolean);
      try {
        const r = await api("/api/interpreter/glossary", { town: g.town, data: g });
        S.glossary = r.glossary;
        renderGlossary(r.towns || towns);
        toast(`word list v${r.glossary.version} saved — the next translation uses it`);
      } catch (e) { toast(e.message, true); }
    };
  }

  async function loadQueue() {
    let items = [];
    try { items = (await api("/api/interpreter/queue")).items || []; } catch (e) {}
    S.queue = items;
    $("#itp-qcount", el).textContent = items.length ? `· ${items.length} open` : "";
    const box = $("#itp-queue", el);
    if (!items.length) {
      box.innerHTML = `<div class="hint" style="margin-top:4px">nothing flagged — all quiet</div>`;
      return;
    }
    box.innerHTML = items.slice(0, 30).map((r, k) => `
      <div style="border:1px solid var(--line);border-radius:7px;padding:6px 8px;margin-top:6px;font-size:11px;background:#fff">
        <div style="color:var(--cream-dim)">${esc(r.title || r.source)} · ${esc((L(r.lang) || {}).name || r.lang)} · line ${r.i + 1}</div>
        <div style="margin:3px 0">${esc(r.text)}</div>
        <div style="color:var(--cream-dim)">${esc(r.src)}</div>
        <textarea data-fix="${k}" rows="2" placeholder="the correct line — leave it as is to dismiss"
          style="width:100%;margin-top:4px;background:var(--ink-2);border:1px solid var(--line);border-radius:5px;padding:3px 6px;font-size:11px;color:var(--cream)">${esc(r.text)}</textarea>
        <div style="display:flex;gap:6px;margin-top:4px">
          <button class="btn" data-apply="${k}" style="width:auto;padding:2px 8px;font-size:11px">Save the fix</button>
          <button class="btn" data-dismiss="${k}" style="width:auto;padding:2px 8px;font-size:11px">It's fine</button>
        </div>
      </div>`).join("");
    const act = async (k, withFix) => {
      const r = S.queue[k];
      const fix = withFix ? $(`textarea[data-fix="${k}"]`, box).value.trim() : "";
      try {
        const res = await api("/api/interpreter/resolve",
          { source: r.source, lang: r.lang, i: r.i,
            correction: (withFix && fix !== r.text) ? fix : "" });
        toast(res.applied ? "fixed — the subtitle file rewrote itself" : "dismissed");
        loadQueue();
        if (S.source === r.source && S.view === r.lang) { loadCues(S.view); open(S.source); }
      } catch (e) { toast(e.message, true); }
    };
    $$("button[data-apply]", box).forEach(b => b.onclick = () => act(+b.dataset.apply, true));
    $$("button[data-dismiss]", box).forEach(b => b.onclick = () => act(+b.dataset.dismiss, false));
  }

  /* ---------- wire up ---------- */
  let inited = false;
  function init() {
    $("#itp-back", el).onclick = shelf;
    wireDropZone($("#itp-center", el), open);
  }

  async function onshow(arg) {
    const first = !inited;
    if (!inited) { init(); inited = true; }
    await loadStatus();
    loadQueue();
    if (arg && arg.openPath) open(arg.openPath);
    else if (first || !S.source) shelf();
  }

  function reset() {
    Object.assign(S, { source: null, meta: null, video: null, langs: {}, nSeg: 0,
      origin: null, session: false, selected: new Set(), view: null, cues: [], url: null });
    if (inited) shelf();
  }

  registerPage("interpreter", el, onshow, { reset });
  return { onshow };
})();
