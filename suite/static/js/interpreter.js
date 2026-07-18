/* Community Interpreter — every read meeting, carried across.
   Open anything Highlighter has read: pick languages, one queue job lands
   timed .srt/.vtt tracks beside the meeting in the seven panel languages
   (Simple English first-class). Provenance is UI on every track; every
   line takes one tap to flag into the review queue; corrections come back
   through the queue and rewrite the track in place. */

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
      <input type="text" id="itp-path" spellcheck="false"
        placeholder="/path/to/program.mp4 — or a Highlighter session folder"
        style="flex:1;min-width:200px;background:var(--ink);border:1px solid var(--line);border-radius:7px;padding:6px 9px;font-size:12px;font-family:var(--mono);color:var(--cream)">
      <button class="btn" id="itp-open" style="width:auto">Open</button>
      <button class="btn" id="itp-browse" style="width:auto">Browse…</button>
    </div>
    <div class="ws-body">
      <div class="ws-center" id="itp-center" style="overflow-y:auto;padding:16px 20px"></div>
      <div class="inspector">
        <div class="insp-head"><h2>Interpreter</h2></div>
        <div class="insp-sec">
          <span class="tag">the engine</span>
          <div class="hint" id="itp-engine">—</div>
        </div>
        <div class="insp-sec" id="itp-glossbox">
          <span class="tag">glossary</span>
          <div class="hint">do-not-translate names + vetted civic terms — applied on every pass</div>
          <div id="itp-gloss"></div>
        </div>
        <div class="insp-sec">
          <span class="tag">review queue <span id="itp-qcount"></span></span>
          <div class="hint">flagged lines, every language, every meeting</div>
          <div id="itp-queue"></div>
        </div>
        <div class="report" id="itp-report"></div>
      </div>
    </div>
  </div>`;

  const S = { source: null, meta: null, video: null, langs: {}, nSeg: 0,
              origin: null, session: false, status: null, selected: new Set(),
              view: null, cues: [], glossary: null, glossLang: "es",
              town: "brookline", queue: [] };

  const fmtT = t => { t = Math.max(0, Math.floor(t)); return t >= 3600
    ? `${Math.floor(t / 3600)}:${String(Math.floor(t % 3600 / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`
    : `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`; };
  const L = code => (S.status ? S.status.languages : []).find(l => l.code === code);
  const trackURL = (code, fmt, dl) => `/api/interpreter/track?path=${encodeURIComponent(S.source)}` +
    `&lang=${code}&fmt=${fmt || "vtt"}${dl ? "&dl=1" : ""}&r=${(S.langs[code] || {}).created || 0}`;

  /* ---------- open + the shelf ---------- */
  async function open(path) {
    if (!path) return;
    $("#itp-path", el).value = path;
    const box = $("#itp-center", el);
    box.innerHTML = `<div class="hint" style="padding:16px 2px">reading the sidecars…</div>`;
    try {
      const r = await api("/api/interpreter/open", { path });
      S.source = r.source; S.meta = r.meta; S.video = r.video;
      S.langs = r.languages; S.nSeg = r.n_segments; S.origin = r.origin;
      S.session = r.session;
      S.view = Object.keys(S.langs).find(c => S.langs[c].has) || null;
      S.cues = [];
      renderMain();
      if (S.view) loadCues(S.view);
    } catch (e) {
      box.innerHTML = `<div class="progmsg err" style="padding:14px 2px">${esc(e.message)}</div>`;
    }
  }

  async function shelf() {
    const box = $("#itp-center", el);
    let rows = [];
    try { rows = (await api("/api/interpreter/library")).rows || []; } catch (e) {}
    if (S.source) return;   // an open beat us here — never clobber it
    const items = rows.slice(0, 24).map(r => `
      <div class="batchrow" data-open="${esc(r.source)}" role="button" tabindex="0"
        aria-label="open ${esc(r.title)}" style="cursor:pointer">
        <span class="bname" title="${esc(r.source)}">${esc(r.title)}</span>
        <span class="bstat">${r.video ? "▮ video" : "words only"}${r.duration ? ` · ${fmtT(r.duration)}` : ""}</span>
      </div>`).join("");
    box.innerHTML = `
      <div class="empty-grain" style="padding:28px 8px;color:var(--cream-dim);max-width:620px">
        <b>drop a read meeting here</b> — a file with sidecars, or a Highlighter session folder.<br>
        seven languages ride the panel: Español · Simple English · 中文 · Português · Kreyòl · Tiếng Việt · Русский.
        every track lands timed (.srt + .vtt), labeled AI, one tap to flag any line.<br><br>
        <span class="hint">fresh meeting? read it first: Grabber fetches, Highlighter reads, then this desk carries it across.</span>
      </div>
      ${rows.length ? `<div class="tag" style="margin-top:10px">read meetings — newest first</div>${items}` : ""}`;
    $$("[data-open]", box).forEach(b => {
      b.onclick = () => open(b.dataset.open);
      b.onkeydown = e => { if (e.key === "Enter" || e.key === " ") {
        e.preventDefault(); open(b.dataset.open); } };
    });
  }

  /* ---------- the loaded view ---------- */
  function chipHTML(l) {
    const st = S.langs[l.code] || {};
    const on = S.selected.has(l.code);
    const dot = st.has ? (st.stale ? "⟳" : "✓") : "·";
    const flags = st.n_flags ? ` ⚑${st.n_flags}` : "";
    return `<button class="chip${on ? " on" : ""}" data-lang="${l.code}"
      aria-pressed="${on}" aria-label="${esc(l.name)} — ${st.has
        ? (st.stale ? "track stale" : "track ready") : "no track yet"}${on ? ", selected" : ""}"
      style="${on ? `border-color:${T.acc};color:var(--cream)` : ""}"
      title="${st.has ? (st.stale ? "track exists but the transcript changed — re-run" : "track ready") : "no track yet — select and carry across"}">
      ${dot} ${esc(l.name)}${flags}</button>`;
  }

  function provenanceHTML(code) {
    const st = S.langs[code] || {};
    if (!st.has) return "";
    const g = st.glossary || {};
    const where = st.engine === "local" ? " — on-device" : " (your key)";
    const bits = [
      `<b>AI translation — beta</b>`,
      esc(st.model || "?") + where,
      `glossary ${esc(g.town || "?")} v${g.version ?? "?"}`,
      esc(st.review || "unreviewed"),
    ];
    if (st.n_fallback) bits.push(`${st.n_fallback} lines kept English`);
    if (st.n_miss) bits.push(`${st.n_miss} glossary misses`);
    if (st.n_corrected) bits.push(`✓ ${st.n_corrected} corrected`);
    return `<div style="border:1px solid var(--line);border-left:3px solid ${T.acc};
      border-radius:7px;padding:7px 10px;margin:8px 0;font-size:12px;color:var(--cream-dim)">
      ${bits.join(" · ")}</div>`;
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
      </video>
      <div class="hint">tracks ride the player — pick a language in its caption menu, or read the rail below</div>`
      : `<div class="hint" style="margin-top:10px">no local recording — the tracks still write and export;
         fetch the full video in Highlighter to watch them ride the player</div>`;

    const rail = !avail.length ? "" : `
      <div class="tag" style="margin-top:18px">the track — read it line by line</div>
      <div class="chips" style="margin:6px 0">
        ${avail.map(l => `<button class="chip${S.view === l.code ? " on" : ""}" data-view="${l.code}"
          aria-pressed="${S.view === l.code}" aria-label="read the ${esc(l.name)} track"
          style="${S.view === l.code ? `border-color:${T.acc};color:var(--cream)` : ""}">${esc(l.name)}</button>`).join("")}
      </div>
      <div id="itp-prov">${S.view ? provenanceHTML(S.view) : ""}</div>
      <div id="itp-cues" style="flex:0 0 auto;max-height:420px;overflow-y:auto;border:1px solid var(--line);border-radius:9px"></div>
      <div class="tag" style="margin-top:16px">exports — timed, labeled, ready for the player or the plant</div>
      ${avail.map(l => `<div class="batchrow"><span class="bname">${esc(l.name)}</span>
        <span class="bstat">
          <a href="${trackURL(l.code, "srt", 1)}" style="color:var(--cream-dim)">SRT ⇩</a> ·
          <a href="${trackURL(l.code, "vtt", 1)}" style="color:var(--cream-dim)">VTT ⇩</a>
        </span>
        <button data-rev="${l.code}">Reveal</button></div>`).join("")}`;

    box.innerHTML = `
      <div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap">
        <h1 style="font-size:19px">${esc(S.meta.title)}</h1>
        <span class="hint">${S.nSeg} segments · words from ${esc(S.origin || "the transcript")}${S.meta.duration ? ` · ${fmtT(S.meta.duration)}` : ""}</span>
      </div>
      <div class="tag" style="margin-top:14px">the languages — select, then carry across</div>
      <div class="chips" style="margin:6px 0">${langs.map(chipHTML).join("")}</div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:4px">
        <button class="btn primary" id="itp-run" style="width:auto" ${nSel && engineOK ? "" : "disabled"}>
          ▶ Carry across${nSel ? ` (${nSel})` : ""}</button>
        <label class="hint" style="display:flex;align-items:center;gap:5px">
          <input type="checkbox" id="itp-fresh"> re-run even if cached</label>
        <span class="hint" id="itp-jobstat"></span>
      </div>
      ${engineOK ? "" : `<div class="progmsg err" style="margin:8px 0">${esc(S.status ? S.status.engine.sentence : "…")}</div>`}
      ${player}
      ${rail}`;

    $$("[data-lang]", box).forEach(b => b.onclick = () => {
      const c = b.dataset.lang;
      S.selected.has(c) ? S.selected.delete(c) : S.selected.add(c);
      renderMain();
    });
    $$("[data-view]", box).forEach(b => b.onclick = () => setView(b.dataset.view));
    $$("[data-rev]", box).forEach(b => b.onclick = () =>
      api("/api/media/reveal", { path: trackPathGuess(b.dataset.rev) })
        .catch(e => toast(e.message, true)));
    $("#itp-run", box) && ($("#itp-run", box).onclick = translateJob);
    renderCues();
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
      b.style.borderColor = on ? T.acc : "";
      b.style.color = on ? "var(--cream)" : "";
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
        c.fallback ? `<span class="badge" title="the model dropped this line — the English stayed, honestly">kept English</span>` : "",
        c.miss ? `<span class="badge" title="do-not-translate terms lost in this line">glossary: ${esc(c.miss.join(", "))}</span>` : "",
        c.corrected ? `<span class="badge" title="a reviewer corrected this line">✓ corrected</span>` : "",
      ].join("");
      return `<div data-cue="${i}" style="display:flex;gap:8px;padding:6px 10px;border-bottom:1px solid var(--line);
        ${c.flag ? "background:rgba(233,196,106,.06);" : ""}cursor:pointer" title="click to jump the player">
        <span style="font-family:var(--mono);font-size:11px;color:var(--cream-dim);min-width:44px;padding-top:2px">${fmtT(c.start)}</span>
        <span style="flex:1;font-size:13px">${esc(c.text)}
          <span style="display:block;font-size:11px;color:var(--cream-dim);margin-top:1px">${esc(c.src || "")}</span>
          ${badges}</span>
        <button data-flag="${i}" aria-pressed="${!!c.flag}"
          aria-label="${c.flag ? `unflag line ${i + 1}` : `flag line ${i + 1} for review`}"
          title="${c.flag ? "flagged — tap to unflag" : "flag this line for review"}"
          style="background:none;border:none;cursor:pointer;font-size:14px;align-self:flex-start;
          color:${c.flag ? "var(--amber, #E9C46A)" : "var(--cream-dim)"}">⚑</button>
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
        toast(on ? "flagged — it joins the review queue" : "unflagged");
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
      const p = czProgress($(".inspector", el), {
        label: "carrying it across", acc: T.acc });
      watchJob(job.id, j => p.update(j));
      const done = await jobDone(job.id);
      p.finish(done);
      if (done.status === "done") {
        toast("tracks written — read before it airs");
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
      eng.innerHTML = esc(S.status.engine.sentence) +
        (S.status.engine.engine ? "" :
          " — the page still reads existing tracks and the review queue");
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
          style="flex:1;min-width:0;background:var(--ink);border:1px solid var(--line);border-radius:5px;padding:3px 6px;font-size:11px;color:var(--cream)">
        <button data-vet="${esc(t)}" title="${vetted ? "vetted by a reviewer" : "suggested — not yet vetted"}"
          style="background:none;border:1px solid var(--line);border-radius:5px;cursor:pointer;font-size:10px;padding:2px 5px;
          color:${vetted ? "var(--ok, #7BA05B)" : "var(--cream-dim)"}">${vetted ? "vetted" : "sugg."}</button>
      </div>`;
    }).join("");
    box.innerHTML = `
      <div class="field"><label>town</label>
        <select id="itp-town">${towns.map(t =>
          `<option value="${esc(t.town)}" ${t.town === g.town ? "selected" : ""}>${esc(t.label)}${t.edited ? " ·edited" : ""}</option>`).join("")}
        </select> <span class="hint" style="display:inline">v${g.version}</span></div>
      <div class="field"><label>never translate <span class="hint" style="display:inline">one per line</span></label>
        <textarea id="itp-keep" rows="4" spellcheck="false"
          style="font-size:11px;font-family:var(--mono)">${esc((g.keep || []).join("\n"))}</textarea></div>
      <div class="field"><label>terms — renders for
        <select id="itp-glang" style="width:auto">${langs.map(l =>
          `<option value="${l.code}" ${l.code === S.glossLang ? "selected" : ""}>${esc(l.name)}</option>`).join("")}
        </select></label>
        ${rows || `<div class="hint">no terms yet</div>`}
        <div style="display:flex;gap:5px;margin-top:6px">
          <input type="text" id="itp-newterm" placeholder="new term"
            style="flex:0 0 34%;min-width:0;background:var(--ink);border:1px solid var(--line);border-radius:5px;padding:3px 6px;font-size:11px;color:var(--cream)">
          <input type="text" id="itp-newrender" placeholder="its ${esc((L(S.glossLang) || {}).name || "")} render"
            style="flex:1;min-width:0;background:var(--ink);border:1px solid var(--line);border-radius:5px;padding:3px 6px;font-size:11px;color:var(--cream)">
          <button class="btn" id="itp-addterm" style="width:auto;padding:3px 8px">+</button>
        </div>
      </div>
      <button class="btn" id="itp-glosssave" style="margin-top:6px">Save glossary</button>
      <div class="hint" style="margin-top:4px">saves bump the version; the next pass carries it</div>`;

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
      if (!r || !r.text) { toast("write a render first, then vet it", true); return; }
      r.status = r.status === "vetted" ? "suggested" : "vetted";
      renderGlossary(towns);
    });
    $("#itp-addterm", box).onclick = () => {
      const t = $("#itp-newterm", box).value.trim();
      const r = $("#itp-newrender", box).value.trim();
      if (!t) { toast("name the term first", true); return; }
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
        toast(`glossary v${r.glossary.version} saved — the next pass carries it`);
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
      box.innerHTML = `<div class="hint" style="margin-top:4px">nothing flagged — the panel is quiet</div>`;
      return;
    }
    box.innerHTML = items.slice(0, 30).map((r, k) => `
      <div style="border:1px solid var(--line);border-radius:7px;padding:6px 8px;margin-top:6px;font-size:11px">
        <div style="color:var(--cream-dim)">${esc(r.title || r.source)} · ${esc((L(r.lang) || {}).name || r.lang)} · line ${r.i + 1}</div>
        <div style="margin:3px 0">${esc(r.text)}</div>
        <div style="color:var(--cream-dim)">${esc(r.src)}</div>
        <textarea data-fix="${k}" rows="2" placeholder="correction — leave empty to dismiss"
          style="width:100%;margin-top:4px;background:var(--ink);border:1px solid var(--line);border-radius:5px;padding:3px 6px;font-size:11px;color:var(--cream)">${esc(r.text)}</textarea>
        <div style="display:flex;gap:6px;margin-top:4px">
          <button class="btn" data-apply="${k}" style="width:auto;padding:2px 8px;font-size:11px">Apply correction</button>
          <button class="btn" data-dismiss="${k}" style="width:auto;padding:2px 8px;font-size:11px">Dismiss</button>
        </div>
      </div>`).join("");
    const act = async (k, withFix) => {
      const r = S.queue[k];
      const fix = withFix ? $(`textarea[data-fix="${k}"]`, box).value.trim() : "";
      try {
        const res = await api("/api/interpreter/resolve",
          { source: r.source, lang: r.lang, i: r.i,
            correction: (withFix && fix !== r.text) ? fix : "" });
        toast(res.applied ? "corrected — the track rewrote itself" : "dismissed");
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
    $("#itp-open", el).onclick = () => open($("#itp-path", el).value.trim());
    $("#itp-path", el).addEventListener("keydown", e => {
      if (e.key === "Enter") open($("#itp-path", el).value.trim()); });
    $("#itp-browse", el).onclick = () => browseForPath(open);
    wireDropZone($("#itp-center", el), open);
  }

  function onshow(arg) {
    if (!inited) { init(); inited = true; shelf(); }
    loadStatus();
    loadQueue();
    if (arg && arg.openPath) open(arg.openPath);
    else if (S.source) { /* keep the loaded meeting */ }
  }

  registerPage("interpreter", el, onshow);
  return { onshow };
})();
