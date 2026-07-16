# control-z Suite — the desktop app

**One app for everything that lives outside Resolve.** Pivot, Stencil, Scribe, Clear,
Rise, and Depth under a single fresh interface — plus an OpenFX installer for Hush/Speak,
a shared batch queue, real scopes, and ProRes-up-to-4444 delivery. macOS first, Windows
second. The Suite is what a member opens *before* the edit (restore, transcribe, rescue)
or *after* picture lock (mattes, reframes, depth) — Resolve stays the editor; the Suite
is the workbench around it.

## 1. Product principles

1. **Fresh but forgiving.** A member who has never opened a scope should get a great
   result with three clicks; a finisher should find channel-level control two clicks
   deeper. Every panel has two densities: **Easy** (big controls, plain language,
   auto-everything visible) and **Studio** (full parameter surface, numbers everywhere).
   The toggle is per-tool and remembered.
2. **Covenant on screen.** "Shows its work" is the interface, not a feature: every tool
   keeps a measurement surface visible by default (path trace, confidence strip,
   residual meter, detail heatmap, depth probe). Turning them off is allowed; shipping
   without them is not.
3. **One vocabulary.** Same viewer, same filmstrip, same queue, same export panel
   everywhere. A user who learns Pivot has learned 70% of Depth.
4. **Local, honest, quiet.** No accounts, no telemetry, no cloud. Models download with
   license cards and pinned hashes into the existing shared store. Synthesis is labeled
   synthesis. Failures are sentences, not codes.

## 2. Architecture (decision)

**v1 = the proven stack, unified:** one Python process (the six engines already share a
venv and `czcore`) exposing a local FastAPI + WebSocket server; UI is a single-page web
app rendered in a native window via **pywebview** (WKWebView on macOS, WebView2 on
Windows). This is the community-captioner / Pivot-v0.2 pattern, graduated.

- Why not Electron/Tauri/Swift now: the engines are Python; every alternative adds a
  second runtime or a rewrite. The UI investment (HTML/canvas/WebGL) carries over 1:1 to
  a Tauri shell later **if** webview performance ever blocks us — that is the named
  escalation path, not a rewrite.
- **Frame service:** server-side decode (PyAV) → cached JPEG/WebP frames at viewer
  resolution + prefetch around the playhead; overlays drawn client-side on canvas/WebGL
  from JSON (paths, mattes, boxes, scopes). Playback targets 24–30 fps at 1080 preview
  (proxied from 4K); pixel-exact inspection via zoom tiles. GPU inference stays in the
  engines (MPS/CoreML/ONNX), never in the webview.
- **Jobs:** czcore.appshell's JobManager grows a persistent SQLite queue: every heavy
  operation (analyze, propagate, transcribe, upscale, export) is a job with progress,
  cancel, logs, and history. The Queue page is cross-tool: batch a whole tape shelf.
- **Sessions:** each tool reads/writes its existing sidecars (`.pivot.json`,
  `.stencil.json`, `.scribe.json`, …) — the app adds a lightweight `.czsession` (recent
  media, per-tool state) so quitting is never destructive.

## 3. Information architecture

```
┌ rail ─────────┐ ┌ workspace ──────────────────────────────────────────┐
│ ⌂ Home        │ │ [media strip: open/recent/drag-anything]            │
│ ─ tools ─     │ │ ┌─────────────────────────────┐ ┌ inspector ──────┐ │
│ ◇ Pivot       │ │ │ VIEWER (A/B, wipe, zoom,    │ │ params (Easy /  │ │
│ ◇ Stencil     │ │ │ overlays per tool)          │ │ Studio) presets │ │
│ ◇ Scribe      │ │ └─────────────────────────────┘ │ export panel    │ │
│ ◇ Clear       │ │ [filmstrip / timeline / transcript lane]           │ │
│ ◇ Rise        │ │ [SCOPE RACK — per-tool set, always one visible]    │ │
│ ◇ Depth       │ └─────────────────────────────────────────────────────┘
│ ─ suite ─     │   Home = two doors: "Prep" (before the edit) and
│ ≡ Queue       │   "Finish" (after picture lock), each listing the
│ ⬇ Install OFX │   right tools with one-line whys + recent files.
│ ◈ Models      │
│ ⚙ Settings    │
└───────────────┘
```

Each tool is its own page with the shared chrome; the center/bottom regions adapt:

| Tool | Viewer overlays | Bottom lane | Scope rack (default on) |
|---|---|---|---|
| Pivot | crop rect, subject dot, deadzone | shot strip + per-shot mode chips | path trace, punch-in meter |
| Stencil | matte tint, prompt points, onion skin | filmstrip + **confidence strip** | confidence curve, matte coverage % |
| Scribe | word-highlight over video | transcript editor (the main surface) | word-confidence shading, speaker map |
| Clear | — (audio) | waveform + spectrogram | loudness (M/S/I + true peak), **residual monitor**, before/after spectra |
| Rise | A/B wipe, tile grid debug | frame queue | **detail heatmap**, interlace verdict, backend badge |
| Depth | false color, probe crosshair | shot strip | depth histogram with in/out handles, stability meter |

Shared everywhere: histogram + waveform of the current frame (image tools), zoom loupe,
frame-accurate step keys (JKL, arrows), and the **Export panel**.

## 4. Export (the delivery contract)

- **Video:** ProRes 422 / 422 HQ / **4444 (+alpha for mattes)** via `prores_ks`, with
  `prores_videotoolbox` hardware encode used on Apple Silicon when available; DNxHR HQX;
  H.264/HEVC via VideoToolbox/NVENC/MF. Never upscale silently; never strip color tags
  (range/primaries passed through and reported).
