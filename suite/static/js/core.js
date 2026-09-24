/* core: state, api, websocket job events, router, session. No framework. */

const $ = (sel, root) => (root || document).querySelector(sel);
const $$ = (sel, root) => [...(root || document).querySelectorAll(sel)];

const CZ = {
  session: { recents: [], tools: {}, ui: { density: {} } },
  appInfo: null,
  jobs: new Map(),          // id -> job dict (live view of queue)
  jobWatchers: new Map(),   // id -> [fn]
  pages: {},                // name -> {el, onshow}
  current: null,
};

/* ---------- tools registry (accents + glyphs + one-liners) ----------
   group "cz" = the resolve workbench; group "community" = the two apps that
   grew up at BIG and moved in (Highlighter, Grabber) — same covenant, their
   own corner of the rail, square glyphs instead of diamonds. */
const TOOLS = [
  { id: "pivot",   name: "Pivot",   acc: "var(--pivot)",   ready: true,
    verb: "follows the subject", one: "9:16 / 1:1 from your 16:9 masters" },
  { id: "stencil", name: "Stencil", acc: "var(--stencil)", ready: true,
    verb: "cuts the stencil", one: "click an object, get a matte" },
  { id: "scribe",  name: "Scribe",  acc: "var(--scribe)",  ready: true,
    verb: "writes it all down", one: "transcripts, captions, text-based cuts" },
  { id: "clear",   name: "Clear",   acc: "var(--clear)",   ready: true,
    verb: "rescues the take", one: "de-hum, de-click, voice isolation" },
  { id: "rise",    name: "Rise",    acc: "var(--rise)",    ready: true,
    verb: "restores the detail", one: "SD→HD/4K for archives and punch-ins" },
  { id: "depth",   name: "Depth",   acc: "var(--depth)",   ready: true,
    verb: "maps the scene", one: "depth mattes + fog/rack-focus templates" },
  { id: "index",   name: "Index",   acc: "var(--index)",   ready: true,
    verb: "knows where everything is", one: "your footage, searchable in plain words" },
  { id: "slate",   name: "Slate",   acc: "var(--slate)",   ready: true,
    verb: "makes it official", one: "lower thirds, slates, bars, countdowns" },
  /* the community rail reads in the order a meeting travels (the wire):
     fetch it → find the moments → kit it → keep it → carry it across */
  { id: "grabber", name: "Grabber", acc: "var(--grabber)",
    ready: true, group: "community", long: "Video Grabber",
    verb: "brings the meeting home", one: "search, fetch, conform civic recordings" },
  { id: "highlighter", name: "Highlighter", acc: "var(--highlighter)",
    ready: true, group: "community", long: "Community Highlighter",
    verb: "finds the moments", one: "meeting video → highlight reel, in text" },
  /* the Library page (id "kb") retired in 1.7.1 — its cross-meeting
     analytics live inside Highlighter's analyzer and Memory's Analytics
     view now (analytics.js), and its montage tray became czTray. The
     /api/kb/* engine still serves them all. */
  /* the community wing grows (specs/12): four more BIG apps moving in.
     Lane ownership + who flips `ready` is law in specs/PARALLEL.md. */
  { id: "publisher", name: "Publisher", acc: "var(--publisher)",
    ready: true, when: "1.6", group: "community", long: "Community Publisher",
    verb: "gets it seen", one: "program in → clips, copy and posts out" },
  { id: "memory", name: "Memory", acc: "var(--memory)",
    ready: true, group: "community", long: "Community Memory",
    verb: "keeps the record", one: "issues tracked across meetings and years" },
  { id: "interpreter", name: "Interpreter", acc: "var(--interpreter)",
    ready: true, when: "1.7", group: "community", long: "Community Interpreter",
    verb: "carries it across", one: "captions in seven languages + simple english" },
  { id: "narrator", name: "Narrator", acc: "var(--narrator)",
    ready: true, when: "1.7", group: "community", long: "Community Narrator",
    verb: "says what's on screen", one: "audio description for community TV" },
];
const toolById = id => TOOLS.find(t => t.id === id);

/* diamond glyph for the workbench (the site's node motif); the community
   pair reads square — same wire, different shape, deliberately */
function glyphSVG(acc, ready, square) {
  const common = `stroke="${acc}" stroke-width="1.6" fill="${ready ? acc : "none"}"
      fill-opacity="${ready ? .28 : 0}"`;
  if (square) {
    return `<svg viewBox="0 0 20 20" fill="none">
      <rect x="3.6" y="3.6" width="12.8" height="12.8" rx="2.6" ${common}/></svg>`;
  }
  return `<svg viewBox="0 0 20 20" fill="none">
    <rect x="10" y="2.8" width="10.2" height="10.2" rx="2.4"
      transform="rotate(45 10 2.8)" ${common}/></svg>`;
}

/* ---------- api ---------- */
/* A route that needs an AI key answers {need:"llm_key", feature, alt}
   (suite/tools/keyneed.py). Instead of a dead-end error, the add-a-key
   popup opens right there; save a key and the same request goes out once
   more, so the click that asked for it simply works. */
async function api(path, body, _retried) {
  const opts = body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
  const r = await fetch(path, opts);
  let data = null;
  try { data = await r.json(); } catch (e) { /* non-JSON error body */ }
  if (!r.ok) {
    if (data && data.need === "llm_key" && !_retried && window.czKeyModal) {
      const saved = await czKeyModal({ feature: data.feature, alt: data.alt });
      if (saved) return api(path, body, true);
    }
    const msg = (data && data.error) ? data.error : `${r.status} ${r.statusText}`;
    const err = new Error(msg);
    if (data && data.need) err.need = data.need;
    throw err;
  }
  return data;
}

