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

/* ---------- tools registry (accents + glyphs + one-liners) ---------- */
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
];
const toolById = id => TOOLS.find(t => t.id === id);

/* simple diamond glyph per tool, wired like the site's node motif */
function glyphSVG(acc, ready) {
  return `<svg viewBox="0 0 20 20" fill="none">
    <rect x="10" y="2.8" width="10.2" height="10.2" rx="2.4"
      transform="rotate(45 10 2.8)"
      stroke="${acc}" stroke-width="1.6" fill="${ready ? acc : "none"}"
      fill-opacity="${ready ? .28 : 0}"/></svg>`;
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
  (CZ.jobWatchers.get(job.id) || []).forEach(fn => { try { fn(job); } catch (e) {} });
  if (window.QueuePage) QueuePage.onJob(job);
}

function watchJob(id, fn) {
  if (!CZ.jobWatchers.has(id)) CZ.jobWatchers.set(id, []);
  CZ.jobWatchers.get(id).push(fn);
  const cur = CZ.jobs.get(id);
  if (cur) fn(cur);
}

/* wait for a job to finish; progress via watcher */
function jobDone(id) {
  return new Promise(resolve => {
    watchJob(id, job => {
      if (["done", "error", "cancelled"].includes(job.status)) resolve(job);
    });
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
async function patchSession(patch) {
  Object.assign(CZ.session, patch.recents ? {} : {});
  try { await api("/api/session", patch); } catch (e) {}
}
function density(tool) { return (CZ.session.ui?.density || {})[tool] || "easy"; }
async function setDensity(tool, d) {
  CZ.session.ui = CZ.session.ui || { density: {} };
  CZ.session.ui.density = CZ.session.ui.density || {};
  CZ.session.ui.density[tool] = d;
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
