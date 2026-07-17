/* The shared viewer: one vocabulary for every tool (specs/08 §1.3).
   Zoom/pan, A/B wipe, canvas overlays, JKL + arrows, filmstrip, scopes. */

class Viewer {
  constructor(wrap, opts = {}) {
    this.wrap = wrap;
    this.h = opts.h || 540;            // frame height requested from the server
    this.clip = null;                  // {path, nFrames, fps, w, h}
    this.i = 0;
    this.zoomMode = "fit";             // "fit" | number (canvas px per image px)
    this.pan = { x: 0, y: 0 };
    this.playing = 0;                  // 0 stop, +1 fwd, -1 rev
    this.wipe = null;                  // 0..1 when A/B active
    this.bSource = null;               // i -> url for the B side
    this.overlay = null;               // (g, view) => {}
    this.onFrame = null;               // page hook
    this.cache = new Map();            // i -> {img, ok}
    this.cacheB = new Map();
    this._raf = null;
    this._lastTick = 0;

    this.onOpen = opts.onOpen || null;   // page hook: (path) => open it

    wrap.classList.add("viewer-wrap");
    wrap.innerHTML = `
      <canvas></canvas>
      <div class="viewer-empty"><div class="big">no clip open</div>
        <div>drag a clip here — or</div>
        <button class="browse-btn">Browse…</button></div>
      <div class="viewer-hud" style="display:none"></div>
      <div class="viewer-ctl" style="display:none">
        <button data-z="fit" class="on" title="fit to window (F)">fit</button>
        <button data-z="1" title="pixel-for-pixel (1)">100%</button>
      </div>`;
    this.canvas = $("canvas", wrap);
    this.hud = $(".viewer-hud", wrap);
    this.ctl = $(".viewer-ctl", wrap);
    this.empty = $(".viewer-empty", wrap);
    this.g = this.canvas.getContext("2d");

    $$("button", this.ctl).forEach(b => b.onclick = () => this.setZoom(b.dataset.z));
    new ResizeObserver(() => this.resize()).observe(wrap);

    wrap.addEventListener("wheel", e => this._wheel(e), { passive: false });
    wrap.addEventListener("mousedown", e => this._down(e));
    wrap.addEventListener("dblclick", () => this.setZoom(this.zoomMode === "fit" ? "1" : "fit"));

    $(".browse-btn", wrap).onclick = e => { e.stopPropagation(); browseForPath(p => this._open(p)); };
    wireDropZone(wrap, p => this._open(p));
  }

  _open(path) {
    if (path && this.onOpen) this.onOpen(path);
    else if (path) toast("this page didn't wire its open handler", true);
  }

  setClip(clip) {
    this.clip = clip;
    this.i = 0;
    this.cache.clear(); this.cacheB.clear();
    this.stop();
    this.zoomMode = "fit"; this.pan = { x: 0, y: 0 };
    this.empty.style.display = clip ? "none" : "flex";
    this.hud.style.display = clip ? "flex" : "none";
    this.ctl.style.display = clip ? "flex" : "none";
    if (clip) this.show(0);
  }

  /* ---------- frames ---------- */
  _get(i, side) {
    const cache = side === "b" ? this.cacheB : this.cache;
    let e = cache.get(i);
    if (e) return e;
    const url = side === "b" ? this.bSource(i) : frameURL(this.clip.path, i, this.h);
    if (!url) return null;
    e = { img: new Image(), ok: false, err: false };
    e.img.onload = () => { e.ok = true; if (i === this.i) this.draw(); };
    e.img.onerror = () => {
      e.err = true;
      // past the honest end of the clip: nb_frames metadata can overstate
      if (side !== "b" && i > 0 && i <= this.i && this.clip) {
        this.clip.nFrames = Math.min(this.clip.nFrames, i);
        if (this.i >= this.clip.nFrames) this.show(this.clip.nFrames - 1);
      }
    };
    e.img.src = url;
    cache.set(i, e);
    if (cache.size > 160) cache.delete(cache.keys().next().value);
    return e;
  }

  show(i) {
    if (!this.clip) return;
    this.i = Math.max(0, Math.min(i, this.clip.nFrames - 1));
    this._get(this.i);
    for (let k = 1; k <= 6; k++) {
      if (this.i + k < this.clip.nFrames) this._get(this.i + k);
    }
    if (this.bSource) this._get(this.i, "b");
    this.draw();
    if (this.onFrame) this.onFrame(this.i);
  }

