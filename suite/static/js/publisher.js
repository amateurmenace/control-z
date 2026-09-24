/* Community Publisher — a meeting in; ready-to-post clips and words out.

   Open any meeting Highlighter has read (a URL session or a local file with
   its transcript). The page walks four steps, each a card that says what
   it's for: ① the recording (clips are cut from a local copy — one click
   fetches it) ② the clips (the strongest moments arrive picked, with their
   reasons; keep, trim, choose shapes) ③ the words (titles, description,
   newsletter, social posts, alt text — drafted from what was actually
   said, labeled, editable) ④ the kit (render the clips; export one folder
   + zip). Nothing publishes itself — the producer reads, tweaks, approves,
   exports. Every kit lands in ONE named folder, shown on the page. */

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
      <span class="clipmeta" id="pb-title" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"></span>
      <button class="btn" id="pb-back" style="width:auto;display:none">← meetings</button>
    </div>
    <div class="ws-body">
      <div class="ws-center" id="pb-center" style="overflow-y:auto;padding:18px 22px 40px"></div>
      <div class="inspector">
        <div class="insp-head"><h2>Your station's look</h2></div>
        <div class="insp-sec">
          <div class="hint" style="margin-bottom:6px">every clip wears this — set it once</div>
          <div class="field"><label>station name</label><input id="pb-station" type="text" spellcheck="false" placeholder="e.g. Brookline Interactive Group"></div>
          <div class="field"><label>second line</label><input id="pb-line2" type="text" spellcheck="false" placeholder="e.g. community media"></div>
          <div class="field"><label>accent color</label><input id="pb-accent" type="color" style="width:52px;height:26px;padding:1px"></div>
          <div class="field"><label>name-bar style</label>
            <select id="pb-style"><option value="bar">bar</option><option value="block">block</option>
              <option value="line">line</option><option value="clean">clean</option></select></div>
          <div class="field"><label>name bar stays on screen</label>
            <input id="pb-ltsec" type="number" min="0" max="10" step="0.5" style="width:64px"> seconds
            <span class="hint" style="display:block">0 = no name bar</span></div>
          <div class="checkrow"><input type="checkbox" id="pb-caps">
            <span>burn captions into every clip <div class="hint">most people watch social video with the sound off</div></span></div>
          <div class="field"><label>writing voice</label>
            <select id="pb-voice"><option value="station">station — plain, factual</option>
              <option value="casual">casual — warm, conversational</option>
              <option value="series">series — matches past episodes</option></select></div>
          <button class="btn" id="pb-brandsave" style="margin-top:8px">Save the look</button>
        </div>
        <div class="insp-sec">
          <span class="tag">where kits are saved</span>
          <div id="pb-dest"></div>
        </div>
        <div class="insp-sec">
          <span class="tag">AI rewrites</span>
          <div class="hint" id="pb-aistat">—</div>
        </div>
        <div class="report" id="pb-report"></div>
      </div>
    </div>
  </div>`;

  const S = { source: null, meta: null, video: null, kit: null, saveTimer: 0,
              kitDir: "", url: null, session: false, brand: null, ai: null };
  const RATIOS = [["16x9", "16:9", "YouTube · web"], ["1x1", "1:1", "Facebook · Instagram feed"],
                  ["9x16", "9:16", "Reels · Shorts · TikTok"]];
  const fmtT = t => { t = Math.max(0, Math.round(t)); return t >= 3600
    ? `${Math.floor(t / 3600)}:${String(Math.floor(t % 3600 / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`
    : `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`; };
  const home = () => (CZ.appInfo && CZ.appInfo.home) || "";
  const tilde = p => home() && (p || "").startsWith(home()) ? "~" + p.slice(home().length) : (p || "");

  /* ---------- the landing: what this is, how it goes, what to open ---------- */
  async function landing() {
    flushSave();
    S.source = null;
    $("#pb-title", el).textContent = "";
    $("#pb-back", el).style.display = "none";
    const box = $("#pb-center", el);
    box.innerHTML = `
      <div class="cz-hero" style="--acc:${T.acc}">
        <div class="tag">community publisher</div>
        <h1>Turn a meeting into <span class="mark">ready-to-post clips and words</span>.</h1>
        <p>Publisher takes a meeting you've read in Highlighter and makes the things you post
          about it: short video clips in the three shapes social media wants — with captions
          burned in and your station's name on screen — plus titles, a description, a newsletter
          blurb, social posts and alt text, all drafted from what was actually said. You check
          every piece; nothing posts itself.</p>
        <div class="cz-how">
          <div class="cz-how-step"><span class="cz-how-n">1</span><b>Pick a meeting</b>
            one Highlighter has read — below, or drop a file here</div>
          <div class="cz-how-step"><span class="cz-how-n">2</span><b>Choose the clips</b>
            the strongest moments arrive picked, with reasons — keep, trim, pick shapes</div>
          <div class="cz-how-step"><span class="cz-how-n">3</span><b>Check the words</b>
            titles, description and posts, drafted from the transcript — edit freely</div>
          <div class="cz-how-step"><span class="cz-how-n">4</span><b>Make the kit</b>
            render the clips, then export one folder (and a .zip) ready to upload</div>
        </div>
        <div class="cz-outs">
          ${RATIOS.map(([, l, w]) => `<span class="cz-out">${l} · ${w}</span>`).join("")}
          <span class="cz-out">captions burned in</span><span class="cz-out">thumbnails</span>
          <span class="cz-out">copy.md</span><span class="cz-out">one .zip</span>
        </div>
      </div>
      <div class="tag" style="margin-top:20px">meetings ready to publish — they have words</div>
      <div id="pb-shelf" class="cz-shelf"><div class="hint">looking…</div></div>
      <div class="cz-pick">
        <input type="text" id="pb-path" spellcheck="false"
          placeholder="…or paste a path — a video file with its transcript, or a Highlighter meeting folder">
        <button class="btn" id="pb-open" style="width:auto">Open</button>
        <button class="btn" id="pb-browse" style="width:auto">Browse…</button>
      </div>
      <div class="hint" style="margin-top:8px">New meeting? It goes down the line first:
        <a href="#" data-go="grabber">Grabber</a> fetches it → <a href="#" data-go="highlighter">Highlighter</a>
        reads it → it shows up here.</div>`;
    $("#pb-open", box).onclick = () => open($("#pb-path", box).value.trim());
    $("#pb-path", box).addEventListener("keydown", e => {
      if (e.key === "Enter") open($("#pb-path", box).value.trim()); });
    $("#pb-browse", box).onclick = () => browseForPath(open);
    $$("[data-go]", box).forEach(a => a.onclick = e => { e.preventDefault(); go(a.dataset.go); });
    let rows = [];
    try { rows = (await api("/api/publisher/library")).rows || []; } catch (e) {}
    if (S.source) return;          // an open beat the shelf here
    const shelf = $("#pb-shelf", box);
    if (!shelf) return;
    shelf.innerHTML = rows.length ? rows.slice(0, 24).map(r => `
      <button class="cz-shelf-item" style="--acc:${T.acc}" data-open="${esc(r.source)}">
        <b title="${esc(r.title)}">${esc(r.title)}</b>
        <span>${r.duration ? fmtT(r.duration) + " · " : ""}${r.video ? "video on this computer" : "words only — the video downloads in step 1"}</span>
      </button>`).join("")
      : `<div class="hint">none yet — read a meeting in Highlighter first and it appears here</div>`;
    $$("[data-open]", shelf).forEach(b => b.onclick = () => open(b.dataset.open));
  }

  /* ---------- open ---------- */
  async function open(path) {
    if (!path) return;
    flushSave();
    const box = $("#pb-center", el);
    box.innerHTML = `<div class="hint" style="padding:16px 2px">reading the meeting…</div>`;
    try {
      const r = await api("/api/publisher/open", { path });
      Object.assign(S, { source: r.source, meta: r.meta, video: r.video, kit: r.kit,
        kitDir: r.kit_dir, url: r.url, session: r.session, fps: 0 });
      $("#pb-title", el).textContent = S.meta.title || "";
      $("#pb-back", el).style.display = "";
      if (S.video) {
        try {
          const info = await api("/api/media/open", { path: S.video, tool: "publisher" });
          S.fps = (info.video && info.video.fps) || 30;
        } catch (e) { S.fps = 30; }
      }
      if (!S.kit) {
        box.innerHTML = `<div class="cz-step current" style="--acc:${T.acc};max-width:640px">
          <div class="cz-step-head"><span class="cz-step-num">!</span><h2>This meeting has no words yet</h2></div>
          <div class="cz-step-sub">Publisher picks clips and drafts posts from the transcript. Open it in
            Highlighter first — it reads the captions in a few seconds — then come back.</div>
          <div class="cz-row"><button class="btn primary cz-bigbtn" id="pb-tohl" style="--acc:var(--highlighter)">Open it in Highlighter</button>
            <button class="btn" id="pb-back2" style="width:auto">← back</button></div></div>`;
        $("#pb-tohl", box).onclick = () => go("highlighter", { openPath: S.source });
        $("#pb-back2", box).onclick = landing;
        return;
      }
      renderKit();
    } catch (e) {
      box.innerHTML = `<div class="progmsg err" style="padding:14px 2px">${esc(e.message)}</div>
        <button class="btn" id="pb-back3" style="width:auto;margin-top:8px">← back</button>`;
      $("#pb-back3", box).onclick = landing;
    }
  }

  function save() {
    clearTimeout(S.saveTimer);
    const source = S.source, kit = S.kit;     // this meeting's, whatever opens next
    S.saveTimer = setTimeout(async () => {
      S.saveTimer = 0;
      try { await api("/api/publisher/save", { source, kit }); }
      catch (e) { toast(e.message, true); }
    }, 600);
  }
  /* leaving the kit (back, reset, another meeting) sends a pending edit NOW
     rather than letting it fire after the page has moved on */
  function flushSave() {
    if (!S.saveTimer) return;
    clearTimeout(S.saveTimer);
    S.saveTimer = 0;
    if (S.source && S.kit) {
      api("/api/publisher/save", { source: S.source, kit: S.kit })
        .catch(e => toast(e.message, true));
    }
  }

  /* ---------- the kit screen: four steps ---------- */
  function renderKit() {
    const k = S.kit, c = k.copy || {};
    const kept = k.clips.filter(cl => cl.keep);
    const nCuts = kept.reduce((a, cl) => a + (cl.ratios || []).length, 0);
    const rendered = (k.files || []).filter(f => f.kind === "clip");
    const box = $("#pb-center", el);

    const clipCard = (cl, i) => {
      const mid = (cl.start + cl.end) / 2;
      const thumb = (S.video && S.fps)
        ? `<img class="pb-cthumb" loading="lazy" alt=""
            src="${frameURL(S.video, Math.round(mid * S.fps), 120)}"
            onerror="if(!this.dataset.r){this.dataset.r=1;this.src+='&r='+Date.now()}else{this.style.visibility='hidden'}">`
        : `<div class="pb-cthumb pb-nothumb">no video yet</div>`;
      const tall = cl.ratios.some(r => r !== "16x9");
      return `<div class="pb-clip${cl.keep ? "" : " off"}" data-i="${i}">
        <label class="pb-keep" title="${cl.keep ? "in the kit — uncheck to leave it out" : "left out — check to include"}">
          <input type="checkbox" data-keep="${i}" ${cl.keep ? "checked" : ""}></label>
        ${thumb}
        <div style="flex:1;min-width:0">
          <div class="pb-cliplabel">${esc(cl.label || "clip " + (i + 1))}</div>
          <div class="pb-cliptime">
            <span>${fmtT(cl.start)} → ${fmtT(cl.end)} · ${(cl.end - cl.start).toFixed(1)}s</span>
            <span class="pb-nudge" title="nudge where the clip starts and ends, half a second at a time">start
              <button data-n="${i}:start:-0.5" aria-label="start earlier">−</button><button data-n="${i}:start:0.5" aria-label="start later">+</button>
              end <button data-n="${i}:end:-0.5" aria-label="end earlier">−</button><button data-n="${i}:end:0.5" aria-label="end later">+</button></span>
          </div>
          <div class="pb-ratios"><span class="hint" style="display:inline">shapes:</span>
            ${RATIOS.map(([r, l, w]) => `<button class="pb-pill${cl.ratios.includes(r) ? " on" : ""}"
              data-r="${i}:${r}" title="${w}" aria-pressed="${cl.ratios.includes(r)}">${l} <small>${w.split(" · ")[0]}</small></button>`).join("")}
            ${tall ? `<span class="pb-off" title="slide the square / vertical crop left or right">crop ◀
              <input type="range" min="-1" max="1" step="0.05" value="${cl.offset || 0}" data-off="${i}"> ▶</span>` : ""}
          </div>
          <div class="pb-why">${(cl.reasons || []).slice(0, 3).map(r => `<span>${esc(r)}</span>`).join("")}</div>
        </div>
      </div>`;
    };

    const words = [
      ...(c.titles || []).map((t, i) => ({ key: `titles:${i}`, label: `title option ${i + 1}`, value: t, kind: "input" })),
      { key: "description", label: "description — for YouTube or your website", value: c.description || "", kind: "area", rows: 7 },
      { key: "newsletter", label: "newsletter blurb", value: c.newsletter || "", kind: "area", rows: 3 },
      { key: "social.vertical", label: "post for Reels / Shorts / TikTok", value: (c.social || {}).vertical || "", kind: "input" },
      { key: "social.feed", label: "post for Facebook / Instagram / X", value: (c.social || {}).feed || "", kind: "input" },
      { key: "alt", label: "alt text — one line per clip, for screen readers", value: (c.alt_text || []).join("\n"), kind: "area", rows: Math.max(2, (c.alt_text || []).length) },
    ];

    const stepState = {
      rec: !!S.video, clips: kept.length > 0 && nCuts > 0, words: !!(c.titles || []).length,
      kit: rendered.length > 0,
    };
    const current = !stepState.rec ? 1 : !stepState.kit ? 4 : 5;

    box.innerHTML = `
      <div class="pb-kithead">
        <div style="min-width:0">
          <div class="tag">publish kit</div>
          <h1 style="font-size:21px;margin-top:3px">${esc(S.meta.title)}</h1>
          <div class="hint">${esc(S.meta.date || "")}${S.session ? " · read from YouTube" : " · local file"}</div>
        </div>
        <div class="pb-kitacts">${czNextHTML("publisher", S.source, { isFile: !S.session })}</div>
      </div>

      <!-- 1 · the recording -->
      <div class="cz-step ${stepState.rec ? "done" : "current"}" style="--acc:${T.acc}">
        <div class="cz-step-head"><span class="cz-step-num">${stepState.rec ? "✓" : "1"}</span>
          <h2>The recording</h2>
          <span class="cz-step-state">${stepState.rec ? "on this computer" : "needed to cut clips"}</span></div>
        ${stepState.rec
          ? `<div class="cz-step-sub">Clips are cut from <code>${esc(tilde(S.video))}</code>.</div>`
          : `<div class="cz-step-sub">Clips are cut from a copy of the video on this computer, and this
              meeting doesn't have one yet. ${S.url ? "Download it once — about a minute for most meetings." :
              "Open it in Highlighter and use “Download full video”."}</div>
             <div class="cz-row">${S.url
               ? `<button class="btn primary cz-bigbtn" id="pb-getvid">⬇ Download the video</button>
                  <select id="pb-getq" title="video quality">
                    <option value="1080" selected>1080p</option><option value="720">720p</option><option value="best">best</option></select>`
               : `<button class="btn" id="pb-tohl2" style="width:auto">Open in Highlighter</button>`}</div>
             <div id="pb-getprog"></div>`}
      </div>

      <!-- 2 · the clips -->
      <div class="cz-step ${stepState.clips ? "done" : ""}" style="--acc:${T.acc}">
        <div class="cz-step-head"><span class="cz-step-num">2</span>
          <h2>Choose the clips</h2>
          <span class="cz-step-state">${kept.length} of ${k.clips.length} kept · ${nCuts} video${nCuts === 1 ? "" : "s"} to make</span></div>
        <div class="cz-step-sub">The strongest moments, picked from the transcript — each says why.
          Uncheck what you don't want, nudge the start and end, and choose the shapes: each shape
          you pick becomes its own video file.</div>
        ${k.clips.map(clipCard).join("")}
        <div class="cz-row"><button class="btn" id="pb-rebuild" style="width:auto"
          title="pick fresh clips and redraft the words from the transcript — your edits are replaced">↺ Pick again from scratch</button></div>
      </div>

      <!-- 3 · the words -->
      <div class="cz-step ${stepState.words ? "done" : ""}" style="--acc:${T.acc}">
        <div class="cz-step-head"><span class="cz-step-num">3</span>
          <h2>Check the words</h2>
          <span class="cz-step-state" id="pb-origin">${esc(c.origin || "")}</span></div>
        <div class="cz-step-sub">Drafted from what was said in the meeting — nothing invented. Edit
          anything; ⧉ copies a piece to paste where it's posted.</div>
        <div class="pb-copy">
          ${words.map(w => `<div class="field"><label>${esc(w.label)}
              <button class="pb-cp" data-cp="${esc(w.key)}" title="copy to the clipboard">⧉ copy</button></label>
            ${w.kind === "input" ? `<input type="text" data-c="${esc(w.key)}" value="${esc(w.value)}">`
              : `<textarea data-c="${esc(w.key)}" rows="${w.rows}">${esc(w.value)}</textarea>`}</div>`).join("")}
          <div class="cz-row">
            <button class="btn" id="pb-ai" data-needs-key style="width:auto">✨ Rewrite with AI</button>
            <input type="text" id="pb-instr" placeholder="optional — how? “shorter”, “warmer”, “for teenagers”…"
              style="flex:1;min-width:180px;background:#fff;border:1px solid var(--line);border-radius:7px;padding:6px 9px;font-size:12px">
            <button class="btn" id="pb-restore" style="width:auto;display:${k.copy_prev ? "" : "none"}">↩ Undo the rewrite</button>
          </div>
        </div>
      </div>

      <!-- 4 · the kit -->
      <div class="cz-step ${stepState.kit ? "done" : stepState.rec ? "current" : ""}" style="--acc:${T.acc}">
        <div class="cz-step-head"><span class="cz-step-num">${stepState.kit ? "✓" : "4"}</span>
          <h2>Make the kit</h2>
          <span class="cz-step-state">${rendered.length ? `${rendered.length} video${rendered.length === 1 ? "" : "s"} made` : "not made yet"}</span></div>
        <div class="cz-step-sub">First make the videos (they wear your station's look — set it on the
          right). Then export: one folder with the videos, thumbnails, the words (copy.md), the
          transcript — and a .zip of it all, ready to hand off or upload.</div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px">
          <div class="field" style="flex:1;min-width:200px;margin-top:0"><label>name bar · line 1</label>
            <input type="text" id="pb-lt1" value="${esc((k.lt || {}).line1 || "")}"
              placeholder="${esc(S.brand && S.brand.station ? S.brand.station : (S.meta.title || "").slice(0, 40))}"></div>
          <div class="field" style="flex:1;min-width:200px;margin-top:0"><label>name bar · line 2</label>
            <input type="text" id="pb-lt2" value="${esc((k.lt || {}).line2 || "")}"
              placeholder="${esc(S.brand && S.brand.station ? (S.meta.title || "").slice(0, 40) : (S.meta.date || ""))}"></div>
        </div>
        <div class="cz-row" style="margin-top:14px">
          <button class="btn primary cz-bigbtn" id="pb-render" ${S.video && nCuts ? "" : "disabled"}
            title="${!S.video ? "download the video first (step 1)" : !nCuts ? "keep at least one clip and one shape (step 2)" : ""}">
            ▶ Make the ${nCuts} video${nCuts === 1 ? "" : "s"}</button>
          <button class="btn primary cz-bigbtn" id="pb-bundle" style="--acc:var(--cream);color:#fff"
            ${rendered.length ? "" : "disabled"} title="${rendered.length ? "" : "make the videos first"}">📦 Export the kit (folder + .zip)</button>
          <span class="hint" id="pb-jobstat"></span>
        </div>
        <div id="pb-prog"></div>
        <div id="pb-kitwhere" style="margin-top:12px"></div>
        ${rendered.length ? `<div class="tag" style="margin-top:14px">made — ${rendered.length} videos</div>
          ${(k.files || []).map(f => `<div class="batchrow"><span class="bname" title="${esc(f.path)}">${esc(f.path.split("/").pop())}</span>
            <span class="bstat">${f.kind === "clip" ? esc(f.ratio.replace("x", ":")) + " video" : "thumbnail"}${f.captions != null ? ` · ${f.captions} captions` : ""}</span>
            <button data-rev="${esc(f.path)}">Show</button></div>`).join("")}` : ""}
      </div>`;

    /* where this kit lives — one folder per meeting */
    czLocRow($("#pb-kitwhere", box), {
      label: "This kit's folder",
      load: async () => S.kitDir,
      save: async p => {
        await api("/api/publisher/destination", { path: p });
        const r = await api("/api/publisher/open", { path: S.source });
        S.kitDir = r.kit_dir;
        loadDest();
        return S.kitDir;
      },
      hint: "Change… picks where ALL kits go — each meeting gets its own folder inside",
    });

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
        () => toast("copied — paste it where it posts"),
        () => toast("the browser blocked the clipboard — select and copy by hand", true));
    });
    const lt1 = $("#pb-lt1", box), lt2 = $("#pb-lt2", box);
    [lt1, lt2].forEach(x => x.onchange = () => {
      k.lt = { line1: lt1.value.trim(), line2: lt2.value.trim() };
      if (!k.lt.line1 && !k.lt.line2) delete k.lt;
      save();
    });
    $("#pb-rebuild", box).onclick = () => {
      if (confirm("Pick fresh clips and redraft the words? Your edits to this kit are replaced.")) rebuild();
    };
    $("#pb-ai", box).onclick = redraft;
    markKeyButtons(box, !!(S.ai && S.ai.enabled));
    const r2 = $("#pb-restore", box);
    if (r2) r2.onclick = () => { k.copy = k.copy_prev; delete k.copy_prev; save(); renderKit(); };
    const hl2 = $("#pb-tohl2", box);
    if (hl2) hl2.onclick = () => go("highlighter", { openPath: S.source });
    const gv = $("#pb-getvid", box);
    if (gv) gv.onclick = fetchVideo;
    $("#pb-render", box).onclick = renderJob;
    $("#pb-bundle", box).onclick = bundleJob;
  }

  /* step 1's button: the recording, fetched the same way Highlighter does */
  async function fetchVideo() {
    const b = $("#pb-getvid", el);
    b.disabled = true;
    try {
      const job = await api("/api/highlighter/fetch",
        { url: S.url, quality: $("#pb-getq", el).value });
      const p = czProgress($("#pb-getprog", el), { label: "downloading the recording", acc: T.acc });
      watchJob(job.id, j => p.update(j));
      const done = await jobDone(job.id);
      p.finish(done);
      if (done.status === "done") { toast("the recording is here — on to the clips"); open(S.source); }
      else {
        b.disabled = false;
        if (done.status === "error") {
          toast(done.error, true);
          if (czBlocked(done.error)) toast("YouTube is limiting this computer — the proxy switch in the Grabber fixes that", true);
        }
      }
    } catch (e) { b.disabled = false; toast(e.message, true); }
  }

  async function rebuild() {
    try {
      const r = await api("/api/publisher/kit", { source: S.source });
      S.kit = r.kit; renderKit(); toast("fresh clips and words, from the transcript");
    } catch (e) { toast(e.message, true); }
  }

  async function redraft() {
    const btn = $("#pb-ai", el);
    btn.disabled = true; btn.textContent = "✨ rewriting…";
    try {
      const r = await api("/api/publisher/copy-ai",
        { source: S.source, instruction: $("#pb-instr", el).value.trim() });
      const prev = S.kit.copy;
      S.kit = r.kit;
      S.kit.copy_prev = prev;
      S.kit.copy = Object.assign({}, prev, S.kit.copy_ai);
      save(); renderKit();
      toast("rewritten on your key — read it before it ships");
      loadStatus();
    } catch (e) { toast(e.message, true); }
    finally { const b = $("#pb-ai", el); if (b) { b.disabled = false; b.textContent = "✨ Rewrite with AI"; } }
  }

  async function renderJob() {
    try {
      const job = await api("/api/publisher/render", { source: S.source });
      const p = czProgress($("#pb-prog", el), { label: "making the videos", acc: T.acc });
      watchJob(job.id, j => p.update(j));
      const done = await jobDone(job.id);
      p.finish(done);
      if (done.status === "done") { toast("videos made — now export the kit"); open(S.source); }
      else if (done.status === "error") toast(done.error, true);
    } catch (e) { toast(e.message, true); }
  }

  async function bundleJob() {
    try {
      const job = await api("/api/publisher/bundle", { source: S.source });
      const p = czProgress($("#pb-prog", el), { label: "exporting the kit", acc: T.acc });
      watchJob(job.id, j => p.update(j));
      const done = await jobDone(job.id);
      p.finish(done);
      if (done.status === "done") {
        const rep = $("#pb-report", el);
        rep.classList.add("show");
        rep.innerHTML += `<b>kit →</b> ${esc(done.result.out)}\n<b>zip →</b> ${esc(done.result.written[0])}\n`;
        toast("kit exported — the folder is opening");
        showFolder(done.result.out);
      } else if (done.status === "error") toast(done.error, true);
    } catch (e) { toast(e.message, true); }
  }

  /* ---------- brand + status ---------- */
  let destRow = null;
  function loadDest() {
    if (!destRow) {
      destRow = czLocRow($("#pb-dest", el), {
        label: "kits go to",
        load: async () => (await api("/api/publisher/status")).out,
        save: async p => (await api("/api/publisher/destination", { path: p })).out,
        hint: "each meeting's kit gets its own folder in here",
      });
    } else destRow.refresh();
  }

  async function loadStatus() {
    try {
      const st = await api("/api/publisher/status");
      const b = st.brand;
      S.brand = b;
      S.ai = st.ai;
      $("#pb-station", el).value = b.station; $("#pb-line2", el).value = b.line2;
      $("#pb-accent", el).value = b.accent; $("#pb-style", el).value = b.style;
      $("#pb-ltsec", el).value = b.lt_seconds; $("#pb-caps", el).checked = b.captions;
      $("#pb-voice", el).value = b.voice;
      $("#pb-aistat", el).innerHTML = st.ai.enabled
        ? `your key ${esc(st.ai.key_masked)} · ${esc(st.ai.model)} — spent only when you press ✨`
        : `no AI key — the drafted words work without one. <a href="#" id="pb-addkey">Add a key</a> to use ✨ Rewrite.`;
      const ak = $("#pb-addkey", el);
      if (ak) ak.onclick = async e => { e.preventDefault(); if (await czKeyModal({ feature: "Rewriting the posts with AI" })) loadStatus(); };
      markKeyButtons(el, !!st.ai.enabled);
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
      toast("saved — every clip you make wears it");
      loadStatus();
    } catch (e) { toast(e.message, true); }
  }

  /* ---------- wire up ---------- */
  let inited = false;
  function init() {
    $("#pb-brandsave", el).onclick = saveBrand;
    $("#pb-back", el).onclick = landing;
    wireDropZone($("#pb-center", el), open);
  }

  function onshow(arg) {
    const first = !inited;
    if (!inited) { init(); inited = true; }
    loadStatus();
    loadDest();
    if (arg && arg.openPath) open(arg.openPath);
    else if (first || !S.source) landing();
  }

  function reset() {
    flushSave();
    Object.assign(S, { source: null, meta: null, video: null, kit: null, kitDir: "", url: null });
    const rep = $("#pb-report", el);
    rep.innerHTML = ""; rep.classList.remove("show");
    if (inited) landing();
  }

  registerPage("publisher", el, onshow, { reset });
  return { onshow };
})();
