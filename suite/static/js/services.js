/* v0.4 suite services: Install OpenFX, Models, Settings — real pages.
   Everything states what it did; the release check runs only on click. */

const fmtBytes = n => {
  if (n == null) return "";
  if (n < 1024) return n + " B";
  if (n < 1 << 20) return (n / 1024).toFixed(0) + " KB";
  if (n < 1 << 30) return (n / (1 << 20)).toFixed(1) + " MB";
  return (n / (1 << 30)).toFixed(2) + " GB";
};

/* Release tags come in shapes: "v3.7.0", "speak-v0.2.0", "0.2.0-beta.1". Compare
   the first run of dotted numbers; anything without one is unknown, not equal. */
const verNums = s => {
  const m = String(s == null ? "" : s).match(/\d+(?:\.\d+)*/);
  return m ? m[0].split(".").map(Number) : null;
};
function cmpVersions(a, b) {
  const x = verNums(a), y = verNums(b);
  if (!x || !y) return null;
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    const d = (x[i] || 0) - (y[i] || 0);
    if (d) return d < 0 ? -1 : 1;
  }
  return 0;
}

/* ---------- Install OpenFX ---------- */
const OfxPage = (() => {
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-ofx";
  el.innerHTML = `<div class="page-pad" style="max-width:760px">
    <div class="tag">suite</div>
    <h1 style="margin-top:6px">Install OpenFX</h1>
    <div style="color:var(--cream-dim);font-size:12.5px;margin-top:4px">
      Hush and Speak straight into Resolve — the installer .pkg handles permissions;
      clear the plugin cache after, so Resolve rescans.</div>
    <div id="ofx-resolve" style="margin-top:18px"></div>
    <div id="ofx-plugins" style="margin-top:10px"></div>
    <div class="door" style="margin-top:14px;background:var(--ink-2)">
      <h2>Plugin cache</h2>
      <div class="why" id="ofx-cachestate"></div>
      <button class="btn" style="width:auto" id="ofx-clearcache">Clear OFX plugin cache</button>
      <span class="clipmeta" id="ofx-cachemsg" style="margin-left:10px"></span>
    </div>
    <div class="report show" id="ofx-report" style="display:none"></div>
  </div>`;

  let status = null, releases = null;

  function pluginCard(key, p) {
    const rel = releases && releases[key];
    const latest = rel && !rel.error ? rel.tag : null;
    const order = latest && p.installed ? cmpVersions(p.installed, latest) : null;
    const behind = order === -1;
    /* the plist can report "unknown" — don't dress that up as a version number */
    const inst = verNums(p.installed) ? `v${esc(p.installed)}` : `version ${esc(p.installed)}`;
    let state;
    if (!p.installed) state = `<span class="badge warn">not installed</span>`;
    else if (behind) state = `<span class="badge" style="color:var(--amber);border-color:var(--amber)">${inst} → ${esc(latest)} available</span>`;
    else if (order === 1) state = `<span class="badge" style="color:var(--ok);border-color:var(--ok)">${inst} installed — newer than the latest release (${esc(latest)})</span>`;
    else if (order === 0) state = `<span class="badge" style="color:var(--ok);border-color:var(--ok)">${inst} installed · latest</span>`;
    else state = `<span class="badge" style="color:var(--ok);border-color:var(--ok)">${inst} installed${latest ? " — can't compare it to " + esc(latest) : ""}</span>`;
    const relLine = rel ? (rel.error
      ? `<div class="hint">${esc(rel.error)}</div>`
      : `<div class="hint">latest: ${esc(rel.tag)}${rel.prerelease ? ' <span class="badge synth">beta</span>' : ""} · <a href="${esc(rel.notes_url)}" target="_blank">release notes</a></div>`) : "";
    const btnLabel = !p.installed ? "Download installer"
      : behind ? "Download update"
      : order === 1 ? "Download the release anyway" : "Reinstall";
    return `<div class="door" style="margin-top:10px;background:var(--ink-2)">
      <h2>${esc(p.name)} <span style="font-weight:400;color:var(--cream-dim);font-size:12.5px">— ${esc(p.one)}</span></h2>
      <div class="why">${state}</div>
      ${relLine}
      <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">
        <button class="btn" style="width:auto" data-install="${key}">${btnLabel}</button>
        ${p.installed ? `<button class="btn" style="width:auto" data-uninstall="${key}">Uninstall…</button>` : ""}
      </div>
      <div class="progmsg" data-msg="${key}"></div>
    </div>`;
  }

  function render() {
    if (!status) return;
    $("#ofx-resolve", el).innerHTML = `<div class="door" style="background:var(--forest)">
      <h2>DaVinci Resolve</h2>
      <div class="why">${status.resolve_present
        ? `found in /Applications — plugins land in <code style="font-family:var(--mono);font-size:11px">${esc(status.plugins_dir)}</code>`
        : "not found in /Applications — install Resolve first (the free edition is the whole point)"}</div>
    </div>`;
    $("#ofx-plugins", el).innerHTML =
      Object.entries(status.plugins).map(([k, p]) => pluginCard(k, p)).join("") +
      `<button class="btn" style="width:auto;margin-top:10px" id="ofx-check">Check for updates (GitHub)</button>
       <span class="hint" style="margin-left:8px">one request to the public API, only when you click</span>`;
    $("#ofx-cachestate", el).textContent = status.cache_file_present
      ? "cache file present — clear it after installing or updating a plugin"
      : "no cache file — Resolve will scan fresh on next launch";

    $("#ofx-check", el).onclick = async e => {
      e.target.disabled = true; e.target.textContent = "checking…";
      releases = await api("/api/ofx/check-updates", {});
      e.target.disabled = false; e.target.textContent = "Check for updates (GitHub)";
      render();
    };
    $$("button[data-install]", el).forEach(b => b.onclick = async () => {
      const key = b.dataset.install;
      b.disabled = true;
      try {
        const job = await api("/api/ofx/install", { plugin: key });
        watchJob(job.id, j => {
          $(`[data-msg="${key}"]`, el).textContent = j.message || j.status;
        });
        const done = await jobDone(job.id);
        b.disabled = false;
        if (done.status === "error") { $(`[data-msg="${key}"]`, el).textContent = done.error; return; }
        if (done.status !== "done") return;
        const rep = $("#ofx-report", el);
        rep.style.display = "";
        rep.innerHTML += `<b>→</b> ${esc(done.result.pkg)} (${esc(done.result.tag)})\n   ${esc(done.result.note)}\n`;
      } catch (err) { b.disabled = false; toast(err.message, true); }
    });
    $$("button[data-uninstall]", el).forEach(b => b.onclick = async () => {
      try {
        const r = await api("/api/ofx/uninstall-hint", { plugin: b.dataset.uninstall });
        const rep = $("#ofx-report", el);
        rep.style.display = "";
        rep.innerHTML += `<b>→</b> ${esc(r.note)}` +
          (r.command ? `\n   <span style="color:var(--cream)">${esc(r.command)}</span>` : "") + `\n`;
        if (!r.needs_admin) refresh();
      } catch (err) { toast(err.message, true); }
    });
    $("#ofx-clearcache", el).onclick = async () => {
      try {
        const r = await api("/api/ofx/clear-cache", {});
        await refresh();   // the file on disk is the truth, not what we just asked for
        $("#ofx-cachemsg", el).textContent = r.note;
      } catch (err) { toast(err.message, true); }
    };
  }

  async function refresh() {
    status = await api("/api/ofx/status");
    render();
  }

  registerPage("ofx", el, refresh);
  return {};
})();