  /* ---------- playback ---------- */
  play(dir) {
    if (!this.clip) return;
    this.playing = dir;
    if (this._raf) cancelAnimationFrame(this._raf);
    const fps = Math.min(this.clip.fps || 24, 30);
    const step = ts => {
      if (!this.playing) return;
      if (ts - this._lastTick >= 1000 / fps) {
        const next = this.i + this.playing;
        const e = next >= 0 && next < this.clip.nFrames ? this._get(next) : null;
        if (!e) { this.stop(); return; }
        if (e.ok) { this._lastTick = ts; this.show(next); }
        else if (e.err) { this.stop(); return; }
        /* not loaded yet: hold this frame, try again next tick (never skip) */
      }
      this._raf = requestAnimationFrame(step);
    };
    this._raf = requestAnimationFrame(step);
  }
  stop() { this.playing = 0; if (this._raf) cancelAnimationFrame(this._raf); this._raf = null; }

  /* ---------- geometry ---------- */
  resize() {
    const r = this.wrap.getBoundingClientRect();
    this.canvas.width = Math.max(2, Math.round(r.width * devicePixelRatio));
    this.canvas.height = Math.max(2, Math.round(r.height * devicePixelRatio));
    this.draw();
  }

  view() {
    /* mapping from preview-image pixels to canvas pixels.
       zoomMode as a number = screen px per preview px (1 → "100%", of the
       preview stream — the HUD says so; native-pixel loupe is a v0.2 item) */
    const e = this.cache.get(this.i);
    if (!e || !e.ok) return null;
    const iw = e.img.width, ih = e.img.height;
    const cw = this.canvas.width, ch = this.canvas.height;
    const scale = this.zoomMode === "fit"
      ? Math.min(cw / iw, ch / ih)
      : Number(this.zoomMode) * devicePixelRatio;
    const x = cw / 2 - iw * scale / 2 + this.pan.x;
    const y = ch / 2 - ih * scale / 2 + this.pan.y;
    return { x, y, scale, iw, ih, img: e.img };
  }

  setZoom(z) {
    this.zoomMode = z === "fit" ? "fit" : Number(z);
    if (z === "fit") this.pan = { x: 0, y: 0 };
    $$("button", this.ctl).forEach(b => b.classList.toggle("on", b.dataset.z == z));
    this.draw();
  }

  _wheel(e) {
    if (!this.clip) return;
    e.preventDefault();
    const v = this.view(); if (!v) return;
    const cur = v.scale;
    const ns = Math.min(cur * Math.exp(-e.deltaY * 0.002), 8 * devicePixelRatio);
    const fitScale = Math.min(this.canvas.width / v.iw, this.canvas.height / v.ih);
    if (ns <= fitScale * 1.02) { this.setZoom("fit"); return; }
    /* keep the image point under the cursor fixed */
    const rect = this.wrap.getBoundingClientRect();
    const mx = (e.clientX - rect.left) * devicePixelRatio;
    const my = (e.clientY - rect.top) * devicePixelRatio;
    const ix = (mx - v.x) / v.scale, iy = (my - v.y) / v.scale;
    this.zoomMode = ns / devicePixelRatio;
    const nx = this.canvas.width / 2 - v.iw * ns / 2, ny = this.canvas.height / 2 - v.ih * ns / 2;
    this.pan.x = mx - ix * ns - nx;
    this.pan.y = my - iy * ns - ny;
    $$("button", this.ctl).forEach(b => b.classList.remove("on"));
    this.draw();
  }

  _down(e) {
    if (!this.clip) return;
    const rect = this.wrap.getBoundingClientRect();
    const cw = rect.width;
    /* wipe handle drag when A/B is on */
    if (this.wipe != null && Math.abs(e.clientX - rect.left - this.wipe * cw) < 10) {
      const move = ev => { this.wipe = Math.max(0.02, Math.min(0.98, (ev.clientX - rect.left) / cw)); this.draw(); };
      const up = () => { removeEventListener("mousemove", move); removeEventListener("mouseup", up); };
      addEventListener("mousemove", move); addEventListener("mouseup", up);
      return;
    }
    if (this.zoomMode === "fit") return;
    const sx = e.clientX, sy = e.clientY, px = this.pan.x, py = this.pan.y;
    const move = ev => {
      this.pan.x = px + (ev.clientX - sx) * devicePixelRatio;
      this.pan.y = py + (ev.clientY - sy) * devicePixelRatio;
      this.draw();
    };
    const up = () => { removeEventListener("mousemove", move); removeEventListener("mouseup", up); };
    addEventListener("mousemove", move); addEventListener("mouseup", up);
  }

