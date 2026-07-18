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
  { id: "highlighter", name: "Highlighter", acc: "var(--highlighter)",
    ready: true, group: "community", long: "Community Highlighter",
    verb: "finds the moments", one: "meeting video → highlight reel, in text" },
  { id: "grabber", name: "Grabber", acc: "var(--grabber)",
    ready: true, group: "community", long: "BIG Video Grabber",
    verb: "brings the meeting home", one: "find, fetch, conform civic recordings" },
  { id: "kb", name: "Library", acc: "var(--kb)",
    ready: true, group: "community", long: "Meeting Library",
    verb: "reads them together", one: "framing, names, and topics across every meeting" },
  /* the community wing grows (specs/12): four more BIG apps moving in.
     Lane ownership + who flips `ready` is law in specs/PARALLEL.md. */
  { id: "publisher", name: "Publisher", acc: "var(--publisher)",
    ready: true, when: "1.6", group: "community", long: "Community Publisher",
    verb: "gets it seen", one: "program in → clips, copy and posts out" },
  { id: "memory", name: "Memory", acc: "var(--memory)",
    ready: false, when: "1.6", group: "community", long: "Community Memory",
    verb: "keeps the record", one: "issues tracked across meetings and years" },
  { id: "interpreter", name: "Interpreter", acc: "var(--interpreter)",
    ready: false, when: "1.7", group: "community", long: "Community Interpreter",
    verb: "carries it across", one: "captions in seven languages + simple english" },
  { id: "narrator", name: "Narrator", acc: "var(--narrator)",
    ready: false, when: "1.7", group: "community", long: "Community Narrator",
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
async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
  const r = await fetch(path, opts);
  let data = null;
  try { data = await r.json(); } catch (e) { /* non-JSON error body */ }
  if (!r.ok) {
    const msg = (data && data.error) ? data.error : `${r.status} ${r.statusText}`;
    throw new Error(msg);
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
function jobDone(id) {
  return new Promise(resolve => {
    let off = null, settled = false;
    off = watchJob(id, job => {
      if (!["done", "error", "cancelled"].includes(job.status)) return;
      settled = true;
      if (off) off();
      resolve(job);
    });
    if (settled) off();   // already terminal: watchJob fired before off existed
  });
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
function registerPage(name, el, onshow) {
  CZ.pages[name] = { el, onshow };
  $("#main").appendChild(el);
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