function toast(msg, isErr) {
  $$(".toast").forEach(t => t.remove());
  const t = document.createElement("div");
  t.className = "toast" + (isErr ? " err" : "");
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), isErr ? 6000 : 3200);
}

/* ---------- job events ---------- */
function applyJob(job) {
  CZ.jobs.set(job.id, job);
  /* copy: a watcher is allowed to unregister itself from inside the call */
  (CZ.jobWatchers.get(job.id) || []).slice().forEach(fn => { try { fn(job); } catch (e) {} });
  if (window.QueuePage) QueuePage.onJob(job);
  if (window.JobToasts) JobToasts.onJob(job);
}

/* returns an unregister function; callers that only want progress can ignore it */
function watchJob(id, fn) {
  if (!CZ.jobWatchers.has(id)) CZ.jobWatchers.set(id, []);
  const list = CZ.jobWatchers.get(id);
  list.push(fn);
  const off = () => {
    const k = list.indexOf(fn);
    if (k >= 0) list.splice(k, 1);
    if (!list.length) CZ.jobWatchers.delete(id);
  };
  const cur = CZ.jobs.get(id);
  if (cur) fn(cur);
  return off;
}

/* wait for a job to finish; progress via watcher */
const _keyAsked = new Set();
function jobDone(id) {
  return new Promise(resolve => {
    let off = null, settled = false;
    off = watchJob(id, job => {
      if (!["done", "error", "cancelled"].includes(job.status)) return;
      settled = true;
      if (off) off();
      // a job that ran into "no API key" mid-flight offers the popup too
      if (job.status === "error" && /no API key configured/i.test(job.error || "")
          && !_keyAsked.has(id) && window.czKeyModal) {
        _keyAsked.add(id);
        czKeyModal({ feature: job.label || "This step", retry: false });
      }
      resolve(job);
    });
    if (settled) off();   // already terminal: watchJob fired before off existed
  });
}

/* cancel any queued/running job — the ✕ on every progress card and toast */
async function cancelJob(id, btn) {
  const was = btn ? btn.textContent : "";
  if (btn) { btn.disabled = true; btn.textContent = was.length > 2 ? "cancelling…" : "…"; }
  try { await api(`/api/jobs/${id}/cancel`, {}); }
  catch (e) { toast(e.message, true); if (btn) { btn.disabled = false; btn.textContent = was; } }
}

let ws = null, wsRetry = 500;
function connectWS() {
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.type === "hello") m.jobs.forEach(applyJob);
    if (m.type === "job") applyJob(m.job);
  };
  ws.onopen = () => { wsRetry = 500; };
  ws.onclose = () => { setTimeout(connectWS, wsRetry); wsRetry = Math.min(wsRetry * 2, 8000); };
  ws.onerror = () => ws.close();
}
/* poll fallback keeps progress honest whenever the socket is down */
setInterval(async () => {
  if (ws && ws.readyState === 1) { try { ws.send("ping"); } catch (e) {} return; }
  try { (await api("/api/jobs")).forEach(applyJob); } catch (e) {}
}, 2000);

/* ---------- session ---------- */
async function loadSession() {
  try { CZ.session = await api("/api/session"); } catch (e) {}
}
/* mirrors sessions.py: 'tools' and 'ui' merge one level deeper; 'version' and
   'recents' belong to the server and are never patched from here */
async function patchSession(patch) {
  for (const [k, v] of Object.entries(patch)) {
    if ((k === "tools" || k === "ui") && v && typeof v === "object") {
      const cur = CZ.session[k] = CZ.session[k] || {};
      for (const [k2, v2] of Object.entries(v)) {
        if (v2 && typeof v2 === "object" && cur[k2] && typeof cur[k2] === "object") {
          Object.assign(cur[k2], v2);
        } else {
          cur[k2] = v2;
        }
      }
    } else if (k !== "version" && k !== "recents") {
      CZ.session[k] = v;
    }
  }
  try { await api("/api/session", patch); } catch (e) {}
}
function density(tool) { return (CZ.session.ui?.density || {})[tool] || "easy"; }
async function setDensity(tool, d) {
  await patchSession({ ui: { density: { [tool]: d } } });
}

/* ---------- router ---------- */
/* opts.reset: put the page back the way it opens — nothing loaded, no
   results, no half-typed fields. Files and sidecars on disk are never
   touched (a reset clears the VIEW, not the work). Pages with a reset get
   the same ↺ Reset button at the right end of their header bar. */
function registerPage(name, el, onshow, opts) {
  CZ.pages[name] = { el, onshow, reset: opts && opts.reset };
  $("#main").appendChild(el);
  if (opts && opts.reset) {
    const bar = $(".mediabar", el) || $(".cz-resetslot", el);
    if (bar) {
      const b = document.createElement("button");
      b.className = "reset-btn";
      b.type = "button";
      b.textContent = "↺ Reset";
      b.title = "clear this page back to a fresh start — nothing on disk is deleted";
      b.onclick = () => resetPage(name);
      bar.appendChild(b);
    }
  }
}
function resetPage(name) {
  const p = CZ.pages[name];
  if (!p || !p.reset) return;
  try { p.reset(); } catch (e) { console.error(e); }
  // any per-page inner scroller back to the top, too
  $$(".ws-center, .inspector, #hl-landing, #hl-loaded", p.el)
    .forEach(s => { try { s.scrollTop = 0; } catch (e) {} });
  p.el.scrollTop = 0;
  toast(`${(toolById(name) || {}).name || "Page"} reset — your files are untouched`);
}
function go(name, arg) {
  const page = CZ.pages[name];
  if (!page) return;
  Object.values(CZ.pages).forEach(p => p.el.classList.remove("active"));
  page.el.classList.add("active");
  CZ.current = name;
  $$(".rail-item").forEach(b => b.classList.toggle("active", b.dataset.page === name));
  if (page.onshow) page.onshow(arg);
}

