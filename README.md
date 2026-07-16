# control-z

Free, open-source cleaning, prepping, and finishing tools for DaVinci Resolve — built for community media
centers, journalists, filmmakers, and artists. Part of the
[Community AI Project](https://community.weirdmachine.org). **Undo the paywall.**

Siblings: [Hush](https://github.com/amateurmenace/Hush-OpenNR) (denoise, OpenFX) and
[Speak](https://github.com/amateurmenace/Speak) (film character, OpenFX) live in
their own repos. This monorepo holds the standalone tools and the suite site.

## Quick start (macOS)

**Double-click `Start control-z Suite.command`.** First run builds a private
environment beside it and installs what the tools need (a few minutes); after
that it opens in seconds. You need [Python 3.10+](https://www.python.org/downloads/)
and ffmpeg (`brew install ffmpeg`) — the launcher checks both and says so if
either is missing.

Prefer the terminal? Nothing checks the prerequisites for you here, so install
ffmpeg first (`brew install ffmpeg`) — without it the tools fail at the first
decode or render, and the error will sound like your file is broken rather than
like a missing tool.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # what the tools need
.venv/bin/pip install -e .                  # the tools themselves, and the CLIs
.venv/bin/python -m suite            # desktop window
.venv/bin/python -m suite --serve    # or in a browser at 127.0.0.1:8300
```

Both install lines are needed: `requirements.txt` carries the dependencies and
nothing else, `pip install -e .` carries the packages and nothing else (the
pyproject declares no dependencies of its own).

Everything runs on your machine. No accounts, no telemetry, nothing uploaded.
Models download on first use — each shows its license and verifies its hash,
and the **Models** page lists every one with its size and a remove button. Two
exceptions, named in full under [Known gaps](#known-gaps).

> **This is a dev checkout, not a signed app.** The v1.0 build (signed,
> notarized, ffmpeg bundled, double-click DMG) isn't done yet — that's the
> next milestone. What's here is the real thing running from source.

### Two optional extras, honest about their cost

| Extra | What it unlocks | Install |
|---|---|---|
| **Stencil runtime** (~700 MB) | click-to-matte (SAM 2.1) | torch + SAM 2 from Meta — see below |
| **DeepFilterNet binary** | Clear's voice isolation | the Clear page prints the download line |

Everything else works without them, and the pages say so instead of failing.

```sh
.venv/bin/pip install torch
.venv/bin/pip install "git+https://github.com/facebookresearch/sam2.git"
```

SAM 2 installs from Meta's own repository, not from PyPI: the `sam2` name on
PyPI is an unaffiliated third-party fork, and this is a model runtime we hand
your footage to. The ~700 MB is measured on Apple silicon, where torch ships
without CUDA; on Linux/Windows the default wheels bundle CUDA and the install
runs several times larger.

| Package | Tool | Status |
|---|---|---|
| `suite/` | **the Suite** — one desktop app around the tools (viewer, queue, export panel) | working: shell + all six tools |
| `czcore/` | shared core (media IO, encode presets, shots, exports, app shell + job queue, model store, Hush-core denoise) | working |
| `pivot/` | **Pivot** — smart reframe (9:16/1:1 from your masters) | CLI + Suite UI working |
| `stencil/` | **Stencil** — AI roto mattes (SAM 2.1) | CLI + Suite UI working (torch is an optional heavy) |
| `scribe/` | **Scribe** — transcription, captions, text-based cuts | CLI + Suite UI working (incl. speaker labels) |
| `clear/` | **Clear** — dialogue rescue (DF3 + DSP) | CLI + Suite UI working |
| `rise/` | **Rise** — super-resolution (engine also lives inside Pivot) | engine + CLI + Suite UI working |
| `depth/` | **Depth** — depth mattes + Fusion template pack | CLI + Suite UI working |
| `site/` | control-z.org (bake: `python3 site/build.py`) | built, undeployed |

Working = verified end-to-end on real footage this side of packaging. Not yet:
signed installers (the v1.0 gate: PyInstaller app, signing, notarization,
DMG), Windows builds, Resolve paste-tests for the Fusion exports/templates.
See CHANGELOG.md for honest detail.

Specs live in [`specs/`](specs/) — start with [`00-overview.md`](specs/00-overview.md);
the Suite app is [`08-suite-app.md`](specs/08-suite-app.md).

## What each tool is for

Home opens on two doors, split by which way the footage is travelling.
**Prep** is what you do to footage on its way *into* your editor — Clear (hum,
clicks and room out of the dialogue), Stencil (click an object, bring its
matte in with the clip), Depth (a depth map to fog, grade or rack focus
against). **Finish** is the cut on its way back *out* — Pivot (reframed to
9:16 or 1:1), Scribe (captions and subtitles), Rise (pushed up to delivery
resolution). Tools don't police the door you came through: Scribe will paper-
edit raw interviews into a selects EDL, and Rise will take a tape master, both
long before picture lock. The Queue runs one job at a time across all six and
survives quitting; Install OpenFX puts Hush and Speak into Resolve.

Every tool keeps its measurement surface on by default — that's the covenant,
not a feature: Pivot draws the camera path it solved, Rise shows where the
model added energy against honest bicubic, Clear plays you exactly what it
removed, Scribe tints the words it isn't sure about, Stencil charts its
confidence per frame, Depth reports that its preview is per-frame while the
render smooths. Turn them off if you like; shipping without them isn't an
option.

## Development

```sh
python3 -m unittest discover -s tests -t .   # core algorithm tests, no deps needed
.venv/bin/pip install -r requirements.txt    # full pipeline + suite deps
.venv/bin/pip install -e .                   # the packages, and the CLIs
.venv/bin/python -m suite --serve            # drive the UI in a browser
```

Each tool also has a CLI — every UI control mirrors a flag, so stations can
script what the app does by hand. `pip install -e .` is what puts `pivot-cli`,
`rise-cli`, `clear-cli`, `scribe-cli`, `depth-cli`, `stencil-cli` and `suite`
on your PATH; without it they don't exist, and every one of them also runs as
`.venv/bin/python -m pivot.cli` (and so on) straight from a checkout.

### Known gaps

- **Rise's Real-ESRGAN weights are converted, not downloaded**: run
  `.venv/bin/python -m rise.convert`. Until then Rise falls back to lanczos,
  labeled as a scaler, never as synthesis.

Every tool follows the suite covenant: free forever (MIT), works with the **free**
version of Resolve, local-only processing, shows its work, honest limitations.

MIT © Weird Machine / Brookline Interactive Group
