# control-z Suite — packaging, signing, and the v1.0 ship

**The last milestone is not a feature.** `specs/08-suite-app.md` §7 closes with "v1.0 —
ship: PyInstaller .app, Developer ID signing (6M536MV7GT), notarization, DMG, site 'Suite'
card flips to a real download." Everything in that sentence is packaging work, and four
research passes have now measured it rather than guessed at it. Two of the things the
program has been telling itself are false: the sibling repos do **not** have a working
notarization pipeline, and the Suite is **already** shipping GPL code. This spec is where
both get fixed, in the open, before a DMG exists to be embarrassed by.

## 1. The decision, stated up front

**PyInstaller 6.21+ onedir, one `.app`, one signed and notarized DMG, Apple-silicon only.**

Defended:

- **onedir, per `specs/00`.** onefile would unpack 364 MB to a temp dir on every launch and
  break the code-signing story (the seal covers the archive, not the extracted tree). onedir
  is what gets signed, what gets notarized, and what gets stapled.
- **PyInstaller, not py2app/briefcase.** 6.21.0 declares `Requires-Python <3.16,>=3.8` and
  classifies 3.14; two full builds of `suite/__main__` completed against the repo's real venv
  (Python 3.14.6, arm64). Hook coverage in pyinstaller-hooks-contrib 2026.6 already handles
  `av`, `cv2`, `onnxruntime`, `torch`, `sam2`, `soundfile`, `uvicorn`, `websockets`,
  `webview`, `pydantic`. The interpreter risk everyone feared is retired: it builds.
- **DMG, not pkg** — on merit, not necessity. When this was first written the machine had no
  Developer ID **Installer** identity, which was precisely why `OpenNR-3.7.0-macOS.pkg`
  reported `Status: no signature`; that cert now exists (2026-07-16) and both plugins ship
  notarized, so pkg is no longer *blocked*. It is still wrong for this artifact: a pkg
  installs to a system location and wants root, which is right for an OFX plugin dropping
  into `/Library/OFX/Plugins` and pointless for an app the user drags to /Applications. The
  Suite is a normal `.app`; a DMG signs with the Application identity, needs no privilege
  escalation, and is what a user expects to drag.
- **Apple silicon only, said out loud.** `lipo -archs` reports `arm64` for libavcodec,
  libtorch_cpu, libonnxruntime, and the venv's python. There are no universal2 wheels for
  this stack. Hush's `.ofx` is universal; the Suite cannot be. That is a **download-page
  sentence**, not a release-note footnote — the covenant's honest-limitations rule applies
  to the thing people click.

**Escalation path if PyInstaller fails:** it has not, and the two completed builds are the
evidence. If a later dependency defeats it, the fallback is *not* a packager swap — it is
`briefcase`/`py2app` around the same `suite` package with the same signing script, because
§4's signing sequence is packager-agnostic. Rewriting the app is never on this path.

## 2. What actually transfers from Hush and Speak (and what does not)

The program's own notes called OpenNR/Speak a "proven, shipping signing pipeline." As
measured on 2026-07-16 — **all three rows have since been fixed, and the fix is the reason
this section is worth reading**:

| Claim | Reality when measured | Now |
|---|---|---|
| Notarization pipeline works | **Never executed once.** `notarytool history` exited **69**: "No Keychain password item found." Both releases took the script's silent skip branch. | Profile `opennr-notary` stored; Hush 3.7.0 and Speak 0.2.0 notarized and stapled. |
| The shipped pkg is signed | `pkgutil --check-signature` → "Status: no signature". `spctl -a -t install` → **rejected**. | Developer ID **Installer** cert created; both pkgs signed, notarized, stapled. |
| The payload is signed | **True** all along: Developer ID Application, `flags=0x10000(runtime)`, timestamped. | Unchanged — and now carries a stapled ticket too. |

The lesson worth keeping: **both guards failed open.** `if profile exists … else skip` and
`if installer-cert exists … else ship unsigned` each printed one line and moved on, so two
releases shipped Gatekeeper-rejected while the script reported success. A guard around a
release step should fail loudly or not exist.

**Transfers:** the Developer ID Application identity; the identity-autodetect idiom
(`security find-identity | grep -o '"Developer ID Application: [^"]*"'` — grep the literal
string, never `head -1`, because the *first* identity on this machine is a different team,
597T4G6JU5); the `--timestamp --options runtime` flags; the notarize-if-profile-exists guard
and the ad-hoc fallback, so a credential-less machine still produces artifacts.