/* ---------- one gesture, one road (nested-scroller taming) ----------
   A long inner box (a 7-hour transcript is 280k px of scroll) parked deep
   by follow-along used to eat every upward wheel that crossed it — the page
   "couldn't scroll back to the top". Now an inner scroller owns the wheel
   only after you step into it (any click/press inside); until then the
   gesture stays with the page's own scroller. Leaving the box hands the
   wheel back. Fixed overlays (modals, palette) keep native scrolling. */
(() => {
  let engaged = null, engagedId = "";
  const isEngaged = el =>
    el === engaged || (engagedId && el.id === engagedId);
  const innerScrollables = (t, stopAtPage) => {
    const out = [];
    for (let el = t; el; el = el.parentElement) {
      const isPage = el.classList && el.classList.contains("page");
      if (el.nodeType === 1 && el.scrollHeight > el.clientHeight + 4) {
        const oy = getComputedStyle(el).overflowY;
        if (oy === "auto" || oy === "scroll") out.push(el);
      }
      if (isPage && stopAtPage) break;
    }
    return out;
  };
  document.addEventListener("pointerdown", e => {
    const chain = innerScrollables(e.target, true);
    const page = e.target.closest && e.target.closest(".page");
    const next = chain.find(el => page && page.contains(el) && el !== page);
    if (next) {
      // a row click may re-render the box in place; remember its id so the
      // fresh node with the same name keeps the engagement
      engaged = next; engagedId = next.id || "";
      next.addEventListener("mouseleave", () => {
        engaged = null; engagedId = "";
      }, { once: true });
    }
  }, true);
  document.addEventListener("wheel", e => {
    if (!e.deltaY) return;
    const page = e.target.closest && e.target.closest(".page.active");
    if (!page) return;
    // anything fixed between here and the page is an overlay — native rules
    for (let el = e.target; el && el !== page; el = el.parentElement) {
      if (el.nodeType === 1 && getComputedStyle(el).position === "fixed") return;
    }
    const chain = innerScrollables(e.target, false)
      .filter(el => page.contains(el) || el === page);
    if (chain.length < 2) return;              // only the page scrolls: native
    const inner = chain[0], road = chain[chain.length - 1];
    if (inner === road || isEngaged(inner)) return;
    e.preventDefault();
    road.scrollTop += e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
  }, { passive: false, capture: true });
})();

/* ---------- Send to the Record (Community Memory) ----------
   The suite's hub gesture (specs/12 §2): Highlighter and Publisher both
   offer it. Until Memory lands (lane B, specs/PARALLEL.md), the button
   renders dashed and answers honestly; the moment memory's `ready` flips
   in TOOLS, the same button goes live against the contract route. */
function recordBtnHTML(id) {
  const m = toolById("memory");
  return `<button class="btn record-btn${m.ready ? "" : " soon"}" id="${id}"
    style="--acc:var(--memory);width:auto"
    title="${m.ready ? "file this program in the town's record"
    : `Community Memory is being built now — this button lights up in ${m.when}`}">
    ⬛ Send to the Record${m.ready ? "" : ` <span class="soon">${m.when}</span>`}</button>`;
}
async function sendToRecord(payload, btn) {
  // a URL session's "source" is a link, not a file — name it what it is, or
  // the record's ingest takes the local-file road and Scribe meets a URL
  if (payload && /^https?:\/\//i.test(payload.path || "")) {
    payload = { ...payload, url: payload.path };
    delete payload.path;
  }
  if (!toolById("memory").ready) {
    toast(`Community Memory joins in ${toolById("memory").when} — the record ` +
          `opens the day it lands`, true);
    return false;
  }
  if (btn) btn.disabled = true;
  try {
    const r = await api("/api/memory/submissions", payload);
    toast(r.status === "exists"
      ? "already in the record — linked, not duplicated"
      : "sent to the record — Memory is processing it");
    return true;
  } catch (e) {
    toast(`the record didn't take it — ${e.message}`, true);
    return false;
  } finally { if (btn) btn.disabled = false; }
}

/* ---------- czTray: one reel timeline for the whole suite ----------
   Moments picked ANYWHERE — the analyzer's grids, the record's search,
   an issue's beads — land on one persistent timeline that rides the
   bottom of every page. Pin it open with 📌 and it stays across pages
   and relaunches (localStorage). Render cuts one montage across every
   source on it via /api/kb/montage (span-smart: URL sessions fetch only
   the picked seconds). Any page adds a pick button with
   czTray.btnHTML({source,start,end,label,title}) — a delegated handler
   does the rest, no per-page wiring. */
