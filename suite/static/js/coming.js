/* Honest "coming in v0.x" pages — never a dead button, always what works today. */

const ComingPages = (() => {
  function make(id, title, verb, when, nowHTML) {
    const el = document.createElement("div");
    el.className = "page";
    el.id = `page-${id}`;
    el.innerHTML = `<div class="page-pad coming">
      <div class="tag">community ai project</div>
      <h1 style="margin-top:6px">${title}</h1>
      <div class="verb">${verb}</div>
      <span class="when">coming in ${when}</span>
      ${nowHTML ? `<div class="now">${nowHTML}</div>` : ""}
    </div>`;
    registerPage(id, el, null);
  }

  TOOLS.filter(t => !t.ready).forEach(t => {
    make(t.id, t.name, `${t.verb} — ${t.one}.`, t.when,
      t.cli ? `works today from the terminal:<br><code>${t.cli}</code>` : "");
  });

  return {};
})();