- **Audio:** stream-copy by default; Clear exports WAV stems + remux.
- **Data:** each tool's existing interchange (SRT/VTT, marker + selects EDL, Fusion
  .setting, sidecar JSON) reachable from the same panel.
- Frame-accuracy and flush behavior inherit the golden tests already in the repo.

## 5. Install OpenFX page

Detects DaVinci Resolve (app presence + `/Library/OFX/Plugins`), shows installed
Hush/Speak versions vs latest GitHub release, one-button install/update/uninstall,
clears `OFXPluginCacheV2.xml` (the known rescan gotcha), and links each plugin's section
on control-z.org. Windows: `C:\Program Files\Common Files\OFX\Plugins` equivalents.

## 6. Design language

Dark **grade-room** surfaces carrying the site's warmth: ink `#191921`/forest `#24301F`
panels, cream `#F5F3EE` text, amber `#E5A835` reserved for *measurements and attention*,
per-tool accents (slate/plum/ink/teal/gold/indigo) on the rail glyphs and primary
actions. Space Grotesk headings, DM Sans UI, SF Mono numbers. The node-wire motif from
the site is the rail's active indicator. Motion is functional and short;
`prefers-reduced-motion` respected. Grain only in empty states (the brand wink, not a
texture over footage).

## 7. Milestones

- **v0.1 — shell + two tools:** rail/home/viewer/filmstrip/inspector/queue skeleton;
  Pivot and Rise fully moved in (they share the viewer + wipe + heatmap); export panel
  with ProRes 4444/HQ + H.264; sessions.
- **v0.2 — sound + words:** Clear (waveform/spectrogram/residual/loudness) and Scribe
  (transcript-first workspace, pull list, all exports).
- **v0.3 — the GPU pair:** Stencil (click-to-prompt, confidence QC loop) and Depth
  (probe, histogram handles, template pack).
- **v0.4 — suite services:** cross-tool queue/batch, Install OpenFX page, Models page,
  release-check (GitHub API, no telemetry).
- **v1.0 — ship:** PyInstaller .app, Developer ID signing (6M536MV7GT), notarization,
  DMG, site "Suite" card flips to a real download.
- **v1.x — Windows:** WebView2 shell, DirectML/NVENC paths, installer.

## 8. Risks, named

- **Webview 4K preview** — mitigated by proxy previews + zoom tiles; escalation path is
  Tauri around the same server, UI carries over.
- **Bundle weight** (torch for Stencil ≈ 2 GB) — Stencil's runtime ships as an optional
  on-demand component through the Models page, not in the base DMG.
- **prores_ks throughput on long masters** — hardware ProRes on Apple Silicon where
  available; honest time estimates in the queue either way.
- **One process, six engines** — jobs run in worker processes (not threads) so a stuck
  propagation can be killed without taking the app down.

---

## Appendix: kickoff prompt for the build session

> Build **control-z Suite v0.1** — the desktop app shell for the control-z tools — in
> `/Users/stephen/control-z` (existing monorepo, venv at `.venv`, Python 3.14).
>
> **Read first:** `specs/08-suite-app.md` (this plan — follow it), `specs/00-overview.md`
> (shared architecture + covenant), `specs/01-pivot.md` and `specs/05-rise.md` (the two
> tools shipping in v0.1), and `CHANGELOG.md` for what already exists and works. The six
> tool engines are importable and verified (`pivot`, `rise`, plus `czcore` for media/
> shots/models/appshell); ~90 tests pass via `python3 -m unittest discover -s tests -t .`
> — keep them green and don't break the CLIs.
>
> **Scope for this session (v0.1):** a `suite/` package: FastAPI + WebSocket server
> (grow `czcore.appshell`: persistent SQLite job queue with progress/cancel/history),
> frame service (PyAV decode → cached JPEG frames + prefetch, overlay data as JSON),
> and a pywebview-hosted single-page UI (hand-written HTML/CSS/JS, no framework) with:
> left rail (Home, Pivot, Stencil, Scribe, Clear, Rise, Depth, Queue, Install OpenFX,
> Models, Settings — non-v0.1 pages show honest "coming in v0.x" states), Home with
> Prep/Finish doors + recents, the shared viewer (zoom/pan, A/B wipe, canvas overlays,
> JKL + arrow keys), filmstrip, inspector with **Easy/Studio density toggle**, and the
> export panel (ProRes 422/HQ/**4444 + alpha**, DNxHR HQX, H.264/HEVC hw; color tags
> passed through; `prores_videotoolbox` when available, else `prores_ks`).
> Move **Pivot** in fully (analyze/scrub/path-trace overlay/per-shot overrides/render +
> Fusion export — parity with `pivot/ui.py`, then retire that page) and **Rise**
> (probe/interlace guard, A/B wipe, detail heatmap = |out − bicubic| overlay, queue
> batch, enhance-model picker with honest backend labeling).
>
> **Design:** dark grade-room per the spec §6 — ink/forest surfaces, cream text, amber
> strictly for measurements/attention, per-tool accents (Pivot `#5B7A9E`, Rise
> `#C99A3A`), Space Grotesk/DM Sans/SF Mono. The covenant is UI law: measurement
> surfaces on by default; synthesis labeled synthesis; failures in sentences.
>
> **Definition of done:** `python -m suite` opens the window (`--serve` for browser
> dev); a real clip goes open → analyze → scrub with overlays → override a shot →
> render ProRes 4444 → file verified frame-accurate; Rise batch runs through the queue
> with cancel; unit tests for the job store, frame cache, and export-preset mapping;
> verify the UI by driving it in a browser; update `CHANGELOG.md` and `README.md`.
> Test footage: `/Users/stephen/Hush/Test Footage/NR Test SHort Sabby.mov`. Commit
> nothing without asking.