const czTray = (() => {
  const KEY = "cz-tray-v1";
  let S = { items: [], pinned: false };
  try { S = { ...S, ...JSON.parse(localStorage.getItem(KEY) || "{}") }; }
  catch (e) { /* a torn write never breaks boot */ }
  const save = () => localStorage.setItem(KEY, JSON.stringify(S));

  let bar = null, pill = null;
  const build = () => {
    if (bar) return;
    bar = document.createElement("div");
    bar.id = "cztray";
    pill = document.createElement("button");
    pill.id = "cztray-pill";
    pill.title = "the reel timeline — every moment you've picked, suite-wide";
    pill.onclick = () => { S.pinned = true; save(); render(); };
    document.body.append(bar, pill);
  };
  const total = () =>
    S.items.reduce((a, c) => a + (c.end - c.start), 0);
  const chip = (c, i) => `
    <div class="tray-chip" data-i="${i}" title="${esc(c.label || c.title)}">
      <button class="tray-go" data-go="${i}"
        title="open this moment on the tape">${fmtTime(c.start)}</button>
      <span class="tray-name">${esc(c.title || "moment")}</span>
      <span class="tray-span">${(c.end - c.start).toFixed(0)}s</span>
      <span class="tray-acts">
        <button data-mv="${i}:-1" title="earlier">‹</button>
        <button data-mv="${i}:1" title="later">›</button>
        <button data-rm="${i}" title="drop it">✕</button>
      </span>
    </div>`;
  function render() {
    build();
    const n = S.items.length;
    document.body.classList.toggle("tray-open", S.pinned);
    pill.style.display = (n && !S.pinned) ? "" : "none";
    pill.textContent = `🎞 ${n}`;
    bar.style.display = S.pinned ? "" : "none";
    if (!S.pinned) return;
    bar.innerHTML = `
      <button class="tray-pin on" id="tray-unpin"
        title="unpin — the timeline folds to a count until you need it">📌</button>
      <span class="tray-count">${n ? `${n} moment${n > 1 ? "s" : ""} ·
        ${fmtTime(total())} · ${new Set(S.items.map(c => c.source)).size}
        meeting${new Set(S.items.map(c => c.source)).size > 1 ? "s" : ""}`
        : "the reel timeline — pick moments from any page and they land here"}</span>
      <div class="tray-strip">${S.items.map(chip).join("")}</div>
      ${n ? `<button class="btn" id="tray-clear">clear</button>
      <button class="btn primary" id="tray-render"
        style="--acc:var(--hl-cta)"
        title="one montage across every meeting here — URL sessions fetch only these seconds">▶ Render reel</button>` : ""}`;
    $("#tray-unpin", bar).onclick = () => { S.pinned = false; save(); render(); };
    const clr = $("#tray-clear", bar);
    if (clr) clr.onclick = () => { S.items = []; save(); render(); };
    const rd = $("#tray-render", bar);
    if (rd) rd.onclick = renderReel;
    $$("[data-rm]", bar).forEach(b => b.onclick = () => {
      S.items.splice(+b.dataset.rm, 1); save(); render(); });
    $$("[data-mv]", bar).forEach(b => b.onclick = () => {
      const [i, d] = b.dataset.mv.split(":").map(Number);
      const j = i + d;
      if (j < 0 || j >= S.items.length) return;
      [S.items[i], S.items[j]] = [S.items[j], S.items[i]]; save(); render();
    });
    $$("[data-go]", bar).forEach(b => b.onclick = () => {
      const c = S.items[+b.dataset.go];
      if (c) go("highlighter", { openPath: c.source, seek: c.start });
    });
  }
  async function renderReel() {
    const btn = $("#tray-render", bar);
    btn.disabled = true; btn.textContent = "rendering…";
    try {
      const job = await api("/api/kb/montage", { picks: S.items });
      toast(`cutting the reel — ${S.items.length} moments`);
      const done = await jobDone(job.id);
      if (done.status === "error") toast(done.error, true);
      else toast(`the reel is in: ${done.result?.out || "your library"}`);
    } catch (e) { toast(e.message, true); }
    btn.disabled = false; btn.textContent = "▶ Render reel";
  }
  function add(item) {
    const c = { source: String(item.source || ""),
      start: Math.max(0, +item.start || 0),
      end: +item.end || (+item.start || 0) + 12,
      label: String(item.label || "").slice(0, 80),
      title: String(item.title || "").slice(0, 60) };
    if (!c.source) { toast("this moment doesn't name its meeting", true); return; }
    if (S.items.some(x => x.source === c.source
        && Math.abs(x.start - c.start) < 0.5)) {
      toast("already on the timeline"); return;
    }
    S.items.push(c); save(); render();
    toast(`on the timeline — ${fmtTime(c.start)} · ${esc(c.title || "moment")}`);
  }
  const btnHTML = item => `<button class="tray-add" title="add to the reel
    timeline (rides every page)" data-tray='${esc(JSON.stringify(item))}'>⊕ reel</button>`;
  document.addEventListener("click", e => {
    const b = e.target.closest && e.target.closest(".tray-add");
    if (!b) return;
    e.stopPropagation();
    try { add(JSON.parse(b.dataset.tray)); }
    catch (err) { toast("that moment didn't parse", true); }
  }, true);
  document.addEventListener("DOMContentLoaded", render);
  return { add, btnHTML, items: () => S.items.slice(),
           pinned: () => S.pinned, render };
})();
// a deliberate global: pages test `window.czTray` before emitting ⊕ buttons
window.czTray = czTray;

