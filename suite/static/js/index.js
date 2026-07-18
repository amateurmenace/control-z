/* Index — search first, the catalog answers in clips and moments.
   Plain words across filenames, folders and Scribe transcripts; transcript
   hits come back time-coded. Tick rows → FCPXML stringout or CSV. The scan
   is a queue job; missing drives stay listed and say so. */

const IndexPage = (() => {
  const T = toolById("index");
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-index";
  el.innerHTML = `
  <div class="ws" style="--acc:${T.acc}">
    <div class="mediabar">
      <span class="toolname"><i>Index</i> · knows where everything is</span>
      <input type="text" id="ix-q" placeholder="search in plain words — “crosswalk vote”, “b-roll harvard st”, a filename…" spellcheck="false">
      <button class="btn" style="width:auto" id="ix-go">Search</button>
      <span class="clipmeta" id="ix-stats"></span>
    </div>
    <div class="ws-body">
      <div class="ws-center" style="overflow-y:auto;padding:14px 20px" id="ix-results">
        <div class="empty-grain" style="padding:36px 8px;color:var(--cream-faint);text-align:center">
          add your footage folders on the right and scan once —
          the whole catalog appears here, newest first, and plain words
          narrow it (filenames, folders, Scribe transcripts)</div>
      </div>
      <div class="inspector" id="ix-insp">
        <div class="insp-head"><h2>Index</h2></div>

        <div class="insp-sec">
          <span class="tag">folders it watches</span>
          <div id="ix-folders"><div class="hint">none yet</div></div>
          <div class="field"><label>add a folder</label>
            <input type="text" id="ix-addpath" placeholder="/Volumes/Archive/Footage" spellcheck="false">
          </div>
          <button class="btn" id="ix-add">Add folder</button>
          <button class="btn primary" id="ix-scan" style="margin-top:8px">Rescan library</button>
          <div id="ix-scanhost"></div>
        </div>

        <div class="insp-sec">
          <span class="tag">selects — ticked clips</span>
          <div class="hint" id="ix-selmeta">nothing ticked yet</div>
          <button class="btn primary" id="ix-fcpxml" disabled>Export FCPXML stringout</button>
          <button class="btn" id="ix-csv" disabled>Export CSV</button>
          <button class="btn" id="ix-selwords" disabled
            title="Scribe's engine over the ticked clips that still lack a transcript — one queue job">✎ Words for ticked</button>
          <div class="hint" style="margin-top:6px">the stringout imports into Resolve as a
            timeline of your selects — File → Import → Timeline</div>
        </div>

        <div class="report" id="ix-report"></div>
      </div>
    </div>
  </div>`;

  const S = { rows: [], picked: new Set(), filter: "all", hasClips: false,
              stats: null };

  /* the JS twin of czcore/sidecars.py KINDS — kind → owning tool (accent).
     If a kind joins the law there, it joins here. */
  const KIND_TOOL = { words: "scribe", captions: "scribe", cut: "scribe",
                      moments: "highlighter", insight: "highlighter",
                      kit: "publisher", pivot: "pivot", clear: "clear" };
  const kindAcc = k => (toolById(KIND_TOOL[k]) || {}).acc || "var(--cream-dim)";

  async function loadStatus() {
    try {
      const st = await api("/api/index/status");
      S.stats = st.stats;
      const f = $("#ix-folders", el);
      f.innerHTML = st.folders.length ? st.folders.map(r => `
        <div class="batchrow" style="margin-bottom:5px">
          <span class="bname" style="flex:1" title="${esc(r.path)}">${esc(r.path.split("/").slice(-2).join("/"))}</span>
          <span class="bstat">${r.clips} clips</span>
          <button data-rm="${esc(r.path)}">×</button>
        </div>`).join("") : `<div class="hint">none yet</div>`;
      $$("button[data-rm]", f).forEach(b => b.onclick = async () => {
        if (!confirm(`stop watching ${b.dataset.rm}? its clips leave the catalog`)) return;
        await api("/api/index/folders", { remove: b.dataset.rm });
        loadStatus();
      });
      const s = st.stats;
      $("#ix-stats", el).innerHTML =
        `<b>${s.clips || 0}</b> clips · ${((s.seconds || 0) / 3600).toFixed(1)}h` +
        `${s.missing ? ` · ${s.missing} missing` : ""}` +
        (s.fts ? "" : " · slow search (no FTS5)");
    } catch (e) { /* first paint can miss; search still works */ }
  }

  /* the coverage band — the library counted, each gap one click of work */
  function coverBand() {
    const s = S.stats;
    if (!s || !s.clips) return "";
    const kinds = ["words", "moments", "pivot", "kit", "clear"]
      .map(k => ({ k, n: (s.coverage || {})[k] || 0 }))
      .filter(x => x.n || x.k === "words");
    return `<div class="ix-cover">
      <span class="ix-stat"><b>${s.clips}</b>clips</span>
      <span class="ix-stat"><b>${((s.seconds || 0) / 3600).toFixed(1)}</b>hours</span>
      ${kinds.map(({ k, n }) => `
        <button class="ix-stat ix-kind" data-f="${k}" ${n ? "" : "disabled"}
          title="${n} of ${s.clips} clips carry ${k}">
          <b style="color:${kindAcc(k)}">${n}</b>${k}</button>`).join("")}
      ${s.wordless ? `<button class="btn ix-gapbtn" id="ix-batchwords"
          title="run Scribe's engine over every clip that has sound and no transcript — one queue job">
          ✎ words for the ${s.wordless} without</button>`
        : `<span class="hint" style="align-self:center">every clip with sound has its words</span>`}
    </div>`;
  }

  async function batchWords(paths) {
    const n = paths ? paths.length : (S.stats || {}).wordless || 0;
    const hrs = ((S.stats || {}).seconds || 0) / 3600;
    // one click is one road, but 700 clips is a day of the machine's time —
    // say the scale out loud before the queue takes it
    if (!paths &&
        !confirm(`transcribe ${n} clip${n > 1 ? "s" : ""}? Scribe's engine, ` +
                 `one queue job, cancellable — but a big library ` +
                 `(yours is ${hrs.toFixed(1)}h) can take a long while.`)) return;
    const btn = $("#ix-batchwords", el);
    if (btn) btn.disabled = true;
    try {
      const job = await api("/api/index/transcribe-missing",
                            paths ? { paths } : {});
      const p = czProgress($("#ix-scanhost", el), {
        label: "the batch line — words", acc: "var(--index)" });
      watchJob(job.id, j => p.update(j));
      const done = await jobDone(job.id);
      p.finish(done);
      if (done.status === "error") { toast(done.error, true); }
      else {
        const r = done.result || {};
        toast(`${(r.done || []).length} clips got their words` +
              ((r.failed || []).length ? ` · ${r.failed.length} failed` : ""));
        (r.failed || []).slice(0, 4).forEach(f => toast(f, true));
      }
      await loadStatus();
      $("#ix-q", el).value.trim() ? search() : browse();
    } catch (e) {
      toast(e.message, true);
      if (btn) btn.disabled = false;
    }
  }

  function selMeta() {
    $("#ix-selmeta", el).textContent = S.picked.size
      ? `${S.picked.size} clip${S.picked.size > 1 ? "s" : ""} ticked`
      : "nothing ticked yet";
    $("#ix-fcpxml", el).disabled = !S.picked.size;
    $("#ix-csv", el).disabled = !S.picked.size;
    $("#ix-selwords", el).disabled = !S.picked.size;
  }

  function rowHTML(row) {
    const picked = S.picked.has(row.path);
    const res = row.width ? `${row.width}×${row.height}` : (row.codec || "");
    const carries = row.carries || [];
    return `<div class="ix-row${row.missing ? " missing" : ""}" data-path="${esc(row.path)}">
      <input type="checkbox" class="ix-tick" data-path="${esc(row.path)}" ${picked ? "checked" : ""}>
      <img class="ix-thumb" loading="lazy" src="${row.missing ? "" : frameURL(row.path, 24, 90)}"
        onerror="this.style.visibility='hidden'">
      <div class="ix-body">
        <div class="ix-name">${esc(row.name)}
          ${row.missing ? `<span class="badge warn">missing — drive unplugged?</span>` : ""}
          ${carries.map(k => `<span class="sc-chip" title="this clip carries ${k}">
            <i style="background:${kindAcc(k)}"></i>${k}</span>`).join("")}</div>
        <div class="ix-meta">${fmtTime(row.duration)} · ${res}${row.fps ? " @ " + (+row.fps).toFixed(2) : ""} ·
          ${esc(row.folder.split("/").pop())}
          ${row.missing ? "" : `<button class="ix-hit" data-hl="${esc(row.path)}"
            title="open this clip in Community Highlighter — find the moments">→ Highlighter</button>`}</div>
        ${(row.matches || []).map(m => `<button class="ix-hit" data-path="${esc(row.path)}" data-t="${m.t}"
            title="open in Scribe at this moment">${fmtTime(m.t)} “${esc(m.text)}”</button>`).join("")}
      </div>
    </div>`;
  }

  function wireRows(box) {
    $$(".ix-tick", box).forEach(c => c.onchange = () => {
      c.checked ? S.picked.add(c.dataset.path) : S.picked.delete(c.dataset.path);
      selMeta();
    });
    $$(".ix-hit", box).forEach(b => b.onclick = () => b.dataset.hl
      ? go("highlighter", { openPath: b.dataset.hl })
      : go("scribe", { openPath: b.dataset.path,
                       t: parseFloat(b.dataset.t) || 0 }));
    $$(".ix-row .ix-thumb", box).forEach(img => img.onclick = () => {
      const p = img.closest(".ix-row").dataset.path;
      go("scribe", { openPath: p });
    });
  }

  const FILTERS = [
    ["all", "all", () => true],
    ["words", "with words", r => (r.carries || []).includes("words")],
    ["wordless", "no words yet",
     r => !!r.audio && !(r.carries || []).includes("words") && !r.missing],
    ["moments", "moments", r => (r.carries || []).includes("moments")],
    ["pivot", "pivot", r => (r.carries || []).includes("pivot")],
    ["kit", "kit", r => (r.carries || []).includes("kit")],
    ["clear", "clear", r => (r.carries || []).includes("clear")],
    ["missing", "missing", r => !!r.missing],
  ];

  /* the catalog itself, newest first, grouped by folder — the browse the
     center always deserved: scan once and everything is HERE, no query
     needed. Plain words narrow it; clearing them brings the shelf back. */
  async function browse() {
    const box = $("#ix-results", el);
    box.innerHTML = `<div class="hint" style="padding:12px 2px">opening the catalog…</div>`;
    try {
      if (!S.stats) await loadStatus();
      const r = await api(`/api/index/search?q=&limit=300`);
      S.rows = r.rows;
      S.hasClips = !!r.rows.length;
      if (!r.rows.length) {
        box.innerHTML = `<div class="empty-grain" style="padding:36px 8px;color:var(--cream-faint);text-align:center">
          the catalog is empty — add a footage folder on the right and Rescan;
          every clip lands here, newest first</div>`;
        return;
      }
      const fit = FILTERS.find(f => f[0] === S.filter) || FILTERS[0];
      const rows = r.rows.filter(fit[2]);
      const counts = Object.fromEntries(FILTERS.map(f =>
        [f[0], r.rows.filter(f[2]).length]));
      const chips = `<div class="ix-chips">${FILTERS.map(([id, lab]) =>
        `<button class="pb-pill${S.filter === id ? " on" : ""}" data-f="${id}"
          ${counts[id] ? "" : "disabled"}>${lab} · ${counts[id]}</button>`).join("")}
        <span class="hint" style="margin-left:auto">newest first · type to narrow</span></div>`;
      const groups = [];
      for (const row of rows) {
        const g = groups.find(x => x.folder === row.folder);
        g ? g.rows.push(row) : groups.push({ folder: row.folder, rows: [row] });
      }
      box.innerHTML = coverBand() + chips + groups.map(g => `
        <div class="tag ix-folderhead" title="${esc(g.folder)}">${esc(g.folder.split("/").slice(-2).join("/"))}
          <span style="letter-spacing:0;text-transform:none"> · ${g.rows.length} clip${g.rows.length > 1 ? "s" : ""}</span></div>
        ${g.rows.map(rowHTML).join("")}`).join("");
      wireRows(box);
      $$("button[data-f]", box).forEach(b => b.onclick = () => {
        S.filter = b.dataset.f; browse(); });
      const bw = $("#ix-batchwords", box);
      if (bw) bw.onclick = batchWords;
    } catch (e) {
      box.innerHTML = `<div class="progmsg err" style="padding:12px 2px">${esc(e.message)}</div>`;
    }
  }

  async function search() {
    const q = $("#ix-q", el).value.trim();
    if (!q) return browse();
    const box = $("#ix-results", el);
    box.innerHTML = `<div class="hint" style="padding:12px 2px">looking…</div>`;
    try {
      const r = await api(`/api/index/search?q=${encodeURIComponent(q)}&limit=80`);
      S.rows = r.rows;
      if (!r.rows.length) {
        box.innerHTML = `<div class="empty-grain" style="padding:30px 8px;color:var(--cream-faint);text-align:center">
          nothing matched — Index only knows words from filenames, folders and transcripts.
          Scribe the clips that matter, rescan, ask again.</div>`;
        return;
      }
      box.innerHTML = `<div class="ix-chips"><button class="pb-pill" id="ix-back">← the whole catalog</button>
        <span class="hint">${r.rows.length} match${r.rows.length > 1 ? "es" : ""} for “${esc(q)}”</span></div>`
        + r.rows.map(rowHTML).join("");
      wireRows(box);
      $("#ix-back", box).onclick = () => { $("#ix-q", el).value = ""; browse(); };
    } catch (e) {
      box.innerHTML = `<div class="progmsg err" style="padding:12px 2px">${esc(e.message)}</div>`;
    }
  }

  async function scan() {
    const btn = $("#ix-scan", el);
    btn.disabled = true;
    try {
      const job = await api("/api/index/scan", {});
      const p = czProgress($("#ix-scanhost", el), {
        label: "scanning the library", acc: "var(--index)" });
      watchJob(job.id, j => p.update(j));
      const done = await jobDone(job.id);
      p.finish(done);
      btn.disabled = false;
      if (done.status === "error") { toast(done.error, true); return; }
      loadStatus();
      $("#ix-q", el).value ? search() : browse();
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  async function exportSel(kind) {
    try {
      const r = await api("/api/index/export", { paths: [...S.picked], kind });
      const rep = $("#ix-report", el);
      rep.classList.add("show");
      rep.innerHTML += `<b>→</b> ${esc(r.out)}\n   ${r.clips} clips · ${esc(r.note)}\n`;
    } catch (e) { toast(e.message, true); }
  }

  let inited = false;
  function init() {
    $("#ix-go", el).onclick = search;
    $("#ix-q", el).addEventListener("keydown", e => { if (e.key === "Enter") search(); });
    $("#ix-q", el).addEventListener("input", e => {
      if (!e.target.value.trim() && S.hasClips) browse();
    });
    $("#ix-add", el).onclick = async () => {
      const p = $("#ix-addpath", el).value.trim();
      if (!p) return;
      try {
        await api("/api/index/folders", { add: p });
        $("#ix-addpath", el).value = "";
        loadStatus();
        toast("added — now Rescan");
      } catch (e) { toast(e.message, true); }
    };
    $("#ix-scan", el).onclick = scan;
    $("#ix-fcpxml", el).onclick = () => exportSel("fcpxml");
    $("#ix-csv", el).onclick = () => exportSel("csv");
    $("#ix-selwords", el).onclick = () => batchWords([...S.picked]);
  }

  function onshow() {
    if (!inited) { init(); inited = true; }
    loadStatus();
    if (!$("#ix-q", el).value.trim()) browse();
  }

  registerPage("index", el, onshow);
  return { onshow };
})();
