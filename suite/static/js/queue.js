/* Queue: every heavy operation across every tool — progress, cancel — and
   the permanent history: every job that ever finished, searchable, never
   cleared by "clear finished" (czcore/appshell/jobs.py keeps it). */

const QueuePage = (() => {
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-queue";
  el.innerHTML = `<div class="page-pad">
    <div class="cz-resetslot" style="display:flex;align-items:baseline;gap:12px">
      <div><div class="tag">suite</div>
      <h1 style="margin-top:6px">Queue</h1></div>
    </div>
    <div class="q-tabs" role="tablist">
      <button class="q-tab on" role="tab" data-tab="now" aria-selected="true">Now &amp; recent</button>
      <button class="q-tab" role="tab" data-tab="history" aria-selected="false">History — everything, ever</button>
    </div>

    <div id="q-now">
      <div style="color:var(--cream-dim);font-size:12.5px;margin-top:10px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <span>one job at a time, in order. Cancel is honest: partial files are removed.
          “Clear finished” tidies this list — the History tab keeps every record.</span>
        <button class="btn" style="width:auto;padding:4px 12px;font-size:11.5px;margin-left:auto"
          id="q-clearhist">clear finished</button>
      </div>
      <div style="display:flex;gap:8px;align-items:center;margin-top:10px;font-size:12px;flex-wrap:wrap">
        <span class="tag" style="letter-spacing:.1em">outputs land in</span>
        <input id="q-outroot" spellcheck="false" style="flex:1;min-width:260px;background:#fff;
          border:1px solid var(--line);border-radius:7px;padding:5px 9px;font-family:var(--mono);font-size:11px">
        <button class="btn" id="q-outpick" style="width:auto;padding:4px 12px;font-size:11.5px">Choose…</button>
        <button class="btn" id="q-outsave" style="width:auto;padding:4px 12px;font-size:11.5px">Save</button>
        <button class="btn" id="q-outreset" style="width:auto;padding:4px 12px;font-size:11.5px"
          title="back to ~/Movies/control-z">Default</button>
      </div>
      <div class="hint" style="margin-top:4px">renders, reels and kits land here (each tool in its own
        folder) — downloads go to your Downloads folder (Settings → Downloads)</div>
      <div id="q-rows" style="margin-top:14px"></div>
    </div>

    <div id="q-history" style="display:none">
      <div class="q-filters">
        <input id="q-hq" type="text" spellcheck="false" placeholder="search what ran — a title, a file name, an error…">
        <select id="q-htool"><option value="">every tool</option></select>
        <select id="q-hstatus">
          <option value="">every outcome</option>
          <option value="done">done</option>
          <option value="error">failed</option>
          <option value="cancelled">cancelled</option>
        </select>
        <button class="btn" id="q-hcsv" style="width:auto;padding:5px 12px;font-size:11.5px"
          title="the whole history (with these filters) as a spreadsheet — saved to your outputs folder">⤓ Export CSV</button>
      </div>
      <div class="hint" id="q-hcount" style="margin-top:8px"></div>
      <div id="q-hrows" style="margin-top:6px"></div>
      <div style="text-align:center;margin-top:12px">
        <button class="btn" id="q-hmore" style="width:auto;display:none">Show older</button>
      </div>
    </div>
  </div>`;

  const H = { rows: [], total: 0, offset: 0, tab: "now", timer: 0 };

  $("#q-clearhist", el).onclick = async () => {
    try {
      const r = await api("/api/jobs/clear-history", {});
      toast(`${r.removed} finished job(s) cleared from this list — History keeps them`);
      CZ.jobs.clear();
      (await api("/api/jobs")).forEach(j => CZ.jobs.set(j.id, j));
      render();
    } catch (e) { toast(e.message, true); }
  };

  const rows = () => $("#q-rows", el);

  /* where a finished job's files landed. Results come in every shape
     (Narrator's `written` is a {kind: path} map, others a list, some a
     bare string) — flatten, keep paths, drop repeats. */
  const flat = v => Array.isArray(v) ? v
    : v && typeof v === "object" ? Object.values(v) : v ? [v] : [];
  function outputs(j) {
    const r = (j.result && typeof j.result === "object") ? j.result : {};
    return [r.out, r.path, ...flat(r.paths), ...flat(r.written)]
      .filter((p, i, a) => p && typeof p === "string" && p.startsWith("/")
        && a.indexOf(p) === i).slice(0, 3);
  }

  function rowHTML(j) {
    const t = toolById(j.tool);
    const acc = t ? t.acc : "var(--cream-dim)";
    const pct = j.progress >= 0 ? Math.round(j.progress * 100) : null;
    const active = j.status === "queued" || j.status === "running";
    const when = j.created_at ? new Date(j.created_at * 1000).toLocaleTimeString() : "";
    return `<div class="qrow" data-id="${j.id}">
      <div class="qtool" style="--acc-color:${acc}">${esc(j.tool || "suite")}</div>
      <div>
        <div class="qlabel">${esc(j.label || j.kind)}</div>
        <div class="qmsg ${j.status === "error" ? "err" : ""}">${esc(j.error || j.message || "")}</div>
        ${outputs(j).map(p => `<button class="qout" data-rev="${esc(p)}"
            title="reveal in the file browser">📁 ${esc(p)}</button>`).join("")}
        ${j.status === "running" ? `<div class="prog" style="--acc:${acc}"><i style="width:${pct == null ? 30 : pct}%"></i></div>` : ""}
      </div>
      <div>
        <span class="stat-chip stat-${j.status}">${j.status}</span>
        <div class="qstat">${when}${pct != null && j.status === "running" ? ` · ${pct}%` : ""}</div>
      </div>
      <div class="qact">${active ? `<button data-cancel="${j.id}">cancel</button>` : ""}</div>
    </div>`;
  }

  function wireRows(box) {
    $$("button[data-cancel]", box).forEach(b => b.onclick = () => cancelJob(b.dataset.cancel, b));
    $$("button.qout", box).forEach(b => b.onclick = async () => {
      try { await api("/api/media/reveal", { path: b.dataset.rev }); }
      catch (e) { toast(e.message, true); }
    });
  }

  function render() {
    const all = [...CZ.jobs.values()].sort((a, b) => (b.created_at || 0) - (a.created_at || 0));
    if (!all.length) {
      rows().innerHTML = `<div class="empty-grain" style="padding:32px 2px;color:var(--cream-faint)">
        nothing running and nothing recent — analyses, downloads, renders and exports land here.
        Everything that ever finished is in the History tab.</div>`;
      return;
    }
    rows().innerHTML = all.map(rowHTML).join("");
    wireRows(rows());
  }

  /* ---------- the permanent history ---------- */
  const fmtDay = ts => {
    const d = new Date(ts * 1000);
    return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", year: "numeric" });
  };
  const took = r => {
    if (!r.started_at || !r.finished_at) return "";
    const s = Math.max(0, Math.round(r.finished_at - r.started_at));
    return s >= 3600 ? `${Math.floor(s / 3600)}h ${Math.floor(s % 3600 / 60)}m`
      : s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;
  };
  function histQuery() {
    const p = new URLSearchParams();
    const q = $("#q-hq", el).value.trim();
    if (q) p.set("q", q);
    if ($("#q-htool", el).value) p.set("tool", $("#q-htool", el).value);
    if ($("#q-hstatus", el).value) p.set("status", $("#q-hstatus", el).value);
    return p;
  }
  async function loadHistory(more) {
    const p = histQuery();
    p.set("limit", "100");
    p.set("offset", String(more ? H.offset : 0));
    let r;
    try { r = await api("/api/jobs/history?" + p.toString()); }
    catch (e) { $("#q-hrows", el).innerHTML = `<div class="progmsg err">${esc(e.message)}</div>`; return; }
    H.rows = more ? H.rows.concat(r.rows) : r.rows;
    H.total = r.total;
    H.offset = H.rows.length;
    renderHistory();
  }
  function renderHistory() {
    const box = $("#q-hrows", el);
    $("#q-hcount", el).textContent = H.total
      ? `${H.total.toLocaleString()} finished job${H.total === 1 ? "" : "s"}${histQuery().toString() ? " match" : " on record"} — showing ${H.rows.length}`
      : "";
    if (!H.rows.length) {
      box.innerHTML = `<div class="empty-grain" style="padding:32px 2px;color:var(--cream-faint)">
        ${histQuery().toString() ? "nothing matches — loosen the filters" : "no finished jobs yet — every one lands here, for good"}</div>`;
      $("#q-hmore", el).style.display = "none";
      return;
    }
    let day = "", html = "";
    for (const r of H.rows) {
      const d = fmtDay(r.created_at || r.finished_at);   // the list's own order
      if (d !== day) { day = d; html += `<div class="q-day">${esc(d)}</div>`; }
      const t = toolById(r.tool);
      const time = new Date((r.finished_at || r.created_at) * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
      html += `<div class="qrow q-hrow">
        <div class="qtool" style="--acc-color:${t ? t.acc : "var(--cream-dim)"}">${esc(r.tool || "suite")}</div>
        <div>
          <div class="qlabel">${esc(r.label || r.kind)}</div>
          <div class="qmsg ${r.status === "error" ? "err" : ""}">${esc(r.error || r.message || "")}</div>
          ${outputs(r).map(p => `<button class="qout" data-rev="${esc(p)}"
              title="reveal in the file browser">📁 ${esc(p)}</button>`).join("")}
        </div>
        <div><span class="stat-chip stat-${r.status}">${r.status === "error" ? "failed" : r.status}</span>
          <div class="qstat">${time}${took(r) ? " · " + took(r) : ""}</div></div>
        <div class="qact"></div>
      </div>`;
    }
    box.innerHTML = html;
    wireRows(box);
    $("#q-hmore", el).style.display = H.rows.length < H.total ? "" : "none";
  }

  function setTab(tab) {
    H.tab = tab;
    $$(".q-tab", el).forEach(b => {
      b.classList.toggle("on", b.dataset.tab === tab);
      b.setAttribute("aria-selected", String(b.dataset.tab === tab));
    });
    $("#q-now", el).style.display = tab === "now" ? "" : "none";
    $("#q-history", el).style.display = tab === "history" ? "" : "none";
    if (tab === "history") loadHistory(false);
  }
  $$(".q-tab", el).forEach(b => b.onclick = () => setTab(b.dataset.tab));
  $("#q-htool", el).innerHTML = `<option value="">every tool</option>` +
    TOOLS.map(t => `<option value="${t.id}">${esc(t.name)}</option>`).join("") +
    `<option value="suite">suite (installs, settings)</option>`;
  $("#q-hq", el).addEventListener("input", () => {
    clearTimeout(H.timer); H.timer = setTimeout(() => loadHistory(false), 300); });
  $("#q-htool", el).onchange = () => loadHistory(false);
  $("#q-hstatus", el).onchange = () => loadHistory(false);
  $("#q-hmore", el).onclick = () => loadHistory(true);
  $("#q-hcsv", el).onclick = async () => {
    const q = histQuery();
    q.set("save", "1");
    try {
      const r = await api("/api/jobs/history.csv?" + q.toString());
      toast("history saved — " + r.path.split("/").pop());
      api("/api/media/reveal", { path: r.path }).catch(() => {});
    } catch (e) { toast(e.message, true); }
  };

  async function refresh(arg) {
    try { (await api("/api/jobs")).forEach(j => CZ.jobs.set(j.id, j)); } catch (e) {}
    render();
    if (arg && arg.tab) setTab(arg.tab);
    else if (H.tab === "history") loadHistory(false);
    try {
      $("#q-outroot", el).value = (await api("/api/settings/outputs")).root;
    } catch (e) {}
    const saveRoot = async root => {
      try {
        const r = await api("/api/settings/outputs", { root });
        $("#q-outroot", el).value = r.root;
        toast("new work lands in " + r.root);
      } catch (e) { toast(e.message, true); }
    };
    $("#q-outsave", el).onclick = () => saveRoot($("#q-outroot", el).value.trim());
    $("#q-outpick", el).onclick = async () => {
      const p = await pickFolder($("#q-outroot", el).value.trim());
      if (p) saveRoot(p);
    };
    $("#q-outreset", el).onclick = async () => {
      const r = await api("/api/settings/outputs", { root: "" });
      $("#q-outroot", el).value = r.root;
      toast("outputs back to the default");
    };
  }

  function onJob(job) {
    if (CZ.current !== "queue") return;
    if (H.tab === "now") render();
    else if (["done", "error", "cancelled"].includes(job.status)) {
      clearTimeout(H.timer); H.timer = setTimeout(() => loadHistory(false), 600);
    }
  }

  /* reset: back to the live tab, filters cleared (nothing is deleted) */
  function reset() {
    $("#q-hq", el).value = "";
    $("#q-htool", el).value = "";
    $("#q-hstatus", el).value = "";
    setTab("now");
    render();
  }

  registerPage("queue", el, refresh, { reset });
  return { onJob, refresh };
})();
