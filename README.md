# control-z

Free, open-source cleaning, prepping, and finishing tools for DaVinci Resolve — built for community media
centers, journalists, filmmakers, and artists. Part of the
[Community AI Project](https://community.weirdmachine.org). **Undo the paywall.**

Siblings: [Hush](https://github.com/amateurmenace/Hush-OpenNR) (denoise, OpenFX) and
Speak (film character, OpenFX) live in their own repos. This monorepo holds the
standalone tools and the suite site.

| Package | Tool | Status |
|---|---|---|
| `suite/` | **the Suite** — one desktop app around the tools (viewer, queue, export panel) | working: shell + all six tools |
| `czcore/` | shared core (media IO, encode presets, shots, exports, app shell + job queue, model store, Hush-core denoise) | working |
| `pivot/` | **Pivot** — smart reframe (9:16/1:1 from your masters) | CLI + Suite UI working |
| `stencil/` | **Stencil** — AI roto mattes (SAM 2.1) | CLI + Suite UI working (torch is an optional heavy) |
| `scribe/` | **Scribe** — transcription, captions, text-based cuts | CLI + Suite UI working (incl. diarization) |
| `clear/` | **Clear** — dialogue rescue (DF3 + DSP) | CLI + Suite UI working |
| `rise/` | **Rise** — super-resolution (engine also lives inside Pivot) | engine + CLI + Suite UI working |
| `depth/` | **Depth** — depth mattes + Fusion template pack | CLI + Suite UI working |
| `site/` | control-z.org (bake: `python3 site/build.py`) | built, undeployed |

Working = verified end-to-end on real footage this side of packaging. Not yet:
signed installers, Windows builds, the v0.4 suite services (Install OpenFX,
Models, Settings pages), Resolve paste-tests for the Fusion exports/templates.
See CHANGELOG.md for honest detail.

Specs live in [`specs/`](specs/) — start with [`00-overview.md`](specs/00-overview.md);
the Suite app is [`08-suite-app.md`](specs/08-suite-app.md).

## Run the Suite

```sh
pip install -r requirements.txt
python -m suite            # desktop window (pywebview)
python -m suite --serve    # same app in your browser at 127.0.0.1:8300
```

## Development

```sh
python3 -m unittest discover -s tests -t .   # core algorithm tests, no deps needed
pip install -r requirements.txt            # full pipeline + suite deps
```

Every tool follows the suite covenant: free forever (MIT), works with the **free**
version of Resolve, local-only processing, shows its work, honest limitations.

MIT © Weird Machine / Brookline Interactive Group
