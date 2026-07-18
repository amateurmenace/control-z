/* Community Narrator — the picture, spoken, with a reviewer in the loop.
   Three moves on one page: map the program (shots + pauses + the
   graphics wedge), draft descriptions (vision on your key, DCMP-linted),
   render (one clear voice, auto-ducked under the program). The timeline
   is the product: every gap and every slide is a card; accept, edit or
   regenerate each one; nothing unaccepted reaches a track. */

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
      <input type="text" id="nr-path" spellcheck="false"
        placeholder="/path/to/program.mp4 — or a session with its full video fetched"
        style="flex:1;min-width:200px;background:var(--ink);border:1px solid var(--line);border-radius:7px;padding:6px 9px;font-size:12px;font-family:var(--mono);color:var(--cream)">
      <button class="btn" id="nr-open" style="width:auto">Open</button>
      <button class="btn" id="nr-browse" style="width:auto">Browse…</button>
    </div>
    <div class="ws-body">
      <div class="ws-center" id="nr-center" style="overflow-y:auto;padding:16px 20px"></div>
      <div class="inspector">
        <div class="insp-head"><h2>Narrator</h2></div>
        <div class="insp-sec">
          <span class="tag">the engines</span>
          <div class="hint" id="nr-vision">—</div>
          <div class="hint" id="nr-tts" style="margin-top:4px">—</div>
        </div>
        <div class="insp-sec">
          <span class="tag">the style</span>
          <div class="hint">DCMP: present tense · concise · describe, don't
          interpret · graphics read aloud. The lint marks drafts that
          drift; your accept is what airs.</div>
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

  /* ---------- open + shelf ---------- */
  async function open(path) {
    if (!path) return;
    $("#nr-path", el).value = path;
    const box = $("#nr-center", el);
    box.innerHTML = `<div class="hint" style="padding:16px 2px">reading the sidecars…</div>`;
    try {
      const r = await api("/api/narrator/open", { path });
      S.source = r.source; S.meta = r.meta; S.video = r.video;
      S.script = r.script; S.outputs = r.outputs || {}; S.sel = -1;
      renderMain();
    } catch (e) {
      box.innerHTML = `<div class="progmsg err" style="padding:14px 2px">${esc(e.message)}</div>`;
    }
  }

  async function shelf() {
    const box = $("#nr-center", el);
    let rows = [];
    try { rows = (await api("/api/narrator/library")).rows || []; } catch (e) {}
    if (S.source) return;
    const items = rows.slice(0, 20).map(r => `
      <div class="batchrow" data-open="${esc(r.source)}" role="button" tabindex="0"
        aria-label="open ${esc(r.title)}" style="cursor:pointer">
        <span class="bname" title="${esc(r.source)}">${esc(r.title)}</span>
        <span class="bstat">▮ video${r.duration ? ` · ${fmtT(r.duration)}` : ""}</span>
      </div>`).join("");
    box.innerHTML = `
      <div class="empty-grain" style="padding:28px 8px;color:var(--cream-dim);max-width:620px">
        <b>drop a program with its recording here</b> — description needs the picture.<br>
        the pipeline: map the pauses and the slides → AI drafts each description in DCMP style →
        you accept or rewrite each card → one clear voice, auto-ducked, lands a mixed track,
        a narration track, and a descriptions transcript.<br><br>
        <span class="hint">audio description in public access barely exists — this desk is the
        suite leading, not retrofitting. slides and charts read aloud are the point.</span>
      </div>
      ${rows.length ? `<div class="tag" style="margin-top:10px">meetings with their video — newest first</div>${items}` : ""}`;
    $$("[data-open]", box).forEach(b => {
      b.onclick = () => open(b.dataset.open);
      b.onkeydown = e => { if (e.key === "Enter" || e.key === " ") {
        e.preventDefault(); open(b.dataset.open); } };
    });
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
    if (sc.model) bits.push(`vision ${esc(sc.model)} (your key)`);
    if (sc.voice) bits.push(`voice ${esc(sc.voice)} — local`);
    bits.push(esc(sc.review || "unreviewed"));
    const n = (sc.cues || []).filter(c => c.text).length;
    const ok = (sc.cues || []).filter(c =>
      c.text && ["accepted", "edited"].includes(c.status)).length;
    bits.push(`${ok}/${n} accepted`);
    return `<div style="border:1px solid var(--line);border-left:3px solid ${T.acc};
      border-radius:7px;padding:7px 10px;margin:8px 0;font-size:12px;color:var(--cream-dim)">
      ${bits.join(" · ")}</div>`;
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
      return `<button data-tl="${i}" title="${esc(c.kind)} · ${fmtT(c.start)} · ${c.dur.toFixed(1)}s"
        aria-label="cue ${i + 1}: ${esc(c.kind)} at ${fmtT(c.start)}"
        style="position:absolute;left:${x}%;width:${w}%;top:${c.kind === "graphic" ? "2px" : "14px"};
        height:10px;background:${fill};border:1px solid ${S.sel === i ? "var(--cream)" : "transparent"};
        border-radius:3px;cursor:pointer;padding:0"></button>`;
    }).join("");
    return `
      <div class="tag" style="margin-top:16px">the timeline — graphics ride the top lane, pauses the bottom</div>
      <div style="position:relative;height:28px;background:var(--ink);border:1px solid var(--line);
        border-radius:7px;margin:6px 0 2px">${blocks}</div>
      <div class="hint">${fmtT(0)} — ${fmtT(dur)} · click a block to open its card</div>`;
  }

  function cueCard(c, i) {
    const done = ["accepted", "edited"].includes(c.status);
    const lintChips = (c.lint || []).map(l =>
      `<span class="badge" title="the lint marks style drift — your call stands">${esc(l)}</span>`).join("");
    const budget = c.words_budget
      ? `${c.words_budget} words fit this ${c.dur.toFixed(1)}s pause`
      : `no pause here — transcript + extended mode only`;
    return `<div data-card="${i}" style="border:1px solid var(--line);border-radius:9px;padding:8px 10px;
      margin-top:8px;${S.sel === i ? `border-color:${T.acc};` : ""}${done ? "opacity:.92;" : ""}">
      <div style="display:flex;gap:8px;align-items:baseline;flex-wrap:wrap">
        <span style="font-family:var(--mono);font-size:11px;color:var(--cream-dim)">${fmtT(c.start)}</span>
        <span class="badge">${c.kind === "graphic" ? "▤ graphic" : "pause"}</span>
        <span class="hint" style="display:inline">${budget}</span>
        <span style="margin-left:auto" class="badge">${esc(c.status)}</span>
      </div>
      <textarea data-text="${i}" rows="2" placeholder="${c.status === "failed" ? "the draft failed — write it, or regenerate" : "no draft yet — Draft descriptions writes one; or write your own"}"
        style="width:100%;margin-top:6px;background:var(--ink);border:1px solid var(--line);border-radius:6px;
        padding:5px 8px;font-size:12.5px;color:var(--cream)">${esc(c.text || "")}</textarea>
      <div style="display:flex;gap:6px;margin-top:5px;align-items:center;flex-wrap:wrap">
        ${lintChips}
        <span style="margin-left:auto"></span>
        <button class="btn" data-accept="${i}" style="width:auto;padding:3px 10px;font-size:11.5px"
          ${c.text || $("[data-text='" + i + "']", el) ? "" : "disabled"}>${done ? "✓ accepted" : "Accept"}</button>
        <button class="btn" data-regen="${i}" style="width:auto;padding:3px 10px;font-size:11.5px"
          title="one fresh draft for this cue, on your key">↻ Regenerate</button>
      </div>
    </div>`;
  }

  function renderMain() {
    const box = $("#nr-center", el);
    const sc = S.script;
    const st = stepState();
    const vision = S.status && S.status.vision.ok;
    const voice = S.status && S.status.tts.ok;

    const player = `
      <video id="nr-video" controls preload="metadata" crossorigin="anonymous"
        style="width:100%;max-height:340px;background:#000;border-radius:9px;margin-top:10px">
        <source src="/api/narrator/media?path=${encodeURIComponent(S.video)}">
        ${S.outputs.vtt ? `<track kind="descriptions" label="Descriptions" srclang="en"
          src="/api/narrator/track?path=${encodeURIComponent(S.source)}&kind=vtt&r=${(sc && sc.rendered) || 0}">` : ""}
      </video>`;

    const steps = `
      <div class="tag" style="margin-top:14px">the pass — three moves, one queue</div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:6px">
        <button class="btn${st.planned ? "" : " primary"}" id="nr-plan" style="width:auto">
          ${st.planned ? "↺ Re-map" : "① Map the program"}</button>
        <button class="btn${st.planned && !st.drafted ? " primary" : ""}" id="nr-draft" style="width:auto"
          ${st.planned && vision ? "" : "disabled"}>② Draft descriptions</button>
        <button class="btn${st.fitted && !st.rendered ? " primary" : ""}" id="nr-render" style="width:auto"
          ${st.fitted && voice ? "" : "disabled"}
          title="${st.accepted && !st.fitted ? "no pauses fit narration — the transcript carries these (extended mode)" : "voice every fitted description, duck the program under it"}">③ Render AD</button>
        <button class="btn" id="nr-vttonly" style="width:auto" ${st.accepted ? "" : "disabled"}
          title="the descriptions transcript alone — no voice needed; the record and the extended mode read it">Write transcript</button>
        <button class="btn" id="nr-acceptall" style="width:auto"
          ${st.drafted ? "" : "disabled"}
          title="accept every clean draft — lint-flagged cards wait for your eyes">✓ Accept all clean</button>
        <span class="hint" id="nr-jobstat"></span>
      </div>
      ${vision ? "" : `<div class="progmsg err" style="margin:6px 0">${esc(S.status ? S.status.vision.sentence : "…")}</div>`}
      ${voice ? "" : `<div class="progmsg err" style="margin:6px 0">${esc(S.status ? S.status.tts.sentence : "…")}</div>`}`;

    const exports = st.rendered || S.outputs.vtt ? `
      <div class="tag" style="margin-top:16px">the outputs — labeled, timed, ready</div>
      ${[["vtt", "descriptions transcript (.vtt)"], ["ad", "narration track (.wav)"],
         ["mix_audio", "mixed audio (.m4a)"], ["mix_video", "mixed program (.mp4)"]]
        .filter(([k]) => S.outputs[k])
        .map(([k, label]) => `<div class="batchrow"><span class="bname">${label}</span>
          <span class="bstat"><a href="/api/narrator/track?path=${encodeURIComponent(S.source)}&kind=${k}&dl=1"
            style="color:var(--cream-dim)">download ⇩</a></span>
          <button data-rev="${k}">Reveal</button></div>`).join("")}` : "";

    const cards = sc && (sc.cues || []).length ? `
      <div class="tag" style="margin-top:16px">the cards — accept, rewrite, or regenerate each</div>
      <div id="nr-cards">${sc.cues.map((c, i) => cueCard(c, i)).join("")}</div>` : "";

    box.innerHTML = `
      <div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap">
        <h1 style="font-size:19px">${esc(S.meta.title)}</h1>
        <span class="hint">${sc && sc.duration ? fmtT(sc.duration) : ""}${sc && sc.n_shots ? ` · ${sc.n_shots} shots` : ""}${sc && (sc.cues || []).length ? ` · ${sc.cues.length} cues` : ""}</span>
      </div>
      ${provenanceHTML()}
      ${player}
      ${steps}
      ${timelineHTML()}
      ${exports}
      ${cards}`;

    $("#nr-plan", box).onclick = () => runJob("/api/narrator/plan", "mapping the program");
    $("#nr-draft", box).onclick = () => runJob("/api/narrator/describe", "drafting on your key");
    $("#nr-render", box).onclick = () => runJob("/api/narrator/render", "voicing + mixing");
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
      runJob("/api/narrator/describe", "one fresh draft", { only: [+b.dataset.regen] }));
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
            : "no clean unaccepted drafts — the flagged ones want your eyes");
  }

  async function runJob(route, label, extra) {
    try {
      const job = await api(route, { path: S.source, ...(extra || {}) });
      const p = czProgress($(".inspector", el), { label, acc: T.acc });
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
      $("#nr-vision", el).textContent = S.status.vision.sentence;
      $("#nr-tts", el).textContent = S.status.tts.sentence;
    } catch (e) { /* the page still reads scripts */ }
  }

  /* ---------- wire up ---------- */
  let inited = false;
  function init() {
    $("#nr-open", el).onclick = () => open($("#nr-path", el).value.trim());
    $("#nr-path", el).addEventListener("keydown", e => {
      if (e.key === "Enter") open($("#nr-path", el).value.trim()); });
    $("#nr-browse", el).onclick = () => browseForPath(open);
    wireDropZone($("#nr-center", el), open);
  }

  function onshow(arg) {
    if (!inited) { init(); inited = true; shelf(); }
    loadStatus().then(() => { if (S.source) renderMain(); });
    if (arg && arg.openPath) open(arg.openPath);
  }

  registerPage("narrator", el, onshow);
  return { onshow };
})();