**Does not transfer:** `--deep`, and the *shape* of the payload. The siblings sign one
Mach-O inside an `.ofx.bundle` that Resolve dlopens under *Resolve's* entitlements. The
Suite is 500-odd Mach-O files in its own process — §4 is new work with no precedent in the
family. Notarization itself is no longer unknown territory (the plugins and, before them,
the ATEM projects have all been Accepted), but **this dependency set** has never been
submitted. Budget for reading `xcrun notarytool log <id>`: that log is the only thing that
says what Apple actually objected to; `codesign --verify` does not predict it.

**One ordering lesson, learned the hard way and worth inheriting:** ticket the *bundle*
first, then build the pkg and the zip from the stapled copy. The sibling scripts built the
zip *after* notarizing, from an unstapled stage, so the zip would have shipped a ticket-less
payload even on a successful run — which is why Hush's docs still tell users to
`xattr -dr com.apple.quarantine`. And never submit an unsigned pkg: Apple rejects it, and the
error blames the profile rather than the missing certificate.

## 3. FFmpeg and the license (settled)

**This is the buried lede: the violation already shipped, and it is not in the shell-outs.**

`specs/00-overview.md` mandates "bundled **LGPL ffmpeg** build; H.264/HEVC via hardware
encoders … avoids GPL x264." The installed PyAV 18.0.0 wheel bundles FFmpeg 8.1.2 linked
against **libx264 and libx265** — `otool -L av/.dylibs/libavcodec.62.28.102.dylib` shows
`@loader_path/libx264.165.dylib` and `@loader_path/libx265.216.dylib`. `cv2` bundles a
*second* FFmpeg (61.x) with `libx264.164` and `libx265.215`. Both x264 and x265 are
GPL-2.0-or-later (verified from `COPYING`, not memory). A frozen `.app` containing them is
a GPL-3.0 work owing complete corresponding source to every recipient.

Three traps that will fool a careful reader:

1. **`avcodec_license()` returns "LGPL version 3 or later" and it is wrong.** The config
   string has no `--enable-gpl` yet has `--enable-libx264 --enable-libx265` — a combination
   stock FFmpeg's configure refuses (`die_license_disabled gpl libx264`). The string is
   derived from flags, not linkage. **`otool -L` is the only authority.**
2. **PyAV's metadata says `License-Expression: BSD-3-Clause`** and its `dist-info/licenses/`
   contains only PyAV's own BSD notice. Any scanner reading PyPI metadata returns clean and
   is wrong.
3. **"We never call libx264" is not a defense.** GPL attaches to distribution, not
   invocation. It is a reason removal is *cheap*, not a reason it's unnecessary.

**Decision:**

- **Build FFmpeg ourselves, LGPL, no x264/x265**, with `--enable-videotoolbox`. Build PyAV
  from sdist against it (`pip install av --no-binary av`); `setup.py` discovers FFmpeg via
  pkg-config or `--ffmpeg-dir=` and explicitly refuses static FFmpeg — which forces the
  shared linking LGPL wants anyway. The same build supplies the **bundled `ffmpeg` and
  `ffprobe` binaries** `specs/00` has always promised.
- **Drop `--enable-version3`** → LGPL-2.1 rather than LGPL-3.0. It costs opencore-amr (no
  tool needs AMR) and narrows the license surface. See §7 for the relink question this
  leaves open; we answer it with a sentence in NOTICE, **not** with an entitlement.
- **Replace `opencv-python` with a build carrying no FFmpeg.** `cv2`'s video IO is entirely
  unused — grep for `VideoCapture|VideoWriter` across `suite czcore depth pivot rise scribe
  stencil clear` returns **zero hits**; every decode goes through PyAV. Its FFmpeg is not
  merely dead weight, it is an observed runtime hazard: the frozen app logs
  `objc[…]: Class AVFFrameReceiver is implemented in both libavdevice.61.3.100.dylib and
  libavdevice.62.3.102.dylib … may cause spurious casting failures and mysterious crashes.`
  It has not crashed yet, which is exactly what makes it dangerous — it will crash for a
  user, nondeterministically, unreproducibly.
- **Delete the GPL fallbacks rather than let them fail open.** `czcore/media.py` lists
  `libx264`/`libx265` as fallback candidates after the videotoolbox encoders;
  `pivot/render.py`'s legacy `CODECS` maps `h264 → libx264` outright; `rise/cli.py:59-64`
  builds its own libx264 table and passes it *as* `codec_spec`, **overriding**
  `rise/video.py`'s correct `resolve_preset` default (it looks like it inherits the good
  behavior; it does not). Route both CLIs through `czcore.media.resolve_preset` and delete
  both tables.
- **A linkage assertion is a build gate**, not a comment: after the build, `otool -L` every
  shipped dylib and fail on any x264/x265/GPL match. The next contributor who wants better
  low-bitrate H.264 will reach for x264; the build must stop them.

