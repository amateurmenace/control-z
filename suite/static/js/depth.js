/* Depth workspace — false-color scrub with a probe, histogram with in/out
   handles, matte render through the queue, Fusion template pack.
   Preview honesty: per-frame estimate; the render adds temporal smoothing. */

const DepthPage = (() => {
  const T = toolById("depth");
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-depth";
  el.innerHTML = `
  <div class="ws" style="--acc:${T.acc}">
    <div class="mediabar">
      <span class="toolname"><i>Depth</i> · maps the scene</span>
      <input type="text" id="dp-path" placeholder="/path/to/clip.mov — paste a path or Browse" spellcheck="false">
      <button class="btn" style="width:auto" id="dp-open">Open</button>
      <button class="btn" style="width:auto" id="dp-browse">Browse…</button>
      <span class="clipmeta" id="dp-meta"></span>
    </div>
    <div class="ws-body">
      <div class="ws-center">
        <div id="dp-viewer" style="flex:1;position:relative"></div>
        <div class="lane">
          <div id="dp-strip"></div>
          <div class="toollane" style="display:flex;gap:8px;align-items:center">
            <span class="chips" id="dp-mode">
              <span class="chip" data-m="source">source</span>
              <span class="chip on" data-m="blend">blend</span>
              <span class="chip" data-m="depth">depth</span>
            </span>
            <span class="clipmeta" id="dp-note">click the viewer to probe depth</span>
            <span class="clipmeta" id="dp-probe" style="margin-left:auto;color:var(--amber)"></span>
          </div>
        </div>
        <div class="scoperack">
          <div class="scope"><div class="slabel">depth histogram — drag in/out</div>
            <canvas id="dp-hist" width="300" height="76" style="cursor:ew-resize"></canvas>
            <div class="sval" id="dp-histval"></div></div>
          <div class="scope"><div class="slabel">stability</div>
            <canvas id="dp-stab" width="150" height="76"></canvas></div>
          <div class="scope"><div class="slabel">histogram (image)</div>
            <canvas id="dp-imghist" width="150" height="76"></canvas></div>
        </div>
      </div>
      <div class="inspector" id="dp-insp">
        <div class="insp-head"><h2>Depth</h2>
          <div class="density"><button data-d="easy">Easy</button><button data-d="studio">Studio</button></div>
        </div>

        <div class="insp-sec">
          <span class="tag">mapping</span>
          <div class="checkrow"><input type="checkbox" id="dp-invert">
            <span>invert (near = black)
              <div class="hint">default: near = white — Resolve mattes usually want this</div></span>
          </div>
          <div class="field"><label>gamma <span id="dp-gammaval" style="color:var(--amber)">1.0</span></label>
            <input type="range" id="dp-gamma" min="30" max="220" value="100" style="width:100%">
          </div>
          <div class="field studio-only"><label>temporal smoothing (render only, resets at cuts)</label>
            <select id="dp-ema">
              <option value="0.5">0.5 — lighter</option>
              <option value="0.7" selected>0.7 — default</option>
              <option value="0.85">0.85 — steadier</option>
            </select>
          </div>
          <div class="hint" style="margin-top:6px">depth here is relative, not measured —
            the model ranks pixels near-to-far inside one frame, and each shot is normalized
            to its own range, so a value is a place in this shot, never a distance</div>
          <div class="hint" style="margin-top:6px">scrub preview is a per-frame estimate —
            the render smooths temporally and resets at every cut, so the matte is steadier
            than what you scrub</div>
        </div>

        <div class="insp-sec">
          <span class="tag">deliver</span>
          <button class="btn primary" id="dp-render" disabled>Render depth matte</button>
          <div class="hint">10-bit gray ProRes, full res, edge-guided — imports as a matte</div>
          <div class="prog"><i id="dp-bar"></i></div>
          <div class="progmsg" id="dp-msg"></div>
          <button class="btn" id="dp-templates" style="margin-top:10px">Write Fusion template pack</button>
          <div class="hint">fog · rack-focus · depth-grade · parallax · haze-light</div>
        </div>

        <div class="report" id="dp-report"></div>
      </div>
    </div>
  </div>`;

  const D = { clip: null, prev: null, mode: "blend", lo: 0.0, hi: 1.0,
              probe: null, fcImg: null, reqTimer: null, reqId: 0, dragging: null };
  let viewer, strip;

  /* ---------- preview fetch (debounced on scrub/param change) ---------- */
  function requestPreview(delay = 220) {
    if (!D.clip) return;
    clearTimeout(D.reqTimer);
    D.reqTimer = setTimeout(async () => {
      const id = ++D.reqId;   // a slow reply must never paint over a newer frame
      try {
        const r = await api("/api/depth/preview", {
          path: D.clip.path, i: viewer.i,
          invert: $("#dp-invert", el).checked,
          gamma: (+$("#dp-gamma", el).value) / 100,
          lo: D.lo, hi: D.hi,
        });
        if (id !== D.reqId) return;
        D.prev = r;
        const img = new Image();
        img.onload = () => { if (id !== D.reqId) return; D.fcImg = img; viewer.draw(); };
        img.src = r.falsecolor;
        drawHist(); drawStab();
      } catch (e) {
        // a decode-past-EOF while scrubbing is normal and stays quiet; but if
        // we never got a first frame, the engine itself failed (e.g. the depth
        // model isn't downloaded) — say so once, with the remedy, not silence
        if (id === D.reqId && !D.prev && !D.warned) {
          D.warned = true;
          toast(`the depth preview didn't run — ${e.message}`, true);
        }
      }
    }, delay);
  }

  /* ---------- overlay: false color + probe ---------- */
  function overlay(g, v) {
    if (D.mode !== "source" && D.fcImg && D.fcImg.complete) {
      g.globalAlpha = D.mode === "depth" ? 1.0 : 0.62;
      g.drawImage(D.fcImg, v.x, v.y, v.iw * v.scale, v.ih * v.scale);
      g.globalAlpha = 1.0;
    }
    if (D.probe) {
      const px = v.x + D.probe.nx * v.iw * v.scale;
      const py = v.y + D.probe.ny * v.ih * v.scale;
      g.strokeStyle = "#E5A835"; g.lineWidth = 1.4 * devicePixelRatio;
      const r = 9 * devicePixelRatio;
      g.beginPath();
      g.moveTo(px - r, py); g.lineTo(px + r, py);
      g.moveTo(px, py - r); g.lineTo(px, py + r);
      g.stroke();
      g.beginPath(); g.arc(px, py, r * 0.55, 0, 7); g.stroke();
    }
  }

  function probeAt(nx, ny) {
    if (!D.prev) return;
    const ds = D.prev.depth_small;
    const y = Math.min(ds.length - 1, Math.max(0, Math.round(ny * (ds.length - 1))));
    const x = Math.min(ds[0].length - 1, Math.max(0, Math.round(nx * (ds[0].length - 1))));
    D.probe = { nx, ny, v: ds[y][x] };
    $("#dp-probe", el).textContent =
      `relative depth ${ds[y][x].toFixed(3)} · ${ds[y][x] > 0.5 ? "nearer" : "farther"} — model estimate, this frame`;
    viewer.draw();
  }

  /* ---------- scopes ---------- */
  function drawHist() {
    const c = $("#dp-hist", el), g = c.getContext("2d");
    g.fillStyle = "#0D0D12"; g.fillRect(0, 0, c.width, c.height);
    if (!D.prev) {
      g.fillStyle = "#7E7D75"; g.font = "10px SF Mono, monospace";
      g.fillText("open a clip", 10, 42);
      return;
    }
    const h = D.prev.hist, max = Math.max(...h, 1);
    const bw = c.width / h.length;
    for (let b = 0; b < h.length; b++) {
      const t = b / (h.length - 1);
      const inside = t >= D.lo && t <= D.hi;
      g.fillStyle = inside ? "#5B63B8" : "#33333F";
      const bh = Math.pow(h[b] / max, 0.5) * (c.height - 14);
      g.fillRect(b * bw + 0.5, c.height - 4 - bh, bw - 1, bh);
    }
    /* in/out handles */
    [["lo", D.lo], ["hi", D.hi]].forEach(([k, vv]) => {
      const x = vv * c.width;
      g.fillStyle = "#E5A835";
      g.fillRect(x - 1.2, 0, 2.4, c.height);
      g.beginPath(); g.moveTo(x - 5, 0); g.lineTo(x + 5, 0); g.lineTo(x, 7); g.fill();
    });
    $("#dp-histval", el).textContent =
      `in ${D.lo.toFixed(2)} · out ${D.hi.toFixed(2)}` +
      (D.prev.stability != null ? "" : "");
  }

  function drawStab() {
    const c = $("#dp-stab", el), g = c.getContext("2d");
    g.fillStyle = "#0D0D12"; g.fillRect(0, 0, c.width, c.height);
    g.font = "9.5px SF Mono, monospace";
    if (!D.prev) { g.fillStyle = "#7E7D75"; g.fillText("—", 10, 42); return; }
    if (D.prev.stability == null) {
      g.fillStyle = "#7E7D75";
      g.fillText("step ±1 frame to", 10, 36);
      g.fillText("measure stability", 10, 50);
      return;
    }
    const s = D.prev.stability;
    const frac = Math.min(s / 0.08, 1);
    g.fillStyle = s < 0.02 ? "#7FA05B" : (s < 0.05 ? "#E5A835" : "#C4694F");
    g.fillRect(8, c.height - 20, (c.width - 16) * frac, 9);
    g.strokeStyle = "#2A2A35"; g.strokeRect(8, c.height - 20, c.width - 16, 9);
    g.fillStyle = "#B9B7AC";
    g.fillText(`Δdepth ${s.toFixed(4)}/frame`, 8, 24);
    g.fillStyle = "#7E7D75";
    g.fillText("(render smooths this)", 8, 40);
  }

  /* ---------- open / render ---------- */
  async function open(path) {
    try {
      const r = await api("/api/media/open", { path, tool: "depth" });
      if (!r.video) { toast("no video stream in that file", true); return; }
      D.clip = { path: r.path, nFrames: r.video.n_frames_estimate || 1,
                 fps: r.video.fps, w: r.video.width, h: r.video.height };
      $("#dp-path", el).value = r.path;
      $("#dp-meta", el).innerHTML =
        `<b>${esc(r.name)}</b> · ${r.video.width}×${r.video.height} @ ${r.video.fps.toFixed(2)}`;
      D.prev = null; D.fcImg = null; D.probe = null; D.reqId = 0; D.warned = false;
      viewer.setClip(D.clip);
      strip.setClip(viewer.clip);
      $("#dp-render", el).disabled = false;
      requestPreview(50);
    } catch (e) { toast(e.message, true); }
  }

  async function render() {
    $("#dp-bar", el).style.width = "4%";
    try {
      const job = await api("/api/depth/render", {
        path: D.clip.path,
        invert: $("#dp-invert", el).checked,
        gamma: (+$("#dp-gamma", el).value) / 100,
        ema: +$("#dp-ema", el).value,
      });
      watchJob(job.id, j => {
        $("#dp-msg", el).textContent = j.status === "queued" ? "queued" : (j.message || j.status);
        $("#dp-bar", el).style.width = Math.round(Math.max(j.progress, 0.04) * 100) + "%";
      });
      const done = await jobDone(job.id);
      if (done.status === "error") { $("#dp-msg", el).textContent = done.error; $("#dp-msg", el).classList.add("err"); return; }
      if (done.status === "cancelled") { $("#dp-msg", el).textContent = "cancelled — partial removed"; return; }
      $("#dp-msg", el).classList.remove("err");
      $("#dp-msg", el).textContent = "done";
      const r = done.result;
      const rep = $("#dp-report", el);
      rep.classList.add("show");
      rep.innerHTML += `<b>→</b> ${esc(r.out)}\n   ${r.frames} frames · ${r.shots} shot(s) · near = ${r.near}\n   ${esc(r.note)}\n`;
    } catch (e) { toast(e.message, true); }
  }

  /* ---------- wire up ---------- */
  function init() {
    viewer = new Viewer($("#dp-viewer", el), { h: 540 });
    viewer.onOpen = p => open(p);
    viewer.overlay = overlay;
    viewer.onFrame = () => {
      strip.setFrame(viewer.i);
      drawHistogram($("#dp-imghist", el), viewer.frameData());
      D.probe = null; $("#dp-probe", el).textContent = "";
      requestPreview();
    };
    strip = new Filmstrip($("#dp-strip", el), i => { viewer.stop(); viewer.show(i); });

    $("#dp-viewer", el).addEventListener("click", e => {
      const v = viewer.view(); if (!v || !D.prev) return;
      const rect = $("#dp-viewer", el).getBoundingClientRect();
      const nx = ((e.clientX - rect.left) * devicePixelRatio - v.x) / (v.iw * v.scale);
      const ny = ((e.clientY - rect.top) * devicePixelRatio - v.y) / (v.ih * v.scale);
      if (nx >= 0 && nx <= 1 && ny >= 0 && ny <= 1) probeAt(nx, ny);
    });

    /* histogram handle drag */
    const hist = $("#dp-hist", el);
    hist.addEventListener("mousedown", e => {
      const r = hist.getBoundingClientRect();
      const t = (e.clientX - r.left) / r.width;
      D.dragging = Math.abs(t - D.lo) < Math.abs(t - D.hi) ? "lo" : "hi";
      const move = ev => {
        const tt = Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width));
        if (D.dragging === "lo") D.lo = Math.min(tt, D.hi - 0.02);
        else D.hi = Math.max(tt, D.lo + 0.02);
        drawHist(); requestPreview(120);
      };
      const up = () => { removeEventListener("mousemove", move); removeEventListener("mouseup", up); };
      addEventListener("mousemove", move); addEventListener("mouseup", up);
      move(e);
    });

    $$("#dp-mode .chip", el).forEach(ch => ch.onclick = () => {
      D.mode = ch.dataset.m;
      $$("#dp-mode .chip", el).forEach(x => x.classList.toggle("on", x === ch));
      viewer.draw();
    });
    $("#dp-gamma", el).addEventListener("input", e => {
      $("#dp-gammaval", el).textContent = ((+e.target.value) / 100).toFixed(1);
      requestPreview(200);
    });
    $("#dp-invert", el).addEventListener("change", () => requestPreview(50));
    $("#dp-open", el).onclick = () => { const p = $("#dp-path", el).value.trim(); if (p) open(p); };
    $("#dp-path", el).addEventListener("keydown", e => { if (e.key === "Enter") $("#dp-open", el).click(); });
    $("#dp-browse", el).onclick = async () => {
      try {
        const r = await api("/api/dialog/open-file", {});
        if (r.paths && r.paths[0]) open(r.paths[0]);
      } catch (e) { toast(e.message, true); }
    };
    $("#dp-render", el).onclick = render;
    $("#dp-templates", el).onclick = async () => {
      try {
        const r = await api("/api/depth/templates", {});
        const rep = $("#dp-report", el);
        rep.classList.add("show");
        rep.innerHTML += `<b>→</b> ${esc(r.dir)}\n   ${r.templates.join(" · ")}\n   ${esc(r.note)}\n`;
      } catch (e) { toast(e.message, true); }
    };

    const insp = $("#dp-insp", el);
    const dens = $$(".density button", insp);
    function applyDensity(d) {
      insp.classList.toggle("studio", d === "studio");
      dens.forEach(b => b.classList.toggle("on", b.dataset.d === d));
    }
    dens.forEach(b => b.onclick = () => { applyDensity(b.dataset.d); setDensity("depth", b.dataset.d); });
    applyDensity(density("depth"));
  }

  let inited = false;
  function onshow(arg) {
    if (!inited) { init(); inited = true; }
    Viewer.active = viewer;
    if (arg && arg.openPath) open(arg.openPath);
    if (viewer) viewer.resize();
  }

  registerPage("depth", el, onshow);
  return { onshow };
})();