/* ---------- czProgress: the house progress card ----------
   One look for every download, conversion, render and export: an accent
   bar that shimmers while indeterminate and fills when the job knows its
   fraction, the stage message in mono, a live elapsed clock, green on
   done, the error sentence on error. Attach to a job id; it cleans up
   after itself.

     const p = czProgress(container, { label: "fetching…", acc: "var(--grabber)" });
     watchJob(job.id, j => p.update(j));
     const done = await jobDone(job.id);  p.finish(done);
*/
function czProgress(container, opts = {}) {
  const box = document.createElement("div");
  box.className = "czprog";
  if (opts.acc) box.style.setProperty("--acc", opts.acc);
  box.innerHTML = `
    <div class="czprog-top">
      <span class="czprog-label">${esc(opts.label || "working…")}</span>
      <span class="czprog-pct"></span>
      <span class="czprog-clock">0s</span>
      <button class="czprog-cancel" type="button" style="display:none"
        title="stop this job — partial files are removed">✕ Cancel</button>
    </div>
    <div class="czprog-bar"><i class="indet"></i></div>
    <div class="czprog-msg">queued…</div>`;
  container.appendChild(box);
  const bar = $(".czprog-bar i", box);
  const pct = $(".czprog-pct", box);
  const msg = $(".czprog-msg", box);
  const clock = $(".czprog-clock", box);
  const cancel = $(".czprog-cancel", box);
  const t0 = Date.now();
  const tick = setInterval(() => {
    const s = Math.round((Date.now() - t0) / 1000);
    clock.textContent = s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;
  }, 1000);
  return {
    el: box,
    update(j) {
      if (j.message) msg.textContent = j.message;
      if (j.id) {
        const live = ["queued", "running"].includes(j.status);
        cancel.style.display = live ? "" : "none";
        cancel.onclick = () => cancelJob(j.id, cancel);
      }
      const has = j.progress != null && j.progress > 0;
      bar.classList.toggle("indet", !has);
      if (has) {
        bar.style.width = `${Math.round(Math.min(1, j.progress) * 100)}%`;
        pct.textContent = `${Math.round(Math.min(1, j.progress) * 100)}%`;
      }
    },
    finish(done) {
      clearInterval(tick);
      cancel.style.display = "none";
      bar.classList.remove("indet");
      if (done.status === "done") {
        box.classList.add("ok");
        bar.style.width = "100%";
        pct.textContent = "";
        msg.textContent = done.message || "done";
      } else if (done.status === "cancelled") {
        box.classList.add("cancelled");
        msg.textContent = "cancelled — partial files removed";
      } else {
        box.classList.add("err");
        msg.textContent = done.error || done.message || "stopped";
      }
      setTimeout(() => { box.classList.add("fade"); }, 4000);
      setTimeout(() => { box.remove(); }, 5000);
    },
    remove() { clearInterval(tick); box.remove(); },
  };
}

/* ---------- open-a-clip helpers: drop zones + the Browse dialog ----------
   The server opens files by PATH (local-only covenant — nothing uploads).
   In the app window pywebview stamps dragged Files with pywebviewFullPath;
   plain browsers don't reveal paths, so the drop explains itself instead
   of failing silently. file:// URIs (dragged from some file managers) work
   everywhere. */
function droppedPath(dt) {
  for (const f of dt.files || []) {
    if (f.pywebviewFullPath) return f.pywebviewFullPath;
    if (f.path) return f.path;               // some embedded runtimes
  }
  const uri = dt.getData && (dt.getData("text/uri-list") || dt.getData("text/plain"));
  if (uri) {
    const line = uri.split("\n").map(s => s.trim()).find(s => s && !s.startsWith("#"));
    if (line && line.startsWith("file://")) {
      try { return decodeURIComponent(new URL(line).pathname); } catch (e) {}
    }
    if (line && line.startsWith("/")) return line;
  }
  return null;
}

function wireDropZone(el, onPath) {
  let depth = 0;
  el.addEventListener("dragover", e => { e.preventDefault(); });
  el.addEventListener("dragenter", e => {
    e.preventDefault();
    depth++;
    el.classList.add("dropping");
  });
  el.addEventListener("dragleave", () => {
    if (--depth <= 0) { depth = 0; el.classList.remove("dropping"); }
  });
  el.addEventListener("drop", e => {
    e.preventDefault();
    depth = 0;
    el.classList.remove("dropping");
    const p = droppedPath(e.dataTransfer);
    if (p) onPath(p);
    else if ((e.dataTransfer.files || []).length) {
      toast("the browser hides file paths — use the app window for drag & " +
            "drop, or Browse / paste the path", true);
    }
  });
}

async function browseForPath(onPath) {
  try {
    const r = await api("/api/dialog/open-file", {});
    if (r.paths && r.paths[0]) onPath(r.paths[0]);
  } catch (e) { toast(e.message, true); }
}

/* frame URL helper */
const frameURL = (path, i, h) =>
  `/api/media/frame?path=${encodeURIComponent(path)}&i=${i}&h=${h || 540}`;

