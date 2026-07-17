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
  el.innerHTML = `<div class="page-pad" style="max-width:860px">
    <div class="hl-hero" style="margin-bottom:18px">
      <div class="tag">davinci tools · resolve resources · free forever</div>
      <h1 style="margin-top:6px">The best free editor in the world,
        made <span class="mark">even better</span>.</h1>
      <p style="color:var(--cream-dim);margin-top:8px;font-size:13.5px;max-width:640px;line-height:1.65">
        Free DaVinci Resolve is already a professional cutting room. Everything
        in the control-z suite and in this toolkit exists to help amateurs
        level up to pros <b>without the paywall</b> — no Studio license, no
        expensive third-party plugins. Whether you're an aspiring filmmaker, a
        journalist, an advocate, an artist, or just someone who wants the form
        of the work to match the quality of what it says — these are the
        grades, node trees, templates and plugins that close the gap.</p>
      <p style="color:var(--cream-faint);margin-top:6px;font-size:12px">
        An evolving set — new resources land here and on
        <a href="https://control-z.org" target="_blank" rel="noopener">control-z.org</a>
        as they're built. Downloads arrive in your Downloads folder and reveal
        themselves; every card links the guide that teaches it.</p>
    </div>
    <div id="dv-items"></div>
    <div class="hl-panel" style="margin-top:14px">
      <span class="tag">openfx plugins — effects inside Resolve itself</span>
      <p style="font-size:12.5px;color:var(--cream-dim);margin:6px 0 10px">
        The suite's OpenFX plugins put its cleanup and finishing passes on
        Resolve's own effects shelf. They install from their own page —
        versions checked, paths handled, one click.</p>
      <button class="btn cta" id="dv-ofx" style="width:auto">Open the OpenFX installer</button>
    </div>
  </div>`;

  async function refresh() {
    const box = $("#dv-items", el);
    box.innerHTML = `<div class="hint">reading…</div>`;
    try {
      const r = await api("/api/davinci/list");
      const ACC = { "node-tree": "var(--pivot)", "middle-gray": "var(--amber)",
                    "fusion-templates": "var(--depth)" };
      box.innerHTML = `<div class="hl-cards" style="grid-template-columns:1fr">` +
        r.items.map(it => `
        <div class="hl-card" style="display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap">
          <div style="flex:1;min-width:260px">
            <h2><span class="nub" style="background:${ACC[it.id] || "var(--amber)"}"></span>${esc(it.label)}</h2>
            <p style="margin-top:4px">${esc(it.what)}.</p>
          </div>
          <div style="display:flex;flex-direction:column;gap:7px;min-width:220px">
            <button class="btn cta" data-get="${esc(it.id)}" style="width:100%">
              ⬇ Download${it.size ? ` · ${it.size > 1048576 ? (it.size / 1048576).toFixed(1) + " MB" : (it.size / 1024).toFixed(0) + " KB"}` : ""}</button>
            <a class="btn" style="width:100%;text-decoration:none;display:inline-block;text-align:center;box-sizing:border-box"
              href="${esc(it.guide)}" target="_blank" rel="noopener">Read the guide</a>
            <span class="hint" data-msg="${esc(it.id)}" style="min-height:14px"></span>
          </div>
        </div>`).join("") + `</div>`;
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