  /* ---------- draw ---------- */
  draw() {
    const g = this.g;
    g.clearRect(0, 0, this.canvas.width, this.canvas.height);
    const v = this.view();
    if (!v) return;
    g.imageSmoothingEnabled = v.scale < 2;
    g.drawImage(v.img, v.x, v.y, v.iw * v.scale, v.ih * v.scale);

    /* B side (A/B wipe) */
    if (this.wipe != null && this.bSource) {
      const eb = this.cacheB.get(this.i);
      const wx = this.wipe * this.canvas.width;
      if (eb && eb.ok) {
        g.save();
        g.beginPath(); g.rect(wx, 0, this.canvas.width - wx, this.canvas.height); g.clip();
        g.drawImage(eb.img, v.x, v.y, v.iw * v.scale, v.ih * v.scale);
        g.restore();
      }
      g.fillStyle = "#F5F3EE"; g.fillRect(wx - 1, 0, 2, this.canvas.height);
      g.beginPath(); g.arc(wx, this.canvas.height / 2, 7, 0, 7); g.fill();
    }

    if (this.overlay) { g.save(); this.overlay(g, { ...v, frame: this.i, canvas: this.canvas }); g.restore(); }
    this._hud();
  }

  _hud() {
    if (!this.clip) return;
    const z = this.zoomMode === "fit" ? "fit"
      : Math.round(this.zoomMode * 100) + "% preview";
    const t = this.clip.fps ? (this.i / this.clip.fps) : null;
    this.hud.innerHTML =
      `<span>frame <b>${this.i}</b>/${this.clip.nFrames - 1}</span>` +
      (t != null ? `<span><b>${fmtTime(t)}</b></span>` : "") +
      `<span>zoom <b>${z}</b></span>` +
      (this.wipe != null ? `<span>A|B wipe</span>` : "");
  }

  /* current frame pixels for the scopes (small, cheap) */
  frameData(w = 192) {
    const e = this.cache.get(this.i);
    if (!e || !e.ok) return null;
    const h = Math.max(2, Math.round(w * e.img.height / e.img.width));
    const off = Viewer._off || (Viewer._off = document.createElement("canvas"));
    off.width = w; off.height = h;
    const og = off.getContext("2d", { willReadFrequently: true });
    og.drawImage(e.img, 0, 0, w, h);
    return og.getImageData(0, 0, w, h);
  }

  /* keyboard: pages call this from a global handler when they're current */
  key(e) {
    if (!this.clip) return false;
    const k = e.key.toLowerCase();
    if (k === "l") { this.play(1); return true; }
    if (k === "j") { this.play(-1); return true; }
    if (k === "k" || k === " ") { this.playing ? this.stop() : this.play(1); return true; }
    if (k === "f") { this.setZoom("fit"); return true; }
    if (k === "1") { this.setZoom("1"); return true; }
    if (e.key === "ArrowRight") { this.stop(); this.show(this.i + (e.shiftKey ? 10 : 1)); return true; }
    if (e.key === "ArrowLeft") { this.stop(); this.show(this.i - (e.shiftKey ? 10 : 1)); return true; }
    if (e.key === "Home") { this.stop(); this.show(0); return true; }
    if (e.key === "End") { this.stop(); this.show(this.clip.nFrames - 1); return true; }
    return false;
  }
}

/* ---------- filmstrip ---------- */
class Filmstrip {
  constructor(el, onSeek) {
    this.el = el; this.onSeek = onSeek;
    el.classList.add("filmstrip");
    el.innerHTML = "<canvas></canvas>";
    this.canvas = $("canvas", el);
    this.g = this.canvas.getContext("2d");
    this.clip = null; this.thumbs = []; this.i = 0; this.marks = [];
    new ResizeObserver(() => this.draw()).observe(el);
    const seek = e => {
      if (!this.clip) return;
      const r = el.getBoundingClientRect();
      const f = Math.round((e.clientX - r.left) / r.width * this._span());
      this.onSeek(Math.max(0, Math.min(this.clip.nFrames - 1, f)));
    };
    el.addEventListener("mousedown", e => {
      seek(e);
      const move = ev => seek(ev);
      const up = () => { removeEventListener("mousemove", move); removeEventListener("mouseup", up); };
      addEventListener("mousemove", move); addEventListener("mouseup", up);
    });
  }