**What this costs, honestly:** nothing to the delivery contract, and something to the
picture. All six export presets already resolve to non-GPL encoders on Apple silicon —
verified by real encodes, not table-reading: `prores-422/hq → prores_videotoolbox`,
`prores-4444 → prores_ks`, `dnxhr-hqx → dnxhd`, `h264/hevc → *_videotoolbox` (387134 and
258062 bytes out, x264 never touched). But VideoToolbox H.264 at `q:v 55` is not x264
`crf 18`. Someone should eyeball an export before we claim parity, and the export report
should keep saying which encoder ran (`presets_report` already carries `hardware`).

**NOTICE must grow a native-libraries section.** Today it documents *models only* and never
mentions FFmpeg, x264, x265, LAME, or opencore-amr. Before v1.0 it names the FFmpeg build,
its license, and a written offer for source.

## 4. Signing (the sequence, and the trap)

The frozen tree holds ~363 signed Mach-O files in the no-torch build (523 `.so`/`.dylib`
exist across the venv). Sign **inside-out, leaf-first, batched**. Never `--deep` on
`codesign`; `--deep` is fine and useful on `codesign --verify`.

1. `find "$APP" -type f` → filter by `file`/Mach-O **inspection, not extension**, and sign
   each with `--force --timestamp --options runtime --sign "$DEV_ID"` via one batched
   `-exec … {} +` pass.
2. `Python.framework/Versions/3.14/Python`, then `Python.framework`.
3. The main executable.
4. The `.app` **last**, with the entitlements plist if any — the outer seal is what carries
   entitlements.
5. `codesign --verify --strict --deep`.

**The trap, and it is measured.** A first pass matching only `*.dylib`/`*.so` missed
`_internal/Python.framework/Versions/3.14/Python` — no file extension — and the app died at
launch: *"code signature in '…/Python.framework/Versions/3.14/Python' not valid for use in
process: mapping process and mapped file (non-platform) have different Team IDs."* This is
the exact failure that makes people paste `disable-library-validation` into their recipe.
**Do not.** The bug is an unsigned nested Mach-O. The entitlement masks it and weakens the
one guarantee notarization exists to provide.

Two more: `sherpa_onnx/lib/libonnxruntime.dylib` is a **symlink** and `codesign` errors on
symlinks — hence `-type f`. And onnxruntime's dylib is duplicated between
`onnxruntime/capi/` and `sherpa_onnx/lib/`; PyInstaller 6 relocates into
`Contents/Frameworks` and symlinks back into `Resources`. **Write the sign loop against the
actual bundle layout, not the venv's.**

### Entitlements: start at zero

**Measured:** onnxruntime 1.27 with the CoreML EP runs a real MiDaS inference on a real 4K
clip under a full Developer ID hardened-runtime signature with **no entitlements file at
all** — `POST /api/depth/preview` → 200, log: "number of nodes supported by CoreML: 191" of
196. `codesign --verify --strict --deep` → valid, satisfies its Designated Requirement.

So: hardened runtime, **zero entitlements**, and let a real launch plus the notarization log
tell us what breaks. The two commonly-pasted entitlements are both suspect here.
`disable-library-validation` is needed only if we dlopen a Mach-O signed by neither Apple
nor 6M536MV7GT — if the build signs everything we ship, it is satisfied.
`allow-unsigned-executable-memory` is a much broader hole than `allow-jit` and the honest
prior is that neither is needed: onnxruntime's EPs don't JIT, torch/MPS compiles Metal in a
system daemon, CPython 3.14's JIT is off by default. The one live candidate is libffi
trampolines via `_cffi_backend`/ctypes, which `allow-jit` covers on arm64. **Every
entitlement gets justified in writing in the build script's comments or it doesn't ship.**

### Order of operations (stapling is load-bearing)

sign nested → sign `.app` → `ditto -c -k --keepParent Suite.app Suite.zip` →
`notarytool submit Suite.zip --keychain-profile <p> --wait` → **`stapler staple Suite.app`**
→ build the DMG **from the stapled .app** → `codesign --timestamp --sign "$DEV_ID"
Suite.dmg` → `notarytool submit Suite.dmg --wait` → `stapler staple Suite.dmg` → verify.

Two submissions is correct, not wasteful. Build the DMG from an *un*-stapled app and the
DMG's ticket covers the download while the app the user drags to /Applications carries no
embedded ticket — it then works online and fails offline or on a slow network, which is the
worst possible bug shape.

## 5. What goes in the bundle

Measured, `du -sh`: **364 MB onedir without torch/sam2 (134 MB gzipped); 1.1 GB with them.**
Torch triples the app. `specs/08` §8's instinct was right; the number it guessed (~2 GB) was
not — Apple-silicon torch 2.13 is 492 MB unpacked. Realistic base DMG: **150–200 MB
compressed**. Do not promise smaller. Top of `_internal`: onnxruntime 64 MB, cv2 41,
scipy 33, a duplicated `libonnxruntime.1.27.0.dylib` 27.