const fmtTime = s => {
  if (s == null) return "";
  const m = Math.floor(s / 60), ss = (s % 60).toFixed(1).padStart(4, "0");
  return `${m}:${ss}`;
};
const esc = s => String(s).replace(/[&<>"']/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* ---------- czModal: one overlay for every popup ----------
   Closes on ✕, Escape, or a click on the dimmed backdrop. Returns
   {el, box, close}; onClose runs once however it closed. */
function czModal({ title = "", html = "", width = 560, onClose } = {}) {
  const el = document.createElement("div");
  el.className = "cz-overlay";
  el.innerHTML = `<div class="cz-modal" role="dialog" aria-modal="true"
      aria-label="${esc(title)}" style="width:min(${width}px,94vw)">
    <div class="cz-modal-head"><h2>${esc(title)}</h2>
      <button class="cz-modal-x" type="button" aria-label="close">✕</button></div>
    <div class="cz-modal-body">${html}</div></div>`;
  document.body.appendChild(el);
  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    el.remove();
    removeEventListener("keydown", onKey, true);
    if (onClose) onClose();
  };
  const onKey = e => { if (e.key === "Escape") { e.stopPropagation(); close(); } };
  addEventListener("keydown", onKey, true);
  $(".cz-modal-x", el).onclick = close;
  el.addEventListener("mousedown", e => { if (e.target === el) close(); });
  // keys typed in a popup are the popup's (Space on a tab button must not
  // toggle the Highlighter's playback underneath); Escape still closes it
  el.addEventListener("keydown", e => { if (e.key !== "Escape") e.stopPropagation(); });
  const opener = document.activeElement;
  const done = close;
  return { el, box: $(".cz-modal-body", el), close: () => {
    done();
    try { if (opener && opener.focus) opener.focus(); } catch (e) {}
  } };
}

/* ---------- czKeyModal: "this needs an AI key" — and how to get one ----------
   Opened by api() when a route answers need:"llm_key", by jobDone when a
   job hits "no API key" mid-flight, and by any ✨ button whose feature
   needs a key. Resolves true once a key is saved (the caller retries). */
const KEY_PROVIDERS = [
  { id: "anthropic", name: "Anthropic (Claude)", prefix: "sk-ant-",
    url: "https://console.anthropic.com/settings/keys",
    steps: [
      `Go to <a href="https://console.anthropic.com/" target="_blank" rel="noopener">console.anthropic.com</a> and sign up or sign in.`,
      `Open <b>Settings → Billing</b> and add a little credit — $5 goes a long way (a meeting summary costs about a cent).`,
      `Open <b>Settings → API Keys</b>, press <b>Create Key</b>, name it “Civic Media Studio”, and copy it. It starts with <code>sk-ant-</code>.`,
      `Paste it below and press <b>Save key</b>.`] },
  { id: "openai", name: "OpenAI", prefix: "sk-",
    url: "https://platform.openai.com/api-keys",
    steps: [
      `Go to <a href="https://platform.openai.com/" target="_blank" rel="noopener">platform.openai.com</a> and sign up or sign in.`,
      `Open <b>Settings → Billing</b> and add a few dollars of credit.`,
      `Open <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">API keys</a>, press <b>Create new secret key</b>, and copy it. It starts with <code>sk-</code>.`,
      `Paste it below and press <b>Save key</b>.`] },
  { id: "gemini", name: "Google Gemini", prefix: "AIza",
    url: "https://aistudio.google.com/apikey",
    steps: [
      `Go to <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener">aistudio.google.com/apikey</a> and sign in with a Google account.`,
      `Press <b>Create API key</b> and copy it. It starts with <code>AIza</code>. Gemini has a free tier — a good way to try this out.`,
      `Paste it below and press <b>Save key</b>.`] },
];

function czKeyModal({ feature = "", alt = "", retry = true } = {}) {
  if (window._czKeyOpen) return window._czKeyOpen;   // one popup at a time
  const p = new Promise(resolve => {
    let saved = false;
    const m = czModal({
      title: "🔑 Add an AI key",
      width: 600,
      onClose: () => { window._czKeyOpen = null; resolve(saved); },
      html: `
        <p class="cz-lede">${feature ? `<b>${esc(feature)}</b> writes new text with an AI model,
          so it needs a key.` : "This feature writes new text with an AI model, so it needs a key."}
          Everything else in the app works without one.</p>
        <div class="cz-note">
          <b>What's a key?</b> A private code from an AI company that lets this app use
          their model on <i>your</i> account. Only the words of the meeting you're working on
          are sent — only when you press a button marked ✨. The key is stored on this
          computer only. You can remove it any time in Settings → AI.</div>
        <div class="cz-tabs" role="tablist">${KEY_PROVIDERS.map((pv, i) =>
          `<button class="cz-tab${i ? "" : " on"}" role="tab" data-pv="${pv.id}"
            aria-selected="${!i}">${pv.name}</button>`).join("")}</div>
        <div id="cz-key-steps"></div>
        <div class="cz-keyrow">
          <input type="password" id="cz-key-in" spellcheck="false" autocomplete="off"
            placeholder="paste your key here — sk-ant-… · sk-… · AIza…">
          <button class="btn primary" id="cz-key-save" style="width:auto">Save key</button>
        </div>
        <div class="cz-keymsg" id="cz-key-msg"></div>
        ${alt ? `<div class="cz-alt">No key? ${esc(alt)}.</div>` : ""}`,
    });
    const steps = id => {
      const pv = KEY_PROVIDERS.find(x => x.id === id);
      $("#cz-key-steps", m.box).innerHTML =
        `<ol class="cz-steps">${pv.steps.map(s => `<li>${s}</li>`).join("")}</ol>`;
    };
    steps("anthropic");
    $$(".cz-tab", m.box).forEach(t => t.onclick = () => {
      $$(".cz-tab", m.box).forEach(x => {
        x.classList.toggle("on", x === t);
        x.setAttribute("aria-selected", String(x === t));
      });
      steps(t.dataset.pv);
    });
    const input = $("#cz-key-in", m.box);
    setTimeout(() => input.focus(), 50);
    const save = async () => {
      const key = input.value.trim();
      const msg = $("#cz-key-msg", m.box);
      if (!key) { msg.textContent = "paste a key first"; msg.className = "cz-keymsg err"; return; }
      if (!/^(sk-|AIza)/.test(key)) {
        msg.textContent = "that doesn't look like a key — Anthropic keys start sk-ant-, OpenAI sk-, Gemini AIza";
        msg.className = "cz-keymsg err"; return;
      }
      $("#cz-key-save", m.box).disabled = true;
      try {
        const st = await api("/api/settings/llm", { api_key: key, model: "" });
        saved = true;
        msg.textContent = `✓ saved — ${st.provider || "key"} · ${st.model || ""}`;
        msg.className = "cz-keymsg ok";
        toast(retry ? "AI key saved — carrying on with what you asked for"
                    : "AI key saved — press the button again to run it");
        setTimeout(m.close, 500);
      } catch (e) {
        msg.textContent = e.message; msg.className = "cz-keymsg err";
        $("#cz-key-save", m.box).disabled = false;
      }
    };
    $("#cz-key-save", m.box).onclick = save;
    input.addEventListener("keydown", e => { if (e.key === "Enter") save(); });
  });
  window._czKeyOpen = p;
  return p;
}
window.czKeyModal = czKeyModal;

/* the ✨ buttons wear a small key mark while no key is set — clicking them
   opens the popup instead of failing. Pages call this after a status read. */
function markKeyButtons(root, hasKey) {
  $$("[data-needs-key]", root).forEach(b => {
    // remember the button's own tooltip once, so adding a key restores it
    if (b.dataset.titleKey === undefined) b.dataset.titleKey = b.title || "";
    b.classList.toggle("needs-key", !hasKey);
    b.title = hasKey ? b.dataset.titleKey
      : "needs an AI key — press to add one (a popup explains how)";
  });
}

/* ---------- folders: pick one, show one ---------- */
async function pickFolder(start) {
  try {
    const r = await api("/api/dialog/open-folder", { start: start || "" });
    return r.path || null;
  } catch (e) {
    // a plain browser has no native picker — ask for the path instead
    const typed = prompt("Folder path (e.g. ~/Downloads/Civic Media Studio):", start || "");
    return typed ? typed.trim() : null;
  }
}

async function showFolder(path) {
  try { await api("/api/media/reveal", { path, open: true, mkdir: true }); }
  catch (e) { toast(e.message, true); }
}

/* a "files go HERE" row: the path, Show in Finder, Change…, Default.
   load() -> path; save(pathOr"") -> new path. Returns {refresh}. */
function czLocRow(container, { label, load, save, hint }) {
  const row = document.createElement("div");
  row.className = "cz-loc";
  container.appendChild(row);
  let cur = "";
  async function refresh() {
    try { cur = await load(); } catch (e) { cur = ""; }
    const home = (CZ.appInfo && CZ.appInfo.home) || "";
    const shown = home && cur.startsWith(home) ? "~" + cur.slice(home.length) : cur;
    row.innerHTML = `
      <span class="cz-loc-label">${esc(label)}</span>
      <code class="cz-loc-path" title="${esc(cur)}">${esc(shown || "—")}</code>
      <span class="cz-loc-acts">
        <button type="button" data-act="show">Show in Finder</button>
        <button type="button" data-act="change">Change…</button>
      </span>
      ${hint ? `<span class="cz-loc-hint">${hint}</span>` : ""}`;
    $('[data-act="show"]', row).onclick = () => cur && showFolder(cur);
    $('[data-act="change"]', row).onclick = async () => {
      const p = await pickFolder(cur);
      if (!p) return;
      try { await save(p); toast("saved — new files land in " + p); refresh(); }
      catch (e) { toast(e.message, true); }
    };
  }
  refresh();
  return { refresh, get: () => cur };
}

/* ---------- the proxy switch (Grabber + Highlighter + Settings) ----------
   YouTube sometimes refuses one computer ("429 Too Many Requests",
   "confirm you're not a bot"). The switch routes YouTube requests through
   a residential proxy — OFF by default; pages call card.nudge(why) the
   moment a fetch fails that way, and the card opens itself to explain. */
const czBlocked = msg => /429|too many requests|not a bot|confirm you.re not|rate.?limit|flagged this address|limiting this computer|HTTP Error 403/i
  .test(msg || "");

function czProxyCard(container, { compact = true } = {}) {
  const card = document.createElement("div");
  card.className = "cz-proxy" + (compact ? " compact" : "");
  container.appendChild(card);
  let st = null, open = !compact, why = "";
  async function refresh() {
    try { st = await api("/api/settings/proxy"); } catch (e) { return; }
    render();
  }
  function whose() {
    if (!st) return "";
    return st.source === "house" ? "the built-in account"
      : st.source === "env" ? "the account set in this computer's environment"
      : st.source === "file" ? `your Webshare account (${esc(st.username_masked)})` : "";
  }
  function render() {
    if (!st) return;
    const on = !!st.enabled, avail = !!st.available, env = st.source === "env";
    card.classList.toggle("on", on);
    card.classList.toggle("alert", !!why && !on);
    card.innerHTML = `
      <div class="cz-proxy-head">
        <button class="cz-proxy-title" type="button" aria-expanded="${open}">
          <span class="cz-proxy-dot"></span>
          <b>Proxy ${on ? "on" : "off"}</b>
          <span class="cz-proxy-sum">${on ? `YouTube requests go through ${whose()}`
            : why ? "YouTube is limiting this computer — the proxy usually fixes it"
            : "YouTube blocking downloads or captions? Turn this on."}</span>
          <span class="cz-proxy-caret">${open ? "▴" : "▾"}</span>
        </button>
        ${env ? `<span class="badge">set by environment</span>` : `
        <label class="cz-switch" title="${avail ? "route YouTube requests through the proxy"
          : "no proxy account yet — set one up in Settings"}">
          <input type="checkbox" ${on ? "checked" : ""} ${avail ? "" : "disabled"}
            aria-label="use the proxy for YouTube">
          <span></span></label>`}
      </div>
      <div class="cz-proxy-body" style="display:${open ? "" : "none"}">
        ${why ? `<div class="cz-proxy-why">What happened: ${esc(why.slice(0, 220))}</div>` : ""}
        <p><b>What this is.</b> Sometimes YouTube stops answering one computer — you'll see
          <i>“HTTP Error 429: Too Many Requests”</i> or <i>“confirm you're not a bot”</i>.
          The proxy sends this app's YouTube requests through a different internet address
          (a <a href="https://www.webshare.io/" target="_blank" rel="noopener">Webshare</a>
          residential network), so they go through. It only carries YouTube traffic for the
          fetches you start, and only while it's on.</p>
        <p><b>When to use it.</b> Leave it off until YouTube refuses you, then switch it on and
          try again. Downloads can be a little slower through it.</p>
        <p>${avail ? `Account in use: <b>${whose()}</b>.` :
          `<b>No proxy account yet.</b> This copy of the app doesn't include one — add your own Webshare account in Settings.`}
          To use your own account, go to <a href="#" data-go-settings>Settings → Fetch network</a>.</p>
        <div class="cz-proxy-acts">
          ${avail ? `<button class="btn" type="button" data-test style="width:auto">Test the connection</button>` : ""}
          <button class="btn" type="button" data-go-settings style="width:auto">${st.own ? "Change my account" : "Use my own account"}</button>
          <span class="cz-proxy-msg"></span>
        </div>
      </div>`;
    $(".cz-proxy-title", card).onclick = () => { open = !open; render(); };
    const sw = $(".cz-switch input", card);
    if (sw) sw.onchange = async () => {
      try {
        st = await api("/api/settings/proxy", { enabled: sw.checked });
        if (st.enabled) why = "";
        toast(st.enabled ? "proxy on — YouTube requests now go through it"
                         : "proxy off — fetching directly from this computer");
        render();
      } catch (e) { toast(e.message, true); sw.checked = !sw.checked; }
    };
    $$("[data-go-settings]", card).forEach(a => a.onclick = e => {
      e.preventDefault(); go("settings", { section: "proxy" }); });
    const t = $("[data-test]", card);
    if (t) t.onclick = async () => {
      const msg = $(".cz-proxy-msg", card);
      t.disabled = true; msg.textContent = "testing…"; msg.className = "cz-proxy-msg";
      try {
        const r = await api("/api/settings/proxy/test", {});
        msg.textContent = r.ok ? `✓ working — exit address ${r.ip}` : `✗ ${r.error}`;
        msg.className = "cz-proxy-msg " + (r.ok ? "ok" : "err");
      } catch (e) { msg.textContent = e.message; msg.className = "cz-proxy-msg err"; }
      t.disabled = false;
    };
  }
  refresh();
  return {
    refresh,
    /* a fetch just failed the way the proxy fixes: open and say so */
    nudge(reason) {
      why = String(reason || "YouTube refused this computer");
      open = true;
      render();
      card.scrollIntoView({ behavior: "smooth", block: "nearest" });
    },
    enabled: () => !!(st && st.enabled),
  };
}

/* ---------- the wire: Send to Next App ----------
   A meeting travels the line — Grabber fetches it, Highlighter finds the
   moments, Publisher makes the posts, the Record keeps it — and the
   access chain carries it across: captions → languages → description.
   Every page that holds a meeting offers the next stop with the meeting
   in hand, plus a ▾ for any other stop that can take it. */
const WIRE = {
  grabber:     { next: "highlighter", verb: "find the moments" },
  highlighter: { next: "publisher",   verb: "make the posts" },
  publisher:   { next: "memory",      verb: "file it in the record" },
  scribe:      { next: "interpreter", verb: "translate the captions" },
  interpreter: { next: "narrator",    verb: "describe the picture" },
  narrator:    { next: "publisher",   verb: "make the posts" },
};
/* who can open what: sessions (a read URL meeting folder) only go where
   sidecars are enough; the workbench tools need a local file */
const WIRE_TAKES = {
  highlighter: "any", publisher: "any", interpreter: "any", narrator: "any",
  memory: "any", scribe: "file", clear: "file", pivot: "file",
};

function czNextHTML(from, source, { isFile } = {}) {
  const w = WIRE[from];
  if (!w || !source) return "";
  const t = toolById(w.next);
  return `<span class="cz-next" data-from="${esc(from)}" data-src="${esc(source)}"
      data-file="${isFile ? 1 : 0}" style="--acc:${t.acc}">
    <button class="cz-next-go" type="button"
      title="open this in ${esc(t.long || t.name)} — ${esc(w.verb)}">
      Send to next app <b>→ ${esc(t.name)}</b></button>
    <button class="cz-next-more" type="button" aria-label="send somewhere else"
      title="send it to another app">▾</button>
  </span>`;
}

async function czSendTo(dest, source) {
  if (dest === "memory") {
    const ok = await sendToRecord({ path: source });
    if (ok) go("memory");
    return;
  }
  go(dest, { openPath: source });
}

document.addEventListener("click", e => {
  const go1 = e.target.closest && e.target.closest(".cz-next-go");
  const more = e.target.closest && e.target.closest(".cz-next-more");
  $$(".cz-next-menu").forEach(m => { if (!m.contains(e.target)) m.remove(); });
  if (!go1 && !more) return;
  const box = e.target.closest(".cz-next");
  const from = box.dataset.from, src = box.dataset.src;
  const isFile = box.dataset.file === "1";
  if (go1) { czSendTo(WIRE[from].next, src); return; }
  const menu = document.createElement("div");
  menu.className = "cz-next-menu";
  const dests = Object.keys(WIRE_TAKES).filter(d => d !== from
    && (WIRE_TAKES[d] === "any" || isFile) && toolById(d) && toolById(d).ready);
  menu.innerHTML = `<div class="cz-next-menu-h">send it to…</div>` + dests.map(d => {
    const t = toolById(d);
    return `<button type="button" data-dest="${d}" style="--acc:${t.acc}">
      <span class="dot"></span>${esc(t.long || t.name)}
      <i>${esc(d === "memory" ? "file it in the record" : t.one || "")}</i></button>`;
  }).join("");
  document.body.appendChild(menu);
  const r = more.getBoundingClientRect();
  menu.style.top = `${Math.min(innerHeight - menu.offsetHeight - 8, r.bottom + 4)}px`;
  menu.style.left = `${Math.max(8, Math.min(innerWidth - menu.offsetWidth - 8, r.right - menu.offsetWidth))}px`;
  $$("button[data-dest]", menu).forEach(b => b.onclick = () => {
    menu.remove(); czSendTo(b.dataset.dest, src); });
}, true);
