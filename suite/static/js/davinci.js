/* DaVinci Tools — the site's Resolve resources, one page inside the app.

   Everything control-z publishes for Resolve itself: the node-tree
   PowerGrade, the middle-gray contrast anchor, the Fusion template pack,
   and the OpenFX plugins (which have their own installer page). Files land
   in ~/Downloads and reveal themselves; every card links its guide on
   control-z.org. */

const DavinciPage = (() => {
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-davinci";
  el.innerHTML = `<div class="page-pad" style="max-width:820px">
    <div class="tag">resolve resources</div>
    <h1 style="margin-top:6px">DaVinci Tools</h1>
    <p style="color:var(--cream-dim);font-size:13.5px;max-width:560px">
      Everything the suite publishes for Resolve itself — grades, node trees,
      Fusion templates, plugins. Downloads land in your Downloads folder;
      every card links the guide that explains it.</p>
    <div id="dv-items" style="margin-top:16px"></div>
    <div class="hl-panel" style="margin-top:14px">
      <span class="tag">openfx plugins</span>
      <p style="font-size:12.5px;color:var(--cream-dim);margin:6px 0 10px">
        The suite's OpenFX plugins install straight into Resolve from their own
        page — versions checked, paths handled.</p>
      <button class="btn cta" id="dv-ofx" style="width:auto">Open the OpenFX installer</button>
    </div>
    <div class="hint" style="margin-top:14px">
      the same downloads live on <a href="https://control-z.org" target="_blank" rel="noopener">control-z.org</a> —
      this page is them, without leaving the app</div>
  </div>`;

  async function refresh() {
    const box = $("#dv-items", el);
    box.innerHTML = `<div class="hint">reading…</div>`;
    try {
      const r = await api("/api/davinci/list");
      box.innerHTML = r.items.map(it => `
        <div class="hl-panel" style="margin-bottom:12px">
          <div style="display:flex;gap:12px;align-items:baseline;flex-wrap:wrap">
            <b style="font-size:14.5px">${esc(it.label)}</b>
            <span class="hint" style="flex:1;min-width:200px">${esc(it.what)}</span>
          </div>
          <div style="display:flex;gap:8px;margin-top:9px;align-items:center;flex-wrap:wrap">
            <button class="btn cta" data-get="${esc(it.id)}" style="width:auto">
              ⬇ Download ${esc(it.filename)}${it.size ? ` (${(it.size / 1024).toFixed(0)} KB)` : ""}</button>
            <a class="btn" style="width:auto;text-decoration:none;display:inline-block"
              href="${esc(it.guide)}" target="_blank" rel="noopener">Read the guide</a>
            <span class="hint" data-msg="${esc(it.id)}"></span>
          </div>
        </div>`).join("");
      $$("button[data-get]", box).forEach(b => b.onclick = async () => {
        const msg = $(`[data-msg="${b.dataset.get}"]`, box);
        b.disabled = true;
        msg.textContent = "fetching…";
        try {
          const got = await api("/api/davinci/get", { id: b.dataset.get });
          msg.innerHTML = `landed in Downloads (${got.source}) · <a href="#" data-rev="${esc(got.path)}">Reveal</a>`;
          $("a[data-rev]", msg).onclick = async e => {
            e.preventDefault();
            try { await api("/api/media/reveal", { path: e.target.dataset.rev }); }
            catch (err) { toast(err.message, true); }
          };
          toast(`${got.path.split("/").pop()} → Downloads`);
        } catch (e) { msg.textContent = e.message; toast(e.message, true); }
        b.disabled = false;
      });
    } catch (e) { box.innerHTML = `<div class="progmsg err">${esc(e.message)}</div>`; }
  }

  function init() {
    $("#dv-ofx", el).onclick = () => go("ofx");
  }

  let inited = false;
  registerPage("davinci", el, () => {
    if (!inited) { init(); inited = true; }
    refresh();
  });
  return {};
})();