### Torch / Stencil: not in the base DMG (decided)

`specs/08` §8 said Stencil's runtime ships on-demand through the Models page. It was right
and **the mechanism does not exist**: `suite/tools/stencil.py:22-40` currently tells the
user to `pip install torch … sam2` "in the suite's venv" — a frozen `.app` has no venv and
no pip. That is the single biggest spec-vs-reality gap in the milestone.

**Decision:** the Stencil runtime is a **second component, signed with the same Team ID
(6M536MV7GT) and notarized**, downloaded by the Models page into
`~/Library/Application Support/control-z/runtime`, with `sys.path` extended at launch when
present. Same-team signatures satisfy library validation, so this needs **no entitlement** —
but it *only* works if it is genuinely signed by 6M536MV7GT. Note that hooks-contrib's
`hook-torch.py` and `hook-sam2.py` both set `module_collection_mode = 'pyz+py'` (torch.script
and hydra do source introspection), so the component must carry source `.py` on disk; it
cannot be a trivially stripped payload.

**If the component slips, v1.0 still ships** — with Stencil's page saying, in a sentence,
that the packaged app can't install its runtime yet and pointing at the source checkout.
What it must **not** ship is today's string, which instructs the user to pip-install into a
venv that does not exist. An instruction the user physically cannot follow is the covenant
violated in the most literal way available.

### Three other things that would ship broken

- **faster-whisper's VAD asset is silently absent.** `scribe/transcribe.py:34` passes
  `vad_filter=True`; `faster_whisper/vad.py:291` loads `get_assets_path()/silero_vad_v6.onnx`;
  there is no hook for faster_whisper in hooks-contrib 2026.6; `find _internal -ipath
  "*faster_whisper*"` in the trial build returns **nothing**. Scribe dies on first transcribe.
  Needs `--collect-data faster_whisper` **and a smoke test that actually transcribes** — the
  test is what found this, not the hook audit.
- **Rise's model is unobtainable in a DMG.** `czcore/models.py` pins `realesrgan-x4` with
  `url=None` and hint `run: python -m rise.convert` — a command that cannot exist in the app
  (`rise.convert` imports torch; the TOC shows it MISSING from the no-torch build). The
  Models page would display an instruction the user cannot follow, and Rise silently degrades
  to lanczos. **v1.0 hosts the converted ONNX as a control-z release asset** with the already-
  pinned sha256 (`dd1d2f07a166…`), or the download page says Rise ships without its upscaler.
- **`ffprobe` resolution will fail in the shipped app even for Homebrew users.**
  `czcore/media.py:77` does `shutil.which("ffprobe")` and the error says "or use a packaged
  control-z build, which bundles it" — nothing bundles it. Worse, a Finder-launched `.app`
  inherits launchd's PATH, not the shell's; `/opt/homebrew/bin` is not on it. This looks fine
  forever in dev (terminal launches) and breaks for every downloader. And
  `suite/server.py:116` catches the exception and returns HTTP 415 "couldn't read that file
  as media" — a *file format* error for a *missing dependency*, on every file. That is
  "failures are sentences" inverted: a true sentence blaming the wrong thing.
  **Fix:** one `czcore/tools.py` with `ffmpeg_path()`/`ffprobe_path()` — bundle-relative when
  `sys.frozen`, else `shutil.which`, else the honest sentence — and swap the five call sites
  (`czcore/media.py:77`, `scribe/cli.py:21`, `suite/tools/clear.py:48` and `:324`,
  `suite/tools/scribe.py:72`) in **one commit**. Sign the bundled binaries like any other
  Mach-O. Test by **double-clicking from Finder**, never from a shell.

### Non-issues, retired here so nobody re-litigates them

- **Lazy imports do not defeat PyInstaller.** Its modulegraph scans bytecode for IMPORT_NAME
  regardless of scope. Controlled test: function-level `import colorsys` → PRESENT,
  function-level `from mailbox import Maildir` → PRESENT, `importlib.import_module("wave")`
  → MISSING. The repo has essentially zero dynamic-string imports (one literal
  `__import__("os")` at `suite/tools/ofx.py:99`). **No repo-side hiddenimports are required.**
  Don't spend a day on this.