/* ---------- Models ---------- */
const ModelsPage = (() => {
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-models";
  el.innerHTML = `<div class="page-pad" style="max-width:860px">
    <div class="tag">suite</div>
    <h1 style="margin-top:6px">Models</h1>
    <div style="color:var(--cream-dim);font-size:12.5px;margin-top:4px" id="md-store"></div>
    <div id="md-registry" style="margin-top:16px"></div>
    <div id="md-extra" style="margin-top:6px"></div>
  </div>`;

  function row(m) {
    const state = m.present
      ? `<span class="badge" style="color:var(--ok);border-color:var(--ok)">${fmtBytes(m.size)}</span>`
      : m.problem ? `<span class="badge warn">unusable</span>`
                  : `<span class="badge">not downloaded</span>`;
    const act = (m.present || m.problem)
      ? `<button data-del="${m.name}">remove</button>`
      : (m.downloadable ? `<button data-dl="${m.name}">download</button>`
                        : `<span class="hint">${esc(m.hint || "")}</span>`);
    return `<div class="qrow" style="grid-template-columns:150px 1fr 110px 110px">
      <div class="qtool">${esc(m.name)}</div>
      <div><div class="qlabel" style="font-size:12.5px">${esc(m.card)}</div>
        <div class="qmsg">${esc(m.license)}${m.pinned ? " · sha-256 pinned" : ""}</div>
        ${m.problem ? `<div class="qmsg err">${esc(m.problem)}</div>` : ""}
        <div class="qmsg" data-mmsg="${m.name}"></div></div>
      <div>${state}</div>
      <div class="qact">${act}</div>
    </div>`;
  }

  async function refresh() {
    const d = await api("/api/models/list");
    $("#md-store", el).innerHTML =
      `shared store: <code style="font-family:var(--mono);font-size:11px">${esc(d.store)}</code> · ${fmtBytes(d.total_size)} total — every model in the registry below names its license; the ones marked sha-256 pinned are verified as they download`;
    $("#md-registry", el).innerHTML =
      `<div class="tag" style="margin-bottom:6px">shared store (czcore registry)</div>` +
      d.registry.map(row).join("");
    const rt = d.stencil_runtime;
    $("#md-extra", el).innerHTML =
      `<div class="tag" style="margin:16px 0 6px">whisper (scribe)</div>
       <div class="hint" style="margin-bottom:6px">not in the registry above: faster-whisper
         fetches these from Hugging Face itself on the first transcribe — CTranslate2 int8
         conversions of OpenAI's Whisper (MIT). No pinned hash, no license card, whatever
         tag the library asks for. They live here so you can see and remove them.</div>` +
      (d.whisper.length ? d.whisper.map(w => `<div class="qrow" style="grid-template-columns:150px 1fr 110px 110px">
          <div class="qtool">${esc(w.name)}</div><div class="qlabel" style="font-size:12.5px">CTranslate2 int8</div>
          <div><span class="badge" style="color:var(--ok);border-color:var(--ok)">${fmtBytes(w.size)}</span></div>
          <div class="qact"><button data-delw="${esc(w.path)}">remove</button></div></div>`).join("")
        : `<div class="hint">none yet — the first transcribe downloads the size you pick</div>`) +
      `<div class="tag" style="margin:16px 0 6px">stencil runtime</div>
       <div class="hint">${rt.torch
         ? `torch ${esc(rt.torch)} (${rt.mps ? "MPS" : "CPU"}) + sam2 ${rt.sam2 ? "✓" : "missing"} — installed in the suite's venv`
         : "not installed — pip install torch sam2 (~1 GB); the Stencil page says the same"}</div>`;

    $$("button[data-dl]", el).forEach(b => b.onclick = async () => {
      b.disabled = true;
      const name = b.dataset.dl;
      try {
        const job = await api("/api/models/download", { name });
        watchJob(job.id, j => { $(`[data-mmsg="${name}"]`, el).textContent = j.message || j.status; });
        const done = await jobDone(job.id);
        if (done.status === "error") toast(done.error, true);
        refresh();
      } catch (e) { b.disabled = false; toast(e.message, true); }
    });
    $$("button[data-del]", el).forEach(b => b.onclick = async () => {
      if (!confirm(`Remove ${b.dataset.del}? It re-downloads on next use.`)) return;
      await api("/api/models/delete", { name: b.dataset.del, kind: "registry" });
      refresh();
    });
    $$("button[data-delw]", el).forEach(b => b.onclick = async () => {
      if (!confirm("Remove this whisper model? It re-downloads on next transcribe.")) return;
      await api("/api/models/delete", { name: b.dataset.delw, kind: "whisper" });
      refresh();
    });
  }

  registerPage("models", el, refresh);
  return {};
})();

/* ---------- Settings ---------- */
const SettingsPage = (() => {
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-settings";
  el.innerHTML = `<div class="page-pad" style="max-width:720px">
    <div class="tag">suite</div>
    <h1 style="margin-top:6px">Settings</h1>
    <div id="se-proxy" style="margin-top:16px"></div>
    <div id="se-caches" style="margin-top:22px"></div>
    <div id="se-about" style="margin-top:22px"></div>
  </div>`;

  async function refreshProxy() {
    const box = $("#se-proxy", el);
    let p = { enabled: false, source: null, host: "", username_masked: "" };
    try { p = await api("/api/settings/proxy"); } catch (e) {}
    const envLocked = p.source === "env";
    box.innerHTML = `
      <div class="tag" style="margin-bottom:6px">fetch network — webshare residential proxy</div>
      <div class="hint" style="margin-bottom:8px;line-height:1.6">
        YouTube gates caption delivery by IP reputation; the community-highlighter web
        app routes those fetches through a
        <a href="https://www.webshare.io/" target="_blank" rel="noopener">Webshare</a>
        rotating residential proxy, and the same account works here. Your credentials
        stay in app support on this machine and are used only for the fetches you ask
        for. Status: <b style="color:${p.enabled ? "var(--ok)" : "var(--cream-dim)"}">${
          p.enabled ? `active (${esc(p.username_masked)} @ ${esc(p.host)}${envLocked ? ", via environment" : ""})`
                    : "not configured"}</b></div>
      ${envLocked ? "" : `
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <input type="text" id="se-pxuser" placeholder="proxy username" spellcheck="false"
          style="flex:1;min-width:150px;background:#fff;border:1px solid var(--line);border-radius:7px;padding:6px 9px;font-size:12.5px">
        <input type="password" id="se-pxpass" placeholder="proxy password"
          style="flex:1;min-width:150px;background:#fff;border:1px solid var(--line);border-radius:7px;padding:6px 9px;font-size:12.5px">
        <input type="text" id="se-pxhost" placeholder="p.webshare.io:80" spellcheck="false"
          style="flex:0 1 150px;background:#fff;border:1px solid var(--line);border-radius:7px;padding:6px 9px;font-size:12.5px">
        <button class="btn" id="se-pxsave" style="width:auto">Save</button>
        ${p.enabled ? `<button class="btn" id="se-pxclear" style="width:auto">Remove</button>` : ""}
      </div>`}`;
    const save = $("#se-pxsave", box);
    if (save) save.onclick = async () => {
      try {
        await api("/api/settings/proxy", {
          username: $("#se-pxuser", box).value,
          password: $("#se-pxpass", box).value,
          host: $("#se-pxhost", box).value,
        });
        toast("proxy saved — fetches now ride your Webshare pool");
        refreshProxy();
      } catch (e) { toast(e.message, true); }
    };
    const clear = $("#se-pxclear", box);
    if (clear) clear.onclick = async () => {
      await api("/api/settings/proxy", { username: "", password: "" });
      toast("proxy removed — fetches go direct again");
      refreshProxy();
    };
  }

  async function refresh() {
    refreshProxy();
    const d = await api("/api/settings/info");
    $("#se-caches", el).innerHTML =
      `<div class="tag" style="margin-bottom:6px">caches — all regenerable, nothing here can lose work</div>` +
      d.caches.map(c => `<div class="qrow" style="grid-template-columns:170px 1fr 90px 90px">
        <div class="qtool">${esc(c.label)}</div>
        <div><div class="qlabel" style="font-size:12.5px">${esc(c.what)}</div>
          <div class="qmsg">${esc(c.path)}</div></div>
        <div><span class="badge">${fmtBytes(c.size)}</span></div>
        <div class="qact"><button data-clear="${c.id}">clear</button></div>
      </div>`).join("") +
      `<div class="qrow" style="grid-template-columns:170px 1fr 90px 90px">
        <div class="qtool">job history</div>
        <div><div class="qlabel" style="font-size:12.5px">finished queue entries</div>
          <div class="qmsg">active jobs are never touched</div></div>
        <div><span class="badge">${fmtBytes(d.jobs_db_size)}</span></div>
        <div class="qact"><button id="se-clearjobs">clear</button></div>
      </div>`;
    $("#se-about", el).innerHTML =
      `<div class="tag" style="margin-bottom:6px">about</div>
       <div class="hint" style="line-height:1.8">
         control-z Suite ${esc(d.version)} · python ${esc(d.python)}<br>
         model store: ${esc(d.model_store.path)} (${fmtBytes(d.model_store.size)})<br>
         app data: ${esc(d.app_support)}<br>
         free forever · local only · shows its work · honest limitations</div>`;

    $$("button[data-clear]", el).forEach(b => b.onclick = async () => {
      const r = await api("/api/settings/clear-cache", { which: b.dataset.clear });
      toast(r.note);
      refresh();
    });
    $("#se-clearjobs", el).onclick = async () => {
      const r = await api("/api/jobs/clear-history", {});
      toast(`${r.removed} finished job(s) cleared`);
      CZ.jobs.clear();
      try { (await api("/api/jobs")).forEach(applyJob); } catch (e) {}
      refresh();
    };
  }

  registerPage("settings", el, refresh);
  return {};
})();
