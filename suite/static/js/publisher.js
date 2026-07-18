/* Community Publisher — the review queue around the publish kit.
   Open anything Highlighter can read (a local program with sidecars, or a
   URL-session folder): candidates arrive picked, copy arrives drafted and
   labeled, and the kit renders as one queue job — three frames, captions
   burned, the station on the clip. Nothing publishes itself: the producer
   reads, tweaks, approves, exports. */

const PublisherPage = (() => {
  const T = toolById("publisher");
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-publisher";

  el.innerHTML = `
  <div class="ws" style="--acc:${T.acc}">
    <div class="mediabar">
      <span class="toolname"><i>Community Publisher</i> · gets it seen</span>
      <span class="beta-chip" title="beta — every word and cut deserves your eyes before it ships">beta</span>
      <input type="text" id="pb-path" spellcheck="false"
        placeholder="/path/to/program.mp4 — or a Highlighter session folder"
        style="flex:1;min-width:200px;background:var(--ink);border:1px solid var(--line);border-radius:7px;padding:6px 9px;font-size:12px;font-family:var(--mono);color:var(--cream)">
      <button class="btn" id="pb-open" style="width:auto">Open</button>
      <button class="btn" id="pb-browse" style="width:auto">Browse…</button>
    </div>
    <div class="ws-body">
      <div class="ws-center" id="pb-center" style="overflow-y:auto;padding:16px 20px"></div>
      <div class="inspector">
        <div class="insp-head"><h2>Publisher</h2></div>
        <div class="insp-sec">
          <span class="tag">brand kit — every export wears it</span>
          <div class="field"><label>station</label><input id="pb-station" type="text" spellcheck="false"></div>
          <div class="field"><label>second line</label><input id="pb-line2" type="text" spellcheck="false"></div>
          <div class="field"><label>accent</label><input id="pb-accent" type="color" style="width:52px;height:26px;padding:1px"></div>
          <div class="field"><label>third style</label>
            <select id="pb-style"><option>bar</option><option>block</option><option>line</option><option>clean</option></select></div>
          <div class="field"><label>third holds</label>
            <input id="pb-ltsec" type="number" min="0" max="10" step="0.5" style="width:64px"> s
            <span class="hint" style="display:inline">0 = no lower-third</span></div>
          <div class="field"><label><input type="checkbox" id="pb-caps"> burn captions</label></div>
          <div class="field"><label>copy voice</label>
            <select id="pb-voice"><option>station</option><option>casual</option><option>series</option></select></div>
          <button class="btn" id="pb-brandsave" style="margin-top:6px">Save brand</button>
        </div>
        <div class="insp-sec">
          <span class="tag">ai copy</span>
          <div class="hint" id="pb-aistat">—</div>
        </div>
        <div class="report" id="pb-report"></div>
      </div>
    </div>
  </div>`;

  const S = { source: null, meta: null, video: null, kit: null, saveTimer: 0 };
  const RATIOS = ["16x9", "1x1", "9x16"];
  const fmtT = t => { t = Math.max(0, Math.round(t)); return t >= 3600
    ? `${Math.floor(t / 3600)}:${String(Math.floor(t % 3600 / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`
    : `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`; };

  /* ---------- open ---------- */
  async function open(path) {
    if (!path) return;
    $("#pb-path", el).value = path;
    const box = $("#pb-center", el);
    box.innerHTML = `<div class="hint" style="padding:16px 2px">reading the sidecars…</div>`;
    try {
      const r = await api("/api/publisher/open", { path });
      S.source = r.source; S.meta = r.meta; S.video = r.video; S.kit = r.kit;
      S.fps = 0;
      if (S.video) {
        try {
          const info = await api("/api/media/open", { path: S.video, tool: "publisher" });
          S.fps = (info.video && info.video.fps) || 30;
        } catch (e) { S.fps = 30; }
      }
      if (!S.kit) {
        box.innerHTML = `<div class="empty-grain" style="padding:34px 6px;color:var(--cream-dim);max-width:520px">
          no transcript or highlights beside this yet — the kit builds from the record.<br><br>
          <button class="btn" id="pb-tohl" style="width:auto">Open it in Highlighter first</button></div>`;
        $("#pb-tohl", box).onclick = () => go("highlighter", { openPath: S.source });
        return;
      }
      renderKit();
    } catch (e) { box.innerHTML = `<div class="progmsg err" style="padding:14px 2px">${esc(e.message)}</div>`; }
  }

  function save() {
    clearTimeout(S.saveTimer);
    S.saveTimer = setTimeout(async () => {
      try { await api("/api/publisher/save", { source: S.source, kit: S.kit }); }
      catch (e) { toast(e.message, true); }
    }, 600);
  }

  /* ---------- the kit screen ---------- */
  function renderKit() {
    const k = S.kit, c = k.copy || {};
    const box = $("#pb-center", el);
    const clips = k.clips.map((cl, i) => {
      const tall = cl.ratios.some(r => r !== "16x9");
      const mid = (cl.start + cl.end) / 2;
      const thumb = (S.video && S.fps)
        ? `<img class="pb-cthumb" loading="lazy" alt=""
            src="${frameURL(S.video, Math.round(mid * S.fps), 120)}"
            onerror="if(!this.dataset.r){this.dataset.r=1;this.src+='&r='+Date.now()}else{this.style.visibility='hidden'}">` : "";
      return `<div class="pb-clip${cl.keep ? "" : " off"}" data-i="${i}">
        <label class="pb-keep"><input type="checkbox" data-keep="${i}" ${cl.keep ? "checked" : ""}></label>
        ${thumb}
        <div style="flex:1;min-width:0">
          <div class="pb-cliplabel">${esc(cl.label || "clip " + (i + 1))}</div>
          <div class="pb-cliptime">
            <span>${fmtT(cl.start)} → ${fmtT(cl.end)} · ${(cl.end - cl.start).toFixed(1)}s</span>
            <span class="pb-nudge">in <button data-n="${i}:start:-0.5">−</button><button data-n="${i}:start:0.5">+</button>
            out <button data-n="${i}:end:-0.5">−</button><button data-n="${i}:end:0.5">+</button></span>
          </div>
          <div class="pb-ratios">${RATIOS.map(r => `<button class="pb-pill${cl.ratios.includes(r) ? " on" : ""}" data-r="${i}:${r}">${r.replace("x", ":")}</button>`).join("")}
            ${tall ? `<span class="pb-off">frame <input type="range" min="-1" max="1" step="0.05" value="${cl.offset || 0}" data-off="${i}" title="slide the square/vertical crop"></span>` : ""}
          </div>
          <div class="pb-why">${(cl.reasons || []).slice(0, 3).map(r => `<span>${esc(r)}</span>`).join("")}</div>
        </div>
      </div>`;
    }).join("");

    const files = (k.files || []).length ? `
      <div class="tag" style="margin-top:18px">rendered — ${k.files.length} files</div>
      ${k.files.map(f => `<div class="batchrow"><span class="bname">${esc(f.path.split("/").pop())}</span>
        <span class="bstat">${f.kind}${f.captions != null ? ` · ${f.captions} caps` : ""}</span>
        <button data-rev="${esc(f.path)}">Reveal</button></div>`).join("")}` : "";

    box.innerHTML = `
      <div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap">
        <h1 style="font-size:19px">${esc(S.meta.title)}</h1>
        <span class="hint">${esc(S.meta.date || "")}</span>
        <button class="btn" id="pb-rebuild" style="width:auto;margin-left:auto"
          title="fresh candidates + fresh extractive copy — your edits reset">↺ Rebuild kit</button>
      </div>
      <div class="tag" style="margin-top:14px">the clips — keep, trim, frame</div>
      ${clips}
      <div class="tag" style="margin-top:20px">the words — <span id="pb-origin" style="text-transform:none;letter-spacing:0">${esc(c.origin || "")}</span></div>
      <div class="pb-copy">
        ${(c.titles || []).map((t, i) => `<div class="field"><label>title ${i + 1}
          <button class="pb-cp" data-cp="titles:${i}" title="copy to clipboard">⧉</button></label>
          <input type="text" data-c="titles:${i}" value="${esc(t)}"></div>`).join("")}
        <div class="field"><label>description
          <button class="pb-cp" data-cp="description" title="copy to clipboard">⧉</button></label>
          <textarea data-c="description" rows="7">${esc(c.description || "")}</textarea></div>
        <div class="field"><label>newsletter
          <button class="pb-cp" data-cp="newsletter" title="copy to clipboard">⧉</button></label>
          <textarea data-c="newsletter" rows="3">${esc(c.newsletter || "")}</textarea></div>
        <div class="field"><label>social · vertical
          <button class="pb-cp" data-cp="social.vertical" title="copy to clipboard">⧉</button></label>
          <input type="text" data-c="social.vertical" value="${esc((c.social || {}).vertical || "")}"></div>
        <div class="field"><label>social · feed
          <button class="pb-cp" data-cp="social.feed" title="copy to clipboard">⧉</button></label>
          <input type="text" data-c="social.feed" value="${esc((c.social || {}).feed || "")}"></div>
        <div class="field"><label>alt text
          <button class="pb-cp" data-cp="alt" title="copy all to clipboard">⧉</button><br>
          <span class="hint">one per clip</span></label>
          <textarea data-c="alt" rows="${Math.max(2, (c.alt_text || []).length)}">${esc((c.alt_text || []).join("\n"))}</textarea></div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:4px">
          <button class="btn" id="pb-ai" style="width:auto">✨ Redraft with AI</button>
          <input type="text" id="pb-instr" placeholder="optional instruction — “shorter, warmer”"
            style="flex:1;min-width:180px;background:var(--ink);border:1px solid var(--line);border-radius:7px;padding:6px 9px;font-size:12px;color:var(--cream)">
          <button class="btn" id="pb-restore" style="width:auto;display:${k.copy_prev ? "" : "none"}">↩ previous copy</button>
        </div>
      </div>
      <div class="tag" style="margin-top:20px">render & export</div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:6px">
        <div class="field" style="flex:1;min-width:200px;margin-top:0"><label>lower-third · line 1</label>
          <input type="text" id="pb-lt1" value="${esc((k.lt || {}).line1 || "")}"
            placeholder="${esc(S.brand && S.brand.station ? S.brand.station : (S.meta.title || "").slice(0, 40))}"></div>
        <div class="field" style="flex:1;min-width:200px;margin-top:0"><label>lower-third · line 2</label>
          <input type="text" id="pb-lt2" value="${esc((k.lt || {}).line2 || "")}"
            placeholder="${esc(S.brand && S.brand.station ? (S.meta.title || "").slice(0, 40) : (S.meta.date || ""))}"></div>
      </div>
      ${S.video ? "" : `<div class="progmsg err" style="margin:6px 0">no local recording yet — fetch the full video in Highlighter, then render.
        <button class="btn" id="pb-tohl2" style="width:auto;margin-left:8px">Open in Highlighter</button></div>`}
      <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;align-items:center">
        <button class="btn primary" id="pb-render" style="width:auto" ${S.video ? "" : "disabled"}>Render kit</button>
        <button class="btn" id="pb-bundle" style="width:auto" ${(k.files || []).some(f => f.kind === "clip") ? "" : "disabled"}>Export bundle (zip)</button>
        ${recordBtnHTML("pb-record")}
        <span class="hint" id="pb-jobstat"></span>
      </div>
      ${files}`;

    /* wire it */
    $$("input[data-keep]", box).forEach(x => x.onchange = () => {
      k.clips[+x.dataset.keep].keep = x.checked; save(); renderKit(); });
    $$("button[data-n]", box).forEach(b => b.onclick = () => {
      const [i, key, d] = b.dataset.n.split(":");
      const cl = k.clips[+i];
      cl[key] = Math.max(0, +(cl[key] + parseFloat(d)).toFixed(2));
      if (cl.end - cl.start < 1) cl.end = cl.start + 1;
      save(); renderKit(); });
    $$(".pb-pill", box).forEach(b => b.onclick = () => {
      const [i, r] = b.dataset.r.split(":");
      const cl = k.clips[+i];
      cl.ratios = cl.ratios.includes(r) ? cl.ratios.filter(x => x !== r)
        : [...cl.ratios, r];
      save(); renderKit(); });
    $$("input[data-off]", box).forEach(x => x.oninput = () => {
      k.clips[+x.dataset.off].offset = parseFloat(x.value); save(); });
    $$("[data-c]", box).forEach(x => x.onchange = () => {
      const path = x.dataset.c;
      if (path === "alt") k.copy.alt_text = x.value.split("\n").filter(s => s.trim());
      else if (path.startsWith("titles:")) k.copy.titles[+path.split(":")[1]] = x.value;
      else if (path.startsWith("social.")) (k.copy.social = k.copy.social || {})[path.split(".")[1]] = x.value;
      else k.copy[path] = x.value;
      if (!/· your edits$/.test(k.copy.origin || "")) k.copy.origin = (k.copy.origin || "") + " · your edits";
      $("#pb-origin", box).textContent = k.copy.origin;
      save(); });
    $$("button[data-rev]", box).forEach(b => b.onclick = () =>
      api("/api/media/reveal", { path: b.dataset.rev }).catch(e => toast(e.message, true)));
    $$(".pb-cp", box).forEach(b => b.onclick = e => {
      e.preventDefault();
      const p = b.dataset.cp;
      const c2 = k.copy || {};
      let v = "";
      if (p === "alt") v = (c2.alt_text || []).join("\n");
      else if (p.startsWith("titles:")) v = (c2.titles || [])[+p.split(":")[1]] || "";
      else if (p.startsWith("social.")) v = ((c2.social || {})[p.split(".")[1]]) || "";
      else v = c2[p] || "";
      navigator.clipboard.writeText(v).then(
        () => toast("copied — paste it where it publishes"),
        () => toast("the browser blocked the clipboard — select and copy by hand", true));
    });
    const lt1 = $("#pb-lt1", box), lt2 = $("#pb-lt2", box);
    [lt1, lt2].forEach(x => x.onchange = () => {
      k.lt = { line1: lt1.value.trim(), line2: lt2.value.trim() };
      if (!k.lt.line1 && !k.lt.line2) delete k.lt;
      save();
    });
    $("#pb-record", box).onclick = ev =>
      sendToRecord({ path: S.source }, ev.currentTarget);
    $("#pb-rebuild", box).onclick = rebuild;
    $("#pb-ai", box).onclick = redraft;
    const r2 = $("#pb-restore", box);
    if (r2) r2.onclick = () => { k.copy = k.copy_prev; delete k.copy_prev; save(); renderKit(); };
    const hl2 = $("#pb-tohl2", box);
    if (hl2) hl2.onclick = () => go("highlighter", { openPath: S.source });
    $("#pb-render", box).onclick = renderJob;
    $("#pb-bundle", box).onclick = bundleJob;
  }

  async function rebuild() {
    try {
      const r = await api("/api/publisher/kit", { source: S.source });
      S.kit = r.kit; renderKit(); toast("kit rebuilt from the record");
    } catch (e) { toast(e.message, true); }
  }

  async function redraft() {
    const btn = $("#pb-ai", el);
    btn.disabled = true; btn.textContent = "✨ drafting…";
    try {
      const r = await api("/api/publisher/copy-ai",
        { source: S.source, instruction: $("#pb-instr", el).value.trim() });
      const prev = S.kit.copy;
      S.kit = r.kit;
      S.kit.copy_prev = prev;
      S.kit.copy = Object.assign({}, prev, S.kit.copy_ai);
      save(); renderKit();
      toast("drafted on your key — read it before it ships");
    } catch (e) { toast(e.message, true); }
    finally { btn.disabled = false; btn.textContent = "✨ Redraft with AI"; }
  }

  async function renderJob() {
    try {
      const job = await api("/api/publisher/render", { source: S.source });
      const p = czProgress($(".inspector", el), {
        label: "rendering the kit", acc: "var(--publisher)" });
      watchJob(job.id, j => p.update(j));
      const done = await jobDone(job.id);
      p.finish(done);
      if (done.status === "done") { toast("kit rendered"); open(S.source); }
      else if (done.status === "error") toast(done.error, true);
    } catch (e) { toast(e.message, true); }
  }

  async function bundleJob() {
    try {
      const job = await api("/api/publisher/bundle", { source: S.source });
      const p = czProgress($(".inspector", el), {
        label: "exporting the bundle", acc: "var(--publisher)" });
      watchJob(job.id, j => p.update(j));
      const done = await jobDone(job.id);
      p.finish(done);
      if (done.status === "done") {
        const rep = $("#pb-report", el);
        rep.classList.add("show");
        rep.innerHTML += `<b>bundle →</b> ${esc(done.result.out)}\n<b>zip →</b> ${esc(done.result.written[0])}\n`;
        toast("bundle exported — nothing left to rename");
        api("/api/media/reveal", { path: done.result.out }).catch(() => {});
      } else if (done.status === "error") toast(done.error, true);
    } catch (e) { toast(e.message, true); }
  }

  /* ---------- brand + status ---------- */
  async function loadStatus() {
    try {
      const st = await api("/api/publisher/status");
      const b = st.brand;
      S.brand = b;
      $("#pb-station", el).value = b.station; $("#pb-line2", el).value = b.line2;
      $("#pb-accent", el).value = b.accent; $("#pb-style", el).value = b.style;
      $("#pb-ltsec", el).value = b.lt_seconds; $("#pb-caps", el).checked = b.captions;
      $("#pb-voice", el).value = b.voice;
      $("#pb-aistat", el).innerHTML = st.ai.enabled
        ? `key ${esc(st.ai.key_masked)} · ${esc(st.ai.model)} — redrafts spend it only when you click`
        : `no key — copy stays extractive (Settings → AI to add yours)`;
    } catch (e) { /* the page still opens kits */ }
  }

  async function saveBrand() {
    try {
      await api("/api/publisher/brand", { patch: {
        station: $("#pb-station", el).value.trim(),
        line2: $("#pb-line2", el).value.trim(),
        accent: $("#pb-accent", el).value,
        style: $("#pb-style", el).value,
        lt_seconds: parseFloat($("#pb-ltsec", el).value || "4.5"),
        captions: $("#pb-caps", el).checked,
        voice: $("#pb-voice", el).value,
      } });
      toast("brand saved — every export wears it");
    } catch (e) { toast(e.message, true); }
  }

  /* ---------- wire up ---------- */
  let inited = false;
  function init() {
    $("#pb-open", el).onclick = () => open($("#pb-path", el).value.trim());
    $("#pb-path", el).addEventListener("keydown", e => {
      if (e.key === "Enter") open($("#pb-path", el).value.trim()); });
    $("#pb-browse", el).onclick = () => browseForPath(open);
    $("#pb-brandsave", el).onclick = saveBrand;
    wireDropZone($("#pb-center", el), open);
    $("#pb-center", el).innerHTML = `
      <div class="empty-grain" style="padding:40px 8px;color:var(--cream-dim);max-width:560px">
        <b>drop a program here</b> — a file with sidecars, or a Highlighter session folder.<br>
        the kit builds itself: clips picked with reasons, copy drafted and labeled,
        three frames rendered with your captions and your third.<br><br>
        <span class="hint">fresh footage? send it through the wire first:
        Grabber fetches it, Highlighter finds the moments, then this desk kits it.</span>
      </div>`;
  }

  function onshow(arg) {
    if (!inited) { init(); inited = true; }
    loadStatus();
    if (arg && arg.openPath) open(arg.openPath);
  }

  registerPage("publisher", el, onshow);
  return { onshow };
})();