- **`suite/static` needs no `sys._MEIPASS` branch.** `STATIC = Path(__file__).parent /
  "static"` (`suite/server.py:28`) works unmodified frozen — PyInstaller sets `__file__` to a
  real `_MEIPASS`-relative path. Verified on the running frozen binary: `/` → 200,
  `/static/app.css` → 200. Same for `depth/templates` via `parents[2]`
  (`suite/tools/depth.py:195`): `POST /api/depth/templates` wrote all five `.setting` files
  from the frozen bundle. The load-bearing detail is the `--add-data` **destination**:
  `suite/static:suite/static` and `depth/templates:depth/templates`. Adding a `resource_path()`
  helper would be dead code solving a problem that doesn't exist.
- **No `multiprocessing.freeze_support()` needed.** Jobs run in daemon threads
  (`czcore/appshell/jobs.py:147,149,168`); there is no ProcessPool anywhere. Note this
  contradicts `specs/08` §8's "jobs run in worker processes … so a stuck propagation can be
  killed" — **that sentence is false today.** Correct the spec or accept the limitation, but
  do **not** "fix" it by adding multiprocessing at v1.0: frozen spawn + `sys.executable`
  re-exec is a whole new class of packaging bug and nothing needs it.
- **pywebview 6.2.1**'s vendored hook collects `webview/js/*.js` automatically; the Cocoa
  backend is reached by a static function-level import and is already in the TOC.
  `--hidden-import webview.platforms.cocoa` is belt-and-braces.
- **Build from `/Users/amateurmenace/control-z/.venv`.** Running PyInstaller from a foreign
  venv prints "This is ALWAYS the wrong thing to do" and becomes a hard error in
  PyInstaller 7.0. Add `packaging = ["pyinstaller>=6.21"]` as an extra in `pyproject.toml` —
  not to the `suite` runtime extra; the shipped app should not carry its own builder.

## 6. Milestones

- **v1.0-a — the LGPL stack.** Build LGPL-2.1 FFmpeg (no x264/x265, videotoolbox on); PyAV
  from sdist against it; FFmpeg-free OpenCV; delete the GPL fallback candidates and the two
  legacy `CODECS` tables; `czcore/tools.py` resolver + five call sites; NOTICE grows its
  native-libraries section. **Gate:** `otool -L` across the whole tree matches no x264/x265,
  and the six export presets still produce files.
- **v1.0-b — the bundle.** `packaging/build_suite.sh` + `.spec`; `--add-data` for
  `suite/static` and `depth/templates`; `--collect-data faster_whisper`; bundled
  ffmpeg/ffprobe. **Gate:** the frozen app opens a real clip and runs one job per engine —
  Pivot analyze, Scribe transcribe (this is what catches the VAD miss), Clear isolate, Rise
  enhance, Depth preview — **launched by double-click from Finder**.
- **v1.0-c — signed.** The §4 sequence, zero entitlements, ad-hoc fallback preserved.
  **Gate:** `codesign --verify --strict --deep` valid; the signed app still runs the §b
  smoke set; `spctl --assess` positive on the `.app`.
- **v1.0-d — notarized.** *Stephen-gated.* **Gate:** `notarytool submit --wait` → Accepted;
  `stapler validate` passes on both `.app` and `.dmg`; `spctl -a -vvv` positive on the DMG;
  and the DMG is verified on a machine that has **never** had a dev cert or Homebrew.
- **v1.0-e — the card flips.** Release tag, DMG asset, Rise's ONNX asset, download page
  states arm64-only and any live limitation. *Site lane, not this one.*
- **v1.1 — the Stencil runtime component.** Second signed+notarized payload, Models-page
  download, `sys.path` extension. Ships in v1.0 if it's ready; does not hold v1.0 if not.
- **v1.x — Windows.** WebView2 shell, DirectML/NVENC, installer. The Windows PyAV wheel has
  the *identical* x264/x265 problem and needs the same custom build — but its DLL config
  does enable `--enable-mediafoundation --enable-nvenc --enable-amf`, so `specs/00`'s Windows
  encoder plan is satisfiable. Do not infer the Windows config from the macOS wheel; the
  macOS one shows `--disable-mediafoundation`, which is a Windows-only no-op. Not scoped
  until macOS v1.0 ships.

## 7. Definition of done

Per `specs/00`'s gate style, a v1.0 is shipped only past the whole chain:

> LGPL linkage gate green → frozen app runs one real job per engine, double-clicked from
> Finder → `codesign --verify --strict --deep` valid → notarytool **Accepted** → `stapler
> validate` on `.app` and `.dmg` → **`spctl --assess` positive on a machine that has never
> seen a dev cert** → 133 tests still green → download page names arm64-only and every live
> limitation → release tag → the site's Suite card points at a real file.

The acceptance criterion is `spctl --assess`, not "the script ran." OpenNR's script runs
fine and ships a Gatekeeper-rejected pkg.

