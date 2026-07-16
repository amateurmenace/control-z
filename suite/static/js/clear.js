/* Clear workspace — dialogue rescue. The covenant surface is the residual
   monitor: one chip plays exactly what was removed. Words in the residual =
   over-processing, and the band readout says where the energy went. */

const ClearPage = (() => {
  const T = toolById("clear");
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-clear";
  el.innerHTML = `
  <div class="ws" style="--acc:${T.acc}">
    <div class="mediabar">
      <span class="toolname"><i>Clear</i> · rescues the take</span>
      <input type="text" id="cl-path" placeholder="/path/to/interview.wav or .mov — paste a path or Browse" spellcheck="false">
      <button class="btn" style="width:auto" id="cl-open">Open</button>
      <button class="btn" style="width:auto" id="cl-browse">Browse…</button>
      <span class="clipmeta" id="cl-meta"></span>
    </div>
    <div class="ws-body">
      <div class="ws-center">
        <div style="flex:1;display:flex;flex-direction:column;min-height:0;background:#0D0D12">
          <div id="cl-waves" style="position:relative;height:38%;min-height:130px;cursor:pointer">
            <canvas style="position:absolute;inset:0;width:100%;height:100%"></canvas>
            <div class="viewer-empty" id="cl-empty"><div class="big">no audio open</div>
              <div>open a WAV, AIFF, or any video — the track is extracted</div></div>
          </div>
          <div id="cl-specwrap" style="position:relative;flex:1;border-top:1px solid var(--line-soft);display:none">
            <img id="cl-spec" style="position:absolute;inset:0;width:100%;height:100%;object-fit:fill">
            <canvas id="cl-specplay" style="position:absolute;inset:0;width:100%;height:100%;pointer-events:none"></canvas>
            <div class="viewer-ctl" style="display:flex">
              <button data-spec="before" class="on">before</button>
              <button data-spec="after" disabled>after</button>
            </div>
          </div>
        </div>
        <div class="lane" style="padding:8px 12px;display:flex;align-items:center;gap:10px">
          <button class="btn" style="width:auto;padding:6px 16px" id="cl-play" disabled>▶</button>
          <span class="clipmeta" id="cl-time">0:00.0</span>
          <span class="chips" id="cl-monitor">
            <span class="chip on" data-m="original">original</span>
            <span class="chip" data-m="cleaned" data-off>cleaned</span>
            <span class="chip" data-m="residual" data-off title="the covenant surface: exactly what the pass removed">
              🔍 what was removed</span>
          </span>
          <span class="clipmeta" id="cl-monhint" style="margin-left:auto"></span>
        </div>
        <div class="scoperack">
          <div class="scope"><div class="slabel">loudness</div>
            <canvas id="cl-loud" width="190" height="76"></canvas></div>
          <div class="scope"><div class="slabel">residual by band — null test</div>
            <canvas id="cl-bands" width="220" height="76"></canvas>
            <div class="sval" id="cl-bandhint"></div></div>
        </div>
      </div>
      <div class="inspector" id="cl-insp">
        <div class="insp-head"><h2>Clear</h2>
          <div class="density"><button data-d="easy">Easy</button><button data-d="studio">Studio</button></div>
        </div>

        <div class="insp-sec">
          <span class="tag">rescue pass</span>
          <div class="field"><label>mains hum</label>
            <select id="cl-dehum">
              <option value="auto" selected>auto-detect (50/60 Hz + harmonics)</option>
              <option value="off">off</option>
              <option value="50">force 50 Hz</option>
              <option value="60">force 60 Hz</option>
            </select>
          </div>
          <div class="checkrow"><input type="checkbox" id="cl-declick" checked>
            <span>repair clicks &amp; crackle
              <div class="hint">transient detect + AR interpolation — never touches speech</div></span>
          </div>
          <div class="field"><label>voice isolation <span id="cl-isoval" style="color:var(--amber)">off</span></label>
            <input type="range" id="cl-isolate" min="0" max="100" value="0" style="width:100%">
            <div class="hint" id="cl-isohint">DeepFilterNet3 with mix-back — 65% is the honest default;
              full-wet is rarely right</div>
          </div>
          <div class="field studio-only"><label>de-ess <span id="cl-deessval" style="color:var(--amber)">off</span></label>
            <input type="range" id="cl-deess" min="0" max="100" value="0" style="width:100%">
          </div>
          <div class="field"><label>loudness</label>
            <select id="cl-loudsel">
              <option value="">off — keep levels</option>
              <option value="broadcast">broadcast −24 LUFS</option>
              <option value="podcast">podcast −16 LUFS</option>
              <option value="streaming">streaming −14 LUFS</option>
            </select>
          </div>
          <div class="field studio-only"><label>custom target (LUFS, overrides preset)</label>
            <input type="text" id="cl-loudcustom" placeholder="e.g. -20" spellcheck="false">
          </div>
          <div class="checkrow" id="cl-remuxrow" style="display:none"><input type="checkbox" id="cl-remux" checked>
            <span>remux into video
              <div class="hint">cleaned track against the untouched video stream</div></span>
          </div>
          <button class="btn primary" id="cl-process" disabled style="margin-top:12px">Run rescue pass</button>
          <div class="prog"><i id="cl-bar"></i></div>
          <div class="progmsg" id="cl-msg"></div>
        </div>

        <div class="insp-sec">
          <span class="tag">room tone</span>
          <div class="field"><label>seconds to generate</label>
            <input type="text" id="cl-tonelen" value="30" spellcheck="false">
          </div>
          <button class="btn" id="cl-roomtone" disabled>Generate matching tone</button>
          <div class="hint" style="margin-top:5px">profiles the quietest 2 s, resynthesizes
            loop-safe tone for gap fills — drop it in the editor's bin</div>
        </div>

        <div class="report" id="cl-report"></div>
      </div>
    </div>
  </div>`;

  const C = { path: null, ov: null, result: null, monitor: "original", playing: false };
  const audio = new Audio();

  /* ---------- waveform ---------- */
  function drawWaves() {
    const wrap = $("#cl-waves", el);
    const c = $("canvas", wrap);
    const r = wrap.getBoundingClientRect();
    c.width = r.width * devicePixelRatio;
    c.height = r.height * devicePixelRatio;
    const g = c.getContext("2d");
    g.fillStyle = "#0D0D12";
    g.fillRect(0, 0, c.width, c.height);
    if (!C.ov) return;
    const draw = (peaks, color, alpha) => {
      if (!peaks) return;
      g.globalAlpha = alpha;
      g.fillStyle = color;
      const n = peaks.length, mid = c.height / 2, sy = c.height / 2.15;
      const bw = c.width / n;
      for (let i = 0; i < n; i++) {
        const [lo, hi] = peaks[i];
        g.fillRect(i * bw, mid - hi * sy, Math.max(1, bw - 0.4), Math.max(1, (hi - lo) * sy));
      }
      g.globalAlpha = 1;
    };
    draw(C.ov.original.peaks, "#B9B7AC", C.result ? 0.4 : 0.85);
    if (C.result) draw(C.result.processed.peaks, "#3E8E7E", 0.9);
    /* playhead */
    if (C.ov.duration) {
      const x = (audio.currentTime / C.ov.duration) * c.width;
      g.fillStyle = "#F5F3EE";
      g.fillRect(x - 1, 0, 2, c.height);
    }
  }

  function drawSpecPlayhead() {
    const c = $("#cl-specplay", el);
    const r = c.parentElement.getBoundingClientRect();
    c.width = r.width * devicePixelRatio;
    c.height = r.height * devicePixelRatio;
    const g = c.getContext("2d");
    if (!C.ov || !C.ov.duration) return;
    const x = (audio.currentTime / C.ov.duration) * c.width;
    g.fillStyle = "rgba(245,243,238,.85)";
    g.fillRect(x - 1, 0, 2, c.height);
  }

  /* ---------- scopes ---------- */
  function drawLoudness() {
    const c = $("#cl-loud", el), g = c.getContext("2d");
    g.fillStyle = "#0D0D12"; g.fillRect(0, 0, c.width, c.height);
    g.font = "9.5px SF Mono, monospace";
    if (!C.ov) { g.fillStyle = "#7E7D75"; g.fillText("open audio", 10, 42); return; }
    const rows = [["before", C.ov.original.lufs, C.ov.original.sample_peak_db, "#B9B7AC"]];
    if (C.result) rows.push(["after", C.result.processed.lufs, C.result.processed.sample_peak_db, "#3E8E7E"]);
    rows.forEach(([label, lufs, peak, color], k) => {
      const y = 18 + k * 30;
      g.fillStyle = "#7E7D75"; g.fillText(label, 6, y - 6);
      /* I bar: -40..0 LUFS */
      const frac = Math.max(0, Math.min(1, (lufs + 40) / 40));
      g.fillStyle = color; g.fillRect(6, y, (c.width - 60) * frac, 7);
      g.strokeStyle = "#2A2A35"; g.strokeRect(6, y, c.width - 60, 7);
      g.fillStyle = "#E5A835";
      g.fillText(`${lufs} LUFS`, c.width - 52, y + 7);
      g.fillStyle = "#7E7D75";
      g.fillText(`peak ${peak} dB`, 6, y + 16);
    });
  }

  function drawBands() {
    const c = $("#cl-bands", el), g = c.getContext("2d");
    g.fillStyle = "#0D0D12"; g.fillRect(0, 0, c.width, c.height);
    g.font = "9px SF Mono, monospace";
    const hint = $("#cl-bandhint", el);
    if (!C.result) {
      g.fillStyle = "#7E7D75"; g.fillText("run the pass, then listen", 10, 42);
      hint.textContent = "";
      return;
    }
    const bands = C.result.residual_bands;
    const bw = c.width / bands.length;
    bands.forEach((b, k) => {
      const frac = Math.max(0, Math.min(1, (b.rel_db + 30) / 30));  // -30..0 dB share
      const danger = b.band === "presence" && b.rel_db > -8;
      g.fillStyle = danger ? "#C4694F" : "#E5A835";
      const h = frac * (c.height - 26);
      g.fillRect(k * bw + 6, c.height - 14 - h, bw - 12, h);
      g.fillStyle = "#7E7D75";
      g.fillText(b.band, k * bw + 6, c.height - 4);
    });
    const pres = bands.find(b => b.band === "presence");
    hint.textContent = pres.rel_db > -8
      ? "presence band is loud — you may be eating words"
      : "presence quiet — dialogue intact";
  }

  /* ---------- transport ---------- */
  function setMonitor(m) {
    C.monitor = m;
    $$("#cl-monitor .chip", el).forEach(ch => ch.classList.toggle("on", ch.dataset.m === m));
    const t = audio.currentTime, was = !audio.paused;
    audio.src = `/api/clear/audio?path=${encodeURIComponent(C.path)}&kind=${m}`;
    audio.currentTime = t;
    if (was) audio.play();
    $("#cl-monhint", el).textContent =
      m === "residual" ? "hearing words here = over-processing — back off isolation" : "";
  }

  /* ---------- open / process ---------- */
  async function open(path) {
    try {
      $("#cl-msg", el).textContent = "reading audio…";
      const ov = await api("/api/clear/overview", { path });
      C.path = path; C.ov = ov; C.result = ov.processed || null;
      $("#cl-path", el).value = path;
      $("#cl-empty", el).style.display = "none";
      $("#cl-meta", el).innerHTML =
        `<b>${esc(path.split("/").pop())}</b> · ${ov.sr} Hz · ${ov.channels} ch · ${fmtTime(ov.duration)}`;
      $("#cl-specwrap", el).style.display = "";
      $("#cl-spec", el).src = ov.original.spectrogram;
      $("#cl-remuxrow", el).style.display = ov.has_video ? "" : "none";
      const iso = $("#cl-isolate", el);
      iso.disabled = !ov.isolate_available;
      $("#cl-isohint", el).textContent = ov.isolate_available
        ? "DeepFilterNet3 with mix-back — 65% is the honest default; full-wet is rarely right"
        : `not installed: ${ov.isolate_hint} (everything else works)`;
      $("#cl-play", el).disabled = false;
      $("#cl-process", el).disabled = false;
      $("#cl-roomtone", el).disabled = false;
      $$("#cl-monitor .chip", el).forEach(ch => {
        if (ch.dataset.m !== "original")
          ch.toggleAttribute("data-off", !C.result);
      });
      $("#cl-msg", el).textContent = C.result ? "earlier rescue pass loaded" : "";
      const specBtns = $$("#cl-specwrap .viewer-ctl button", el);
      specBtns[1].disabled = !C.result;
      setMonitor("original");
      if (C.result) applyResult(C.result, false);
      drawWaves(); drawLoudness(); drawBands();
      await api("/api/media/open", { path, tool: "clear" }).catch(() => {});
    } catch (e) { toast(e.message, true); $("#cl-msg", el).textContent = ""; }
  }

  function applyResult(r, announce) {
    C.result = r;
    $$("#cl-monitor .chip", el).forEach(ch => ch.removeAttribute("data-off"));
    const specBtns = $$("#cl-specwrap .viewer-ctl button", el);
    specBtns[1].disabled = false;
    const rep = $("#cl-report", el);
    rep.classList.add("show");
    if (announce) {
      rep.innerHTML += `<b>→</b> ${esc(r.out)}\n   ` + r.log.map(esc).join("\n   ") +
        (r.remux ? `\n   remuxed → ${esc(r.remux)}` : "") +
        (r.remux_error ? `\n   ${esc(r.remux_error)}` : "") +
        `\n   residual ${r.residual_rms_db} dB RMS — listen before you ship\n`;
    }
    drawWaves(); drawLoudness(); drawBands();
  }

  async function process() {
    const custom = $("#cl-loudcustom", el).value.trim();
    const btn = $("#cl-process", el);
    btn.disabled = true;
    $("#cl-bar", el).style.width = "10%";
    try {
      const job = await api("/api/clear/process", {
        path: C.path,
        dehum: $("#cl-dehum", el).value,
        declick: $("#cl-declick", el).checked,
        isolate: (+$("#cl-isolate", el).value) / 100,
        deess: (+$("#cl-deess", el).value) / 100,
        loudness: custom || $("#cl-loudsel", el).value || null,
        remux: $("#cl-remux", el).checked,
      });
      watchJob(job.id, j => {
        $("#cl-msg", el).textContent = j.status === "queued" ? "queued" : (j.message || j.status);
        $("#cl-bar", el).style.width = j.status === "running" ? "55%" : "10%";
      });
      const done = await jobDone(job.id);
      btn.disabled = false;
      $("#cl-bar", el).style.width = done.status === "done" ? "100%" : "0%";
      if (done.status === "error") { $("#cl-msg", el).textContent = done.error; $("#cl-msg", el).classList.add("err"); return; }
      if (done.status === "cancelled") { $("#cl-msg", el).textContent = "cancelled"; return; }
      $("#cl-msg", el).classList.remove("err");
      $("#cl-msg", el).textContent = "done — flip to cleaned, then listen to what was removed";
      applyResult(done.result, true);
      setMonitor("cleaned");
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  async function roomtone() {
    try {
      const r = await api("/api/clear/roomtone",
        { path: C.path, len: parseFloat($("#cl-tonelen", el).value) || 30 });
      const rep = $("#cl-report", el);
      rep.classList.add("show");
      rep.innerHTML += `<b>→</b> ${esc(r.out)}\n   ${r.seconds}s of tone from the quietest patch (${r.profiled[0]}–${r.profiled[1]}s)\n`;
      toast("room tone written — drop it in the editor's bin");
    } catch (e) { toast(e.message, true); }
  }

  /* ---------- wire up ---------- */
  function init() {
    $("#cl-open", el).onclick = () => { const p = $("#cl-path", el).value.trim(); if (p) open(p); };
    $("#cl-path", el).addEventListener("keydown", e => { if (e.key === "Enter") $("#cl-open", el).click(); });
    $("#cl-browse", el).onclick = async () => {
      try {
        const r = await api("/api/dialog/open-file", {});
        if (r.paths && r.paths[0]) open(r.paths[0]);
      } catch (e) { toast(e.message, true); }
    };

    $("#cl-play", el).onclick = () => { audio.paused ? audio.play() : audio.pause(); };
    audio.addEventListener("play", () => { $("#cl-play", el).textContent = "⏸"; });
    audio.addEventListener("pause", () => { $("#cl-play", el).textContent = "▶"; });
    audio.addEventListener("timeupdate", () => {
      $("#cl-time", el).textContent = fmtTime(audio.currentTime);
      drawWaves(); drawSpecPlayhead();
    });
    $("#cl-waves", el).addEventListener("mousedown", e => {
      if (!C.ov) return;
      const r = $("#cl-waves", el).getBoundingClientRect();
      audio.currentTime = ((e.clientX - r.left) / r.width) * C.ov.duration;
      drawWaves();
    });
    $$("#cl-monitor .chip", el).forEach(ch => ch.onclick = () => {
      if (ch.hasAttribute("data-off")) { toast("run the rescue pass first"); return; }
      setMonitor(ch.dataset.m);
    });
    $$("#cl-specwrap .viewer-ctl button", el).forEach(b => b.onclick = () => {
      $$("#cl-specwrap .viewer-ctl button", el).forEach(x => x.classList.toggle("on", x === b));
      $("#cl-spec", el).src = b.dataset.spec === "after" && C.result
        ? C.result.processed.spectrogram : C.ov.original.spectrogram;
    });
    $("#cl-isolate", el).addEventListener("input", e => {
      $("#cl-isoval", el).textContent = +e.target.value ? e.target.value + "%" : "off";
    });
    $("#cl-deess", el).addEventListener("input", e => {
      $("#cl-deessval", el).textContent = +e.target.value ? e.target.value + "%" : "off";
    });
    $("#cl-process", el).onclick = process;
    $("#cl-roomtone", el).onclick = roomtone;

    const insp = $("#cl-insp", el);
    const dens = $$(".density button", insp);
    function applyDensity(d) {
      insp.classList.toggle("studio", d === "studio");
      dens.forEach(b => b.classList.toggle("on", b.dataset.d === d));
    }
    dens.forEach(b => b.onclick = () => { applyDensity(b.dataset.d); setDensity("clear", b.dataset.d); });
    applyDensity(density("clear"));

    new ResizeObserver(() => { drawWaves(); drawSpecPlayhead(); }).observe($("#cl-waves", el));

    /* the router only toggles .active — watch for it leaving so a tool switch
       can't leave the residual playing underneath the next tool */
    new MutationObserver(() => { if (!el.classList.contains("active")) stop(); })
      .observe(el, { attributes: true, attributeFilter: ["class"] });
  }

  /* stop playing: called when this page stops being current (the playhead here
     is driven by timeupdate, so pausing is all it takes) */
  function stop() {
    audio.pause();
  }

  let inited = false;
  function onshow(arg) {
    if (!inited) { init(); inited = true; }
    Viewer.active = null;  // audio page: no frame viewer keys
    if (arg && arg.openPath) open(arg.openPath);
  }

  registerPage("clear", el, onshow);
  return { onshow, stop };
})();
