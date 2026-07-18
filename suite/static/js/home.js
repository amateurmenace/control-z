/* Home: the wire first — the chains where one tool hands to the next — then
   the three doors. Each tool gets a line written for its place, not its
   generic one-liner (toolById().one): Scribe means "paper edit" going in and
   "captions" coming out, and the door should say the one you came for. */

const HomePage = (() => {
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-home";

  /* the line: the whole project as one conveyor — a meeting travels
     station to station and becomes media. Coming stations ride dashed
     with their date; the package chip picks up each station's color as
     it arrives. The second chain keeps the smaller card form. */
  const LINE = {
    title: "The line — watch a meeting become media",
    why: "one recording in; clips, copy, posts and a place in the record out",
    steps: [
      { id: "grabber", verb: "search + fetch",
        micro: "the portal searched, the recording brought home" },
      { id: "highlighter", verb: "find the moments",
        micro: "read, scored, cut to what mattered" },
      { id: "publisher", verb: "make the kit",
        micro: "three frames, captions burned, copy drafted" },
      { id: "memory", verb: "keep the record",
        micro: "filed with everything the town ever said" },
    ],
  };
  const CHAINS = [
    {
      title: "Seen and heard by everyone",
      why: "captions first; then every language; then the picture, spoken",
      steps: [
        { id: "scribe", micro: "captions + transcript" },
        { id: "interpreter", micro: "seven languages" },
        { id: "narrator", micro: "audio description" },
      ],
    },
  ];

  const PREP = [
    { id: "grabber", line: "the meeting recording, fetched and conformed for air" },
    { id: "clear", line: "hum, clicks and room out of the dialogue first" },
    { id: "stencil", line: "click an object, bring its matte in with the clip" },
    { id: "depth", line: "a depth map to fog, grade or rack focus against" },
  ];
  const MAKE = [
    { id: "highlighter", line: "a meeting, cut down to the moments that matter" },
    { id: "index", line: "the archive, searched in plain words → selects" },
    { id: "slate", line: "lower thirds, slates and countdowns, broadcast-ready" },
  ];
  const FINISH = [
    { id: "pivot", line: "the finished cut, reframed to 9:16 or 1:1" },
    { id: "scribe", line: "captions and subtitles for the locked cut" },
    { id: "rise", line: "the master, pushed up to delivery resolution" },
    { id: "publisher", line: "the kit that gets it seen — clips, copy, posts" },
  ];

  function lineHTML() {
    const live = LINE.steps.filter(s => toolById(s.id).ready).length;
    const n = LINE.steps.length;
    const stations = LINE.steps.map(({ id, verb, micro }, i) => {
      const t = toolById(id);
      return `<button class="line-station${t.ready ? "" : " soon-step"}"
        data-tool="${t.id}" style="--acc:${t.acc}" title="${t.long || t.name}">
        <span class="line-glyph">${glyphSVG(t.acc, t.ready, t.group === "community")}</span>
        <span class="line-name">${t.name}${t.ready ? "" : `<span class="soon">${t.when}</span>`}</span>
        <span class="line-verb">${verb}</span>
        <span class="line-micro">${micro}</span>
      </button>`;
    }).join("");
    // the belt's package pauses under each station — timing baked as CSS
    // keyframes over --n stations; accents painted per stop
    const accs = LINE.steps.map(s => toolById(s.id).acc);
    return `<div class="line" style="--n:${n}">
      <div class="chain-head"><h2>${LINE.title}</h2>
        <span class="chain-live">${live} of ${n} stations live today</span></div>
      <div class="why">${LINE.why}</div>
      <div class="line-belt">
        <span class="line-rail-wire" aria-hidden="true"></span>
        <span class="line-pkg" aria-hidden="true"
          style="${accs.map((a, i) => `--acc${i}:${a}`).join(";")}"></span>
        <div class="line-stations">${stations}</div>
      </div>
      <div class="line-foot">
        <button class="btn primary" id="line-run" style="--acc:var(--grabber);width:auto">▶ Run the line</button>
        <span class="hint">starts at the search desk — every station hands to the next</span>
      </div>
    </div>`;
  }

  function chainHTML(chain) {
    const live = chain.steps.filter(s => toolById(s.id).ready).length;
    const steps = chain.steps.map(({ id, micro }, i) => {
      const t = toolById(id);
      const wire = i ? `<span class="chain-wire" aria-hidden="true"></span>` : "";
      return `${wire}<button class="chain-step${t.ready ? "" : " soon-step"}"
        data-tool="${t.id}" style="--acc:${t.acc}" title="${t.long || t.name}">
        <span class="glyph">${glyphSVG(t.acc, t.ready, t.group === "community")}</span>
        <span><span class="name">${t.name}</span>
          <span class="micro">${micro}</span></span>
        ${t.ready ? "" : `<span class="soon">${t.when}</span>`}
      </button>`;
    }).join("");
    return `<div class="chain">
      <div class="chain-head"><h2>${chain.title}</h2>
        <span class="chain-live">${live} of ${chain.steps.length} live today</span></div>
      <div class="why">${chain.why}</div>
      <div class="chain-rail">${steps}</div>
    </div>`;
  }

  function doorHTML(title, why, entries, cls) {
    const tools = entries.map(({ id, line }) => {
      const t = toolById(id);
      return `<button class="door-tool${t.group === "community" ? " community" : ""}"
        data-tool="${t.id}" style="--acc:${t.acc}">
        <span class="glyph">${glyphSVG(t.acc, t.ready, t.group === "community")}</span>
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

    el.innerHTML = `<div class="page-pad wide">
      <div class="tag">the community ai project</div>
      <h1 style="margin-top:6px">Make Something.</h1>
      <div class="chains">
        <div class="tag">the wire — where one tool hands to the next</div>
        ${lineHTML()}
        ${CHAINS.map(chainHTML).join("")}
      </div>
      <div class="doors">
        ${doorHTML("Prep", "footage on its way into your editor", PREP, "prep")}
        ${doorHTML("Make", "made new — from your footage, or from scratch", MAKE, "make")}
        ${doorHTML("Finish", "the cut on its way back out", FINISH, "finish")}
      </div>
      <div class="recents">
        <div class="tag">recent media</div>
        ${recents || `<div class="empty-grain" style="padding:22px 2px;color:var(--cream-faint);font-size:13px">
          nothing yet — open a clip in any tool and it lands here</div>`}
      </div>
      <div class="covenant-line">free forever · runs with free resolve · local only · shows its work · honest limitations</div>
    </div>`;

    $$(".door-tool", el).forEach(b => b.onclick = () => go(b.dataset.tool));
    $$(".chain-step", el).forEach(b => b.onclick = () => go(b.dataset.tool));
    $$(".line-station", el).forEach(b => b.onclick = () => go(b.dataset.tool));
    const run = $("#line-run", el);
    if (run) run.onclick = () => go("grabber", { focusSearch: true });
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