Note the test suite is not evidence of compliance: `tests/test_export_presets.py:35,41,72`
and `tests/test_frames.py:31` hardcode `libx264` — `test_frames.py:31` calls
`out.add_stream('libx264', …)` for real and **will fail** against the LGPL build. 133-green
today means the tests depend on the GPL encoder. Fixing them is part of v1.0-a.

## 8. Risks, named

- **First notarization *of this stack*.** Not the first ever — that claim was in an earlier
  draft of this spec and it was wrong. `notarytool history` shows this team notarizing since
  2026-06-13 (ATEM IP Patchbay `.dmg`, `atem-net-diag` `.app.zip`, all Accepted), and Hush
  3.7.0 and Speak 0.2.0 were notarized and stapled on 2026-07-16 — the plugins had only ever
  taken the skip branch because no profile was stored, not because anything was broken. What
  is *actually* unproven is this **dependency set**: a 500-Mach-O PyInstaller tree with
  onnxruntime, ctranslate2, sherpa-onnx and PyAV. `codesign --verify` passing does not predict
  what Apple objects to. Mitigation: submit early — a throwaway submission of a minimal
  PyInstaller app with this stack converts three of §9's open questions into facts for the
  price of one upload.
- **GPL contamination is physical and already in the tree.** libx264 ×2 and libx265 ×2, linked
  by libavcodec per `otool`. It cannot be fixed by deleting the dylibs — avcodec links them at
  load; it needs a rebuild. Rebuilding PyAV against a custom FFmpeg is real work, not a flag
  flip. Discovering this at DMG-signing time would be very expensive; it is decided here.
- **Two FFmpeg copies collide at the ObjC runtime today** and macOS says so out loud. It has
  not crashed for us — which is why it will crash for a user, once, unreproducibly. Fix before
  ship, not after the bug report.
- **`shutil.which` in a Finder-launched app.** Works forever in dev, breaks for every
  downloader. Only a genuine double-click tests it. (A terminal `open ./Suite.app` can leak
  the caller's environment — that test is inconclusive and was flagged rather than trusted.)
- **The Stencil component is the largest net-new work in the milestone**, and it is a
  packaging *design* problem (where it lands, what the page says while it fetches ~750 MB,
  how `sys.path` is extended, same-Team-ID signing) rather than a build-flag problem. It is
  §6's v1.1 for exactly that reason. Do not let it become a footnote *or* a v1.0 blocker.
- **VideoToolbox is a picture change, not just a license change.** Free legally, free against
  the preset contract, not free against low-bitrate H.264 quality. Eyeball it.
- **CI cannot produce a shippable artifact.** Both sibling workflows run on `macos-14` with no
  certs, so the `if DEV_ID` guard silently ad-hoc-signs. `gh run download` output is not
  signable after the fact. **The release build is a local, human-run step on Stephen's Mac**
  unless someone deliberately adds .p12-import-from-secrets. Note CI's macOS 14 is older than
  this machine's macOS 26.1 — local verification does not transfer to CI.
- **`torch`'s JIT under hardened runtime is untested.** The zero-entitlements result is
  measured for onnxruntime+CoreML only; torch was excluded from the signing experiment, and
  ctranslate2's `libctranslate2.4.8.1.dylib` is bundled but was never exercised in a signed
  app. Both must be tested before the Stencil component ships.

## 9. Open questions (not answered here on purpose)

- **Does Stephen want a Developer ID Installer certificate?** The DMG route needs only the
  Application identity he has. Issuing one would retroactively fix the Hush/Speak pkg
  rejection. If not, that defect should be stated on their download pages rather than left
  silent.
- **One notary profile or several?** Speak's script hardcodes `opennr-notary` (and
  `org.opennr.speak`). A notarytool profile is per-Apple-ID, not per-product. Pick one name —
  `cz-notary` — and say so, or Stephen stores credentials twice and a third script references
  a fourth product.
- **LGPL relink vs. library validation.** LGPL wants a user to be able to swap in their own
  libavcodec; hardened runtime will refuse to load it. We do **not** buy the freedom with
  `disable-library-validation` — that trades the app's security posture for a right nobody
  has exercised. The honest move is a NOTICE sentence saying relinking is blocked by the code
  signature. Stephen should confirm he's comfortable with that reading.
- **Who builds and hosts the LGPL FFmpeg**, for macOS now and Windows later? This is real
  recurring build infrastructure that `specs/00`'s one-line mandate doesn't acknowledge.
- **Does `deep-filter` stay a runtime download?** `clear/isolate.py` fetches and execs a
  DeepFilterNet3 binary (MIT/Apache, sha256-pinned). It's signed by a different team and is
  exec'd, not dlopened, so library validation doesn't apply — but nobody has run it from a
  notarized app. Bundling it makes it part of our submission and couples our release to
  theirs. Test first, then decide.
