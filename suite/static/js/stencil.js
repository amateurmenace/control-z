/* Stencil workspace — click the subject, propagate, QC the confidence strip.
   Positive prompts are plum dots, negatives are red rings (⌥-click).
   The runtime (PyTorch + SAM 2.1) is optional and the page says so honestly. */

const StencilPage = (() => {
  const T = toolById("stencil");
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-stencil";
  el.innerHTML = `
  <div class="ws" style="--acc:${T.acc}">
    <div class="mediabar">
      <span class="toolname"><i>Stencil</i> · cuts the stencil</span>
      <input type="text" id="st-path" placeholder="/path/to/clip.mov — paste a path or Browse" spellcheck="false">
      <button class="btn" style="width:auto" id="st-open">Open</button>
      <button class="btn" style="width:auto" id="st-browse">Browse…</button>
      <span class="clipmeta" id="st-meta"></span>
    </div>
    <div class="ws-body">
      <div class="ws-center">
        <div id="st-viewer" style="flex:1;position:relative"></div>
        <div class="lane">
          <div id="st-strip"></div>
          <div class="toollane" style="display:flex;gap:10px;align-items:center">
            <span class="clipmeta">⊕ click = include · ⌥-click = exclude</span>
            <span class="clipmeta" id="st-promptcount"></span>
            <button class="btn" style="width:auto;padding:3px 10px;font-size:11px" id="st-clear">clear points</button>
            <span class="chips" style="margin-left:auto">
              <span class="chip on" id="st-tint">matte tint</span>
              <span class="chip" id="st-onion">onion skin</span>
            </span>
          </div>
        </div>
        <div class="scoperack">
          <div class="scope"><div class="slabel">confidence — the QC loop</div>
            <canvas id="st-conf" width="380" height="76"></canvas>
            <div class="sval" id="st-confval"></div></div>
          <div class="scope"><div class="slabel">coverage</div>
            <canvas id="st-cov" width="150" height="76"></canvas></div>
        </div>
      </div>
      <div class="inspector" id="st-insp">
        <div class="insp-head"><h2>Stencil</h2>
          <div class="density"><button data-d="easy">Easy</button><button data-d="studio">Studio</button></div>
        </div>

        <div class="insp-sec" id="st-runtimewarn" style="display:none">
          <div class="hint" style="border:1px solid var(--amber);border-radius:7px;padding:9px 11px;color:var(--cream-dim)"
            id="st-runtimehint"></div>
        </div>

        <div class="insp-sec">
          <span class="tag">propagate</span>
          <div class="field studio-only"><label>frame range (blank = whole clip)</label>
            <input type="text" id="st-range" placeholder="e.g. 0:96" spellcheck="false">
          </div>
          <div class="field studio-only"><label>analysis height</label>
            <select id="st-height"><option>540</option><option selected>720</option></select>
          </div>
          <button class="btn primary" id="st-run" disabled>Propagate through the shot</button>
          <div class="hint">SAM 2.1 follows your clicks both directions; ~2 fps at 720p —
            the queue shows honest progress</div>
          <div class="prog"><i id="st-bar"></i></div>
          <div class="progmsg" id="st-msg"></div>
        </div>

        <div class="insp-sec" id="st-exportsec" style="display:none">
          <span class="tag">export matte</span>
          <div class="field studio-only"><label>grow/shrink (px)</label>
            <input type="text" id="st-grow" value="0" spellcheck="false"></div>
          <div class="field studio-only"><label>feather (px sigma)</label>
            <input type="text" id="st-feather" value="1.5" spellcheck="false"></div>
          <div class="field studio-only"><label>despeckle (min px)</label>
            <input type="text" id="st-despeckle" value="64" spellcheck="false"></div>
          <div class="checkrow studio-only"><input type="checkbox" id="st-temporal" checked>
            <span>3-frame temporal majority</span></div>
          <button class="btn primary" id="st-rgba">Export ProRes 4444 + alpha</button>
          <button class="btn" id="st-luma">Export luma matte</button>
        </div>

        <div class="report" id="st-report"></div>
      </div>
    </div>
  </div>`;

  const ST = { clip: null, prompts: [], result: null, tint: true, onion: false,
               maskCache: new Map(), runtime: null };
  let viewer, strip;

  const range = () => {
    const m = $("#st-range", el).value.trim().match(/^(\d+)\s*:\s*(\d+)$/);
    if (m) return [Math.max(0, +m[1]), Math.min(ST.clip.nFrames, +m[2])];
    return [0, ST.clip.nFrames];
  };

  /* ---------- masks ----------
     A decoded 720p mask is ~3.7 MB and its alpha canvas another ~3.7 MB, so
     these two caches are held to the scrub window around the playhead rather
     than the whole propagation, and evicted canvases hand their backing store
     back (a.width = 0) instead of waiting for the GC. Re-fetching is cheap:
     the masks are PNGs on disk one hop away. */
  const MASK_WINDOW = 24, ALPHA_WINDOW = 12;

  function maskImg(i) {
    if (!ST.result) return null;
    const rel = i - ST.result.start;
    if (rel < 0 || rel >= ST.result.frames) return null;
    let e = ST.maskCache.get(rel);
    if (e) return e.ok ? e.img : null;
    e = { img: new Image(), ok: false };
    e.img.onload = () => { e.ok = true; viewer.draw(); };
    e.img.src = `/api/stencil/mask?path=${encodeURIComponent(ST.clip.path)}` +
      `&start=${ST.result.start}&end=${ST.result.end}&i=${rel}` +
      `&tag=${encodeURIComponent(ST.result.tag)}`;
    ST.maskCache.set(rel, e);
    for (const [k, v] of ST.maskCache)
      if (Math.abs(k - rel) > MASK_WINDOW) { v.img.src = ""; ST.maskCache.delete(k); }
    return null;
  }

  /* tint the grayscale mask plum via an offscreen canvas */
  function tinted(img, color, alpha) {
    const off = tinted._off || (tinted._off = document.createElement("canvas"));
    off.width = img.width; off.height = img.height;
    const og = off.getContext("2d");
    og.clearRect(0, 0, off.width, off.height);
    og.drawImage(img, 0, 0);
    og.globalCompositeOperation = "source-in";
    og.fillStyle = color;
    og.fillRect(0, 0, off.width, off.height);
    og.globalCompositeOperation = "source-over";
    return off;
  }

  /* the mask PNG is white-on-black, not alpha — build alpha via luminance */
  function maskToAlpha(img) {
    const off = document.createElement("canvas");
    off.width = img.width; off.height = img.height;
    const og = off.getContext("2d");
    og.drawImage(img, 0, 0);
    const d = og.getImageData(0, 0, off.width, off.height);
    for (let p = 0; p < d.data.length; p += 4) {
      d.data[p + 3] = d.data[p];       // alpha = luminance
    }
    og.putImageData(d, 0, 0);
    return off;
  }

  const alphaCache = new Map();
  function alphaMask(i) {
    const img = maskImg(i);
    if (!img) return null;
    let a = alphaCache.get(i);
    if (!a) {
      a = maskToAlpha(img);
      alphaCache.set(i, a);
      for (const [k, c] of alphaCache)
        if (Math.abs(k - i) > ALPHA_WINDOW) { c.width = c.height = 0; alphaCache.delete(k); }
    }
    return a;
  }

  function dropMasks() {
    for (const e of ST.maskCache.values()) e.img.src = "";
    for (const c of alphaCache.values()) c.width = c.height = 0;
    ST.maskCache.clear(); alphaCache.clear();
  }

  /* ---------- click preview: the mask, the moment you ask ---------- */
  let previewSeq = 0;
  async function clickPreview(frame) {
    const pts = ST.prompts.filter(p => p.frame === frame);
    if (!pts.length || !ST.clip) return;
    const seq = ++previewSeq;
    try {
      const r = await api("/api/stencil/click-preview", {
        path: ST.clip.path, frame,
        points: pts.map(p => ({ x: p.x, y: p.y, label: p.label })) });
      if (seq !== previewSeq) return;      // a newer click superseded this one
      const img = new Image();
      img.onload = () => {
        if (seq !== previewSeq) return;
        ST.preview = { frame, img, alpha: maskToAlpha(img), conf: r.conf };
        viewer.draw();
      };
      img.src = "data:image/png;base64," + r.png;
    } catch (e) { toast(e.message, true); }
  }

  /* ---------- overlay ---------- */
  function overlay(g, v) {
    if (ST.preview && ST.preview.frame === v.frame && ST.tint
        && !(ST.result && alphaMask(v.frame))) {
      g.save();
      g.globalAlpha = 0.5;
      g.drawImage(tinted(ST.preview.alpha, "#8E6B9E", 0.5),
                  v.x, v.y, v.iw * v.scale, v.ih * v.scale);
      g.restore();
    }
    if (ST.result && ST.tint) {
      const a = alphaMask(v.frame);
      if (a) {
        g.save();
        g.globalAlpha = 0.5;
        const off = tinted(a, "#8E6B9E", 0.5);
        g.drawImage(off, v.x, v.y, v.iw * v.scale, v.ih * v.scale);
        g.restore();
      }
    }
    if (ST.result && ST.onion) {
      const a = alphaMask(v.frame - 1);
      if (a) {
        g.save();
        g.globalAlpha = 0.28;
        g.drawImage(tinted(a, "#C4694F", 0.3), v.x, v.y, v.iw * v.scale, v.ih * v.scale);
        g.restore();
      }
    }
    /* prompt points on their frame */
    ST.prompts.forEach(p => {
      if (p.frame !== v.frame) return;
      const px = v.x + p.x * v.iw * v.scale;
      const py = v.y + p.y * v.ih * v.scale;
      g.lineWidth = 2 * devicePixelRatio;
      if (p.label === 1) {
        g.fillStyle = "#8E6B9E";
        g.beginPath(); g.arc(px, py, 5.5 * devicePixelRatio, 0, 7); g.fill();
        g.strokeStyle = "#F5F3EE"; g.stroke();
      } else {
        g.strokeStyle = "#C4694F";
        g.beginPath(); g.arc(px, py, 6 * devicePixelRatio, 0, 7); g.stroke();
        g.beginPath();
        g.moveTo(px - 4 * devicePixelRatio, py); g.lineTo(px + 4 * devicePixelRatio, py);
        g.stroke();
      }
    });
  }

  /* ---------- scopes ---------- */
  function drawConf() {
    const c = $("#st-conf", el), g = c.getContext("2d");
    g.fillStyle = "#0D0D12"; g.fillRect(0, 0, c.width, c.height);
    g.font = "9.5px SF Mono, monospace";
    if (!ST.result) {
      g.fillStyle = "#7E7D75";
      g.fillText("propagate to see per-frame confidence", 10, 42);
      $("#st-confval", el).textContent = "";
      return;
    }
    const conf = ST.result.confidence, n = conf.length;
    /* 0.85 threshold line */
    const ty = c.height - 6 - 0.85 * (c.height - 16);
    g.strokeStyle = "#33333F"; g.setLineDash([3, 3]);
    g.beginPath(); g.moveTo(0, ty); g.lineTo(c.width, ty); g.stroke();
    g.setLineDash([]);
    conf.forEach((v, i) => {
      const x = i / Math.max(1, n - 1) * c.width;
      const h = v * (c.height - 16);
      g.fillStyle = v < 0.85 ? "#C4694F" : "#8E6B9E";
      g.fillRect(x, c.height - 6 - h, Math.max(1, c.width / n - 0.5), h);
    });
    /* playhead */
    const rel = viewer.i - ST.result.start;
    if (rel >= 0 && rel < n) {
      g.fillStyle = "#F5F3EE";
      g.fillRect(rel / Math.max(1, n - 1) * c.width - 1, 0, 2, c.height);
    }
    $("#st-confval", el).textContent = ST.result.note;
  }

  function drawCov() {
    const c = $("#st-cov", el), g = c.getContext("2d");
    g.fillStyle = "#0D0D12"; g.fillRect(0, 0, c.width, c.height);
    g.font = "9.5px SF Mono, monospace";
    if (!ST.result) { g.fillStyle = "#7E7D75"; g.fillText("—", 10, 42); return; }
    const rel = Math.max(0, Math.min(viewer.i - ST.result.start, ST.result.coverage.length - 1));
    const cov = ST.result.coverage[rel] || 0;
    g.fillStyle = "#B9B7AC";
    g.fillText("this frame", 10, 22);
    g.fillStyle = "#E5A835";
    g.font = "17px SF Mono, monospace";
    g.fillText(`${(cov * 100).toFixed(1)}%`, 10, 48);
    g.font = "9.5px SF Mono, monospace";
    g.fillStyle = "#7E7D75";
    g.fillText("of frame matted", 10, 64);
  }

  /* ---------- actions ---------- */
  async function open(path) {
    try {
      const r = await api("/api/media/open", { path, tool: "stencil" });
      if (!r.video) { toast("no video stream in that file", true); return; }
      ST.clip = { path: r.path, nFrames: r.video.n_frames_estimate || 1,
                  fps: r.video.fps, w: r.video.width, h: r.video.height };
      $("#st-path", el).value = r.path;
      $("#st-meta", el).innerHTML =
        `<b>${esc(r.name)}</b> · ${r.video.width}×${r.video.height} @ ${r.video.fps.toFixed(2)}`;
      ST.prompts = []; ST.result = null;
      dropMasks();
      viewer.setClip(ST.clip);
      strip.setClip(viewer.clip);
      $("#st-run", el).disabled = !(ST.runtime && ST.runtime.available);
      $("#st-exportsec", el).style.display = "none";
      updatePromptCount(); drawConf(); drawCov();
    } catch (e) { toast(e.message, true); }
  }

  function updatePromptCount() {
    const pos = ST.prompts.filter(p => p.label === 1).length;
    const neg = ST.prompts.length - pos;
    $("#st-promptcount", el).textContent =
      ST.prompts.length ? `${pos} include · ${neg} exclude` : "";
  }

  async function propagate() {
    const [s, e] = range();
    const btn = $("#st-run", el);
    btn.disabled = true;
    $("#st-bar", el).style.width = "5%";
    try {
      const job = await api("/api/stencil/propagate", {
        path: ST.clip.path, start: s, end: e,
        prompts: ST.prompts,
        height: +$("#st-height", el).value,
      });
      watchJob(job.id, j => {
        $("#st-msg", el).textContent = j.status === "queued" ? "queued" : (j.message || j.status);
        $("#st-bar", el).style.width = j.status === "running" ? "50%" : "5%";
      });
      const done = await jobDone(job.id);
      btn.disabled = false;
      $("#st-bar", el).style.width = done.status === "done" ? "100%" : "0%";
      if (done.status === "error") { $("#st-msg", el).textContent = done.error; $("#st-msg", el).classList.add("err"); return; }
      if (done.status === "cancelled") { $("#st-msg", el).textContent = "cancelled"; return; }
      $("#st-msg", el).classList.remove("err");
      ST.result = done.result;
      dropMasks();
      $("#st-exportsec", el).style.display = "";
      $("#st-msg", el).textContent = done.result.note;
      drawConf(); drawCov(); viewer.draw();
      if (done.result.low_confidence.length)
        toast(`low confidence at frames ${done.result.low_confidence.slice(0, 5).join(", ")}${done.result.low_count > 5 ? "…" : ""} — scrub those`, true);
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  async function exportMatte(kind) {
    if (!ST.result) { toast("propagate first — there's nothing to export", true); return; }
    const [s, e] = [ST.result.start, ST.result.end];
    try {
      const job = await api("/api/stencil/export", {
        path: ST.clip.path, start: s, end: e, kind, tag: ST.result.tag,
        post: {
          grow: parseInt($("#st-grow", el).value) || 0,
          feather: parseFloat($("#st-feather", el).value) || 0,
          despeckle: parseInt($("#st-despeckle", el).value) || 0,
          temporal: $("#st-temporal", el).checked,
        },
      });
      watchJob(job.id, j => { $("#st-msg", el).textContent = j.message || j.status; });
      const done = await jobDone(job.id);
      if (done.status === "error") { toast(done.error, true); return; }
      if (done.status !== "done") return;
      const r = done.result;
      const rep = $("#st-report", el);
      rep.classList.add("show");
      rep.innerHTML += `<b>→</b> ${esc(r.out)}\n   ${r.frames} frames · ${r.kind} · feather ${r.post.feather}px${r.post.temporal ? " · temporal majority" : ""}\n   ${esc(r.note)}\n`;
      $("#st-msg", el).textContent = "matte exported";
    } catch (e) { toast(e.message, true); }
  }

  /* ---------- wire up ---------- */
  function init() {
    viewer = new Viewer($("#st-viewer", el), { h: 540 });
    viewer.onOpen = p => open(p);
    viewer.overlay = overlay;
    viewer.onFrame = () => { strip.setFrame(viewer.i); drawConf(); drawCov(); };
    strip = new Filmstrip($("#st-strip", el), i => { viewer.stop(); viewer.show(i); });

    $("#st-viewer", el).addEventListener("click", e => {
      if (!ST.clip) return;
      const v = viewer.view(); if (!v) return;
      const rect = $("#st-viewer", el).getBoundingClientRect();
      const nx = ((e.clientX - rect.left) * devicePixelRatio - v.x) / (v.iw * v.scale);
      const ny = ((e.clientY - rect.top) * devicePixelRatio - v.y) / (v.ih * v.scale);
      if (nx < 0 || nx > 1 || ny < 0 || ny > 1) return;
      ST.prompts.push({ frame: viewer.i, x: nx, y: ny, label: e.altKey ? 0 : 1 });
      updatePromptCount();
      viewer.draw();
      clickPreview(viewer.i);
    });
    $("#st-clear", el).onclick = () => {
      ST.prompts = []; ST.preview = null;
      updatePromptCount(); viewer.draw();
    };
    $("#st-tint", el).onclick = e => { ST.tint = !ST.tint; e.target.classList.toggle("on", ST.tint); viewer.draw(); };
    $("#st-onion", el).onclick = e => { ST.onion = !ST.onion; e.target.classList.toggle("on", ST.onion); viewer.draw(); };
    $("#st-open", el).onclick = () => { const p = $("#st-path", el).value.trim(); if (p) open(p); };
    $("#st-path", el).addEventListener("keydown", e => { if (e.key === "Enter") $("#st-open", el).click(); });
    $("#st-browse", el).onclick = async () => {
      try {
        const r = await api("/api/dialog/open-file", {});
        if (r.paths && r.paths[0]) open(r.paths[0]);
      } catch (e) { toast(e.message, true); }
    };
    $("#st-run", el).onclick = propagate;
    $("#st-rgba", el).onclick = () => exportMatte("rgba");
    $("#st-luma", el).onclick = () => exportMatte("luma");

    const insp = $("#st-insp", el);
    const dens = $$(".density button", insp);
    function applyDensity(d) {
      insp.classList.toggle("studio", d === "studio");
      dens.forEach(b => b.classList.toggle("on", b.dataset.d === d));
    }
    dens.forEach(b => b.onclick = () => { applyDensity(b.dataset.d); setDensity("stencil", b.dataset.d); });
    applyDensity(density("stencil"));

    api("/api/stencil/status").then(st => {
      ST.runtime = st;
      const warn = $("#st-runtimewarn", el);
      if (!st.available) {
        warn.style.display = "";
        $("#st-runtimehint", el).textContent = st.hint;
      } else if (st.hint) {
        warn.style.display = "";
        $("#st-runtimehint", el).textContent = st.hint;
        $("#st-run", el).disabled = !ST.clip;
      } else {
        $("#st-run", el).disabled = !ST.clip;
      }
    }).catch(() => {});
  }

  let inited = false;
  function onshow(arg) {
    if (!inited) { init(); inited = true; }
    Viewer.active = viewer;
    if (arg && arg.openPath) open(arg.openPath);
    if (viewer) viewer.resize();
  }

  registerPage("stencil", el, onshow);
  return { onshow };
})();
