/* Home: two doors, split by which way the footage is travelling — into your
   editor, or back out of it. Each tool gets a line written for its door, not
   its generic one-liner (toolById().one): Scribe means "paper edit" going in
   and "captions" coming out, and the door should say the one you came for. */

const HomePage = (() => {
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-home";

  const PREP = [
    { id: "clear", line: "hum, clicks and room out of the dialogue first" },
    { id: "stencil", line: "click an object, bring its matte in with the clip" },
    { id: "depth", line: "a depth map to fog, grade or rack focus against" },
  ];
  const FINISH = [
    { id: "pivot", line: "the finished cut, reframed to 9:16 or 1:1" },
    { id: "scribe", line: "captions and subtitles for the locked cut" },
    { id: "rise", line: "the master, pushed up to delivery resolution" },
  ];

  function doorHTML(title, why, entries, cls) {
    const tools = entries.map(({ id, line }) => {
      const t = toolById(id);
      return `<button class="door-tool" data-tool="${t.id}" style="--acc:${t.acc}">
        <span class="glyph">${glyphSVG(t.acc, t.ready)}</span>
        <span><span class="name">${t.name}</span>
          <span class="one"> — ${line}</span></span>
        ${t.ready ? "" : `<span class="soon">coming ${t.when}</span>`}
      </button>`;
    }).join("");
    return `<div class="door ${cls}"><h2>${title}</h2>
      <div class="why">${why}</div>${tools}</div>`;
  }

  function render() {
    const recents = (CZ.session.recents || []).map(r => {
      const name = r.path.split("/").pop();
      const tool = toolById(r.tool)?.name || "";
      return `<button class="recent-row" data-path="${esc(r.path)}" data-tool="${esc(r.tool || "pivot")}">
        <span class="name">${esc(name)}</span>
        <span class="meta">${tool}</span></button>`;
    }).join("");

    el.innerHTML = `<div class="page-pad">
      <div class="tag">the workbench around resolve</div>
      <h1 style="margin-top:6px">What are we fixing today?</h1>
      <div class="doors">
        ${doorHTML("Prep", "footage you're about to take into your editor", PREP, "prep")}
        ${doorHTML("Finish", "footage coming back out of it", FINISH, "finish")}
      </div>
      <div class="recents">
        <div class="tag">recent media</div>
        ${recents || `<div class="empty-grain" style="padding:22px 2px;color:var(--cream-faint);font-size:13px">
          nothing yet — open a clip in any tool and it lands here</div>`}
      </div>
      <div class="covenant-line">free forever · runs with free resolve · local only · shows its work · honest limitations</div>
    </div>`;

    $$(".door-tool", el).forEach(b => b.onclick = () => go(b.dataset.tool));
    $$(".recent-row", el).forEach(b => b.onclick = () => {
      const tool = toolById(b.dataset.tool)?.ready ? b.dataset.tool : "pivot";
      go(tool, { openPath: b.dataset.path });
    });
  }

  /* the server owns the recents list — every tool's Open adds to it, so read it
     back each time Home is shown rather than trusting the boot-time copy */
  async function onshow() {
    render();
    await loadSession();
    render();
  }

  registerPage("home", el, onshow);
  return { render };
})();