- **Does any real footage need ffprobe fields PyAV can't give?** PyAV 18 exposes no
  `field_order` — Rise's interlace guard (`rise/video.py:19,68`) refuses footage based on it.
  `frame.interlaced_frame` exists but means something different (decoded reality vs. container
  claim) and costs a decode. Only matters if we go all-PyAV and drop the CLI binaries; this
  spec keeps the binaries, so it stays open. It needs a genuinely interlaced test clip.

## 10. Lanes and git discipline

**main has an active site workstream.** Three regions are in play and two lanes want the same
files, so the boundaries are explicit:

| Lane | Owns | Never touches |
|---|---|---|
| **Packaging (this spec)** | `packaging/**` (new), `.github/workflows/**` (virgin — control-z has no CI), the `packaging` extra in `pyproject.toml`, `tests/test_packaging.py` (new file) | `site/**`, `CHANGELOG.md`, `suite/static/**` |
| **Core/honesty** | `czcore/tools.py` + the five `shutil.which` sites, `czcore/media.py`, the two legacy `CODECS` tables | `packaging/**`, `site/**` |
| **Site (Stephen's)** | `site/**`, the Suite card at `site/templates/home.html:191-192` | everything else |

Rules:

- **`git fetch origin && git merge origin/main` before every push. Never force-push. Never
  rebase.** Merge-not-rebase is already this history's law — see `980ffcf` and `1f7c38f`. A
  push was rejected once today already; three lanes makes that likelier, not rarer.
- **Run the 141 tests *after* the merge, not before.** Two green branches can merge to red.
- **Nobody but the site lane runs `python3 site/build.py`.** It regenerates `site/docs/*.html`
  + `CNAME` wholesale — an unmergeable diff — and it copies files in from
  `~/Hush/Hush-OpenNR/docs` *outside the repo*, so a bake on the wrong machine silently drops
  `whitepaper.html` and the PDF.
- **Only the merging session writes `CHANGELOG.md`.** Every lane wants the same header
  region. Other lanes hand over a scratch entry.
- **The card flip is the handback, not the job.** v1.0's milestone text ends with "site 'Suite'
  card flips to a real download," which tempts the packaging lane into
  `site/templates/home.html` — the highest-traffic file in the repo. Produce the artifact and
  a release URL; the site lane does the two-line edit.
- `suite/tools/ofx.py` parses **Hush and Speak's** GitHub release assets. If control-z's own
  artifact naming changes, don't disturb that page's expectations for the other two repos.
  Different repos, same file. Read before editing.

**Two loose ends are already closed** — don't reopen them. `depth/cli.py`'s full-resolution
frame hoarding is fixed (`native=True`, 256 KB/frame regardless of source; a 659-frame 4K
clip holds 165 MB where it asked for 21.7 GB), and the diarization pair is in the registry
with a named-member tarball extraction and license cards. Both landed in the working tree on
2026-07-16 and are in the CHANGELOG's "loose ends" entry. What remains of the depth issue is
the *length* blowup — pass 1 still accumulates every frame's 256×256 map plus a normalized
copy, ~0.5 GB per 1000 frames, in both `depth/cli.py` and `suite/tools/depth.py:118-148`.
That is engine debt, not packaging, and it belongs to whoever holds this checkout. The
resolution blowup is fixed; the length blowup is not; say both.

One more honesty fix that isn't packaging but should not ship: `suite/tools/modelstore.py`
returns "removed — it re-downloads on next use" for every kind. Verify that's still true now
that diarization is registered, and if any kind is a one-way door, say so.

---

## Appendix: kickoff prompt for the build session

> Package **control-z Suite v1.0** — the macOS ship — in `/Users/amateurmenace/control-z`
> (existing monorepo, venv at `.venv`, Python 3.14.6 arm64, version 0.4.0.dev0, 133 tests
> green via `.venv/bin/python -m unittest discover -s tests -t .`). The app is feature-
> complete: `python -m suite` opens a pywebview window, `--serve` runs it in a browser. All
> that's left is turning it into a signed, notarized DMG.
>
> **Read first, in this order:** `specs/09-packaging.md` — this is your plan, follow it, and
> it already contains the measured answers to most of what you'd otherwise go find out.
> Then `specs/08-suite-app.md` §7–8 (the milestone you're closing, and note §8's "jobs run
> in worker processes" is **false** — they're daemon threads), `specs/00-overview.md`
> (covenant + the packaging and LGPL-ffmpeg mandates), `CHANGELOG.md` (what exists).
> Sibling repos `/Users/amateurmenace/DaVinci Plugins/OpenNR` and `.../Speak` have a
> `build_release.sh` worth reading for its **shape** — identity autodetect, `--timestamp
> --options runtime`, the notarize-if-profile-exists guard, the ad-hoc fallback. Read
> §2 of the spec before you copy anything from them: their notarization has **never run
> once**, their shipped pkg is Gatekeeper-rejected, and their `--deep` flag is wrong for a
> 500-dylib bundle. Do not copy `--deep`.
>
> **Scope, in order.** (a) The LGPL stack: build FFmpeg without x264/x265, PyAV from sdist
> against it, an FFmpeg-free OpenCV, delete the GPL fallback candidates in
> `czcore/media.py` and the legacy `CODECS` tables in `pivot/render.py` and
> `rise/cli.py:59-64`, fix the two tests that hardcode `libx264`, grow NOTICE a
> native-libraries section. Gate: `otool -L` across the tree matches no x264/x265.
> (b) `packaging/build_suite.sh` + a `.spec`: PyInstaller onedir from `.venv` (add
> `packaging = ["pyinstaller>=6.21"]` to `pyproject.toml`; do **not** run PyInstaller from a
> side venv), `--add-data suite/static:suite/static` and `depth/templates:depth/templates`
> (destinations matter; the code needs no `_MEIPASS` branch — this is verified),
> `--collect-data faster_whisper` (its `silero_vad_v6.onnx` is otherwise silently absent and
> Scribe dies on first transcribe), and the bundled `ffmpeg`/`ffprobe` binaries plus a
> `czcore/tools.py` resolver — but the five `shutil.which` call sites are the **core lane's**
> commit, so consume the function signature, don't edit them yourself unless you're told the
> lane is free. (c) Sign per spec §4: leaf-first, batched, Mach-O by inspection not
> extension, `Python.framework/Versions/3.14/Python` included (missing it is the "different
> Team IDs" death), the `.app` last, **zero entitlements** — onnxruntime+CoreML is verified to
> run under hardened runtime with none. If something breaks, find the unsigned binary; do not
> reach for `disable-library-validation`. (d) DMG: sign → submit zip → **staple the .app** →
> build the DMG from the stapled app → sign → submit → staple → verify.
>
> **The credentials wall is gone — an earlier draft of this spec said you would hit one.**
> As of 2026-07-16 the machine has the `opennr-notary` keychain profile, `Developer ID
> Application: Stephen Walter (6M536MV7GT)` **and** `Developer ID Installer` (the latter was
> created that day; its absence is why every Hush/Speak release before it shipped
> Gatekeeper-rejected). So you can take the DMG all the way to notarized and stapled
> yourself — `xcrun notarytool submit … --keychain-profile opennr-notary --wait`. **Never
> enter or handle the app-specific password**; if the profile is ever missing, stop and ask
> Stephen to run `store-credentials` himself. A `403 — a required agreement is missing` is
> not a bad password: it means the Program License Agreement needs re-accepting at
> developer.apple.com, and only Stephen can click it.
>
> **Definition of done for this session:** the LGPL gate is green; the frozen app,
> **double-clicked from Finder** (never launched from a shell — that leaks your PATH and
> hides the `shutil.which` bug), opens a real clip and runs one job per engine (Pivot
> analyze, Scribe transcribe, Clear isolate, Rise enhance, Depth preview); `codesign --verify
> --strict --deep` is valid on the signed `.app`; `spctl --assess` is positive on a NOTARIZED, stapled DMG; the 141 tests
> are still green; `tests/test_packaging.py` covers the linkage gate and the resource paths.
> Test footage: `/Users/amateurmenace/Movies/NR Test SHort Sabby.mov`.
>
> **Git discipline — main has an active site workstream.** Your lane is `packaging/**`,
> `.github/workflows/**` (virgin territory, no CI exists), `pyproject.toml`'s packaging
> extra, and a new `tests/test_packaging.py`. **Stay out of `site/**` entirely** — never run
> `site/build.py`, and the "Suite card flips to a real download" part of the milestone is
> *not yours*; hand back a release URL. Don't write `CHANGELOG.md`; hand over a scratch
> entry. `git fetch origin && git merge origin/main` before every push, run the tests *after*
> the merge, **never force-push, never rebase**.
>
> **Honesty rules, which are the product.** Don't add an entitlement you can't justify in a
> written comment. Don't ship a string that tells a user to do something they cannot do — the
> Stencil page currently says to pip install into a venv the .app doesn't have, and
> `czcore/models.py`'s `realesrgan-x4` hint says to run a command that needs torch; flag both
> rather than papering over them. Don't cite `avcodec_license()` or PyPI metadata as license
> evidence — both say "not GPL" here and both are wrong; `otool -L` is the authority. If
> something doesn't work, the DMG doesn't ship with a sentence claiming it does. **Commit
> nothing without asking.**
