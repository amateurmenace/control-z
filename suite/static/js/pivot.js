/* Pivot workspace — full parity with the old pivot page, plus the suite
   vocabulary: shared viewer + filmstrip, Easy/Studio inspector, export panel,
   path-trace scope, per-shot overrides, queue-aware jobs. */

const PivotPage = (() => {
  const T = toolById("pivot");
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-pivot";
  el.innerHTML = `
  <div class="ws" style="--acc:${T.acc}">
    <div class="mediabar">
      <span class="toolname"><i>Pivot</i> · follows the subject</span>
      <input type="text" id="pv-path" placeholder="/path/to/master.mov — paste a path or Browse" spellcheck="false">
      <button class="btn" style="width:auto" id="pv-open">Open</button>
      <button class="btn" style="width:auto" id="pv-browse">Browse…</button>
      <span class="clipmeta" id="pv-meta"></span>
    </div>
    <div class="ws-body">
      <div class="ws-center">
        <div id="pv-viewer"></div>
        <div class="lane">
          <div id="pv-strip"></div>
          <div class="toollane"><div class="shotstrip" id="pv-shots">
            <span style="color:var(--cream-faint);font-size:12px">analyze to see shots</span>
          </div></div>
        </div>
        <div class="scoperack">
          <div class="scope"><div class="slabel">path trace — targets vs solved</div>
            <canvas id="pv-spark" width="560" height="76"></canvas></div>
          <div class="scope"><div class="slabel">punch-in</div>
            <canvas id="pv-punch" width="120" height="76"></canvas>
            <div class="sval" id="pv-punchval"></div></div>
          <div class="scope"><div class="slabel">histogram</div>
            <canvas id="pv-hist" width="150" height="76"></canvas></div>
          <div class="scope"><div class="slabel">waveform</div>
            <canvas id="pv-wave" width="150" height="76"></canvas></div>
        </div>
      </div>
      <div class="inspector" id="pv-insp">
        <div class="insp-head"><h2>Pivot</h2>
          <div class="density"><button data-d="easy">Easy</button><button data-d="studio">Studio</button></div>
        </div>

        <div class="insp-sec">
          <span class="tag">aspects</span>
          <div class="chips" id="pv-aspects">
            <span class="chip on" data-a="9:16">9:16</span>
            <span class="chip" data-a="1:1">1:1</span>
            <span class="chip" data-a="4:5">4:5</span>
          </div>
          <div class="field"><label>camera feel</label>
            <select id="pv-solver">
              <option value="calm">Calm — moves only when it must</option>
              <option value="standard" selected>Standard — editor's default</option>
              <option value="attentive">Attentive — follows closely</option>
            </select>
          </div>
          <button class="btn primary" id="pv-analyze" disabled style="margin-top:12px">Analyze</button>
          <div class="prog"><i id="pv-abar"></i></div>
          <div class="progmsg" id="pv-amsg"></div>
        </div>

        <div class="insp-sec" id="pv-viewsec" style="display:none">
          <span class="tag">viewing</span>
          <div class="chips" id="pv-viewaspects"></div>
          <div class="hint field" style="color:var(--cream-faint);font-size:10.5px">
            crop + subject drawn on the viewer — every camera decision visible.
            Override any shot below the filmstrip.</div>
        </div>

        <div class="insp-sec" id="pv-exportsec" style="display:none">
          <span class="tag">export</span>
          <div class="field"><label>format</label>
            <select id="pv-preset"></select>
            <div class="hint" id="pv-presetnote"></div>
          </div>
          <div class="field studio-only"><label>output size (blank = native crop, never silently upscaled)</label>
            <input type="text" id="pv-outsize" placeholder="e.g. 1080x1920" spellcheck="false">
          </div>
          <div class="checkrow"><input type="checkbox" id="pv-denoise">
            <span>Denoise crops (Hush core)
              <div class="hint">punch-ins amplify noise — clean at crop scale before any
                scaling. Neighbor frames are cropped at the same rect, so the temporal
                stack stays registered while the camera moves. Slower; σ lands in the report.</div></span>
          </div>
          <div class="checkrow"><input type="checkbox" id="pv-enhance">
            <span>Enhance punch-ins <span class="badge synth" id="pv-enhbadge" style="display:none">synthesis</span>
              <div class="hint" id="pv-enhhint">routes upscaled crops through Rise</div></span>
          </div>
          <div class="field studio-only"><label>enhance model</label>
            <select id="pv-enhmodel"></select>
          </div>
          <button class="btn primary" id="pv-render" style="margin-top:12px">Render</button>
          <button class="btn" id="pv-fusion">Export Fusion .setting</button>
          <div class="prog"><i id="pv-rbar"></i></div>
          <div class="progmsg" id="pv-rmsg"></div>
          <div class="report" id="pv-report"></div>
        </div>
      </div>
    </div>
  </div>`;

  /* overrides: "<aspect>:<shot>" -> mode the user picked. renderShots runs on
     every shot change under the playhead, so the select's choice has to be
     remembered here — the DOM one is rebuilt out from under it. */
  const P = { clip: null, analysis: null, aspect: null, backends: [], overrides: {} };
  let viewer, strip;

  /* ---------- helpers ---------- */
  const sol = () => P.analysis && P.aspect ? P.analysis.aspects[P.aspect] : null;

  function shotAt(i) {
    if (!P.analysis) return -1;
    return P.analysis.shots.findIndex(([s, e]) => i >= s && i < e);
  }

  /* ---------- overlay: the covenant surface ---------- */
  function overlay(g, v) {
    const a = P.analysis, s = sol();
    if (!a || !s) return;
    const i = Math.min(v.frame, s.centers.length - 1);
    const sx = v.iw * v.scale / a.width;   // source px -> canvas px
    const sy = v.ih * v.scale / a.height;
    let rx, ry, rw, rh;
    if (s.axis === "x") {
      const c = s.centers[i];
      let x = c * a.width - s.crop_w / 2;
      x = Math.max(0, Math.min(a.width - s.crop_w, x));
      [rx, ry, rw, rh] = [x, 0, s.crop_w, s.crop_h];
    } else if (s.axis === "y") {
      const c = s.centers[i];
      let y = c * a.height - s.crop_h / 2;
      y = Math.max(0, Math.min(a.height - s.crop_h, y));
      [rx, ry, rw, rh] = [0, y, s.crop_w, s.crop_h];
    } else {
      [rx, ry, rw, rh] = [0, 0, a.width, a.height];
    }
    const cx = v.x + rx * sx, cy = v.y + ry * sy, cw = rw * sx, ch = rh * sy;
    /* darken outside the crop */
    g.fillStyle = "rgba(10,10,14,.55)";
    g.beginPath();
    g.rect(v.x, v.y, v.iw * v.scale, v.ih * v.scale);
    g.rect(cx, cy, cw, ch);
    g.fill("evenodd");
    g.strokeStyle = "#5B7A9E"; g.lineWidth = 2 * devicePixelRatio;
    g.strokeRect(cx, cy, cw, ch);
    /* detected subject: amber dot at the raw target */
    const t = (s.targets || [])[v.frame];
    if (t != null) {
      g.fillStyle = "#E5A835";
      g.beginPath();
      const tx = s.axis === "y" ? v.x + 0.5 * v.iw * v.scale : v.x + t * v.iw * v.scale;
      const ty = s.axis === "y" ? v.y + t * v.ih * v.scale : v.y + 0.4 * v.ih * v.scale;
      g.arc(tx, ty, 4.5 * devicePixelRatio, 0, 7);
      g.fill();
    }
  }

  /* ---------- scopes ---------- */
  function drawSpark() {
    const c = $("#pv-spark", el), g = c.getContext("2d");
    g.fillStyle = "#0D0D12"; g.fillRect(0, 0, c.width, c.height);
    const a = P.analysis, s = sol();
    if (!a || !s) {
      g.fillStyle = "#7E7D75"; g.font = "10px SF Mono, monospace";
      g.fillText("analyze to trace the camera path", 10, 42);
      return;
    }
    const N = a.n_frames;
    g.strokeStyle = "#2A2A35";
    a.shots.forEach(sh => {
      const x = sh[0] / N * c.width;
      g.beginPath(); g.moveTo(x, 0); g.lineTo(x, c.height); g.stroke();
    });
    /* raw targets — amber (the measurement) */
    g.strokeStyle = "#E5A835"; g.lineWidth = 1; g.globalAlpha = .8;
    g.beginPath(); let started = false;
    (s.targets || []).forEach((t, i) => {
      if (t == null) { started = false; return; }
      const x = i / N * c.width, y = (1 - t) * (c.height - 6) + 3;
      started ? g.lineTo(x, y) : g.moveTo(x, y); started = true;
    });
    g.stroke(); g.globalAlpha = 1;
    /* solved path — tool accent */
    g.strokeStyle = "#5B7A9E"; g.lineWidth = 2;
    g.beginPath();
    s.centers.forEach((v, i) => {
      const x = i / N * c.width, y = (1 - v) * (c.height - 6) + 3;
      i ? g.lineTo(x, y) : g.moveTo(x, y);
    });
    g.stroke();
    /* playhead */
    g.fillStyle = "#F5F3EE";
    g.fillRect(viewer.i / N * c.width - 1, 0, 2, c.height);
  }

  function drawPunch() {
    const c = $("#pv-punch", el), g = c.getContext("2d");
    g.fillStyle = "#0D0D12"; g.fillRect(0, 0, c.width, c.height);
    const s = sol(), val = $("#pv-punchval", el);
    if (!s) { val.textContent = ""; return; }
    let ow = s.crop_w;
    const m = ($("#pv-outsize", el).value || "").match(/^(\d+)\s*x\s*(\d+)$/i);
    if (m) ow = +m[1];
    const punch = ow / s.crop_w;
    const frac = Math.min(punch / 2, 1);
    g.fillStyle = punch > 1.001 ? "#E5A835" : "#7FA05B";
    g.fillRect(6, c.height - 14, (c.width - 12) * frac, 8);
    g.strokeStyle = "#2A2A35"; g.strokeRect(6, c.height - 14, c.width - 12, 8);
    const mid = 6 + (c.width - 12) * 0.5;
    g.fillStyle = "#7E7D75"; g.fillRect(mid, c.height - 18, 1, 16);
    g.font = "10px SF Mono, monospace"; g.fillStyle = "#B9B7AC";
    g.fillText("1×", mid - 4, c.height - 22);
    val.textContent = punch > 1.001
      ? `${punch.toFixed(2)}× past native — soft; Enhance helps`
      : `${punch.toFixed(2)}× — native detail`;
  }

  function updateScopes() {
    drawSpark(); drawPunch();
    const d = viewer.frameData();
    drawHistogram($("#pv-hist", el), d);
    drawWaveform($("#pv-wave", el), d);
  }

  /* ---------- shots lane ---------- */
  function renderShots() {
    const box = $("#pv-shots", el);
    const a = P.analysis, s = sol();
    if (!a || !s) {
      box.innerHTML = `<span style="color:var(--cream-faint);font-size:12px">analyze to see shots</span>`;
      return;
    }
    const cur = shotAt(viewer.i);
    box.innerHTML = a.subjects.map((row, i) => {
      const subj = row.fallback_center ? "center"
        : `${row.subject_source || "face"}·${row.detections}`;
      return `<span class="shotchip ${i === cur ? "cur" : ""}" data-shot="${i}">
        <span>#${i}</span><span class="m">${s.shot_modes[i]}</span>
        <span>${subj}</span>
        ${row.fallback_center ? `<span class="warn" title="no subject found — static center crop">◦</span>` : ""}
        <select data-shot="${i}">
          ${["auto", "punch", "follow", "center"].map(m => `<option>${m}</option>`).join("")}
        </select></span>`;
    }).join("");
    $$(".shotchip", box).forEach(chip => {
      chip.onclick = e => {
        if (e.target.tagName === "SELECT") return;
        const [s0] = a.shots[+chip.dataset.shot];
        viewer.stop(); viewer.show(s0);
      };
    });
    $$("select", box).forEach(sel => {
      const i = +sel.dataset.shot;
      sel.value = P.overrides[`${P.aspect}:${i}`] || "auto";
      sel.onchange = async () => {
        const key = `${P.aspect}:${i}`, prev = P.overrides[key] || "auto", mode = sel.value;
        try {
          const r = await api("/api/pivot/override",
            { path: P.clip.path, aspect: P.aspect, shot: i, mode });
          const [s0, e0] = a.shots[i];
          s.centers.splice(s0, e0 - s0, ...r.centers);
          s.shot_modes[i] = r.mode;
          if (mode === "auto") delete P.overrides[key]; else P.overrides[key] = mode;
          renderShots(); updateScopes(); viewer.draw();
          toast(`shot #${i} → ${r.mode} (${r.moves} moves)`);
        } catch (err) {
          sel.value = prev;   // the solve didn't change; neither should the control
          toast(err.message, true);
        }
      };
    });
  }

  /* ---------- open / analyze / render ---------- */
  async function open(path) {
    try {
      const r = await api("/api/media/open", { path, tool: "pivot" });
      P.clip = r;
      $("#pv-path", el).value = r.path;
      const v = r.video;
      $("#pv-meta", el).innerHTML = v
        ? `<b>${esc(r.name)}</b> · ${v.width}×${v.height} @ ${v.fps.toFixed(2)} · ~${v.n_frames_estimate ?? "?"} frames · audio ${r.audio_streams ? "✓" : "—"}`
        : esc(r.name);
      $("#pv-analyze", el).disabled = false;
      P.analysis = null; P.aspect = null; P.overrides = {};
      viewer.setClip({ path: r.path, nFrames: v.n_frames_estimate || 1, fps: v.fps, w: v.width, h: v.height });
      strip.setClip(viewer.clip); strip.setMarks([]);
      renderShots(); updateScopes();
      $("#pv-viewsec", el).style.display = "none";
      $("#pv-exportsec", el).style.display = "none";
      $("#pv-amsg", el).classList.remove("err");   // a fresh clip is not last clip's error
      const side = await api("/api/pivot/load", { path: r.path });
      if (side.analysis) { applyAnalysis(side.analysis); $("#pv-amsg", el).textContent = "sidecar found — solved paths loaded"; }
      // a present-but-unparseable sidecar carries a remedy sentence — say it,
      // don't blank it as if the prior analysis were simply absent
      else if (side.warning) { $("#pv-amsg", el).textContent = side.warning; $("#pv-amsg", el).classList.add("err"); }
      else $("#pv-amsg", el).textContent = r.sidecars.pivot ? "" : "ready to analyze";
      try { P.backends = (await api("/api/rise/probe", { path: r.path })).backends; } catch (e) { P.backends = []; }
      renderEnhance();
    } catch (e) { toast(e.message, true); }
  }

  function applyAnalysis(a) {
    P.analysis = a;
    P.aspect = Object.keys(a.aspects)[0];
    P.overrides = {};   // a fresh solve is auto everywhere again
    viewer.clip.nFrames = a.n_frames;       // exact now, estimate before
    viewer.clip.fps = a.fps;
    strip.setClip(viewer.clip);
    strip.setMarks(a.shots.map(s => s[0]).slice(1));
    $("#pv-viewsec", el).style.display = "";
    $("#pv-exportsec", el).style.display = "";
    const va = $("#pv-viewaspects", el);
    va.innerHTML = Object.keys(a.aspects).map(x =>
      `<span class="chip ${x === P.aspect ? "on" : ""}" data-a="${x}">${x}</span>`).join("");
    $$(".chip", va).forEach(ch => ch.onclick = () => {
      P.aspect = ch.dataset.a;
      $$(".chip", va).forEach(c => c.classList.toggle("on", c === ch));
      renderShots(); updateScopes(); viewer.draw();
    });
    viewer.show(Math.min(viewer.i, a.n_frames - 1));
    renderShots(); updateScopes();
  }

  async function analyze() {
    const aspects = $$("#pv-aspects .chip.on", el).map(c => c.dataset.a);
    if (!aspects.length) { toast("pick at least one aspect", true); return; }
    const btn = $("#pv-analyze", el);
    btn.disabled = true;
    $("#pv-abar", el).style.width = "6%";
    try {
      const job = await api("/api/pivot/analyze",
        { path: P.clip.path, aspects, preset: $("#pv-solver", el).value });
      watchJob(job.id, j => {
        $("#pv-amsg", el).textContent = j.message || j.status;
        $("#pv-abar", el).style.width = j.status === "queued" ? "6%" : "40%";
      });
      const done = await jobDone(job.id);
      btn.disabled = false;
      $("#pv-abar", el).style.width = done.status === "done" ? "100%" : "0%";
      if (done.status === "error") { $("#pv-amsg", el).textContent = done.error; $("#pv-amsg", el).classList.add("err"); return; }
      if (done.status === "cancelled") { $("#pv-amsg", el).textContent = "analyze cancelled"; return; }
      $("#pv-amsg", el).classList.remove("err");
      $("#pv-amsg", el).textContent = `${done.result.shots.length} shots · ${done.result.n_frames} frames`;
      applyAnalysis(done.result);
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  function renderEnhance() {
    const sel = $("#pv-enhmodel", el);
    const present = P.backends.filter(b => b.present);
    sel.innerHTML = `<option value="auto">auto — best available</option>` +
      P.backends.map(b =>
        `<option value="${b.id}" ${b.present ? "" : "disabled"}>${b.id}${b.present ? "" : " — not converted yet"}</option>`).join("");
    const synth = present.some(b => b.synthesized);
    $("#pv-enhbadge", el).style.display = synth ? "" : "none";
    $("#pv-enhhint", el).textContent = synth
      ? "routes upscaled crops through Rise (Real-ESRGAN — synthesized texture, labeled in the report)"
      : "Rise model not converted yet — enhance falls back to honest lanczos resampling (no invented detail)";
  }

  async function render() {
    const presetSel = $("#pv-preset", el);
    $("#pv-rbar", el).style.width = "3%";
    $("#pv-rmsg", el).classList.remove("err");
    try {
      const job = await api("/api/pivot/render", {
        path: P.clip.path, aspect: P.aspect,
        preset: presetSel.value,
        out_size: $("#pv-outsize", el).value.trim() || null,
        enhance: $("#pv-enhance", el).checked,
        enhance_model: $("#pv-enhmodel", el).value,
        denoise: $("#pv-denoise", el).checked,
      });
      watchJob(job.id, j => {
        $("#pv-rbar", el).style.width = Math.round(Math.max(j.progress, 0.03) * 100) + "%";
        $("#pv-rmsg", el).textContent = j.status === "queued" ? "queued behind another job" : (j.message || j.status);
      });
      const done = await jobDone(job.id);
      if (done.status === "error") { $("#pv-rmsg", el).textContent = done.error; $("#pv-rmsg", el).classList.add("err"); return; }
      if (done.status === "cancelled") { $("#pv-rmsg", el).textContent = "render cancelled — partial file removed"; return; }
      const r = done.result;
      $("#pv-rmsg", el).textContent = "done";
      const rep = $("#pv-report", el);
      rep.classList.add("show");
      const dn = r.denoise;
      const dnLine = dn && dn !== "off"
        ? `\n   cleaned: hush core, σY ${(dn.sigma_y * 100).toFixed(1)}% → residual ${(dn.residual_y * 100).toFixed(1)}%`
        : "";
      rep.innerHTML += `<b>→</b> ${esc(r.out)}\n   ${r.size[0]}×${r.size[1]} · ${r.frames} frames · ${esc(r.encoder)} · audio ${esc(r.audio)}${dnLine}\n   ${esc(r.color)}` +
        (r.punch_in > 1.001 ? `\n   punch-in ${r.punch_in}× · enhance: ${esc(r.enhance)}` : "") + `\n`;
    } catch (e) { toast(e.message, true); }
  }

  async function exportFusion() {
    try {
      const r = await api("/api/pivot/export_fusion", { path: P.clip.path, aspect: P.aspect });
      const rep = $("#pv-report", el);
      rep.classList.add("show");
      rep.innerHTML += `<b>→</b> ${esc(r.out)}\n   ${r.keyframes} keyframes — paste onto the clip in Resolve's Fusion page\n`;
    } catch (e) { toast(e.message, true); }
  }

  /* ---------- wire up ---------- */
  function init() {
    viewer = new Viewer($("#pv-viewer", el), { h: 360 });  // analyze warms this cache
    viewer.onOpen = p => open(p);
    viewer.overlay = overlay;
    viewer.onFrame = i => { strip.setFrame(i); updateScopes(); renderShotHighlight(); };
    strip = new Filmstrip($("#pv-strip", el), i => { viewer.stop(); viewer.show(i); });

    let lastShot = -1;
    function renderShotHighlight() {
      const cur = shotAt(viewer.i);
      if (cur !== lastShot) { lastShot = cur; renderShots(); }
    }

    $("#pv-open", el).onclick = () => { const p = $("#pv-path", el).value.trim(); if (p) open(p); };
    $("#pv-path", el).addEventListener("keydown", e => { if (e.key === "Enter") $("#pv-open", el).click(); });
    $("#pv-browse", el).onclick = async () => {
      try {
        const r = await api("/api/dialog/open-file", {});
        if (r.paths && r.paths[0]) open(r.paths[0]);
      } catch (e) { toast(e.message, true); }
    };
    $$("#pv-aspects .chip", el).forEach(c => c.onclick = () => c.classList.toggle("on"));
    $("#pv-analyze", el).onclick = analyze;
    $("#pv-render", el).onclick = render;
    $("#pv-fusion", el).onclick = exportFusion;
    $("#pv-outsize", el).addEventListener("input", drawPunch);

    /* density toggle */
    const insp = $("#pv-insp", el);
    const dens = $$(".density button", insp);
    function applyDensity(d) {
      insp.classList.toggle("studio", d === "studio");
      dens.forEach(b => b.classList.toggle("on", b.dataset.d === d));
    }
    dens.forEach(b => b.onclick = () => { applyDensity(b.dataset.d); setDensity("pivot", b.dataset.d); });
    applyDensity(density("pivot"));

    /* export presets */
    api("/api/export/presets").then(list => {
      const sel = $("#pv-preset", el);
      sel.innerHTML = list.map(p =>
        `<option value="${p.id}" ${p.available ? "" : "disabled"} data-note="${esc(p.note)}" data-hw="${p.hardware}">
          ${p.label}${p.hardware ? " · hw" : ""}${p.available ? "" : " — unavailable"}</option>`).join("");
      sel.value = "prores-hq";
      const note = () => {
        const o = sel.selectedOptions[0];
        $("#pv-presetnote", el).textContent = o ? o.dataset.note + (o.dataset.hw === "true" ? " (hardware encoder)" : "") : "";
      };
      sel.onchange = note; note();
    }).catch(() => {});
  }

  function onshow(arg) {
    if (!viewer) init();
    Viewer.active = viewer;
    if (arg && arg.openPath) open(arg.openPath);
    viewer.resize();
  }

  registerPage("pivot", el, onshow);
  return { onshow };
})();
