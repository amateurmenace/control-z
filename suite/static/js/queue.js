/* Queue: every heavy operation across every tool — progress, cancel, history. */

const QueuePage = (() => {
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-queue";
  el.innerHTML = `<div class="page-pad">
    <div class="tag">suite</div>
    <h1 style="margin-top:6px">Queue</h1>
    <div style="color:var(--cream-dim);font-size:12.5px;margin-top:4px;display:flex;align-items:center;gap:12px">
      <span>one job at a time, in order — history survives quitting. Cancel is honest:
      partial files are removed.</span>
      <button class="btn" style="width:auto;padding:4px 12px;font-size:11.5px;margin-left:auto"
        id="q-clearhist">clear finished</button>
    </div>
    <div style="display:flex;gap:8px;align-items:center;margin-top:10px;font-size:12px;flex-wrap:wrap">
      <span class="tag" style="letter-spacing:.1em">outputs land in</span>
      <input id="q-outroot" spellcheck="false" style="flex:1;min-width:260px;background:#fff;
        border:1px solid var(--line);border-radius:7px;padding:5px 9px;font-family:var(--mono);font-size:11px">
      <button class="btn" id="q-outsave" style="width:auto;padding:4px 12px;font-size:11.5px">Change</button>
      <button class="btn" id="q-outreset" style="width:auto;padding:4px 12px;font-size:11.5px"
        title="back to ~/Movies/control-z">Default</button>
    </div>
    <div id="q-rows" style="margin-top:18px"></div>
  </div>`;
  $("#q-clearhist", el).onclick = async () => {
    try {
      const r = await api("/api/jobs/clear-history", {});
      toast(`${r.removed} finished job(s) cleared`);
      CZ.jobs.clear();
      (await api("/api/jobs")).forEach(j => CZ.jobs.set(j.id, j));
      render();
    } catch (e) { toast(e.message, true); }
  };

  const rows = () => $("#q-rows", el);

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
        ${(() => {   // finished work says where it landed, clickably
          const r = j.result || {};
          const outs = [r.out, r.path, ...(r.paths || []), ...(r.written || [])]
            .filter((p, i, a) => p && a.indexOf(p) === i).slice(0, 3);
          return outs.map(p => `<button class="qout" data-rev="${esc(p)}"
            title="reveal in the file browser">📁 ${esc(p)}</button>`).join("");
        })()}
        ${j.status === "running" ? `<div class="prog" style="--acc:${acc}"><i style="width:${pct == null ? 30 : pct}%"></i></div>` : ""}
      </div>
      <div>
        <span class="stat-chip stat-${j.status}">${j.status}</span>
        <div class="qstat">${when}${pct != null && j.status === "running" ? ` · ${pct}%` : ""}</div>
      </div>
      <div class="qact">${active ? `<button data-cancel="${j.id}">cancel</button>` : ""}</div>
    </div>`;
  }

  function render() {
    const all = [...CZ.jobs.values()].sort((a, b) => (b.created_at || 0) - (a.created_at || 0));
    if (!all.length) {
      rows().innerHTML = `<div class="empty-grain" style="padding:32px 2px;color:var(--cream-faint)">
        no jobs yet — analyses, renders and upscales land here</div>`;
      return;
    }
    rows().innerHTML = all.map(rowHTML).join("");
    $$("button[data-cancel]", rows()).forEach(b => b.onclick = async () => {
      b.disabled = true;
      try { await api(`/api/jobs/${b.dataset.cancel}/cancel`, {}); }
      catch (e) { toast(e.message, true); }
    });
    $$("button.qout", rows()).forEach(b => b.onclick = async () => {
      try { await api("/api/media/reveal", { path: b.dataset.rev }); }
      catch (e) { toast(e.message, true); }
    });
  }

  async function refresh() {
    try { (await api("/api/jobs")).forEach(j => CZ.jobs.set(j.id, j)); } catch (e) {}
    render();
    try {
      $("#q-outroot", el).value = (await api("/api/settings/outputs")).root;
    } catch (e) {}
    $("#q-outsave", el).onclick = async () => {
      try {
        const r = await api("/api/settings/outputs",
          { root: $("#q-outroot", el).value.trim() });
        $("#q-outroot", el).value = r.root;
        toast("new work lands in " + r.root);
      } catch (e) { toast(e.message, true); }
    };
    $("#q-outreset", el).onclick = async () => {
      const r = await api("/api/settings/outputs", { root: "" });
      $("#q-outroot", el).value = r.root;
      toast("outputs back to the default");
    };
  }

  function onJob(job) {
    if (CZ.current === "queue") render();
  }

  registerPage("queue", el, refresh);
  return { onJob, refresh };
})();
