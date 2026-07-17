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
          add your footage folders on the right, scan once, then just ask —
          words come from filenames, folders, and Scribe transcripts</div>
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
          <div class="prog"><i id="ix-scanbar"></i></div>
          <div class="progmsg" id="ix-scanmsg"></div>
        </div>

        <div class="insp-sec">
          <span class="tag">selects — ticked clips</span>
          <div class="hint" id="ix-selmeta">nothing ticked yet</div>
          <button class="btn primary" id="ix-fcpxml" disabled>Export FCPXML stringout</button>
          <button class="btn" id="ix-csv" disabled>Export CSV</button>
          <div class="hint" style="margin-top:6px">the stringout imports into Resolve as a
            timeline of your selects — File → Import → Timeline</div>
        </div>

        <div class="report" id="ix-report"></div>
      </div>
    </div>
  </div>`;

  const S = { rows: [], picked: new Set() };

  async function loadStatus() {
    try {
      const st = await api("/api/index/status");
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
        `<b>${s.clips || 0}</b> clips · ${((s.seconds || 0) / 3600).toFixed(1)}h · ` +
        `${s.transcribed || 0} transcribed${s.missing ? ` · ${s.missing} missing` : ""}` +
        (s.fts ? "" : " · slow search (no FTS5)");
    } catch (e) { /* first paint can miss; search still works */ }
  }

  function selMeta() {
    $("#ix-selmeta", el).textContent = S.picked.size
      ? `${S.picked.size} clip${S.picked.size > 1 ? "s" : ""} ticked`
      : "nothing ticked yet";
    $("#ix-fcpxml", el).disabled = !S.picked.size;
    $("#ix-csv", el).disabled = !S.picked.size;
  }

  async function search() {
    const box = $("#ix-results", el);
    box.innerHTML = `<div class="hint" style="padding:12px 2px">looking…</div>`;
    try {
      const r = await api(`/api/index/search?q=${encodeURIComponent($("#ix-q", el).value)}&limit=80`);
      S.rows = r.rows;
      if (!r.rows.length) {
        box.innerHTML = `<div class="empty-grain" style="padding:30px 8px;color:var(--cream-faint);text-align:center">
          nothing matched — Index only knows words from filenames, folders and transcripts.
          Scribe the clips that matter, rescan, ask again.</div>`;
        return;
      }
      box.innerHTML = r.rows.map(row => {
        const picked = S.picked.has(row.path);
        const res = row.width ? `${row.width}×${row.height}` : (row.codec || "");
        return `<div class="ix-row${row.missing ? " missing" : ""}" data-path="${esc(row.path)}">
          <input type="checkbox" class="ix-tick" data-path="${esc(row.path)}" ${picked ? "checked" : ""}>
          <img class="ix-thumb" loading="lazy" src="${row.missing ? "" : frameURL(row.path, 24, 90)}"
            onerror="this.style.visibility='hidden'">
          <div class="ix-body">
            <div class="ix-name">${esc(row.name)}
              ${row.missing ? `<span class="badge warn">missing — drive unplugged?</span>` : ""}
              ${row.sidecar_mtime ? `<span class="badge">words</span>` : ""}</div>
            <div class="ix-meta">${fmtTime(row.duration)} · ${res}${row.fps ? " @ " + (+row.fps).toFixed(2) : ""} ·
              ${esc(row.folder.split("/").pop())}</div>
            ${(row.matches || []).map(m => `<button class="ix-hit" data-path="${esc(row.path)}" data-t="${m.t}"
                title="open in Scribe at this moment">${fmtTime(m.t)} “${esc(m.text)}”</button>`).join("")}
          </div>
        </div>`;
      }).join("");
      $$(".ix-tick", box).forEach(c => c.onchange = () => {
        c.checked ? S.picked.add(c.dataset.path) : S.picked.delete(c.dataset.path);
        selMeta();
      });
      $$(".ix-hit", box).forEach(b => b.onclick = () =>
        go("scribe", { openPath: b.dataset.path }));
      $$(".ix-row .ix-thumb", box).forEach(img => img.onclick = () => {
        const p = img.closest(".ix-row").dataset.path;
        go("scribe", { openPath: p });
      });
    } catch (e) {
      box.innerHTML = `<div class="progmsg err" style="padding:12px 2px">${esc(e.message)}</div>`;
    }
  }

  async function scan() {
    const btn = $("#ix-scan", el);
    btn.disabled = true;
    $("#ix-scanbar", el).style.width = "10%";
    try {
      const job = await api("/api/index/scan", {});
      watchJob(job.id, j => {
        $("#ix-scanmsg", el).textContent = j.message || j.status;
        $("#ix-scanbar", el).style.width = j.status === "running" ? "55%" : "10%";
      });
      const done = await jobDone(job.id);
      btn.disabled = false;
      $("#ix-scanbar", el).style.width = done.status === "done" ? "100%" : "0";
      if (done.status === "error") { toast(done.error, true); return; }
      $("#ix-scanmsg", el).textContent = done.message || "scanned";
      loadStatus();
      if ($("#ix-q", el).value) search();
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
  }

  function onshow() {
    if (!inited) { init(); inited = true; }
    loadStatus();
  }

  registerPage("index", el, onshow);
  return { onshow };
})();
