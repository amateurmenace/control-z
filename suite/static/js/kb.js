/* Meeting Library — every meeting on this machine, read together.

   The web app calls this its Knowledge Base and asks a cloud model; here
   every number is the same local counted reading the analyzer shows for
   one meeting, aggregated across all of them. Cards need at least two
   read meetings to compare anything — below that they say so. */

const KBPage = (() => {
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-kb";
  el.innerHTML = `<div class="page-pad wide">
    <div class="hl-hero" style="margin-bottom:16px">
      <div class="tag">meeting library · via BIG · read together</div>
      <h1 style="margin-top:6px">One meeting is a moment. The library is
        <span class="mark">memory</span>.</h1>
      <p style="color:var(--cream-dim);margin-top:8px;font-size:13.5px;max-width:680px;line-height:1.65">
        Every meeting the Highlighter has read leaves its transcript and its
        counted reading beside it on this machine. This page reads them
        together — how the framing moves across meetings, who keeps
        appearing, how any topic travels — with the same local passes the
        analyzer uses. Nothing uploads; nothing here is a model's opinion.</p>
      <div class="hint" id="kb-status" style="margin-top:8px"></div>
    </div>
    <div class="hl-panel" style="margin-bottom:14px">
      <span class="tag">the meetings — click one to open it in the Highlighter</span>
      <div id="kb-meetings" style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px"></div>
    </div>
    <div class="hl-panel" style="margin-bottom:14px">
      <span class="tag">framing across meetings — eight lenses, each meeting a column; click a cell for its moments</span>
      <div id="kb-trends" style="display:flex;gap:14px;flex-wrap:wrap;margin:8px 0 4px"></div>
      <div id="kb-framing" style="margin-top:8px;overflow-x:auto"></div>
    </div>
    <div class="hl-panel" style="margin-bottom:14px">
      <span class="tag">entity tracking — who appears across which meetings, and how often; click a name to trace it</span>
      <div id="kb-entities" style="margin-top:8px;overflow-x:auto"></div>
    </div>
    <div class="hl-panel" style="margin-bottom:14px">
      <span class="tag">meeting comparison — two meetings, side by side</span>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin:8px 0">
        <select id="kb-cmp-a" style="flex:1;min-width:220px"></select>
        <select id="kb-cmp-b" style="flex:1;min-width:220px"></select>
      </div>
      <div id="kb-compare"></div>
    </div>
    <div class="hl-panel" style="margin-bottom:14px">
      <span class="tag">discourse analysis — trace one topic or name through every meeting, oldest first</span>
      <div style="display:flex;gap:8px;margin:8px 0;flex-wrap:wrap">
        <input type="text" id="kb-q" placeholder="override · Harvard Street · superintendent…" spellcheck="false"
          style="flex:1;min-width:240px;background:#fff;border:1px solid var(--line);border-radius:7px;padding:6px 10px;font-size:13px">
        <button class="btn cta" id="kb-trace" style="width:auto;padding:6px 16px">Trace it</button>
      </div>
      <div id="kb-discourse"></div>
    </div>
    <div class="hl-panel">
      <span class="tag">meeting montage — moments picked across meetings, cut into one reel</span>
      <div class="hint" style="margin:6px 0">every ➕ on a traced moment or a framing cell's list lands here.
        Local meetings cut in place; URL sessions download only the picked seconds. Each clip
        wears a title card naming its own meeting.</div>
      <div id="kb-tray" style="margin:8px 0"></div>
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
        <label class="hint" style="display:flex;align-items:center;gap:5px">
          <input type="checkbox" id="kb-mcards" checked> title cards</label>
        <button class="btn cta" id="kb-render" style="width:auto;padding:6px 16px" disabled>Render montage</button>
        <span class="hint" id="kb-mmsg"></span>
      </div>
    </div>
    <div id="kb-modal" style="display:none;position:fixed;inset:0;background:rgba(20,20,16,.45);z-index:60;align-items:center;justify-content:center">
      <div style="background:var(--ink);border:1px solid var(--line);border-radius:12px;max-width:640px;width:92%;max-height:76vh;display:flex;flex-direction:column;padding:16px 18px">
        <div style="display:flex;align-items:baseline;gap:10px;margin-bottom:8px">
          <b id="kb-modal-title" style="flex:1"></b>
          <button class="btn" id="kb-modal-open" style="width:auto;padding:4px 12px">Open in Highlighter →</button>
          <button class="btn" id="kb-modal-close" style="width:auto;padding:4px 10px">✕</button>
        </div>
        <div id="kb-modal-body" style="overflow-y:auto;font-size:13px;line-height:1.6"></div>
      </div>
    </div>
  </div>`;

  const K = { rows: null, over: null, busy: false, modalSource: null,
              picks: [], traceRows: [], modalMoments: null };
  const LENS_ORDER = ["financial", "safety", "community", "environmental",
                      "legal", "equity", "infrastructure", "process"];
  const dayLabel = d => d ? d.slice(5) : "—";
  const shortTitle = t => {
    // titles repeat the town and the date — the chip only needs the body
    const s = t.replace(/brookline\s*/i, "").replace(/\s*[-–—]\s*\w+ \d{1,2},? \d{4}.*/i, "");
    return s.length > 38 ? s.slice(0, 36) + "…" : s;
  };

  function openMeeting(source) { go("highlighter", { openPath: source }); }

  /* ---------- montage tray ---------- */
  function addPick(p) {
    K.picks.push(p);
    renderTray();
    toast(`on the montage — ${fmtTime(p.start)} from ${p.title}`);
  }

  function renderTray() {
    const box = $("#kb-tray", el);
    $("#kb-render", el).disabled = !K.picks.length;
    box.innerHTML = K.picks.map((p, i) => `
      <div style="display:flex;gap:8px;align-items:center;padding:3px 0;border-bottom:1px dashed var(--line);font-size:12.5px">
        <span class="tpill">${fmtTime(p.start)}</span>
        <b style="flex:0 0 auto">${esc(p.title)}</b>
        <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--cream-dim)">${esc(p.label)}</span>
        <button class="btn" data-unpick="${i}" style="width:auto;padding:1px 8px">✕</button>
      </div>`).join("")
      || `<div class="hint">nothing picked yet</div>`;
    $$("button[data-unpick]", box).forEach(b => b.onclick = () => {
      K.picks.splice(+b.dataset.unpick, 1);
      renderTray();
    });
  }

  async function renderMontage() {
    const btn = $("#kb-render", el), msg = $("#kb-mmsg", el);
    btn.disabled = true;
    try {
      const job = await api("/api/kb/montage",
        { picks: K.picks, cards: $("#kb-mcards", el).checked });
      msg.textContent = "queued — the corner card follows it";
      watchJob(job.id, j => { msg.textContent = j.message || j.status; });
      const done = await jobDone(job.id);
      btn.disabled = !K.picks.length;
      if (done.status !== "done") { msg.textContent = done.error || "stopped"; return; }
      msg.textContent = done.result?.out
        ? `done — ${done.result.out.split("/").pop()} (the Queue can reveal it)`
        : "done";
      toast("montage rendered — the Queue shows where it landed");
    } catch (e) { btn.disabled = !K.picks.length; msg.textContent = e.message; }
  }

  function modal(title, source, bodyHTML) {
    K.modalSource = source;
    $("#kb-modal-title", el).textContent = title;
    $("#kb-modal-body", el).innerHTML = bodyHTML;
    $("#kb-modal", el).style.display = "flex";
  }

  /* ---------- meetings strip ---------- */
  function renderMeetings() {
    const box = $("#kb-meetings", el);
    const rows = K.over?.meetings || [];
    box.innerHTML = rows.map(m => `
      <button class="chip" data-src="${esc(m.source)}" title="${esc(m.title)}"
        style="${m.read ? "" : "opacity:.5"}">
        ${esc(shortTitle(m.title))}
        <span style="opacity:.65">· ${m.day ? esc(m.day) : "no date"}${m.read ? "" : " · unread"}</span>
      </button>`).join("")
      || `<div class="hint">no meetings yet — open one in the Highlighter and it joins the library</div>`;
    $$("button[data-src]", box).forEach(b => b.onclick = () => openMeeting(b.dataset.src));
  }

  /* ---------- framing across meetings ---------- */
  function renderFraming() {
    const box = $("#kb-framing", el), chips = $("#kb-trends", el);
    const rows = K.rows || [];
    if (rows.length < 2) {
      chips.innerHTML = "";
      box.innerHTML = `<div class="hint">cross-meeting framing needs at least two read meetings — the library has ${rows.length}</div>`;
      return;
    }
    const lensOf = (r, name) => (r.framing || []).find(l => l.lens === name);
    // trend: average share over the older half vs the newer half
    const half = Math.ceil(rows.length / 2);
    const trend = [];
    LENS_ORDER.forEach(name => {
      const shares = rows.map(r => lensOf(r, name)?.share || 0);
      const a = shares.slice(0, half).reduce((x, y) => x + y, 0) / half;
      const b = shares.slice(half).reduce((x, y) => x + y, 0) / (rows.length - half || 1);
      if (Math.abs(b - a) >= 0.03)
        trend.push({ name, dir: b > a ? "rising" : "fading", d: Math.abs(b - a) });
    });
    trend.sort((x, y) => y.d - x.d);
    chips.innerHTML = trend.slice(0, 4).map(t => {
      const color = lensOf(rows[0], t.name)?.color || "var(--cream)";
      return `<span style="font-size:12.5px;display:flex;align-items:center;gap:6px">
        <i style="width:9px;height:9px;border-radius:2px;background:${color};display:inline-block"></i>
        <b style="color:${color}">${t.name}</b> framing is ${t.dir} across meetings ${t.dir === "rising" ? "↑" : "↓"}</span>`;
    }).join("") || `<span class="hint">no lens moved more than 3 points between the older and newer halves — steady library</span>`;
    const maxShare = Math.max(0.01, ...rows.flatMap(r => (r.framing || []).map(l => l.share || 0)));
    box.innerHTML = `<div style="display:grid;grid-template-columns:110px repeat(${rows.length},minmax(56px,1fr));gap:3px;align-items:center">
      <span></span>
      ${rows.map(r => `<button class="chip" data-src="${esc(r.source)}" title="${esc(r.title)}"
         style="justify-content:center;font-size:11px;padding:2px 4px">${dayLabel(r.day)}</button>`).join("")}
      ${LENS_ORDER.map(name => {
        const color = lensOf(rows[0], name)?.color || "#7E7D75";
        return `<span style="font-size:12px;display:flex;align-items:center;gap:6px">
            <i style="width:8px;height:8px;border-radius:2px;background:${color};display:inline-block"></i>${name}</span>`
          + rows.map((r, ri) => {
            const l = lensOf(r, name);
            const a = l ? (l.share / maxShare) : 0;
            return `<button data-cell="${ri}:${name}" title="${esc(r.title)} — ${name} ×${l ? l.count : 0} (${l ? Math.round(l.share * 100) : 0}% of its lens talk)"
              style="height:26px;border:1px solid var(--line);border-radius:5px;cursor:pointer;
                     background:color-mix(in srgb, ${color} ${Math.round(a * 82)}%, transparent)"></button>`;
          }).join("");
      }).join("")}
    </div>`;
    $$("button[data-src]", box).forEach(b => b.onclick = () => openMeeting(b.dataset.src));
    $$("button[data-cell]", box).forEach(c => c.onclick = () => {
      const [ri, name] = c.dataset.cell.split(":");
      const r = rows[+ri], l = lensOf(r, name);
      if (!l || !l.count) { toast(`no ${name} vocabulary in that meeting`); return; }
      K.modalMoments = { source: r.source, title: shortTitle(r.title), rows: l.moments || [] };
      modal(`${name} framing — ${esc(shortTitle(r.title))} (${l.count} mentions)`, r.source,
        (l.moments || []).map((m, mi) => `<div style="display:flex;gap:8px;align-items:baseline;padding:4px 0;border-bottom:1px dashed var(--line)">
          <span class="tpill">${fmtTime(m.t)}</span><span style="flex:1">${esc(m.text)}</span>
          <button class="btn" data-mpick="${mi}" title="add to the montage" style="width:auto;padding:1px 8px">➕</button></div>`).join("")
        || `<div class="hint">moments not cached — open the meeting</div>`);
      $$("button[data-mpick]", $("#kb-modal-body", el)).forEach(b => b.onclick = () => {
        const m = K.modalMoments.rows[+b.dataset.mpick];
        addPick({ source: K.modalMoments.source, title: K.modalMoments.title,
                  start: m.t, end: m.end || m.t + 12, label: m.text || "" });
      });
    });
  }

  /* ---------- entity tracking ---------- */
  function renderEntities() {
    const box = $("#kb-entities", el);
    const rows = K.rows || [];
    if (rows.length < 2) {
      box.innerHTML = `<div class="hint">entity tracking needs at least two read meetings</div>`;
      return;
    }
    const totals = new Map();  // name -> {kind, total, per: Map(rowIdx -> count)}
    rows.forEach((r, ri) => {
      [["people", "person"], ["places", "place"], ["organizations", "org"]]
        .forEach(([bucket, kind]) => (r.entities?.[bucket] || []).forEach(e => {
          const key = e.name.toLowerCase();
          const row = totals.get(key) || { name: e.name, kind, total: 0, per: new Map() };
          row.total += e.count;
          row.per.set(ri, (row.per.get(ri) || 0) + e.count);
          totals.set(key, row);
        }));
    });
    const ents = [...totals.values()].filter(e => e.per.size >= 1)
      .sort((a, b) => (b.per.size - a.per.size) || (b.total - a.total)).slice(0, 14);
    if (!ents.length) { box.innerHTML = `<div class="hint">no entities harvested yet</div>`; return; }
    const maxC = Math.max(...ents.flatMap(e => [...e.per.values()]), 1);
    box.innerHTML = `<div style="display:grid;grid-template-columns:190px repeat(${rows.length},minmax(56px,1fr));gap:3px;align-items:center">
      <span></span>
      ${rows.map(r => `<span style="font-size:11px;text-align:center;color:var(--cream-dim)">${dayLabel(r.day)}</span>`).join("")}
      ${ents.map(e => `
        <button class="hl-click" data-ent="${esc(e.name)}" title="trace ${esc(e.name)} through every meeting"
          style="display:flex;align-items:center;gap:6px;border:none;background:none;cursor:pointer;font-size:12.5px;text-align:left;padding:2px 0">
          <span class="hl-kind hl-kind-${e.kind}">${e.kind}</span>
          <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(e.name)}</span>
          <span class="cnt">×${e.total} · ${e.per.size} mtg</span>
        </button>`
        + rows.map((r, ri) => {
          const c = e.per.get(ri) || 0;
          return `<div title="${esc(e.name)} — ${c ? "×" + c + " in " : "absent from "}${esc(shortTitle(r.title))}"
            style="height:22px;border:1px solid var(--line);border-radius:5px;display:flex;align-items:center;justify-content:center">
            ${c ? `<i style="width:${6 + 10 * c / maxC}px;height:${6 + 10 * c / maxC}px;border-radius:50%;
                     background:var(--kb);opacity:${0.45 + 0.55 * c / maxC}"></i>` : ""}</div>`;
        }).join("")).join("")}
    </div>`;
    $$("button[data-ent]", box).forEach(b => b.onclick = () => {
      $("#kb-q", el).value = b.dataset.ent;
      trace();
      $("#kb-discourse", el).scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }

  /* ---------- comparison ---------- */
  function renderCompareSelects() {
    const rows = K.rows || [];
    const opts = rows.map((r, i) =>
      `<option value="${i}">${esc(shortTitle(r.title))} · ${r.day || "no date"}</option>`).join("");
    const a = $("#kb-cmp-a", el), b = $("#kb-cmp-b", el);
    a.innerHTML = opts; b.innerHTML = opts;
    if (rows.length >= 2) { a.value = String(rows.length - 2); b.value = String(rows.length - 1); }
    a.onchange = renderCompare; b.onchange = renderCompare;
  }

  function renderCompare() {
    const box = $("#kb-compare", el);
    const rows = K.rows || [];
    if (rows.length < 2) {
      box.innerHTML = `<div class="hint">comparison needs at least two read meetings</div>`;
      return;
    }
    const A = rows[+$("#kb-cmp-a", el).value], B = rows[+$("#kb-cmp-b", el).value];
    if (!A || !B) return;
    const topics = r => new Set((r.topics || []).map(t => t.topic));
    const shared = [...topics(A)].filter(t => topics(B).has(t));
    const entNames = r => new Set(["people", "places", "organizations"]
      .flatMap(k => (r.entities?.[k] || []).map(e => e.name.toLowerCase())));
    const sharedEnts = [...entNames(A)].filter(n => entNames(B).has(n));
    const col = (r, other) => `
      <div style="flex:1;min-width:280px">
        <button class="chip" data-src="${esc(r.source)}" style="margin-bottom:6px"><b>${esc(shortTitle(r.title))}</b>&nbsp;· ${r.day || "no date"}</button>
        <div class="hint" style="margin-bottom:6px">${fmtTime(r.duration)} · ${r.wpm_avg} wpm ·
          ${r.decisions} decision${r.decisions === 1 ? "" : "s"}
          ${Object.entries(r.outcomes || {}).map(([k, n]) => `<span class="hl-outcome ${k}" style="margin-left:4px">${k} ${n}</span>`).join("")}
          · ${r.questions} questions · ${r.disagreements} tense moments</div>
        <div style="margin-bottom:6px">${(r.framing || []).slice(0, 5).map(l => `
          <div style="display:flex;align-items:center;gap:6px;font-size:11.5px;margin:2px 0">
            <span style="flex:0 0 92px">${l.lens}</span>
            <span class="hl-bar" style="width:${Math.max(1, l.share * 130).toFixed(0)}px;background:${l.color}"></span>
            <span class="cnt">×${l.count}</span></div>`).join("")}</div>
        <div style="font-size:12px">${(r.topics || []).slice(0, 6).map(t =>
          `<span class="chip" style="margin:2px 3px 0 0;${shared.includes(t.topic) ? "border-color:var(--kb);font-weight:600" : ""}">${esc(t.topic)} ×${t.count}</span>`).join("") || `<span class="hint">no recurring topics</span>`}</div>
      </div>`;
    box.innerHTML = `
      <div style="display:flex;gap:16px;flex-wrap:wrap">${col(A, B)}${col(B, A)}</div>
      <div class="hint" style="margin-top:8px">
        ${shared.length ? `shared topics (outlined): ${shared.slice(0, 6).map(esc).join(" · ")}` : "no topics recur in both"}
        ${sharedEnts.length ? ` — shared names: ${sharedEnts.slice(0, 6).map(esc).join(" · ")}` : ""}</div>`;
    $$("button[data-src]", box).forEach(b => b.onclick = () => openMeeting(b.dataset.src));
  }

  /* ---------- discourse ---------- */
  async function trace() {
    const q = $("#kb-q", el).value.trim();
    const box = $("#kb-discourse", el);
    if (q.length < 3) { toast("a trace needs at least three letters", true); return; }
    box.innerHTML = `<div class="hint">reading every transcript for “${esc(q)}”…</div>`;
    try {
      const r = await api("/api/kb/discourse", { q });
      const rows = (r.rows || []).filter(x => x.read !== false);
      const maxRate = Math.max(...rows.map(x => x.rate), 0.01);
      const total = rows.reduce((n, x) => n + x.count, 0);
      if (!total) {
        box.innerHTML = `<div class="hint">“${esc(q)}” doesn't appear in any read meeting — the library can only trace words it holds</div>`;
        return;
      }
      box.innerHTML = `
        <div style="display:flex;gap:6px;align-items:flex-end;height:86px;margin:6px 0 4px">
          ${rows.map(x => `<div data-src="${esc(x.source)}" title="${esc(shortTitle(x.title))} — ×${x.count} (${x.rate}/1k words)"
            style="flex:1;min-width:22px;cursor:pointer;border-radius:4px 4px 0 0;background:var(--kb);
                   opacity:${x.count ? 0.45 + 0.55 * x.rate / maxRate : 0.12};
                   height:${Math.max(4, 82 * x.rate / maxRate)}px"></div>`).join("")}
        </div>
        <div style="display:flex;gap:6px">${rows.map(x =>
          `<span style="flex:1;min-width:22px;text-align:center;font-size:10.5px;color:var(--cream-dim)">${dayLabel(x.day)}</span>`).join("")}</div>
        <div style="margin-top:10px">${rows.filter(x => x.count).map((x, xi) => `
          <div style="padding:6px 0;border-bottom:1px dashed var(--line)">
            <button class="chip" data-src="${esc(x.source)}"><b>${esc(shortTitle(x.title))}</b>&nbsp;· ${x.day || "no date"} · ×${x.count} · ${x.rate}/1k words</button>
            ${(x.moments || []).map((m, mi) => `<div style="display:flex;gap:8px;align-items:baseline;font-size:12.5px;padding:2px 0 0 12px;color:var(--cream-dim)">
              <span class="tpill">${fmtTime(m.t)}</span><span style="flex:1">${esc(m.text)}</span>
              <button class="btn" data-tpick="${xi}:${mi}" title="add to the montage" style="width:auto;padding:1px 8px">➕</button></div>`).join("")}
          </div>`).join("")}</div>
        <div class="hint" style="margin-top:6px">×${total} across ${rows.filter(x => x.count).length} of ${rows.length} read meetings — counted, per-1k-word rate so long meetings can't out-shout short ones</div>`;
      K.traceRows = rows.filter(x => x.count);
      $$("[data-src]", box).forEach(b => b.onclick = () => openMeeting(b.dataset.src));
      $$("button[data-tpick]", box).forEach(b => b.onclick = e => {
        e.stopPropagation();
        const [xi, mi] = b.dataset.tpick.split(":").map(Number);
        const x = K.traceRows[xi], m = x.moments[mi];
        addPick({ source: x.source, title: shortTitle(x.title),
                  start: m.t, end: m.t + 12, label: m.text || "" });
      });
    } catch (e) { box.innerHTML = `<div class="hint">${esc(e.message)}</div>`; }
  }

  /* ---------- load ---------- */
  async function load() {
    if (K.busy) return;
    K.busy = true;
    const status = $("#kb-status", el);
    try {
      K.over = await api("/api/kb/overview");
      renderMeetings();
      const n = (K.over.meetings || []).length;
      status.textContent = n
        ? `${n} meeting${n === 1 ? "" : "s"} on this machine · ${K.over.read} read — reading them together…`
        : "";
      const m = await api("/api/kb/matrix", {});
      K.rows = m.rows || [];
      status.textContent = `${(K.over.meetings || []).length} meetings · ${K.rows.length} read together`
        + (m.skipped?.length ? ` · ${m.skipped.length} without words yet (${m.skipped.slice(0, 2).map(shortTitle).join(", ")}${m.skipped.length > 2 ? "…" : ""})` : "");
      renderFraming(); renderEntities(); renderCompareSelects(); renderCompare();
    } catch (e) {
      status.textContent = e.message;
    } finally { K.busy = false; }
  }

  function init() {
    $("#kb-trace", el).onclick = trace;
    $("#kb-render", el).onclick = renderMontage;
    renderTray();
    $("#kb-q", el).addEventListener("keydown", e => { if (e.key === "Enter") trace(); });
    $("#kb-modal-close", el).onclick = () => { $("#kb-modal", el).style.display = "none"; };
    $("#kb-modal", el).onclick = e => { if (e.target === $("#kb-modal", el)) $("#kb-modal", el).style.display = "none"; };
    $("#kb-modal-open", el).onclick = () => {
      $("#kb-modal", el).style.display = "none";
      if (K.modalSource) openMeeting(K.modalSource);
    };
  }

  let inited = false;
  function onshow(arg) {
    if (!inited) { init(); inited = true; }
    Viewer.active = null;
    load();
    if (arg && arg.q) { $("#kb-q", el).value = arg.q; trace(); }
  }

  registerPage("kb", el, onshow);
  return { onshow };
})();
