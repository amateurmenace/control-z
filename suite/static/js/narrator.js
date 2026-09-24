/* Community Narrator — audio description: the picture, spoken, with a
   reviewer in the loop.

   Four moves on one page, each a card that says what it's for: map the
   program (the pauses in the talk, and the slides/graphics), draft a short
   description for each (vision — on-device or your key — style-checked),
   review every card (accept, rewrite, regenerate — nothing unaccepted is
   ever used), render (one clear local voice, auto-ducked under the
   program). Out come a described version of the meeting and a
   descriptions transcript. */

const NarratorPage = (() => {
  const T = toolById("narrator");
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-narrator";

  el.innerHTML = `
  <div class="ws" style="--acc:${T.acc}">
    <div class="mediabar">
      <span class="toolname"><i>Community Narrator</i> · says what's on screen</span>
      <span class="beta-chip" title="beta — AI drafts, a human accepts; every track says so">beta</span>
      <span class="clipmeta" id="nr-title" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"></span>
      <button class="btn" id="nr-back" style="width:auto;display:none">← meetings</button>
    </div>
    <div class="ws-body">
      <div class="ws-center" id="nr-center" style="overflow-y:auto;padding:18px 22px 40px"></div>
      <div class="inspector">
        <div class="insp-head"><h2>Narrator</h2></div>
        <div class="insp-sec">
          <span class="tag">what writes the descriptions</span>
          <div class="hint" id="nr-vision" style="line-height:1.55">—</div>
        </div>
        <div class="insp-sec">
          <span class="tag">the voice</span>
          <div class="hint" id="nr-tts" style="line-height:1.55">—</div>
        </div>
        <div class="insp-sec">
          <span class="tag">the style — DCMP</span>
          <div class="hint" style="line-height:1.55">The description standard broadcasters use:
            present tense · short · say what you see, don't interpret · read on-screen
            text and slides aloud. Drafts that drift get a marker; your accept is what airs.</div>
        </div>
        <div class="report" id="nr-report"></div>
      </div>
    </div>
  </div>`;

  const S = { source: null, meta: null, video: null, script: null,
              outputs: {}, status: null, sel: -1 };

  const fmtT = t => { t = Math.max(0, Math.floor(t)); return t >= 3600
    ? `${Math.floor(t / 3600)}:${String(Math.floor(t % 3600 / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`
    : `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`; };

  /* the two engines, each with its one-click fix */
  function enginesHTML() {
    const st = S.status;
    if (!st) return "";
    const v = st.vision, t = st.tts;
    return `<div class="nr-engines">
      <div class="nr-eng ${v.ok ? "ok" : "need"}">
        <b>${v.ok ? "✓" : "✗"} Descriptions</b>
        <span>${v.ok ? esc(v.sentence) : "need an AI model to look at the picture — an AI key is the simplest way"}</span>
        ${v.ok ? "" : `<button class="btn primary" id="nr-addkey" style="width:auto;color:#fff">🔑 Add an AI key</button>`}
      </div>
      <div class="nr-eng ${t.ok ? "ok" : "need"}">
        <b>${t.ok ? "✓" : "✗"} Voice</b>
        <span>${t.ok ? esc(t.sentence) : "the narration voice isn't downloaded yet — one click on the Models page (112 MB, runs on this computer)"}</span>
        ${t.ok ? "" : `<button class="btn" id="nr-getvoice" style="width:auto">Get the voice</button>`}
      </div>
    </div>`;
  }
  function wireEngines(box) {
    const k = $("#nr-addkey", box);
    if (k) k.onclick = async () => {
      if (await czKeyModal({ feature: "Drafting descriptions" })) { await loadStatus(); S.source ? renderMain() : shelf(); }
    };
    const v = $("#nr-getvoice", box);
    if (v) v.onclick = () => go("models");
  }

  /* ---------- the landing ---------- */
  async function shelf() {
    S.source = null;
    $("#nr-title", el).textContent = "";
    $("#nr-back", el).style.display = "none";
    const box = $("#nr-center", el);
    box.innerHTML = `
      <div class="cz-hero" style="--acc:${T.acc}">
        <div class="tag">community narrator</div>
        <h1>Say what's on screen, for <span class="mark">viewers who can't see it</span>.</h1>
        <p>Audio description is a narration for blind and low-vision viewers: in the pauses between
          speakers, a calm voice says what's on screen — the slide being shown, the chart, who stepped to
          the podium, the hands raised for a vote. Narrator finds those pauses and slides, drafts a short
          description for each, lets you approve every word, then records it with a voice that runs on
          this computer and mixes it under the meeting.</p>
        <div class="cz-how">
          <div class="cz-how-step"><span class="cz-how-n">1</span><b>Map the program</b>
            finds the pauses in the talk and every slide or graphic</div>
          <div class="cz-how-step"><span class="cz-how-n">2</span><b>Draft descriptions</b>
            an AI looks at each moment and writes one short line</div>
          <div class="cz-how-step"><span class="cz-how-n">3</span><b>Review every card</b>
            accept, rewrite or redo — only what you accept is used</div>
          <div class="cz-how-step"><span class="cz-how-n">4</span><b>Render</b>
            the voice speaks your lines; the meeting dips under it</div>
        </div>
        <div class="cz-outs"><span class="cz-out">described video (.mp4)</span>
          <span class="cz-out">described audio (.m4a)</span><span class="cz-out">narration track (.wav)</span>
          <span class="cz-out">descriptions transcript (.vtt)</span></div>
      </div>
      <div style="margin-top:14px">${enginesHTML()}</div>
      <div class="tag" style="margin-top:18px">meetings you can describe — words and video on this computer</div>
      <div id="nr-shelf" class="cz-shelf"><div class="hint">looking…</div></div>
      <div class="cz-pick">
        <input type="text" id="nr-path" spellcheck="false"
          placeholder="…or paste a path — a video with its transcript, or a Highlighter meeting folder">
        <button class="btn" id="nr-open" style="width:auto">Open</button>
        <button class="btn" id="nr-browse" style="width:auto">Browse…</button>
      </div>
      <div class="hint" style="margin-top:8px">Description needs the picture: a meeting read from a link must have its
        video downloaded first (Highlighter → Download full video, or the Grabber).</div>`;
    wireEngines(box);
    $("#nr-open", box).onclick = () => open($("#nr-path", box).value.trim());
    $("#nr-path", box).addEventListener("keydown", e => {
      if (e.key === "Enter") open($("#nr-path", box).value.trim()); });
    $("#nr-browse", box).onclick = () => browseForPath(open);
    let rows = [];
    try { rows = (await api("/api/narrator/library")).rows || []; } catch (e) {}
    if (S.source) return;
    const sh = $("#nr-shelf", box);
    if (!sh) return;
    sh.innerHTML = rows.length ? rows.slice(0, 20).map(r => `
      <button class="cz-shelf-item" style="--acc:${T.acc}" data-open="${esc(r.source)}">
        <b title="${esc(r.title)}">${esc(r.title)}</b>
        <span>video ready${r.duration ? ` · ${fmtT(r.duration)}` : ""}</span>
      </button>`).join("")
      : `<div class="hint">none yet — a meeting needs its words (Highlighter) and its video
         (Download full video) on this computer</div>`;
    $$("[data-open]", sh).forEach(b => b.onclick = () => open(b.dataset.open));
  }

  /* ---------- open ---------- */
  async function open(path) {
    if (!path) return;
    const box = $("#nr-center", el);
    box.innerHTML = `<div class="hint" style="padding:16px 2px">reading the meeting…</div>`;
    try {
      const r = await api("/api/narrator/open", { path });
      S.source = r.source; S.meta = r.meta; S.video = r.video;
      S.script = r.script; S.outputs = r.outputs || {}; S.sel = -1;
      $("#nr-title", el).textContent = S.meta.title || "";
      $("#nr-back", el).style.display = "";
      renderMain();
    } catch (e) {
      box.innerHTML = `<div class="cz-step current" style="--acc:${T.acc};max-width:640px">
        <div class="cz-step-head"><span class="cz-step-num">!</span><h2>Not ready to describe yet</h2></div>
        <div class="cz-step-sub">${esc(e.message)}</div>
        <div class="cz-row"><button class="btn" id="nr-hl" style="width:auto">Open it in Highlighter</button>
          <button class="btn" id="nr-back2" style="width:auto">← back</button></div></div>`;
      $("#nr-hl", box).onclick = () => go("highlighter", { openPath: path });
      $("#nr-back2", box).onclick = shelf;
    }
  }

  /* ---------- the loaded view ---------- */
  function stepState() {
    const sc = S.script;
    const planned = !!(sc && (sc.cues || []).length);
    const drafted = planned && sc.cues.some(c => c.text);
    const accepted = planned && sc.cues.some(c =>
      c.text && ["accepted", "edited"].includes(c.status));
    const fitted = planned && sc.cues.some(c =>
      c.text && ["accepted", "edited"].includes(c.status) &&
      (c.words_budget || 0) > 0);
    const rendered = !!(S.outputs.mix_audio || S.outputs.mix_video);
    return { planned, drafted, accepted, fitted, rendered };
  }

  function provenanceHTML() {
    const sc = S.script || {};
    const st = stepState();
    if (!st.planned) return "";
    const bits = [`<b>AI descriptions — beta</b>`];
    if (sc.model) {
      const one = m => m.startsWith("local:") ? `${esc(m.slice(6))} — on-device`
        : m.startsWith("ai:") ? `${esc(m.slice(3))} (your key)`
        : `${esc(m)} (your key)`;
      const m = String(sc.model);
      const label = m.startsWith("mixed:")
        ? m.slice(6).split("+").map(one).join(" + ") : one(m);
      bits.push(`vision ${label}`);
    }
    if (sc.voice) bits.push(`voice ${esc(sc.voice)} — on this computer`);
    bits.push(esc(sc.review || "unreviewed"));
    const n = (sc.cues || []).filter(c => c.text).length;
    const ok = (sc.cues || []).filter(c =>
      c.text && ["accepted", "edited"].includes(c.status)).length;
    bits.push(`${ok}/${n} accepted`);
    return `<div class="itp-prov">${bits.join(" · ")}</div>`;
  }

  function timelineHTML() {
    const sc = S.script;
    const dur = (sc && sc.duration) || (S.meta && S.meta.duration) || 0;
    if (!sc || !dur || !(sc.cues || []).length) return "";
    const blocks = sc.cues.map((c, i) => {
      const x = (c.start / dur) * 100, w = Math.max(0.5, (c.dur / dur) * 100);
      const done = ["accepted", "edited"].includes(c.status);
      const fill = c.kind === "graphic"
        ? (done ? T.acc : "rgba(169,103,58,.35)")
        : (done ? "rgba(169,103,58,.8)" : "rgba(169,103,58,.18)");
      return `<button data-tl="${i}" title="${c.kind === "graphic" ? "slide / graphic" : "pause"} · ${fmtT(c.start)} · ${c.dur.toFixed(1)}s"
        aria-label="description ${i + 1}: ${esc(c.kind)} at ${fmtT(c.start)}"
        style="position:absolute;left:${x}%;width:${w}%;top:${c.kind === "graphic" ? "3px" : "17px"};
        height:11px;background:${fill};border:1px solid ${S.sel === i ? "var(--cream)" : "transparent"};
        border-radius:3px;cursor:pointer;padding:0"></button>`;
    }).join("");
    return `
      <div class="nr-tl">${blocks}</div>
      <div class="hint">top row: slides &amp; graphics · bottom row: pauses in the talk · ${fmtT(0)}–${fmtT(dur)} · click a block to jump to its card</div>`;
  }

  function cueCard(c, i) {
    const done = ["accepted", "edited"].includes(c.status);
    const lintChips = (c.lint || []).map(l =>
      `<span class="badge" title="the style check flags this — your call stands">${esc(l)}</span>`).join("");
    const budget = c.words_budget
      ? `room for about ${c.words_budget} words in this ${c.dur.toFixed(1)}s pause`
      : `no pause here — it goes in the transcript, not the voice track`;
    return `<div data-card="${i}" class="nr-card${S.sel === i ? " sel" : ""}${done ? " done" : ""}">
      <div style="display:flex;gap:8px;align-items:baseline;flex-wrap:wrap">
        <button class="nr-jump" data-jump="${i}" title="play this moment">▶ ${fmtT(c.start)}</button>
        <span class="badge">${c.kind === "graphic" ? "▤ slide / graphic" : "pause"}</span>
        <span class="hint" style="display:inline">${budget}</span>
        <span style="margin-left:auto" class="badge${done ? " hw" : ""}">${done ? "✓ accepted" : esc(c.status)}</span>
      </div>
      <textarea data-text="${i}" rows="2" placeholder="${c.status === "failed" ? "the draft failed — write it yourself, or redo it" : "no draft yet — Draft descriptions writes one; or write your own"}">${esc(c.text || "")}</textarea>
      <div style="display:flex;gap:6px;margin-top:5px;align-items:center;flex-wrap:wrap">
        ${lintChips}
        <span style="margin-left:auto"></span>
        <button class="btn${done ? "" : " primary"}" data-accept="${i}" style="width:auto;padding:3px 12px;font-size:11.5px;${done ? "" : "color:#fff"}"
          ${c.text ? "" : "disabled"}>${done ? "✓ accepted" : "Accept"}</button>
        <button class="btn" data-regen="${i}" data-needs-key style="width:auto;padding:3px 10px;font-size:11.5px"
          title="one fresh draft for this moment">↻ Redo</button>
      </div>
    </div>`;
  }

  function renderMain() {
    const box = $("#nr-center", el);
    const sc = S.script;
    const st = stepState();
    const vision = S.status && S.status.vision.ok;
    const voice = S.status && S.status.tts.ok;
    const cues = (sc && sc.cues) || [];
    const nText = cues.filter(c => c.text).length;
    const nOk = cues.filter(c => c.text && ["accepted", "edited"].includes(c.status)).length;
    const clean = cues.filter(c => c.text && c.status === "draft" && !(c.lint || []).length).length;
    const cur = !st.planned ? 1 : !st.drafted ? 2 : !st.accepted ? 3 : !st.rendered ? 4 : 5;

    const outputs = [["mix_video", "described video (.mp4)"], ["mix_audio", "described audio (.m4a)"],
                     ["ad", "narration track alone (.wav)"], ["vtt", "descriptions transcript (.vtt)"]]
      .filter(([k]) => S.outputs[k]);

    box.innerHTML = `
      <div class="pb-kithead">
        <div style="min-width:0">
          <div class="tag">audio description</div>
          <h1 style="font-size:21px;margin-top:3px">${esc(S.meta.title)}</h1>
          <div class="hint">${sc && sc.duration ? fmtT(sc.duration) : ""}${sc && sc.n_shots ? ` · ${sc.n_shots} shots` : ""}${cues.length ? ` · ${cues.length} moments to describe` : ""}</div>
        </div>
        <div class="pb-kitacts">${czNextHTML("narrator", S.source, { isFile: S.source === S.video })}</div>
      </div>
      ${provenanceHTML()}
      <video id="nr-video" controls preload="metadata" crossorigin="anonymous"
        style="width:100%;max-height:340px;background:#000;border-radius:9px;margin-top:10px">
        <source src="/api/narrator/media?path=${encodeURIComponent(S.video)}">
        ${S.outputs.vtt ? `<track kind="descriptions" label="Descriptions" srclang="en"
          src="/api/narrator/track?path=${encodeURIComponent(S.source)}&kind=vtt&r=${(sc && sc.rendered) || 0}">` : ""}
      </video>
      ${vision && voice ? "" : `<div style="margin-top:10px">${enginesHTML()}</div>`}

      <div class="cz-step ${st.planned ? "done" : "current"}" style="--acc:${T.acc}">
        <div class="cz-step-head"><span class="cz-step-num">${st.planned ? "✓" : "1"}</span>
          <h2>Map the program</h2>
          <span class="cz-step-state">${st.planned ? `${cues.length} moments found` : "runs on this computer"}</span></div>
        <div class="cz-step-sub">Finds the pauses between speakers (where a description can be spoken)
          and every slide or graphic (always worth reading aloud).</div>
        <div class="cz-row"><button class="btn${st.planned ? "" : " primary cz-bigbtn"}" id="nr-plan"
          style="${st.planned ? "width:auto" : "color:#fff"}">${st.planned ? "↺ Map again" : "① Map the program"}</button></div>
        ${timelineHTML()}
      </div>

      <div class="cz-step ${st.drafted ? "done" : cur === 2 ? "current" : ""}" style="--acc:${T.acc}">
        <div class="cz-step-head"><span class="cz-step-num">${st.drafted ? "✓" : "2"}</span>
          <h2>Draft the descriptions</h2>
          <span class="cz-step-state">${st.drafted ? `${nText} drafted` : ""}</span></div>
        <div class="cz-step-sub">An AI looks at each moment's picture and writes one short line in the
          broadcast description style. ${vision ? "" : "It needs an AI key (or an on-device model) — the button asks for one."}</div>
        <div class="cz-row"><button class="btn${cur === 2 ? " primary cz-bigbtn" : ""}" id="nr-draft" data-needs-key
          style="${cur === 2 ? "color:#fff" : "width:auto"}" ${st.planned ? "" : "disabled"}>② Draft descriptions</button></div>
        <div id="nr-prog"></div>
      </div>

      <div class="cz-step ${st.accepted && !cues.some(c => c.text && c.status === "draft") ? "done" : cur === 3 ? "current" : ""}" style="--acc:${T.acc}">
        <div class="cz-step-head"><span class="cz-step-num">3</span>
          <h2>Review every card</h2>
          <span class="cz-step-state">${nOk} of ${nText} accepted</span></div>
        <div class="cz-step-sub">Read each line against the picture (▶ plays that moment). Accept it,
          rewrite it, or redo it. Only accepted lines are spoken or written — nothing else is ever used.</div>
        <div class="cz-row">
          <button class="btn" id="nr-acceptall" style="width:auto" ${clean ? "" : "disabled"}
            title="accept every draft the style check had no notes on — flagged ones wait for you">✓ Accept all ${clean} clean drafts</button>
        </div>
        ${cues.length ? `<div id="nr-cards">${cues.map((c, i) => cueCard(c, i)).join("")}</div>`
          : `<div class="hint" style="margin-top:8px">the cards appear after step 1</div>`}
      </div>

      <div class="cz-step ${st.rendered ? "done" : cur === 4 ? "current" : ""}" style="--acc:${T.acc}">
        <div class="cz-step-head"><span class="cz-step-num">${st.rendered ? "✓" : "4"}</span>
          <h2>Render the described version</h2></div>
        <div class="cz-step-sub">The voice speaks every accepted line in its pause, and the meeting's sound
          dips underneath. ${voice ? "" : "The voice is a one-time download on the Models page."}
          ${st.accepted && !st.fitted ? " None of the accepted lines has a pause to fit in — write the transcript instead (for extended description)." : ""}</div>
        <div class="cz-row">
          <button class="btn${cur === 4 && st.fitted && voice ? " primary cz-bigbtn" : ""}" id="nr-render"
            style="${cur === 4 && st.fitted && voice ? "color:#fff" : "width:auto"}" ${st.fitted && voice ? "" : "disabled"}>▶ Render with the voice</button>
          <button class="btn" id="nr-vttonly" style="width:auto" ${st.accepted ? "" : "disabled"}
            title="the descriptions as a timed text file — no voice needed">Write the transcript only</button>
          <span class="hint" id="nr-jobstat"></span>
        </div>
        <div id="nr-rprog"></div>
        ${outputs.length ? `<div class="tag" style="margin-top:12px">made</div>
          ${outputs.map(([k, label]) => `<div class="batchrow"><span class="bname">${label}</span>
            <span class="bstat"><a href="/api/narrator/track?path=${encodeURIComponent(S.source)}&kind=${k}&dl=1"
              class="itp-dl">⇩ download</a></span>
            <button data-rev="${k}">Show in Finder</button></div>`).join("")}` : ""}
      </div>`;

    wireEngines(box);
    markKeyButtons(box, !!vision);
    $("#nr-plan", box).onclick = () => runJob("/api/narrator/plan", "mapping the program", null, "#nr-prog");
    $("#nr-draft", box).onclick = () => runJob("/api/narrator/describe", "drafting descriptions", null, "#nr-prog");
    $("#nr-render", box).onclick = () => runJob("/api/narrator/render", "voicing + mixing", null, "#nr-rprog");
    $("#nr-vttonly", box).onclick = async () => {
      try {
        const r = await api("/api/narrator/transcript", { path: S.source });
        toast("descriptions transcript written");
        S.outputs.vtt = r.vtt;
        open(S.source);
      } catch (e) { toast(e.message, true); }
    };
    $("#nr-acceptall", box).onclick = acceptAllClean;
    $$("[data-tl]", box).forEach(b => b.onclick = () => select(+b.dataset.tl));
    $$("[data-jump]", box).forEach(b => b.onclick = () => {
      const c = S.script.cues[+b.dataset.jump];
      const vid = $("#nr-video", el);
      if (vid && c) { vid.currentTime = Math.max(0, c.start - 0.5); vid.play().catch(() => {}); }
      vid && vid.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
    $$("[data-rev]", box).forEach(b => b.onclick = () =>
      api("/api/media/reveal", { path: S.outputs[b.dataset.rev] })
        .catch(e => toast(e.message, true)));
    $$("[data-text]", box).forEach(x => x.onchange = () =>
      patchCue(+x.dataset.text, { text: x.value }));
    $$("[data-accept]", box).forEach(b => b.onclick = () => {
      const i = +b.dataset.accept;
      const ta = $(`[data-text="${i}"]`, box);
      const cue = S.script.cues[i];
      if (ta.value !== (cue.text || "")) patchCue(i, { text: ta.value, status: "accepted" });
      else patchCue(i, { status: "accepted" });
    });
    $$("[data-regen]", box).forEach(b => b.onclick = () =>
      runJob("/api/narrator/describe", "one fresh draft", { only: [+b.dataset.regen] }, "#nr-prog"));
  }

  function select(i) {
    S.sel = i;
    const c = S.script.cues[i];
    const vid = $("#nr-video", el);
    if (vid && c) { vid.currentTime = Math.max(0, c.start - 0.5); }
    renderMain();
    const card = $(`[data-card="${i}"]`, el);
    if (card) card.scrollIntoView({ block: "center", behavior: "smooth" });
  }

  async function patchCue(i, patch) {
    try {
      const r = await api("/api/narrator/cue", { path: S.source, i, ...patch });
      S.script.cues[i] = r.cue;
      S.script.review = r.review;
      renderMain();
    } catch (e) { toast(e.message, true); }
  }

  async function acceptAllClean() {
    const cues = S.script.cues;
    let n = 0;
    for (let i = 0; i < cues.length; i++) {
      const c = cues[i];
      if (c.text && c.status === "draft" && !(c.lint || []).length) {
        await patchCue(i, { status: "accepted" });
        n++;
      }
    }
    toast(n ? `${n} clean drafts accepted — the flagged ones wait for you`
            : "no clean drafts to accept — the flagged ones want your eyes");
  }

  async function runJob(route, label, extra, slot) {
    try {
      const job = await api(route, { path: S.source, ...(extra || {}) });
      const p = czProgress($(slot || "#nr-prog", el) || $(".inspector", el), { label, acc: T.acc });
      watchJob(job.id, j => p.update(j));
      const done = await jobDone(job.id);
      p.finish(done);
      if (done.status === "done") { toast(done.message || "done"); open(S.source); }
      else if (done.status === "error") toast(done.error, true);
    } catch (e) { toast(e.message, true); }
  }

  /* ---------- status ---------- */
  async function loadStatus() {
    try {
      S.status = await api("/api/narrator/status");
      $("#nr-vision", el).textContent = S.status.vision.ok ? S.status.vision.sentence
        : "nothing yet — add an AI key (the page asks when you need it), or install an on-device vision model by hand (Models page)";
      $("#nr-tts", el).innerHTML = S.status.tts.ok ? esc(S.status.tts.sentence)
        : `not downloaded — <a href="#" id="nr-tts-go">Models page → vits-ljs</a> (112 MB, one click)`;
      const g = $("#nr-tts-go", el);
      if (g) g.onclick = e => { e.preventDefault(); go("models"); };
    } catch (e) { /* the page still reads scripts */ }
  }

  /* ---------- wire up ---------- */
  let inited = false;
  function init() {
    $("#nr-back", el).onclick = shelf;
    wireDropZone($("#nr-center", el), open);
  }

  async function onshow(arg) {
    const first = !inited;
    if (!inited) { init(); inited = true; }
    await loadStatus();
    if (arg && arg.openPath) open(arg.openPath);
    else if (first || !S.source) shelf();
    else renderMain();
  }

  function reset() {
    const v = $("#nr-video", el);
    if (v) v.pause();
    Object.assign(S, { source: null, meta: null, video: null, script: null, outputs: {}, sel: -1 });
    if (inited) shelf();
  }

  registerPage("narrator", el, onshow, { reset });
  return { onshow };
})();
