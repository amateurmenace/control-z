/* Rise workspace — probe + interlace guard, A/B wipe vs honest bicubic,
   detail heatmap (|model − bicubic|), batch through the queue.
   The backend that actually ran is on screen at all times. */

const RisePage = (() => {
  const T = toolById("rise");
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-rise";
  el.innerHTML = `
  <div class="ws" style="--acc:${T.acc}">
    <div class="mediabar">
      <span class="toolname"><i>Rise</i> · restores the detail</span>
      <input type="text" id="rs-path" placeholder="/path/to/archive.mov — paste a path or Browse" spellcheck="false">
      <button class="btn" style="width:auto" id="rs-open">Open</button>
      <button class="btn" style="width:auto" id="rs-browse">Browse…</button>
      <span class="clipmeta" id="rs-meta"></span>
    </div>
    <div class="ws-body">
      <div class="ws-center">
        <div style="flex:1;position:relative;min-height:220px">
          <div id="rs-viewer" style="position:absolute;inset:0"></div>
          <div id="rs-ab" style="display:none;position:absolute;inset:0;z-index:5;background:#0D0D12">
            <canvas id="rs-abcanvas" style="position:absolute;inset:0;width:100%;height:100%"></canvas>
            <div class="viewer-ctl" style="display:flex">
              <button id="rs-heat">heatmap</button>
              <button id="rs-abback">← back to clip</button>
            </div>
            <div class="viewer-hud" style="display:flex" id="rs-abhud"></div>
          </div>
        </div>
        <div class="lane">
          <div id="rs-strip"></div>
          <div class="toollane"><div class="batchlist" id="rs-batch">
            <span style="color:var(--cream-faint);font-size:12px">open a clip — it joins the batch here</span>
          </div></div>
        </div>
        <div class="scoperack">
          <div class="scope"><div class="slabel">detail heat — |model − bicubic|</div>
            <canvas id="rs-heatscope" width="150" height="76"></canvas>
            <div class="sval" id="rs-heatval"></div></div>
          <div class="scope"><div class="slabel">interlace verdict</div>
            <canvas id="rs-interlace" width="150" height="76"></canvas></div>
          <div class="scope"><div class="slabel">backend</div>
            <canvas id="rs-backend" width="150" height="76"></canvas></div>
          <div class="scope"><div class="slabel">histogram</div>
            <canvas id="rs-hist" width="150" height="76"></canvas></div>
        </div>
      </div>
      <div class="inspector" id="rs-insp">
        <div class="insp-head"><h2>Rise</h2>
          <div class="density"><button data-d="easy">Easy</button><button data-d="studio">Studio</button></div>
        </div>

        <div class="insp-sec" id="rs-probesec" style="display:none">
          <span class="tag">probe</span>
          <div id="rs-verdict" style="font-size:12.5px;line-height:1.5"></div>
          <div id="rs-targets" class="hint" style="margin-top:6px"></div>
        </div>

        <div class="insp-sec">
          <span class="tag">enhance</span>
          <div class="chips" id="rs-scale">
            <span class="chip on" data-s="2">×2</span>
            <span class="chip" data-s="4">×4</span>
          </div>
          <div class="field"><label>model</label>
            <select id="rs-model"></select>
            <div class="hint" id="rs-modelnote"></div>
          </div>
          <div class="checkrow"><input type="checkbox" id="rs-denoise" checked>
            <span>clean noise first (Hush core)
              <div class="hint">upscaling amplifies noise — knee-gated 3-frame temporal +
                fine NLM at input scale, the Hush algorithm's core. Roughly halves speed;
                the report names the σ measured on the last frame.</div></span>
          </div>
          <div class="checkrow"><input type="checkbox" id="rs-stab">
            <span>temporal stabilization
              <div class="hint">flow-gated blend — kills per-frame shimmer on video</div></span>
          </div>
          <div class="field studio-only"><label>tile size (VRAM bound)</label>
            <select id="rs-tile"><option>256</option><option selected>512</option><option>768</option></select>
          </div>
          <div class="checkrow studio-only"><input type="checkbox" id="rs-force">
            <span>bypass interlace guard <span class="badge warn">on your head</span>
              <div class="hint">upscaling combed fields sharpens the combs — deinterlace first unless you know better</div></span>
          </div>
        </div>

        <div class="insp-sec">
          <span class="tag">preview</span>
          <button class="btn" id="rs-preview" disabled>Preview this frame (A/B + heat)</button>
          <div class="hint" style="margin-top:5px">click the viewer to move the probe patch — preview is a
            native-pixel window, not the whole frame</div>
        </div>

        <div class="insp-sec">
          <span class="tag">batch → queue</span>
          <div class="field"><label>deliver as</label>
            <select id="rs-preset"></select>
            <div class="hint" id="rs-presetnote"></div>
          </div>
          <button class="btn primary" id="rs-start" disabled>Start batch</button>
          <div class="report" id="rs-report"></div>
        </div>
      </div>
    </div>
  </div>`;

  /* reported: job ids already printed. Watchers re-fire on every poll, and a
     terminal job stays terminal forever — without this the report grows. */
  const R = { clip: null, probe: null, cx: 0.5, cy: 0.5, preview: null,
              batch: [], heatOn: true, reported: new Set() };
  let viewer, strip;

  /* ---------- probe panel ---------- */
  function renderProbe() {
    const p = R.probe;
    $("#rs-probesec", el).style.display = p ? "" : "none";
    if (!p) return;
    const inter = p.interlace;
    $("#rs-verdict", el).innerHTML = inter.interlaced
      ? `<span class="badge warn">interlaced</span> ${esc(inter.verdict)}`
      : `<span class="badge" style="color:var(--ok);border-color:var(--ok)">progressive</span> ${esc(inter.verdict)}`;
    $("#rs-targets", el).innerHTML = p.punch_targets.length
      ? "to " + p.punch_targets.map(t =>
          `${t.label}: <b style="color:var(--amber)">${t.factor}×</b> (×${t.model_scale} model)`).join(" · ")
      : "already at delivery resolution — Rise is for punch-ins and archives";
    drawInterlaceScope();
  }

  function renderModels() {
    const sel = $("#rs-model", el);
    const backends = (R.probe?.backends) || [{ id: "lanczos", present: true, synthesized: false,
      note: "honest resampling + edge-masked sharpen — no invented detail" }];
    sel.innerHTML = backends.map(b =>
      `<option value="${b.id}" ${b.present ? "" : "disabled"} data-note="${esc(b.note)}${b.hint ? " — " + esc(b.hint) : ""}">
        ${b.id}${b.synthesized ? " (synthesis)" : " (honest resample)"}${b.present ? "" : " — not converted"}</option>`).join("");
    const firstPresent = backends.find(b => b.present);
    if (firstPresent) sel.value = firstPresent.id;
    const note = () => {
      const o = sel.selectedOptions[0];
      $("#rs-modelnote", el).textContent = o ? o.dataset.note : "";
      drawBackendScope();
    };
    sel.onchange = note; note();
  }

  /* ---------- scopes ---------- */
  function drawInterlaceScope() {
    const c = $("#rs-interlace", el), g = c.getContext("2d");
    g.fillStyle = "#0D0D12"; g.fillRect(0, 0, c.width, c.height);
    g.font = "10.5px SF Mono, monospace";
    if (!R.probe) { g.fillStyle = "#7E7D75"; g.fillText("open a clip", 10, 42); return; }
    const inter = R.probe.interlace;
    g.fillStyle = inter.interlaced ? "#C4694F" : "#7FA05B";
    g.fillText(inter.interlaced ? "COMBED" : "PROGRESSIVE", 10, 34);
    g.fillStyle = "#7E7D75";
    g.fillText(`field: ${inter.field_order}`, 10, 52);
  }

  function drawBackendScope() {
    const c = $("#rs-backend", el), g = c.getContext("2d");
    g.fillStyle = "#0D0D12"; g.fillRect(0, 0, c.width, c.height);
    g.font = "10.5px SF Mono, monospace";
    const ran = R.preview?.backend;
    const sel = $("#rs-model", el).value;
    g.fillStyle = "#B9B7AC";
    g.fillText(`selected: ${sel || "—"}`, 10, 30);
    if (ran) {
      g.fillStyle = R.preview.synthesized ? "#E5A835" : "#7FA05B";
      g.fillText(`ran: ${ran}`, 10, 48);
      g.fillStyle = "#7E7D75";
      g.fillText(R.preview.synthesized ? "synthesized texture" : "no invented detail", 10, 64);
    } else {
      g.fillStyle = "#7E7D75"; g.fillText("preview to confirm", 10, 48);
    }
  }

  function drawHeatScope() {
    const c = $("#rs-heatscope", el), g = c.getContext("2d");
    g.fillStyle = "#0D0D12"; g.fillRect(0, 0, c.width, c.height);
    $("#rs-heatval", el).textContent = "";
    if (!R.preview) {
      g.fillStyle = "#7E7D75"; g.font = "10px SF Mono, monospace";
      g.fillText("preview a frame", 10, 42);
      return;
    }
    const img = new Image();
    img.onload = () => {
      /* amber-tint the grayscale heat */
      g.drawImage(img, 0, 0, c.width, c.height);
      g.globalCompositeOperation = "multiply";
      g.fillStyle = "#E5A835"; g.fillRect(0, 0, c.width, c.height);
      g.globalCompositeOperation = "source-over";
    };
    img.src = R.preview.heat;
    $("#rs-heatval", el).textContent =
      `added energy ${R.preview.added_energy} (0 = pure resample)`;
  }

  /* ---------- viewer overlay: probe patch target ---------- */
  function overlay(g, v) {
    if (!R.clip) return;
    const scale = +$$("#rs-scale .chip.on", el)[0].dataset.s;
    const [pw, ph] = scale === 2 ? [320, 180] : [192, 108];
    const w = R.clip.video.width, h = R.clip.video.height;
    const x0 = Math.min(Math.max(R.cx * w - pw / 2, 0), Math.max(w - pw, 0)) / w;
    const y0 = Math.min(Math.max(R.cy * h - ph / 2, 0), Math.max(h - ph, 0)) / h;
    const rx = v.x + x0 * v.iw * v.scale, ry = v.y + y0 * v.ih * v.scale;
    const rw = (pw / w) * v.iw * v.scale, rh = (ph / h) * v.ih * v.scale;
    g.strokeStyle = "#C99A3A"; g.lineWidth = 1.6 * devicePixelRatio;
    g.setLineDash([6, 4]);
    g.strokeRect(rx, ry, rw, rh);
    g.setLineDash([]);
    g.font = `${9 * devicePixelRatio}px SF Mono, monospace`;
    g.fillStyle = "#C99A3A";
    g.fillText("probe", rx + 3 * devicePixelRatio, ry - 4 * devicePixelRatio);
  }

  /* ---------- A/B preview panel ---------- */
  const ab = { wipe: 0.5, imgs: {} };

  function showAB() {
    $("#rs-ab", el).style.display = "";
    ab.imgs = {};
    ["bicubic", "up", "heat"].forEach(k => {
      const img = new Image();
      img.onload = () => drawAB();
      img.src = R.preview[k];
      ab.imgs[k] = img;
    });
    drawAB();
  }
  function hideAB() { $("#rs-ab", el).style.display = "none"; }

  function drawAB() {
    const c = $("#rs-abcanvas", el);
    const r = c.parentElement.getBoundingClientRect();
    c.width = r.width * devicePixelRatio; c.height = r.height * devicePixelRatio;
    const g = c.getContext("2d");
    g.fillStyle = "#0D0D12"; g.fillRect(0, 0, c.width, c.height);
    const A = ab.imgs.bicubic, B = ab.imgs.up;
    if (!A || !A.complete || !A.width) return;
    const s = Math.min(c.width / A.width, c.height / A.height);
    const x = c.width / 2 - A.width * s / 2, y = c.height / 2 - A.height * s / 2;
    g.imageSmoothingEnabled = s < 1;
    g.drawImage(A, x, y, A.width * s, A.height * s);
    const wx = ab.wipe * c.width;
    if (B && B.complete && B.width) {
      g.save();
      g.beginPath(); g.rect(wx, 0, c.width - wx, c.height); g.clip();
      g.drawImage(B, x, y, A.width * s, A.height * s);
      if (R.heatOn && ab.imgs.heat && ab.imgs.heat.complete) {
        g.globalAlpha = 0.55; g.globalCompositeOperation = "screen";
        /* tint heat amber via offscreen */
        const off = drawAB._off || (drawAB._off = document.createElement("canvas"));
        off.width = ab.imgs.heat.width; off.height = ab.imgs.heat.height;
        const og = off.getContext("2d");
        og.drawImage(ab.imgs.heat, 0, 0);
        og.globalCompositeOperation = "multiply";
        og.fillStyle = "#E5A835"; og.fillRect(0, 0, off.width, off.height);
        g.drawImage(off, x, y, A.width * s, A.height * s);
        g.globalAlpha = 1; g.globalCompositeOperation = "source-over";
      }
      g.restore();
    }
    g.fillStyle = "#F5F3EE"; g.fillRect(wx - 1, 0, 2, c.height);
    g.beginPath(); g.arc(wx, c.height / 2, 7, 0, 7); g.fill();
    g.font = `${10 * devicePixelRatio}px SF Mono, monospace`;
    g.fillStyle = "#B9B7AC";
    g.fillText("bicubic (honest)", 12, c.height - 12);
    const lab = R.preview.synthesized ? `${R.preview.backend} — synthesized` : `${R.preview.backend} — resampled`;
    g.fillText(lab, c.width - g.measureText(lab).width - 12, c.height - 12);
    const dn = R.preview.denoise;
    $("#rs-abhud", el).innerHTML =
      `<span>frame <b>${R.preview.frame}</b></span><span>added energy <b>${R.preview.added_energy}</b></span>` +
      (dn && dn !== "off" ? `<span>cleaned first · σ <b>${(dn.sigma_y * 100).toFixed(1)}%</b></span>` : "") +
      `<span>drag to wipe</span>`;
  }

  /* ---------- batch ---------- */
  function addToBatch(path) {
    if (R.batch.some(b => b.path === path)) return;
    R.batch.push({ path, jobId: null });
    renderBatch();
  }

  function renderBatch() {
    const box = $("#rs-batch", el);
    $("#rs-start", el).disabled = !R.batch.length;
    $("#rs-start", el).textContent = `Start batch (${R.batch.length})`;
    if (!R.batch.length) {
      box.innerHTML = `<span style="color:var(--cream-faint);font-size:12px">open a clip — it joins the batch here</span>`;
      return;
    }
    box.innerHTML = R.batch.map((b, k) => {
      const j = b.jobId ? CZ.jobs.get(b.jobId) : null;
      const pct = j && j.progress >= 0 ? Math.round(j.progress * 100) : null;
      const stat = j ? `<span class="stat-chip stat-${j.status}">${j.status}</span> ${j.status === "running" && pct != null ? pct + "%" : ""}`
                     : "ready";
      return `<div class="batchrow">
        <span class="bname">${esc(b.path.split("/").pop())}</span>
        <span class="bstat">${stat}</span>
        ${j && ["queued", "running"].includes(j.status)
          ? `<button data-cancel="${j.id}">cancel</button>`
          : `<button data-rm="${k}">remove</button>`}
      </div>`;
    }).join("");
    $$("button[data-rm]", box).forEach(b => b.onclick = () => { R.batch.splice(+b.dataset.rm, 1); renderBatch(); });
    $$("button[data-cancel]", box).forEach(b => b.onclick = async () => {
      b.disabled = true;
      try { await api(`/api/jobs/${b.dataset.cancel}/cancel`, {}); } catch (e) { toast(e.message, true); }
    });
  }

  async function startBatch() {
    const scale = +$$("#rs-scale .chip.on", el)[0].dataset.s;
    try {
      const r = await api("/api/rise/batch", {
        files: R.batch.map(b => b.path),
        scale, model: $("#rs-model", el).value,
        stabilize: $("#rs-stab", el).checked,
        force: $("#rs-force", el).checked,
        denoise: $("#rs-denoise", el).checked,
        preset: $("#rs-preset", el).value,
        tile: +$("#rs-tile", el).value,
      });
      r.jobs.forEach((j, k) => {
        R.batch[k].jobId = j.id;
        watchJob(j.id, job => {
          renderBatch();
          if (job.status !== "done" || !job.result) return;
          if (R.reported.has(job.id)) return;
          R.reported.add(job.id);
          const rep = $("#rs-report", el);
          rep.classList.add("show");
          const dn = job.result.denoise;
          const dnLine = dn && dn !== "off"
            ? `\n   cleaned first: hush core, σY ${(dn.sigma_y * 100).toFixed(1)}% → residual ${(dn.residual_y * 100).toFixed(1)}% — measured on frame ${dn.measured_on_frame} of ${job.result.frames}, not the clip`
            : "";
          rep.innerHTML += `<b>→</b> ${esc(job.result.out)}\n   ${job.result.size[0]}×${job.result.size[1]} · ${job.result.frames} frames · backend ${esc(job.result.backend)}${job.result.synthesized ? " (synthesized)" : " (resampled)"}${dnLine}\n   ${esc(job.result.color)}\n`;
        });
      });
      renderBatch();
      toast(`${r.jobs.length} upscale${r.jobs.length > 1 ? "s" : ""} queued`);
    } catch (e) { toast(e.message, true); }
  }

  /* ---------- open / preview ---------- */
  async function open(path) {
    try {
      const r = await api("/api/media/open", { path, tool: "rise" });
      if (!r.video) { toast("no video stream in that file", true); return; }
      R.clip = r;
      $("#rs-path", el).value = r.path;
      const v = r.video;
      $("#rs-meta", el).innerHTML =
        `<b>${esc(r.name)}</b> · ${v.width}×${v.height} @ ${v.fps.toFixed(2)} · ${esc(v.codec)}`;
      viewer.setClip({ path: r.path, nFrames: v.n_frames_estimate || 1, fps: v.fps, w: v.width, h: v.height });
      strip.setClip(viewer.clip);
      R.preview = null; hideAB();
      $("#rs-preview", el).disabled = false;
      R.probe = await api("/api/rise/probe", { path: r.path });
      renderProbe(); renderModels(); drawBackendScope(); drawHeatScope();
      addToBatch(r.path);
    } catch (e) { toast(e.message, true); }
  }

  async function preview() {
    const btn = $("#rs-preview", el);
    btn.disabled = true; btn.textContent = "computing…";
    try {
      const scale = +$$("#rs-scale .chip.on", el)[0].dataset.s;
      const r = await api("/api/rise/preview", {
        path: R.clip.path, i: viewer.i, cx: R.cx, cy: R.cy,
        scale, model: $("#rs-model", el).value,
        denoise: $("#rs-denoise", el).checked,
        tile: +$("#rs-tile", el).value,
      });
      r.frame = viewer.i;
      R.preview = r;
      showAB(); drawHeatScope(); drawBackendScope();
    } catch (e) { toast(e.message, true); }
    btn.disabled = false; btn.textContent = "Preview this frame (A/B + heat)";
  }

  /* ---------- wire up ---------- */
  function init() {
    viewer = new Viewer($("#rs-viewer", el), { h: 540 });
    viewer.overlay = overlay;
    viewer.onFrame = i => {
      strip.setFrame(i);
      drawHistogram($("#rs-hist", el), viewer.frameData());
    };
    strip = new Filmstrip($("#rs-strip", el), i => { viewer.stop(); viewer.show(i); });

    /* click moves the probe patch */
    $("#rs-viewer", el).addEventListener("click", e => {
      if (!R.clip || $("#rs-ab", el).style.display !== "none") return;
      const v = viewer.view(); if (!v) return;
      const rect = $("#rs-viewer", el).getBoundingClientRect();
      const mx = (e.clientX - rect.left) * devicePixelRatio;
      const my = (e.clientY - rect.top) * devicePixelRatio;
      R.cx = Math.max(0, Math.min(1, (mx - v.x) / (v.iw * v.scale)));
      R.cy = Math.max(0, Math.min(1, (my - v.y) / (v.ih * v.scale)));
      viewer.draw();
    });

    /* A/B interactions */
    const abEl = $("#rs-ab", el);
    abEl.addEventListener("mousedown", e => {
      const rect = abEl.getBoundingClientRect();
      const move = ev => { ab.wipe = Math.max(0.02, Math.min(0.98, (ev.clientX - rect.left) / rect.width)); drawAB(); };
      move(e);
      const up = () => { removeEventListener("mousemove", move); removeEventListener("mouseup", up); };
      addEventListener("mousemove", move); addEventListener("mouseup", up);
    });
    $("#rs-heat", el).onclick = e => { R.heatOn = !R.heatOn; e.target.classList.toggle("on", R.heatOn); drawAB(); };
    $("#rs-heat", el).classList.add("on");
    $("#rs-abback", el).onclick = hideAB;
    new ResizeObserver(() => { if ($("#rs-ab", el).style.display !== "none") drawAB(); }).observe($("#rs-viewer", el));

    $("#rs-open", el).onclick = () => { const p = $("#rs-path", el).value.trim(); if (p) open(p); };
    $("#rs-path", el).addEventListener("keydown", e => { if (e.key === "Enter") $("#rs-open", el).click(); });
    $("#rs-browse", el).onclick = async () => {
      try {
        const r = await api("/api/dialog/open-file", {});
        (r.paths || []).forEach((p, k) => k === 0 ? open(p) : addToBatch(p));
      } catch (e) { toast(e.message, true); }
    };
    $$("#rs-scale .chip", el).forEach(c => c.onclick = () => {
      $$("#rs-scale .chip", el).forEach(x => x.classList.toggle("on", x === c));
      viewer.draw();
    });
    $("#rs-preview", el).onclick = preview;
    $("#rs-start", el).onclick = startBatch;

    const insp = $("#rs-insp", el);
    const dens = $$(".density button", insp);
    function applyDensity(d) {
      insp.classList.toggle("studio", d === "studio");
      dens.forEach(b => b.classList.toggle("on", b.dataset.d === d));
    }
    dens.forEach(b => b.onclick = () => { applyDensity(b.dataset.d); setDensity("rise", b.dataset.d); });
    applyDensity(density("rise"));

    api("/api/export/presets").then(list => {
      const sel = $("#rs-preset", el);
      sel.innerHTML = list.map(p =>
        `<option value="${p.id}" ${p.available ? "" : "disabled"} data-note="${esc(p.note)}">
          ${p.label}${p.hardware ? " · hw" : ""}</option>`).join("");
      sel.value = "prores-hq";
      const note = () => {
        const o = sel.selectedOptions[0];
        $("#rs-presetnote", el).textContent = o ? o.dataset.note : "";
      };
      sel.onchange = note; note();
    }).catch(() => {});
    renderModels();
  }

  function onshow(arg) {
    if (!viewer) init();
    Viewer.active = viewer;
    if (arg && arg.openPath) open(arg.openPath);
    viewer.resize();
  }

  registerPage("rise", el, onshow);
  return { onshow };
})();
