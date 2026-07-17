/* Slate — the maker's bench. The preview IS the renderer: every knob change
   re-renders a half-size frame through the export code path, on a checker
   so the alpha is visible. Scrub in/hold/out to see the move. Exports:
   ProRes 4444 (the real alpha), PNG still, GIF (web — the note says so).
   Below the preview, the rest of the kit: bars+tone, countdown, program slate. */

const SlatePage = (() => {
  const T = toolById("slate");
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-slate";
  el.innerHTML = `
  <div class="ws" style="--acc:${T.acc}">
    <div class="mediabar">
      <span class="toolname"><i>Slate</i> · makes it official</span>
      <span class="clipmeta">the station graphics kit — lower thirds first</span>
      <span class="clipmeta" id="sl-outdir" style="margin-left:auto"></span>
    </div>
    <div class="ws-body">
      <div class="ws-center" style="overflow-y:auto">
        <div class="sl-stage">
          <div class="sl-checker" id="sl-stagebox">
            <img id="sl-preview" alt="lower third preview">
            <div class="viewer-hud" style="pointer-events:none" id="sl-hud"></div>
          </div>
          <div class="sl-scrub">
            <button class="btn" style="width:auto;padding:4px 12px" data-t="in">in</button>
            <button class="btn" style="width:auto;padding:4px 12px" data-t="hold">hold</button>
            <button class="btn" style="width:auto;padding:4px 12px" data-t="out">out</button>
            <input type="range" id="sl-t" min="0" max="5" step="0.033" value="2.5" style="flex:1">
            <span class="clipmeta" id="sl-tlabel">t=2.50s</span>
            <label class="checkrow" style="margin:0"><input type="checkbox" id="sl-safe">
              <span>safe areas</span></label>
          </div>
        </div>

        <div class="sl-kit">
          <div class="tag" style="padding:0 16px">the rest of the kit</div>
          <div class="sl-cards">
            <div class="sl-card">
              <h2>Bars &amp; tone</h2>
              <div class="hint">SMPTE HD bars · 1 kHz at −20 dBFS · ProRes HQ</div>
              <div class="field"><label>duration (seconds)</label>
                <input type="text" id="sl-barsdur" value="30" spellcheck="false"></div>
              <button class="btn" id="sl-bars">Generate</button>
            </div>
            <div class="sl-card">
              <h2>Countdown</h2>
              <div class="hint">leader with sweep + beep each second</div>
              <div class="field"><label>count from</label>
                <input type="text" id="sl-countn" value="8" spellcheck="false"></div>
              <button class="btn" id="sl-count">Generate</button>
            </div>
            <div class="sl-card">
              <h2>Program slate</h2>
              <div class="hint">the card master control reads</div>
              <div class="field"><label>program</label>
                <input type="text" id="sl-cprogram" placeholder="Select Board — July 15" spellcheck="false"></div>
              <div class="field"><label>producer</label>
                <input type="text" id="sl-cproducer" placeholder="" spellcheck="false"></div>
              <div class="field"><label>TRT</label>
                <input type="text" id="sl-ctrt" placeholder="1:42:00" spellcheck="false"></div>
              <button class="btn" id="sl-card">PNG + 10s still</button>
            </div>
          </div>
          <div class="report" id="sl-genreport" style="margin:0 16px 18px"></div>
        </div>
      </div>

      <div class="inspector" id="sl-insp">
        <div class="insp-head"><h2>Lower third</h2>
          <div class="density"><button data-d="easy">Easy</button><button data-d="studio">Studio</button></div>
        </div>

        <div class="insp-sec">
          <span class="tag">the words</span>
          <div class="field"><label>line 1 — the name</label>
            <input type="text" id="sl-line1" value="Firstname Lastname" spellcheck="false"></div>
          <div class="field"><label>line 2 — the title</label>
            <input type="text" id="sl-line2" value="Title, Organization" spellcheck="false"></div>
          <div class="field"><label>font</label><select id="sl-font"></select></div>
        </div>

        <div class="insp-sec">
          <span class="tag">the look</span>
          <div class="chips" id="sl-style">
            <span class="chip on" data-v="bar">bar</span>
            <span class="chip" data-v="block">block</span>
            <span class="chip" data-v="line">line</span>
            <span class="chip" data-v="clean">clean</span>
          </div>
          <div class="field" style="display:flex;gap:10px;margin-top:10px">
            <span style="flex:1"><label>accent</label>
              <input type="color" id="sl-accent" value="#E5A835" class="sl-color"></span>
            <span style="flex:1"><label>text</label>
              <input type="color" id="sl-text" value="#F5F3EE" class="sl-color"></span>
          </div>
          <div class="field studio-only"><label>plate opacity <span id="sl-opv" class="mono-val"></span></label>
            <input type="range" id="sl-opacity" min="0" max="1" step="0.02" value="0.82" style="width:100%"></div>
          <div class="field studio-only"><label>position (left / baseline)</label>
            <div style="display:flex;gap:8px">
              <input type="range" id="sl-x" min="0.03" max="0.6" step="0.005" value="0.08" style="flex:1">
              <input type="range" id="sl-y" min="0.2" max="0.93" step="0.005" value="0.80" style="flex:1">
            </div>
            <div class="hint">title-safe starts at 10% — the safe-area toggle shows the cages</div></div>
          <div class="field studio-only"><label>type scale <span id="sl-scv" class="mono-val"></span></label>
            <input type="range" id="sl-scale" min="0.5" max="2" step="0.05" value="1" style="width:100%"></div>
        </div>

        <div class="insp-sec">
          <span class="tag">the move</span>
          <div class="chips" id="sl-anim">
            <span class="chip on" data-v="slide">slide</span>
            <span class="chip" data-v="rise">rise</span>
            <span class="chip" data-v="fade">fade</span>
            <span class="chip" data-v="none">none</span>
          </div>
          <div class="field studio-only" style="display:flex;gap:8px">
            <span style="flex:1"><label>in (s)</label><input type="text" id="sl-in" value="0.6" spellcheck="false"></span>
            <span style="flex:1"><label>hold (s)</label><input type="text" id="sl-hold" value="4" spellcheck="false"></span>
            <span style="flex:1"><label>out (s)</label><input type="text" id="sl-out" value="0.5" spellcheck="false"></span>
          </div>
        </div>

        <div class="insp-sec">
          <span class="tag">export</span>
          <div class="field" style="display:flex;gap:8px">
            <span style="flex:1.4"><label>frame size</label>
              <select id="sl-size">
                <option value="1920x1080" selected>1920 × 1080</option>
                <option value="3840x2160">3840 × 2160</option>
                <option value="1280x720">1280 × 720</option>
              </select></span>
            <span style="flex:1"><label>fps</label>
              <select id="sl-fps">
                <option value="29.97">29.97</option><option value="30" selected>30</option>
                <option value="25">25</option><option value="24">24</option>
                <option value="23.976">23.976</option><option value="60">60</option>
              </select></span>
          </div>
          <div class="chips" id="sl-formats" style="margin-top:10px">
            <span class="chip on" data-v="prores">ProRes 4444 + alpha</span>
            <span class="chip on" data-v="png">PNG</span>
            <span class="chip" data-v="gif">GIF</span>
          </div>
          <div class="hint" style="margin-top:5px">ProRes carries the real 10-bit alpha —
            that's the one you cut with. GIF is 256 colors, for the web.</div>
          <button class="btn primary" id="sl-render" style="margin-top:10px">Render lower third</button>
          <div class="prog"><i id="sl-bar"></i></div>
          <div class="progmsg" id="sl-msg"></div>
        </div>

        <div class="report" id="sl-report"></div>
      </div>
    </div>
  </div>`;

  const S = { t: 2.5, timer: null, seq: 0 };

  function chipVal(sel) { return $(`${sel} .chip.on`, el)?.dataset.v; }

  function params() {
    const [w, h] = $("#sl-size", el).value.split("x").map(Number);
    return {
      line1: $("#sl-line1", el).value, line2: $("#sl-line2", el).value,
      style: chipVal("#sl-style"), anim: chipVal("#sl-anim"),
      accent: $("#sl-accent", el).value, text_color: $("#sl-text", el).value,
      plate_opacity: parseFloat($("#sl-opacity", el).value),
      x: parseFloat($("#sl-x", el).value), y: parseFloat($("#sl-y", el).value),
      scale: parseFloat($("#sl-scale", el).value),
      font: $("#sl-font", el).value,
      width: w, height: h, fps: parseFloat($("#sl-fps", el).value),
      in_dur: parseFloat($("#sl-in", el).value) || 0.6,
      hold: parseFloat($("#sl-hold", el).value) || 4,
      out_dur: parseFloat($("#sl-out", el).value) || 0.5,
    };
  }

  function dur(p) { return p.in_dur + p.hold + p.out_dur; }

  /* the preview: debounced, sequenced (a slow early render can't stomp a
     newer one), rendered by the same code that exports */
  function schedulePreview(now) {
    clearTimeout(S.timer);
    S.timer = setTimeout(refreshPreview, now ? 0 : 180);
  }
  async function refreshPreview() {
    const p = params();
    const range = $("#sl-t", el);
    range.max = dur(p).toFixed(2);
    if (S.t > dur(p)) S.t = dur(p) / 2;
    $("#sl-tlabel", el).textContent = `t=${(+S.t).toFixed(2)}s`;
    const my = ++S.seq;
    try {
      const r = await fetch("/api/slate/preview", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ params: p, t: +S.t, safe: $("#sl-safe", el).checked }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        $("#sl-hud", el).textContent = err.error || `preview failed (${r.status})`;
        return;
      }
      const blob = await r.blob();
      if (my !== S.seq) return;
      const img = $("#sl-preview", el);
      const old = img.dataset.url;
      img.src = img.dataset.url = URL.createObjectURL(blob);
      if (old) URL.revokeObjectURL(old);
      const k = phaseName(p, +S.t);
      $("#sl-hud", el).innerHTML = `${p.width}×${p.height} · <b>${k}</b> · rendered by the export path`;
    } catch (e) { /* transient while typing */ }
  }
  function phaseName(p, t) {
    if (t < p.in_dur) return "in";
    if (t <= p.in_dur + p.hold) return "hold";
    return "out";
  }

  async function render() {
    const formats = $$("#sl-formats .chip.on", el).map(c => c.dataset.v);
    if (!formats.length) { toast("pick at least one format", true); return; }
    const btn = $("#sl-render", el);
    btn.disabled = true;
    try {
      const job = await api("/api/slate/render", { params: params(), formats });
      watchJob(job.id, j => {
        $("#sl-msg", el).textContent = j.message || j.status;
        $("#sl-bar", el).style.width = `${Math.max(0, j.progress) * 100}%`;
      });
      const done = await jobDone(job.id);
      btn.disabled = false;
      if (done.status === "done") {
        const rep = $("#sl-report", el);
        rep.classList.add("show");
        rep.innerHTML += `<b>→</b> ` + done.result.written.map(esc).join("\n   ")
          + (done.result.notes.length ? `\n   ${esc(done.result.notes.join(" · "))}` : "") + "\n";
        toast("rendered — it's in Movies/control-z/slate");
      } else if (done.status === "error") { toast(done.error, true); }
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  async function generate(kind, body, btn) {
    btn.disabled = true;
    try {
      const job = await api("/api/slate/generate", { kind, ...body });
      watchJob(job.id, j => { $("#sl-msg", el).textContent = j.message || j.status; });
      const done = await jobDone(job.id);
      btn.disabled = false;
      if (done.status === "done") {
        const rep = $("#sl-genreport", el);
        rep.classList.add("show");
        const outs = done.result.out ? [done.result.out]
          : Object.values(done.result).filter(v => typeof v === "string" && v.startsWith("/"));
        rep.innerHTML += `<b>→</b> ${outs.map(esc).join("\n   ")}\n`;
      } else if (done.status === "error") { toast(done.error, true); }
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  let inited = false;
  async function init() {
    try {
      const st = await api("/api/slate/status");
      $("#sl-outdir", el).textContent = st.out.replace(/^\/Users\/[^/]+/, "~");
      const sel = $("#sl-font", el);
      const prefer = ["HelveticaNeue", "Helvetica", "Arial", "SFNS"];
      sel.innerHTML = `<option value="">system default</option>` +
        st.fonts.map(f => `<option value="${esc(f.name)}"
          ${prefer[0] === f.name ? "" : ""}>${esc(f.name)}</option>`).join("");
      sel.onchange = () => schedulePreview();
    } catch (e) { toast(e.message, true); }

    $$("#sl-style .chip, #sl-anim .chip", el).forEach(c => c.onclick = () => {
      c.parentElement.querySelectorAll(".chip").forEach(x => x.classList.remove("on"));
      c.classList.add("on");
      schedulePreview(true);
    });
    $$("#sl-formats .chip", el).forEach(c => c.onclick = () => c.classList.toggle("on"));
    ["sl-line1", "sl-line2", "sl-in", "sl-hold", "sl-out"].forEach(id =>
      $("#" + id, el).addEventListener("input", () => schedulePreview()));
    ["sl-accent", "sl-text", "sl-size", "sl-fps"].forEach(id =>
      $("#" + id, el).addEventListener("input", () => schedulePreview()));
    [["sl-opacity", "sl-opv", v => (+v).toFixed(2)],
     ["sl-scale", "sl-scv", v => `${(+v).toFixed(2)}×`]].forEach(([id, lab, fmt]) => {
      const r = $("#" + id, el);
      const update = () => { $("#" + lab, el).textContent = fmt(r.value); };
      r.addEventListener("input", () => { update(); schedulePreview(); });
      update();
    });
    ["sl-x", "sl-y"].forEach(id =>
      $("#" + id, el).addEventListener("input", () => schedulePreview()));
    $("#sl-safe", el).onchange = () => schedulePreview(true);
    $("#sl-t", el).addEventListener("input", e => {
      S.t = +e.target.value;
      schedulePreview();
    });
    $$(".sl-scrub button[data-t]", el).forEach(b => b.onclick = () => {
      const p = params();
      S.t = b.dataset.t === "in" ? Math.max(0.01, p.in_dur * 0.55)
        : b.dataset.t === "hold" ? p.in_dur + p.hold / 2
        : p.in_dur + p.hold + p.out_dur * 0.55;
      $("#sl-t", el).value = S.t;
      schedulePreview(true);
    });
    $("#sl-render", el).onclick = render;
    $("#sl-bars", el).onclick = e => generate("bars",
      { duration: parseFloat($("#sl-barsdur", el).value) || 30 }, e.target);
    $("#sl-count", el).onclick = e => generate("countdown",
      { seconds: parseInt($("#sl-countn", el).value) || 8, font: $("#sl-font", el).value }, e.target);
    $("#sl-card", el).onclick = e => generate("card", {
      fields: { program: $("#sl-cprogram", el).value,
                producer: $("#sl-cproducer", el).value,
                trt: $("#sl-ctrt", el).value },
      still: 10, font: $("#sl-font", el).value,
    }, e.target);

    const insp = $("#sl-insp", el);
    const dens = $$(".density button", insp);
    function applyDensity(d) {
      insp.classList.toggle("studio", d === "studio");
      dens.forEach(b => b.classList.toggle("on", b.dataset.d === d));
    }
    dens.forEach(b => b.onclick = () => { applyDensity(b.dataset.d); setDensity("slate", b.dataset.d); });
    applyDensity(density("slate"));
  }

  function onshow() {
    if (!inited) { init(); inited = true; }
    schedulePreview(true);
  }

  registerPage("slate", el, onshow);
  return { onshow };
})();
