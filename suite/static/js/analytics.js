/* czAnalytics — the record, drawn readable. One engine, two homes:
   the end of Highlighter's Meeting Analyzer (focused on the open meeting)
   and Memory's Analytics view (the whole record). Replaces the Library
   page: same /api/kb/* engine underneath, redrawn to the dataviz rules —
   identity gets the validated 8-hue family in fixed order, magnitude gets
   one violet ramp, marks stay thin with 2px gaps, labels never drop below
   12.5px, every mark answers to hover, and every moment it surfaces can be
   pulled up in context, jumped to on the tape, or added to the reel
   timeline (czTray). */

const czAnalytics = (() => {
  /* the validated categorical family (see CHANGELOG 1.7.1: house hues,
     chroma-lifted; worst adjacent CVD ΔE 24.9 on the panel surface) —
     fixed order, never cycled */
  const CAT = ["#1D82C4", "#B98300", "#12999B", "#C74A52",
               "#6D5BD0", "#1F8F4F", "#C75A9E", "#B06A2C"];
  const RAMP = (t) =>            /* magnitude: paper → the Library's violet */
    `color-mix(in srgb, var(--kb) ${Math.round(8 + 92 * Math.min(1, t))}%, var(--ink-2))`;

  let cache = null, cacheAt = 0;
  async function matrix() {
    if (cache && Date.now() - cacheAt < 60000) return cache;
    cache = await api("/api/kb/matrix", {});
    cacheAt = Date.now();
    return cache;
  }
  const words = r => (r.wpm_avg || 0) * ((r.duration || 0) / 60);
  const rate = (count, r) =>
    words(r) > 0 ? count / words(r) * 1000 : 0;
  const shortDay = r => (r.day || "").slice(5) || "?";
  const shortTitle = r => {
    const t = r.title || "";
    const m = t.match(/(select board|school committee|town meeting|council|committee|board)/i);
    return (m ? m[1] : t.split(/[-–—]/)[0]).slice(0, 22);
  };

  /* ---------- tooltip + modal singletons ---------- */
  function tip() {
    let t = $("#viz-tip");
    if (!t) { t = document.createElement("div"); t.id = "viz-tip"; document.body.appendChild(t); }
    return t;
  }
  function showTip(e, html) {
    const t = tip();
    t.innerHTML = html;
    t.style.display = "block";
    const w = t.offsetWidth, h = t.offsetHeight;
    t.style.left = Math.min(innerWidth - w - 12, e.clientX + 14) + "px";
    t.style.top = (e.clientY - h - 12 < 8 ? e.clientY + 16 : e.clientY - h - 12) + "px";
  }
  const hideTip = () => { const t = $("#viz-tip"); if (t) t.style.display = "none"; };

  function modal(title, note, bodyHTML) {
    hideTip();
    let ov = $("#viz-overlay");
    if (ov) ov.remove();
    ov = document.createElement("div");
    ov.id = "viz-overlay";
    ov.innerHTML = `<div class="hl-modal">
      <div style="display:flex;align-items:baseline;gap:10px">
        <h3 style="font-family:var(--head);margin:0;flex:1">${title}</h3>
        <button class="btn" id="viz-close">✕ close</button></div>
      ${note ? `<div class="viz-note">${note}</div>` : ""}
      <div id="viz-modal-body">${bodyHTML}</div></div>`;
    document.body.appendChild(ov);
    $("#viz-close", ov).onclick = () => ov.remove();
    ov.onclick = e => { if (e.target === ov) ov.remove(); };
    return ov;
  }

  /* one moment row: the receipt, the tape, the timeline */
  const momentHTML = (m, row, label) => `
    <div class="viz-moment">
      <button class="vm-t" data-tape='${esc(JSON.stringify({ source: row.source, t: m.t }))}'
        title="open the tape at this second">▶ ${fmtTime(m.t)}</button>
      <div class="vm-text">${esc(m.text || "")}
        <div class="vm-meta">${esc(shortTitle(row))} · ${esc(row.day || "undated")}</div></div>
      ${czTray.btnHTML({ source: row.source, start: Math.max(0, (m.t || 0) - 2),
        end: (m.t || 0) + 12, label: (m.text || "").slice(0, 80),
        title: label || shortTitle(row) })}
    </div>`;

  document.addEventListener("click", e => {
    const b = e.target.closest && e.target.closest("[data-tape]");
    if (!b) return;
    try {
      const { source, t } = JSON.parse(b.dataset.tape);
      const ov = $("#viz-overlay"); if (ov) ov.remove();
      go("highlighter", { openPath: source, seek: t });
    } catch (err) { /* an unparseable tape button just stays a button */ }
  }, true);

  /* context pull-up: the transcript around one second of one meeting */
  async function contextModal(row, t, label) {
    const ov = modal(esc(label || shortTitle(row)),
      `${esc(row.title || "")} · around ${fmtTime(t)}`,
      `<div class="viz-empty">reading the transcript…</div>`);
    try {
      const r = await api("/api/kb/context", { source: row.source, t, window: 40 });
      $("#viz-modal-body", ov).innerHTML =
        (r.segments || []).map(s => momentHTML(
          { t: s.start, text: s.text }, row, label)).join("")
        || `<div class="viz-empty">no words around that second</div>`;
    } catch (err) {
      $("#viz-modal-body", ov).innerHTML =
        `<div class="viz-empty">${esc(err.message)}</div>`;
    }
  }

  /* trace one term (the discourse engine) into a modal, optionally scoped
     to one meeting — every receipt pickable */
  async function traceModal(q, onlySource, label) {
    const ov = modal(`“${esc(q)}” in the record`, "counted mentions · rate per 1,000 words — receipts below",
      `<div class="viz-empty">tracing…</div>`);
    try {
      const r = await api("/api/kb/discourse", { q });
      let rows = (r.rows || []).filter(x => x.count > 0);
      if (onlySource) rows = rows.filter(x => x.source === onlySource);
      const maxRate = Math.max(0.01, ...rows.map(x => x.rate));
      $("#viz-modal-body", ov).innerHTML = rows.map(x => `
        <div class="viz-barrow">
          <span class="blabel" title="${esc(x.title)}">${esc(shortTitle(x))} · ${esc(x.day || "")}</span>
          <span class="btrack"><span class="bfill" style="width:${(x.rate / maxRate * 100).toFixed(0)}%"></span></span>
          <span class="bval">×${x.count} · ${x.rate}/1k</span>
        </div>
        ${(x.moments || []).map(m => momentHTML(m, x, q)).join("")}`).join("")
        || `<div class="viz-empty">the record never says it</div>`;
    } catch (err) {
      $("#viz-modal-body", ov).innerHTML = `<div class="viz-empty">${esc(err.message)}</div>`;
    }
  }

  /* ---------- the sections ---------- */

  function statHead(rows) {
    const read = rows.length;
    const hours = rows.reduce((a, r) => a + (r.duration || 0), 0) / 3600;
    const dec = rows.reduce((a, r) => a + (r.decisions || 0), 0);
    const qs = rows.reduce((a, r) => a + (r.questions || 0), 0);
    return `<div class="viz-head">
      <div class="stat"><b>${read}</b><span>meetings read</span></div>
      <div class="stat"><b>${hours.toFixed(1)}h</b><span>on the record</span></div>
      <div class="stat"><b>${dec}</b><span>motions & outcomes</span></div>
      <div class="stat"><b>${qs}</b><span>questions asked</span></div>
    </div>`;
  }

  /* topics over time — a line per recurring topic, rate per 1k words */
  function topicSeries(rows) {
    const tally = {};
    rows.forEach((r, ri) => (r.topics || []).forEach(t => {
      const k = (t.topic || "").toLowerCase();
      if (!k) return;
      (tally[k] = tally[k] || { name: t.topic, per: {}, total: 0, n: 0 });
      tally[k].per[ri] = rate(t.count || 0, r);
      tally[k].total += t.count || 0; tally[k].n += 1;
    }));
    return Object.values(tally).filter(t => t.n >= 2)
      .sort((a, b) => b.total - a.total).slice(0, 6);
  }

  function topicsCard(rows, focusIdx) {
    const series = topicSeries(rows);
    if (rows.length < 2 || !series.length) {
      return `<div class="viz-card"><span class="tag">topics over time</span>
        <div class="viz-empty">the long view needs at least two read meetings —
        every meeting Highlighter reads joins on its own</div></div>`;
    }
    const W = 760, H = 230, L = 46, R = 150, T = 14, B = 34;
    const iw = W - L - R, ih = H - T - B;
    const maxY = Math.max(0.1, ...series.flatMap(s => Object.values(s.per)));
    const x = i => L + (rows.length === 1 ? iw / 2 : i / (rows.length - 1) * iw);
    const y = v => T + ih - (v / maxY) * ih;
    const grid = [0.5, 1].map(f => `<line x1="${L}" y1="${y(maxY * f)}" x2="${L + iw}"
      y2="${y(maxY * f)}" stroke="var(--line-soft)" stroke-width="1"/>`).join("");
    const focus = focusIdx >= 0 ? `<rect x="${x(focusIdx) - 9}" y="${T - 4}" width="18"
      height="${ih + 8}" rx="5" fill="var(--amber)" opacity="0.13"/>` : "";
    const paths = series.map((s, si) => {
      const pts = rows.map((_, ri) => s.per[ri] !== undefined
        ? `${x(ri).toFixed(1)},${y(s.per[ri]).toFixed(1)}` : null);
      const d = pts.map((p, i) => p === null ? null
        : `${pts[i - 1] == null ? "M" : "L"}${p}`).filter(Boolean).join(" ");
      const lastIdx = rows.map((_, ri) => ri).filter(ri => s.per[ri] !== undefined).pop();
      return `<path d="${d}" fill="none" stroke="${CAT[si]}" stroke-width="2"
          stroke-linejoin="round" stroke-linecap="round"/>
        <text x="${L + iw + 8}" y="${y(s.per[lastIdx]) + 4}" font-size="11.5"
          fill="var(--cream)" font-family="var(--ui)">${esc(s.name.slice(0, 20))}</text>
        ${rows.map((_, ri) => s.per[ri] === undefined ? "" :
          `<circle cx="${x(ri)}" cy="${y(s.per[ri])}" r="3.25" fill="${CAT[si]}"
             data-hit="${si}:${ri}" style="cursor:pointer"/>`).join("")}`;
    }).join("");
    const ticks = rows.map((r, ri) => `<text x="${x(ri)}" y="${H - 10}"
      font-size="10.5" text-anchor="middle" fill="var(--cream-faint)"
      font-family="var(--mono)">${esc(shortDay(r))}</text>`).join("");
    return `<div class="viz-card"><span class="tag">topics over time — a line
        per recurring topic, per 1,000 words so a seven-hour meeting can't
        out-shout a one-hour one; click a point for its receipts</span>
      <div class="viz-svgwrap" data-viz="topics">
        <svg viewBox="0 0 ${W} ${H}">${grid}${focus}${paths}${ticks}</svg></div>
      <div class="viz-legend">${series.map((s, si) =>
        `<span><i style="background:${CAT[si]}"></i>${esc(s.name)}</span>`).join("")}
      </div></div>`;
  }

  /* framing across the record — lens rows × meeting columns, magnitude on
     the violet ramp, lens identity on its own insight color chip */
  function framingCard(rows, focusIdx) {
    const lenses = rows.find(r => (r.framing || []).length)?.framing || [];
    if (!lenses.length) {
      return `<div class="viz-card"><span class="tag">framing across the record</span>
        <div class="viz-empty">no framing counted yet</div></div>`;
    }
    const byLens = lenses.map(l => l.lens);
    const cell = (r, ri, lens) => {
      const f = (r.framing || []).find(x => x.lens === lens);
      const share = f ? f.share : 0, n = f ? f.count : 0;
      return `<div class="viz-cell${ri === focusIdx ? " viz-col-focus" : ""}"
        data-n="${n}" data-fr="${esc(lens)}:${ri}"
        style="background:${n ? RAMP(share * 2.2) : "var(--ink-2)"}"></div>`;
    };
    return `<div class="viz-card"><span class="tag">framing across the record —
        eight civic lenses, every meeting; deeper violet = more of the
        meeting's words through that lens. Click a cell for the moments.</span>
      <div class="viz-grid" data-viz="framing"
        style="grid-template-columns:170px repeat(${rows.length},1fr)">
        ${byLens.map(lens => {
          const li = lenses.findIndex(x => x.lens === lens);
          return `<span class="viz-rowlabel"><i style="background:${lenses[li].color}"></i>
            ${esc(lens)}</span>${rows.map((r, ri) => cell(r, ri, lens)).join("")}`;
        }).join("")}
        <span></span>${rows.map(r => `<span class="viz-axis"
          title="${esc(r.title)}">${esc(shortDay(r))}</span>`).join("")}
      </div></div>`;
  }

  /* who keeps appearing — entities as dot-strips, dot area = mentions */
  function entityCard(rows, union, focusIdx) {
    const top = (union || []).slice(0, 12);
    if (!top.length) {
      return `<div class="viz-card"><span class="tag">who keeps appearing</span>
        <div class="viz-empty">no recurring names yet</div></div>`;
    }
    const maxN = Math.max(1, ...top.flatMap(u => Object.values(u.per)));
    return `<div class="viz-card"><span class="tag">who keeps appearing —
        names the record hears again and again; the dot grows with the
        mentions. Click a dot to read those moments.</span>
      <div class="viz-grid" data-viz="entities"
        style="grid-template-columns:210px repeat(${rows.length},1fr)">
        ${top.map((u, ui) => `
          <span class="viz-rowlabel" title="${esc(u.name)}${u.also?.length
            ? " — also spelled " + esc(u.also.join(", ")) : ""}">
            <span class="hl-kind hl-kind-${u.kind}">${u.kind}</span>${esc(u.name)}
            <span class="hint" style="margin-left:auto">×${u.total}</span></span>
          ${rows.map((r, ri) => {
            const n = u.per[ri] || 0;
            const d = n ? Math.max(7, Math.sqrt(n / maxN) * 24) : 0;
            return `<span class="viz-dot${ri === focusIdx ? " viz-col-focus" : ""}"
              data-ent="${ui}:${ri}"><i style="width:${d}px;height:${d}px;
              ${n ? "" : "background:var(--line-soft);width:4px;height:4px"}"></i></span>`;
          }).join("")}`).join("")}
        <span></span>${rows.map(r => `<span class="viz-axis"
          title="${esc(r.title)}">${esc(shortDay(r))}</span>`).join("")}
      </div></div>`;
  }

  /* trace anything — the discourse engine as a front door */
  const traceCard = () => `
    <div class="viz-card"><span class="tag">trace anything through the years —
        a name, a street, a phrase; counted per meeting with receipts</span>
      <div style="display:flex;gap:8px;margin-top:8px">
        <input type="text" id="viz-traceq" placeholder="crosswalk, override, a name…"
          style="flex:1" />
        <button class="btn primary" id="viz-tracego">Trace</button>
      </div></div>`;

  function aiCard() {
    return `<div class="viz-card"><span class="tag">the read across meetings —
        generative, your key, counted inputs only (no transcripts leave this
        machine)</span>
      <div style="display:flex;gap:8px;margin-top:8px;align-items:center">
        <button class="btn" id="viz-aigo">🤖 Ask for the read</button>
        <span class="hint" id="viz-aiusage"></span></div>
      <div id="viz-aiout" style="display:none;margin-top:10px;font-size:13.5px;
        line-height:1.65;white-space:pre-wrap"></div>
      <div class="viz-note" id="viz-aiorigin" style="margin-top:6px"></div>
    </div>`;
  }

  /* focus header — the open meeting held against the record */
  function focusCard(rows, union, focusIdx) {
    const me = rows[focusIdx];
    if (!me) return "";
    const mine = new Set((me.topics || []).map(t => (t.topic || "").toLowerCase()));
    const shared = topicSeries(rows).filter(s =>
      mine.has(s.name.toLowerCase()) && Object.keys(s.per).length >= 2);
    const faces = (union || []).filter(u => u.per[focusIdx] &&
      Object.keys(u.per).length >= 2).slice(0, 6);
    return `<div class="viz-card"><span class="tag">this meeting against the
        record</span>
      <div class="viz-note">${esc(shortTitle(me))} · ${esc(me.day || "undated")} —
        what tonight shares with the rest of the shelf; click anything to trace it</div>
      <div style="display:flex;gap:7px;flex-wrap:wrap;margin-top:4px">
        ${shared.map(s => `<button class="tpill" data-trace="${esc(s.name)}"
          title="everywhere the record says it">${esc(s.name)} ·
          ${Object.keys(s.per).length} meetings</button>`).join("")}
        ${faces.map(u => `<button class="tpill" data-trace="${esc(u.name)}"
          title="${esc(u.kind)} · ×${u.total} across the record">${esc(u.name)} ·
          ×${u.total}</button>`).join("")}
        ${shared.length + faces.length ? "" :
          `<span class="viz-empty">nothing here recurs elsewhere yet — the
           record is young</span>`}
      </div></div>`;
  }

  /* ---------- wiring ---------- */
  function wire(box, rows, union, data) {
    const sByHit = topicSeries(rows);
    box.addEventListener("mousemove", e => {
      const c = e.target.closest && e.target.closest("[data-hit],[data-fr],[data-ent],.viz-axis");
      if (!c) { hideTip(); return; }
      if (c.dataset.hit) {
        const [si, ri] = c.dataset.hit.split(":").map(Number);
        const s = sByHit[si], r = rows[ri];
        showTip(e, `<div class="tt">${esc(s.name)}</div>
          <div>${(s.per[ri] || 0).toFixed(2)} per 1k words</div>
          <div class="td">${esc(r.title || "")} · ${esc(r.day || "")}</div>
          <div class="td">click for the receipts</div>`);
      } else if (c.dataset.fr) {
        const [lens, ri] = c.dataset.fr.split(":");
        const r = rows[+ri];
        const f = (r.framing || []).find(x => x.lens === lens);
        showTip(e, `<div class="tt">${esc(lens)}</div>
          <div>×${f ? f.count : 0} moments ·
            ${f ? (f.share * 100).toFixed(1) : 0}% of framed words ·
            ${f ? esc(f.drift) : "—"}</div>
          <div class="td">${esc(r.title || "")} · ${esc(r.day || "")}</div>`);
      } else if (c.dataset.ent) {
        const [ui, ri] = c.dataset.ent.split(":").map(Number);
        const u = union[ui], r = rows[ri];
        showTip(e, `<div class="tt">${esc(u.name)}</div>
          <div>×${u.per[ri] || 0} in this meeting · ×${u.total} on the record</div>
          <div class="td">${esc(r.title || "")} · ${esc(r.day || "")}</div>`);
      } else if (c.classList.contains("viz-axis")) {
        showTip(e, `<div class="tt">${esc(c.title)}</div>`);
      }
    });
    box.addEventListener("mouseleave", hideTip, true);
    box.addEventListener("click", e => {
      const tr = e.target.closest && e.target.closest("[data-trace]");
      if (tr) { traceModal(tr.dataset.trace); return; }
      const hit = e.target.closest && e.target.closest("[data-hit]");
      if (hit) {
        const [si, ri] = hit.dataset.hit.split(":").map(Number);
        traceModal(sByHit[si].name, rows[ri].source);
        return;
      }
      const fr = e.target.closest && e.target.closest("[data-fr]");
      if (fr) {
        const [lens, ri] = fr.dataset.fr.split(":");
        const r = rows[+ri];
        const f = (r.framing || []).find(x => x.lens === lens);
        if (!f || !f.count) return;
        modal(`${esc(lens)} framing`, `${esc(r.title || "")} · ×${f.count} ·
          ${esc(f.drift)} across the meeting`,
          (f.moments || []).map(m => momentHTML(m, r, lens)).join("")
          || `<div class="viz-empty">counted, but the example moments weren't
              kept — open the meeting's analyzer for the full set</div>`);
        return;
      }
      const en = e.target.closest && e.target.closest("[data-ent]");
      if (en) {
        const [ui, ri] = en.dataset.ent.split(":").map(Number);
        if (union[ui].per[ri]) traceModal(union[ui].name, rows[ri].source);
        return;
      }
    });
    const tq = $("#viz-traceq", box), tgo = $("#viz-tracego", box);
    if (tgo) {
      const run = () => { if (tq.value.trim().length >= 3) traceModal(tq.value.trim()); };
      tgo.onclick = run;
      tq.onkeydown = e => { if (e.key === "Enter") run(); };
    }
    const ai = $("#viz-aigo", box);
    if (ai) ai.onclick = async () => {
      ai.disabled = true; ai.textContent = "reading…";
      try {
        const job = await api("/api/kb/ai-compare", {});
        const done = await jobDone(job.id);
        if (done.status === "error") throw new Error(done.error);
        $("#viz-aiout", box).style.display = "";
        $("#viz-aiout", box).textContent = done.result.text;
        $("#viz-aiorigin", box).textContent = done.result.origin
          + (done.result.usage ? ` · ${done.result.usage}` : "");
      } catch (err) { toast(err.message, true); }
      ai.disabled = false; ai.textContent = "🤖 Ask for the read";
    };
  }

  /* ---------- the door ---------- */
  async function renderInto(container, opts = {}) {
    container.innerHTML = `<div class="viz-empty">reading the record…</div>`;
    let data;
    try { data = await matrix(); }
    catch (err) {
      container.innerHTML = `<div class="viz-empty">${esc(err.message)}</div>`;
      return;
    }
    const rows = data.rows || [], union = data.entity_union || [];
    if (!rows.length) {
      container.innerHTML = `<div class="viz-empty">nothing read yet — open a
        meeting in Highlighter (or send one to the record) and the analytics
        draw themselves</div>`;
      return;
    }
    const focusIdx = opts.focus ? rows.findIndex(r => r.source === opts.focus) : -1;
    container.innerHTML = `<div class="viz">
      ${focusIdx >= 0 ? focusCard(rows, union, focusIdx) : statHead(rows)}
      ${topicsCard(rows, focusIdx)}
      ${framingCard(rows, focusIdx)}
      ${entityCard(rows, union, focusIdx)}
      ${traceCard()}
      ${aiCard()}
      ${data.skipped?.length ? `<div class="viz-note">not counted (no words
        yet): ${esc(data.skipped.join(" · "))}</div>` : ""}
    </div>`;
    wire(container, rows, union, data);
  }

  return { renderInto, traceModal, contextModal,
           invalidate: () => { cache = null; } };
})();
