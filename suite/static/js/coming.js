/* Honest "coming in v0.x" pages — never a dead button, always what works today. */

const ComingPages = (() => {
  function make(id, title, verb, when, nowHTML) {
    const el = document.createElement("div");
    el.className = "page";
    el.id = `page-${id}`;
    el.innerHTML = `<div class="page-pad coming">
      <div class="tag">control-z suite</div>
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

  make("ofx", "Install OpenFX", "one-button install for Hush and Speak, straight into Resolve.",
    "v0.4",
    `today: download from <code>github.com/amateurmenace/Hush-OpenNR</code> and
     <code>github.com/amateurmenace/Speak</code> — each release page has the
     3-step install.`);
  make("models", "Models", "every model the suite uses — license card, hash, size — download and remove.",
    "v0.4",
    `today the tools download what they need on first use (license shown, hash
     verified) into<br><code>~/Library/Application Support/control-z/models</code>.
     Rise's Real-ESRGAN backend is converted locally: <code>python -m rise.convert</code>.`);
  make("settings", "Settings", "cache locations, preview quality, defaults.",
    "v0.4",
    `today: previews cache at <code>~/Library/Caches/control-z/suite/frames</code> —
     safe to delete anytime.`);

  return {};
})();
