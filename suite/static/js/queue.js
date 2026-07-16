/* Queue: every heavy operation across every tool — progress, cancel, history. */

const QueuePage = (() => {
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-queue";
  el.innerHTML = `<div class="page-pad">
    <div class="tag">suite</div>
    <h1 style="margin-top:6px">Queue</h1>
    <div style="color:var(--cream-dim);font-size:12.5px;margin-top:4px">
      one job at a time, in order — history survives quitting. Cancel is honest:
      partial files are removed.</div>
    <div id="q-rows" style="margin-top:18px"></div>
  </div>`;

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
  }

  async function refresh() {
    try { (await api("/api/jobs")).forEach(j => CZ.jobs.set(j.id, j)); } catch (e) {}
    render();
  }

  function onJob(job) {
    if (CZ.current === "queue") render();
  }

  registerPage("queue", el, refresh);
  return { onJob, refresh };
})();