  /* frames the strip spans; a 1-frame clip still has a whole strip to draw in */
  _span() { return Math.max(1, this.clip.nFrames - 1); }

  setClip(clip) {
    this.clip = clip; this.thumbs = []; this.i = 0; this.marks = [];
    if (!clip) { this.draw(); return; }
    /* landscape-ish cells: fill the width without slicing faces into slivers */
    const w = this.el.getBoundingClientRect().width || 1100;
    const h = this.el.getBoundingClientRect().height || 62;
    const n = clip.nFrames > 1
      ? Math.max(8, Math.min(40, Math.round(w / (h * 1.55))))
      : 1;   // one frame, one cell — not 40 requests for the same thumbnail
    for (let k = 0; k < n; k++) {
      const fi = n > 1 ? Math.round(k / (n - 1) * (clip.nFrames - 1)) : 0;
      const img = new Image();
      const t = { img, ok: false, fi };
      img.onload = () => { t.ok = true; this.draw(); };
      img.src = frameURL(clip.path, fi, 54);
      this.thumbs.push(t);
    }
    this.draw();
  }

  setFrame(i) { this.i = i; this.draw(); }
  setMarks(marks) { this.marks = marks || []; this.draw(); }  // frame indices (cuts)

  draw() {
    const r = this.el.getBoundingClientRect();
    this.canvas.width = r.width * devicePixelRatio;
    this.canvas.height = r.height * devicePixelRatio;
    const g = this.g, W = this.canvas.width, H = this.canvas.height;
    g.fillStyle = "#0D0D12"; g.fillRect(0, 0, W, H);
    if (!this.clip) return;
    const n = this.thumbs.length;
    const tw = W / n;
    this.thumbs.forEach((t, k) => {
      if (t.ok) {
        const s = Math.max(tw / t.img.width, H / t.img.height);
        const dw = t.img.width * s, dh = t.img.height * s;
        g.save();
        g.beginPath(); g.rect(k * tw, 0, tw, H); g.clip();
        g.drawImage(t.img, k * tw + (tw - dw) / 2, (H - dh) / 2, dw, dh);
        g.restore();
      }
    });
    g.fillStyle = "rgba(25,25,33,.55)";
    this.marks.forEach(m => {
      const x = m / this._span() * W;
      g.fillRect(x - 1, 0, 2, H);
    });
    const x = this.i / this._span() * W;
    g.fillStyle = "#F5F3EE"; g.fillRect(x - 1.2, 0, 2.4, H);
  }
}

/* ---------- shared scopes: histogram + waveform (covenant: on by default) ---------- */
function drawHistogram(canvas, data) {
  const g = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  g.fillStyle = "#0D0D12"; g.fillRect(0, 0, W, H);
  if (!data) return;
  const bins = new Float32Array(64);
  const d = data.data;
  for (let p = 0; p < d.length; p += 4) {
    const y = 0.2126 * d[p] + 0.7152 * d[p + 1] + 0.0722 * d[p + 2];
    bins[Math.min(63, y / 4 | 0)]++;
  }
  const max = Math.max(...bins, 1);
  g.fillStyle = "#E5A835";
  const bw = W / 64;
  for (let b = 0; b < 64; b++) {
    const h = Math.pow(bins[b] / max, 0.5) * (H - 4);
    g.fillRect(b * bw + 0.5, H - h, bw - 1, h);
  }
}

function drawWaveform(canvas, data) {
  const g = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  g.fillStyle = "#0D0D12"; g.fillRect(0, 0, W, H);
  if (!data) return;
  const d = data.data, dw = data.width, dh = data.height;
  g.globalAlpha = 0.35; g.fillStyle = "#E5A835";
  const colW = W / dw;
  for (let x = 0; x < dw; x++) {
    for (let y = 0; y < dh; y++) {
      const p = (y * dw + x) * 4;
      const lum = (0.2126 * d[p] + 0.7152 * d[p + 1] + 0.0722 * d[p + 2]) / 255;
      g.fillRect(x * colW, (1 - lum) * (H - 2), Math.max(1, colW - 0.4), 1.6);
    }
  }
  g.globalAlpha = 1;
}
