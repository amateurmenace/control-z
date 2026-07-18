/* Scribe workspace — the transcript IS the surface (specs/03: this tool is
   70% UI). Word-click seeks, karaoke follows the audio clock, low-confidence
   words are visibly tinted (proof those, not everything), selections stack
   into the pull list → CMX3600 selects EDL. */

const ScribePage = (() => {
  const T = toolById("scribe");
  const SPEAKER_COLORS = ["#52678C", "#3E8E7E", "#C99A3A", "#8E6B9E", "#C4694F", "#5B7A9E"];
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-scribe";
  el.innerHTML = `
  <div class="ws" style="--acc:${T.acc}">
    <div class="mediabar">
      <span class="toolname"><i>Scribe</i> · writes it all down</span>
      <input type="text" id="sc-path" placeholder="/path/to/interview.mov — paste a path or Browse" spellcheck="false">
      <button class="btn" style="width:auto" id="sc-open">Open</button>
      <button class="btn" style="width:auto" id="sc-browse">Browse…</button>
      <span class="clipmeta" id="sc-meta"></span>
    </div>
    <div class="ws-body">
      <div class="ws-center">
        <div id="sc-viewer" style="height:34%;min-height:170px;position:relative"></div>
        <div class="lane" style="padding:7px 12px;display:flex;align-items:center;gap:10px">
          <button class="btn" style="width:auto;padding:5px 15px" id="sc-play" disabled>▶</button>
          <span class="clipmeta" id="sc-time">0:00.0</span>
          <span class="clipmeta" id="sc-speakernow" style="margin-left:8px"></span>
          <span class="clipmeta" id="sc-edithint" style="margin-left:auto">double-click a paragraph to edit ·
            select words → pull list</span>
        </div>
        <div id="sc-transcript" style="flex:1;overflow-y:auto;padding:16px 22px;background:#fff;
             font-size:14.5px;line-height:2.05">
          <div class="empty-grain" style="padding:36px 8px;color:var(--cream-faint);text-align:center">
            open a clip and transcribe — the transcript becomes the edit surface</div>
        </div>
        <div class="scoperack">
          <div class="scope"><div class="slabel">speaker map</div>
            <canvas id="sc-speakers" width="230" height="76"></canvas></div>
          <div class="scope"><div class="slabel">confidence</div>
            <canvas id="sc-conf" width="170" height="76"></canvas>
            <div class="sval" id="sc-confval"></div></div>
          <div class="scope"><div class="slabel">run</div>
            <canvas id="sc-run" width="150" height="76"></canvas></div>
        </div>
      </div>
      <div class="inspector" id="sc-insp">
        <div class="insp-head"><h2>Scribe</h2>
          <div class="density"><button data-d="easy">Easy</button><button data-d="studio">Studio</button></div>
        </div>

        <div class="insp-sec">
          <span class="tag">transcribe</span>
          <div class="field"><label>model</label>
            <select id="sc-model">
              <option value="tiny">tiny — fastest, drafts</option>
              <option value="base" selected>base — quick + decent</option>
              <option value="small">small — better</option>
              <option value="medium">medium — strong (1.5 GB)</option>
              <option value="large-v3-turbo">large-v3-turbo — best balance (1.6 GB)</option>
              <option value="large-v3">large-v3 — most accurate, best on names (3 GB)</option>
            </select>
            <div class="hint">first use of a size downloads it into the shared model store</div>
          </div>
          <div class="field"><label>teach it the names (optional)</label>
            <input type="text" id="sc-hotwords" spellcheck="false"
              placeholder="Bernard Greene, Harvard Street, Select Board…"
              title="people, places, boards the audio likely carries — the decoder is biased toward them so proper names land right">
          </div>
          <div class="checkrow"><input type="checkbox" id="sc-diarize" checked>
            <span>label speakers <div class="hint" id="sc-dzhint"></div></span>
          </div>
          <div class="field studio-only"><label>speaker count (blank = auto)</label>
            <input type="text" id="sc-speakern" placeholder="e.g. 2" spellcheck="false">
          </div>
          <div class="field studio-only"><label>language (blank = detect)</label>
            <input type="text" id="sc-lang" placeholder="en" spellcheck="false">
          </div>
          <button class="btn primary" id="sc-transcribe" disabled style="margin-top:12px">Transcribe</button>
          <div class="prog"><i id="sc-bar"></i></div>
          <div class="progmsg" id="sc-msg"></div>
        </div>

        <div class="insp-sec" id="sc-exportsec" style="display:none">
          <span class="tag">captions &amp; exports</span>
          <div class="field"><label>caption preset</label>
            <select id="sc-captions">
              <option value="broadcast">broadcast — 32×2 lines</option>
              <option value="standard" selected>standard</option>
              <option value="social">social — short punchy lines</option>
            </select>
          </div>
          <div class="chips" id="sc-kinds">
            <span class="chip on" data-k="srt">SRT</span>
            <span class="chip on" data-k="vtt">VTT</span>
            <span class="chip" data-k="txt">TXT</span>
            <span class="chip on" data-k="markers">marker EDL</span>
          </div>
          <button class="btn" id="sc-export" style="margin-top:10px">Export</button>
        </div>

        <div class="insp-sec" id="sc-pullsec" style="display:none">
          <span class="tag">pull list — the paper edit</span>
          <button class="btn" id="sc-addpull" disabled>Add selection to pull list</button>
          <div id="sc-pulls" style="margin-top:8px"></div>
          <div class="field"><label>handles (seconds each side)</label>
            <input type="text" id="sc-handles" value="0.5" spellcheck="false">
          </div>
          <button class="btn primary" id="sc-selects" disabled>Export selects EDL</button>
        </div>

        <div class="insp-sec" id="sc-tightensec" style="display:none">
          <span class="tag">tighten — strip fillers, close silences</span>
          <div class="chips" id="sc-ttopts" style="margin-bottom:8px">
            <span class="chip on" data-tt="fillers">strip “um / uh”</span>
            <span class="chip on" data-tt="silence">close long silences</span>
          </div>
          <div class="field"><label>silence longer than <span id="sc-ttgapv" class="mono-val">0.70s</span></label>
            <input type="range" id="sc-ttgap" min="0.3" max="2" step="0.05" value="0.7" style="width:100%"></div>
          <button class="btn" id="sc-ttfind">Find what to cut</button>
          <div id="sc-ttlist" class="sc-ttlist"></div>
          <button class="btn primary" id="sc-ttwrite" style="margin-top:8px;display:none">Write the cut list (EDL)</button>
          <div class="hint" style="margin-top:5px">a proposal, not a cut — import the EDL
            and relink; every removal is listed first and your source is never touched</div>
        </div>

        <div class="report" id="sc-report"></div>
      </div>
    </div>
  </div>`;

  const S = { path: null, clip: null, t: null, words: [], curWord: -1,
              pulls: [], dirty: false };
  const audio = new Audio();
  let viewer, raf = null;

  const speakerColor = name => {
    const i = Math.max(0, (S.t?.speakers || []).indexOf(name));
    return SPEAKER_COLORS[i % SPEAKER_COLORS.length];
  };

  /* ---------- transcript rendering ---------- */
  function renderTranscript() {
    const box = $("#sc-transcript", el);
    S.words = [];      // the clock reads this — never leave the last clip's words behind
    S.curWord = -1;
    $("#sc-speakernow", el).innerHTML = "";
    if (!S.t || !S.t.segments.length) {
      box.innerHTML = `<div class="empty-grain" style="padding:36px 8px;color:var(--cream-faint);text-align:center">
        no speech found — is this the right clip?</div>`;
      return;
    }
    let html = "", lastSpeaker = null, wi = 0;
    S.t.segments.forEach((seg, si) => {
      if (seg.speaker !== lastSpeaker) {
        const color = seg.speaker ? speakerColor(seg.speaker) : "var(--cream-faint)";
        html += `${si ? "</p>" : ""}<p data-seg="${si}" style="margin:0 0 10px">
          <button class="spk" data-speaker="${esc(seg.speaker || "")}"
            style="background:none;border:1px solid ${color};color:${color};border-radius:5px;
            font-family:var(--mono);font-size:10px;padding:1px 7px;margin-right:8px;cursor:pointer"
            title="click to rename this speaker everywhere">${esc(seg.speaker || "—")}</button>`;
        lastSpeaker = seg.speaker;
      }
      html += `<span class="seg" data-seg="${si}" title="double-click to edit">`;
      if (seg.words && seg.words.length) {
        seg.words.forEach(w => {
          S.words.push({ ...w, si });
          html += `<span class="sw${w.p < 0.6 ? " lowconf" : ""}" data-wi="${wi++}"
            data-s="${w.s}" data-e="${w.e}">${esc(w.w)}</span> `;
        });
      } else {
        html += esc(seg.text) + " ";
      }
      html += `</span>`;
    });
    html += "</p>";
    box.innerHTML = html;

    $$(".sw", box).forEach(sp => sp.onclick = () => {
      audio.currentTime = parseFloat(sp.dataset.s);
      syncFrame(true);
    });
    $$(".spk", box).forEach(b => b.onclick = () => renameSpeaker(b.dataset.speaker));
    $$(".seg", box).forEach(sp => sp.ondblclick = () => editSegment(sp));
    drawScopes();
  }

  /* A paragraph edit has to reach seg.words, not just seg.text: the transcript
     re-renders from words, and a segment too long for the caption preset is cut
     into blocks by word (scribe/exports.py). Same token count keeps every word's
     measured timing; a rewrite re-spreads the spoken span across the new tokens,
     weighted by length — those timings are an estimate, and the toast says so. */
  function respreadWords(seg, txt) {
    const tokens = txt.split(/\s+/).filter(Boolean);
    if (!seg.words || !seg.words.length || !tokens.length) return false;
    if (tokens.length === seg.words.length) {
      seg.words.forEach((w, i) => { if (w.w !== tokens[i]) { w.w = tokens[i]; w.p = 1; } });
      return false;
    }
    const s = seg.words[0].s;
    const e = Math.max(seg.words[seg.words.length - 1].e, s + 0.01);
    const weights = tokens.map(t => t.length + 1);
    const total = weights.reduce((a, b) => a + b, 0);
    let acc = 0;
    seg.words = tokens.map((tok, i) => {
      const from = s + (e - s) * acc / total;
      acc += weights[i];
      return { w: tok, s: +from.toFixed(3), e: +(s + (e - s) * acc / total).toFixed(3), p: 1 };
    });
    return true;
  }

  function editSegment(span) {
    const si = +span.dataset.seg;
    const seg = S.t.segments[si];
    span.contentEditable = "true";
    span.textContent = seg.text;   // plain text while editing
    span.focus();
    span.style.outline = "1px solid var(--scribe)";
    const finish = async () => {
      span.contentEditable = "false";
      span.style.outline = "";
      const txt = span.textContent.trim();
      if (txt && txt !== seg.text) {
        const respread = respreadWords(seg, txt);
        seg.text = txt;
        await save();
        toast(respread
          ? "saved — captions use the corrected text; word timings re-spread across the edit"
          : "saved — captions use the corrected text");
      }
      renderTranscript();
    };
    span.addEventListener("blur", finish, { once: true });
    span.addEventListener("keydown", e => {
      if (e.key === "Enter") { e.preventDefault(); span.blur(); }
      if (e.key === "Escape") { span.textContent = seg.text; span.blur(); }
    });
  }

  async function renameSpeaker(oldName) {
    if (!oldName) return;
    const name = prompt(`Rename "${oldName}" everywhere:`, oldName);
    if (!name || name === oldName) return;
    S.t.segments.forEach(s => { if (s.speaker === oldName) s.speaker = name; });
    S.t.speakers = S.t.speakers.map(s => (s === oldName ? name : s));
    await save();
    renderTranscript();
  }

  async function save() {
    try { await api("/api/scribe/save", { path: S.path, transcript: S.t }); }
    catch (e) { toast(e.message, true); }
  }

  /* ---------- karaoke + viewer sync ---------- */
  function wordAt(t) {
    let lo = 0, hi = S.words.length - 1, best = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (S.words[mid].s <= t) { best = mid; lo = mid + 1; } else hi = mid - 1;
    }
    return best >= 0 && t <= S.words[best].e + 0.35 ? best : -1;
  }

  function syncFrame(force) {
    if (!S.clip) return;
    const i = Math.min(Math.round(audio.currentTime * S.clip.fps), S.clip.nFrames - 1);
    if (force || viewer.i !== i) viewer.show(i);
  }

  function tick() {
    $("#sc-time", el).textContent = fmtTime(audio.currentTime);
    syncFrame(false);
    const wi = wordAt(audio.currentTime);
    if (wi !== S.curWord) {
      const box = $("#sc-transcript", el);
      const prev = $(`.sw.cur`, box);
      if (prev) prev.classList.remove("cur");
      if (wi >= 0) {
        const sp = $(`.sw[data-wi="${wi}"]`, box);
        if (sp) {
          sp.classList.add("cur");
          if (!audio.paused) sp.scrollIntoView({ block: "nearest" });
        }
        const seg = S.t.segments[S.words[wi].si];
        $("#sc-speakernow", el).innerHTML = seg.speaker
          ? `<b style="color:${speakerColor(seg.speaker)}">${esc(seg.speaker)}</b>` : "";
      }
      S.curWord = wi;
    }
    if (!audio.paused) raf = requestAnimationFrame(tick);
  }

  /* caption overlay on the video: current segment, current word amber */
  function overlay(g, v) {
    if (!S.t || S.curWord < 0) return;
    const w = S.words[S.curWord];
    const seg = S.t.segments[w.si];
    const pad = 8 * devicePixelRatio;
    g.font = `${13 * devicePixelRatio}px "DM Sans", sans-serif`;
    const words = (seg.words || []).map(x => x.w);
    let line = words.join(" ");
    if (g.measureText(line).width > v.iw * v.scale - 40) {
      /* show a window around the current word */
      const k = seg.words.indexOf(seg.words.find(x => x.s === w.s));
      line = words.slice(Math.max(0, k - 4), k + 6).join(" ");
    }
    const tw = g.measureText(line).width;
    const x = v.x + (v.iw * v.scale - tw) / 2;
    const y = v.y + v.ih * v.scale - 16 * devicePixelRatio;
    g.fillStyle = "rgba(13,13,18,.78)";
    g.fillRect(x - pad, y - 15 * devicePixelRatio, tw + pad * 2, 22 * devicePixelRatio);
    /* draw word by word so the current one reads amber */
    let cx = x;
    line.split(" ").forEach(token => {
      const isCur = token === w.w;
      g.fillStyle = isCur ? "#E5A835" : "#F5F3EE";
      g.fillText(token, cx, y);
      cx += g.measureText(token + " ").width;
    });
  }

  /* ---------- scopes ---------- */
  function drawScopes() {
    const cs = $("#sc-speakers", el), gs = cs.getContext("2d");
    gs.fillStyle = "#0D0D12"; gs.fillRect(0, 0, cs.width, cs.height);
    gs.font = "9.5px SF Mono, monospace";
    if (!S.t) { gs.fillStyle = "#7E7D75"; gs.fillText("transcribe first", 10, 42); }
    else {
      const talk = {};
      S.t.segments.forEach(s => {
        const k = s.speaker || "—";
        talk[k] = (talk[k] || 0) + (s.end - s.start);
      });
      const entries = Object.entries(talk).slice(0, 4);
      const max = Math.max(...entries.map(e => e[1]), 1);
      entries.forEach(([name, secs], k) => {
        const y = 14 + k * 16;
        const color = name === "—" ? "#7E7D75" : speakerColor(name);
        gs.fillStyle = color;
        gs.fillRect(64, y - 7, (cs.width - 120) * (secs / max), 8);
        gs.fillText(name.slice(0, 9), 4, y);
        gs.fillStyle = "#B9B7AC";
        gs.fillText(`${Math.round(secs)}s`, cs.width - 46, y);
      });
    }
    const cc = $("#sc-conf", el), gc = cc.getContext("2d");
    gc.fillStyle = "#0D0D12"; gc.fillRect(0, 0, cc.width, cc.height);
    gc.font = "9.5px SF Mono, monospace";
    if (S.t) {
      const low = S.words.filter(w => w.p < 0.6).length;
      gc.fillStyle = "#F5F3EE"; gc.fillText(`${S.words.length} words`, 10, 24);
      gc.fillStyle = low ? "#E5A835" : "#7FA05B";
      gc.fillText(`${low} low-confidence`, 10, 42);
      gc.fillStyle = "#7E7D75"; gc.fillText("tinted amber — proof those", 10, 60);
      $("#sc-confval", el).textContent = "";
    } else { gc.fillStyle = "#7E7D75"; gc.fillText("—", 10, 42); }
    const cr = $("#sc-run", el), gr = cr.getContext("2d");
    gr.fillStyle = "#0D0D12"; gr.fillRect(0, 0, cr.width, cr.height);
    gr.font = "9.5px SF Mono, monospace";
    if (S.t) {
      gr.fillStyle = "#B9B7AC";
      gr.fillText(`model ${S.t.model}`, 10, 24);
      gr.fillText(`language ${S.t.language}`, 10, 42);
      gr.fillStyle = "#7E7D75";
      gr.fillText(`${S.t.segments.length} segments`, 10, 60);
    } else { gr.fillStyle = "#7E7D75"; gr.fillText("—", 10, 42); }
  }

  /* ---------- pull list ---------- */
  function selectionRange() {
    const sel = getSelection();
    if (!sel || sel.isCollapsed) return null;
    const box = $("#sc-transcript", el);
    const inBox = n => n && box.contains(n.nodeType === 3 ? n.parentElement : n);
    if (!inBox(sel.anchorNode) || !inBox(sel.focusNode)) return null;
    const range = sel.getRangeAt(0);
    const spans = $$(".sw", box).filter(sp => range.intersectsNode(sp));
    if (!spans.length) return null;
    const s = Math.min(...spans.map(sp => parseFloat(sp.dataset.s)));
    const e = Math.max(...spans.map(sp => parseFloat(sp.dataset.e)));
    const label = spans.slice(0, 5).map(sp => sp.textContent).join(" ")
      + (spans.length > 5 ? "…" : "");
    return { start: s, end: e, label };
  }

  function renderPulls() {
    const box = $("#sc-pulls", el);
    $("#sc-selects", el).disabled = !S.pulls.length;
    if (!S.pulls.length) {
      box.innerHTML = `<div class="hint">select words in the transcript, then add —
        each pull becomes an EDL event</div>`;
      return;
    }
    box.innerHTML = S.pulls.map((p, k) => `
      <div class="batchrow" style="margin-bottom:5px">
        <span class="bname" style="flex:1">${esc(p.label)}</span>
        <span class="bstat">${fmtTime(p.start)}–${fmtTime(p.end)}</span>
        <button data-up="${k}" title="earlier">↑</button>
        <button data-rm="${k}">×</button>
      </div>`).join("");
    $$("button[data-rm]", box).forEach(b => b.onclick = () => { S.pulls.splice(+b.dataset.rm, 1); renderPulls(); });
    $$("button[data-up]", box).forEach(b => b.onclick = () => {
      const k = +b.dataset.up;
      if (k > 0) { [S.pulls[k - 1], S.pulls[k]] = [S.pulls[k], S.pulls[k - 1]]; renderPulls(); }
    });
  }

  /* ---------- open / transcribe / export ---------- */
  async function open(path, t) {
    try {
      const r = await api("/api/media/open", { path, tool: "scribe" });
      S.path = r.path;
      $("#sc-path", el).value = r.path;
      // a fresh clip starts clean — no prior clip's sections, pull rows,
      // report, tighten list or filled bar bleeding onto this one
      ["#sc-exportsec", "#sc-pullsec", "#sc-tightensec"].forEach(
        s => $(s, el).style.display = "none");
      $("#sc-pulls", el).innerHTML = "";
      $("#sc-ttlist", el).innerHTML = "";
      $("#sc-ttwrite", el).style.display = "none";
      const rep0 = $("#sc-report", el);
      rep0.classList.remove("show"); rep0.innerHTML = "";
      $("#sc-bar", el).style.width = "0%";
      $("#sc-msg", el).classList.remove("err");
      const v = r.video;
      $("#sc-meta", el).innerHTML = `<b>${esc(r.name)}</b>` +
        (v ? ` · ${v.width}×${v.height} @ ${v.fps.toFixed(2)}` : "") +
        ` · audio ${r.audio_streams ? "✓" : "— none!"}`;
      if (v) {
        S.clip = { path: r.path, nFrames: v.n_frames_estimate || 1, fps: v.fps, w: v.width, h: v.height };
        viewer.setClip(S.clip);
        $("#sc-viewer", el).style.display = "";
      } else {
        S.clip = null;
        viewer.setClip(null);
        $("#sc-viewer", el).style.display = "none";  // audio-only: transcript full-height
      }
      audio.src = `/api/scribe/audio?path=${encodeURIComponent(r.path)}`;
      $("#sc-play", el).disabled = !r.audio_streams;
      $("#sc-transcribe", el).disabled = !r.audio_streams;
      S.t = null; S.words = []; S.pulls = []; S.curWord = -1;
      const side = await api("/api/scribe/load", { path: r.path });
      if (side.transcript) { applyTranscript(side.transcript); $("#sc-msg", el).textContent = "transcript sidecar loaded"; }
      else { renderTranscript(); $("#sc-msg", el).textContent = r.audio_streams ? "ready to transcribe" : "no audio track in this file"; }
      const st = await api("/api/scribe/status");
      $("#sc-dzhint", el).textContent = st.diarize_available
        ? "sherpa-onnx pipeline, local like everything else"
        : `models missing — ${st.diarize_hint}`;
      if (t > 0 && r.audio_streams) {
        // arrived from a time-coded hit (Index) — land on the moment
        audio.currentTime = t;
        tick();
      }
    } catch (e) { toast(e.message, true); }
  }

  function applyTranscript(t) {
    S.t = t;
    $("#sc-exportsec", el).style.display = "";
    $("#sc-pullsec", el).style.display = "";
    $("#sc-tightensec", el).style.display = "";
    $("#sc-ttlist", el).innerHTML = "";
    $("#sc-ttwrite", el).style.display = "none";
    renderTranscript(); renderPulls(); drawScopes();
  }

  async function transcribe() {
    const btn = $("#sc-transcribe", el);
    btn.disabled = true;
    $("#sc-bar", el).style.width = "8%";
    try {
      const job = await api("/api/scribe/transcribe", {
        path: S.path,
        model: $("#sc-model", el).value,
        diarize: $("#sc-diarize", el).checked,
        speakers: parseInt($("#sc-speakern", el).value) || -1,
        language: $("#sc-lang", el).value.trim() || null,
        hotwords: $("#sc-hotwords", el).value.trim(),
      });
      watchJob(job.id, j => {
        $("#sc-msg", el).textContent = j.status === "queued" ? "queued" : (j.message || j.status);
        $("#sc-bar", el).style.width = j.status === "running" ? "50%" : "8%";
      });
      const done = await jobDone(job.id);
      btn.disabled = false;
      $("#sc-bar", el).style.width = done.status === "done" ? "100%" : "0%";
      if (done.status === "error") { $("#sc-msg", el).textContent = done.error; $("#sc-msg", el).classList.add("err"); return; }
      if (done.status === "cancelled") { $("#sc-msg", el).textContent = "cancelled"; return; }
      $("#sc-msg", el).classList.remove("err");
      applyTranscript(done.result);
    } catch (e) { btn.disabled = false; toast(e.message, true); }
  }

  async function exportKinds() {
    const kinds = $$("#sc-kinds .chip.on", el).map(c => c.dataset.k);
    if (!kinds.length) { toast("pick at least one format", true); return; }
    try {
      const r = await api("/api/scribe/export",
        { path: S.path, kinds, captions: $("#sc-captions", el).value });
      const rep = $("#sc-report", el);
      rep.classList.add("show");
      rep.innerHTML += `<b>→</b> ` + r.written.map(esc).join("\n   ") + `\n   ${esc(r.note)}\n`;
    } catch (e) { toast(e.message, true); }
  }

  async function exportSelects() {
    try {
      const r = await api("/api/scribe/selects", {
        path: S.path, selects: S.pulls,
        handles: parseFloat($("#sc-handles", el).value) || 0.5,
      });
      const rep = $("#sc-report", el);
      rep.classList.add("show");
      rep.innerHTML += `<b>→</b> ${esc(r.out)}\n   ${r.selects} events · ${esc(r.note)}\n`;
    } catch (e) { toast(e.message, true); }
  }

  /* tighten — extractive cleanup, visible before commit. Find lists every
     filler and long silence; Write leaves a CMX3600 cut list of what's left,
     never touching the source. */
  function tightenOpts() {
    const on = $$("#sc-ttopts .chip.on", el).map(c => c.dataset.tt);
    return { path: S.path, fillers: on.includes("fillers"),
             silence: on.includes("silence"),
             min_gap: parseFloat($("#sc-ttgap", el).value) || 0.7 };
  }

  async function tightenFind() {
    const o = tightenOpts();
    if (!o.fillers && !o.silence) { toast("pick fillers or silences to find", true); return; }
    try {
      renderTightenList(await api("/api/scribe/tighten", o));
    } catch (e) { toast(e.message, true); }
  }

  function renderTightenList(r) {
    const box = $("#sc-ttlist", el), write = $("#sc-ttwrite", el);
    if (!r.removals || !r.removals.length) {
      box.innerHTML = `<div class="hint" style="margin-top:8px">nothing to cut —
        no fillers or long silences in this transcript</div>`;
      write.style.display = "none";
      return;
    }
    box.innerHTML = `<div class="sc-ttsum">removes <b>${r.removed_seconds}s</b> ·
      keeps <b>${r.kept_seconds}s</b> · ${r.n_fillers} filler${r.n_fillers !== 1 ? "s" : ""},
      ${r.n_silences} silence${r.n_silences !== 1 ? "s" : ""}</div>`
      + r.removals.map(m => `
      <button class="sc-ttrow" data-t="${m.start}" title="jump to this moment">
        <span class="sc-ttkind ${m.kind}">${m.kind === "filler" ? esc(m.text || "um") : "silence"}</span>
        <span class="sc-tttime">${fmtTime(m.start)}–${fmtTime(m.end)}</span>
        <span class="sc-ttdur">−${(m.end - m.start).toFixed(1)}s</span>
      </button>`).join("");
    $$(".sc-ttrow", box).forEach(b => b.onclick = () => {
      if (audio) { audio.currentTime = +b.dataset.t; tick(); }
    });
    write.style.display = "";
  }

  async function tightenWrite() {
    try {
      const r = await api("/api/scribe/tighten", { ...tightenOpts(), write: true });
      const rep = $("#sc-report", el);
      rep.classList.add("show");
      rep.innerHTML += `<b>→</b> ${esc(r.out)}\n   ${r.keeps} keeps · removes ${r.removed_seconds}s · ${esc(r.note)}\n`;
      toast(`cut list written — ${r.keeps} keeps, ${r.removed_seconds}s trimmed`);
    } catch (e) { toast(e.message, true); }
  }

  /* ---------- wire up ---------- */
  function init() {
    viewer = new Viewer($("#sc-viewer", el), { h: 360 });
    viewer.onOpen = p => open(p);
    viewer.overlay = overlay;

    $("#sc-open", el).onclick = () => { const p = $("#sc-path", el).value.trim(); if (p) open(p); };
    $("#sc-path", el).addEventListener("keydown", e => { if (e.key === "Enter") $("#sc-open", el).click(); });
    $("#sc-browse", el).onclick = async () => {
      try {
        const r = await api("/api/dialog/open-file", {});
        if (r.paths && r.paths[0]) open(r.paths[0]);
      } catch (e) { toast(e.message, true); }
    };
    $("#sc-play", el).onclick = () => { audio.paused ? audio.play() : audio.pause(); };
    audio.addEventListener("play", () => { $("#sc-play", el).textContent = "⏸"; raf = requestAnimationFrame(tick); });
    audio.addEventListener("pause", () => { $("#sc-play", el).textContent = "▶"; if (raf) cancelAnimationFrame(raf); tick(); });
    audio.addEventListener("seeked", () => tick());

    document.addEventListener("selectionchange", () => {
      if (CZ.current !== "scribe") return;
      $("#sc-addpull", el).disabled = !selectionRange();
    });
    $("#sc-addpull", el).onclick = () => {
      const r = selectionRange();
      if (!r) return;
      S.pulls.push(r);
      getSelection().removeAllRanges();
      renderPulls();
      toast(`pulled: "${r.label}"`);
    };
    $("#sc-transcribe", el).onclick = transcribe;
    $("#sc-export", el).onclick = exportKinds;
    $("#sc-selects", el).onclick = exportSelects;
    $$("#sc-kinds .chip", el).forEach(c => c.onclick = () => c.classList.toggle("on"));
    $("#sc-ttfind", el).onclick = tightenFind;
    $("#sc-ttwrite", el).onclick = tightenWrite;
    $$("#sc-ttopts .chip", el).forEach(c => c.onclick = () => c.classList.toggle("on"));
    $("#sc-ttgap", el).oninput = () =>
      $("#sc-ttgapv", el).textContent = (+$("#sc-ttgap", el).value).toFixed(2) + "s";

    // transport keys — Space plays/pauses, ←/→ seek ±5s (the house grammar,
    // cf. Highlighter), skipped while typing or editing a paragraph
    addEventListener("keydown", e => {
      if (CZ.current !== "scribe" || $("#sc-play", el).disabled) return;
      const a = document.activeElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(a?.tagName) || a?.isContentEditable) return;
      if (e.code === "Space") {
        e.preventDefault();
        audio.paused ? audio.play() : audio.pause();
      } else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        audio.currentTime = Math.max(0, audio.currentTime + (e.key === "ArrowLeft" ? -5 : 5));
        tick();
      }
    });

    const insp = $("#sc-insp", el);
    const dens = $$(".density button", insp);
    function applyDensity(d) {
      insp.classList.toggle("studio", d === "studio");
      dens.forEach(b => b.classList.toggle("on", b.dataset.d === d));
    }
    dens.forEach(b => b.onclick = () => { applyDensity(b.dataset.d); setDensity("scribe", b.dataset.d); });
    applyDensity(density("scribe"));

    /* the router only toggles .active — watch for it leaving so a tool switch
       can't leave this transcript talking underneath the next tool */
    new MutationObserver(() => { if (!el.classList.contains("active")) stop(); })
      .observe(el, { attributes: true, attributeFilter: ["class"] });
  }

  /* stop playing and give up the clock: called when this page stops being current */
  function stop() {
    audio.pause();
    if (raf) { cancelAnimationFrame(raf); raf = null; }
  }

  let inited = false;
  function onshow(arg) {
    if (!inited) { init(); inited = true; }
    Viewer.active = null;  // the audio element is the clock here, not JKL
    if (arg && arg.openPath) open(arg.openPath, arg.t || 0);
    if (viewer) viewer.resize();
  }

  registerPage("scribe", el, onshow);
  return { onshow, stop };
})();
