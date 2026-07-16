# control-z

Free, open-source finishing tools for DaVinci Resolve — built for community media
centers, journalists, filmmakers, and artists. Part of the
[Community AI Project](https://community.weirdmachine.org). **Undo the paywall.**

Siblings: [Hush](https://github.com/amateurmenace/Hush-OpenNR) (denoise, OpenFX) and
Speak (film character, OpenFX) live in their own repos. This monorepo holds the
standalone tools and the suite site.

| Package | Tool | Status |
|---|---|---|
| `czcore/` | shared core (media IO, shots, exports, app shell, model store) | working |
| `pivot/` | **Pivot** — smart reframe (9:16/1:1 from your masters) | CLI + web UI working |
| `stencil/` | **Stencil** — AI roto mattes (SAM 2.1) | CLI working |
| `scribe/` | **Scribe** — transcription, captions, text-based cuts | CLI working (incl. diarization) |
| `clear/` | **Clear** — dialogue rescue (DF3 + DSP) | CLI working |
| `rise/` | **Rise** — super-resolution (engine also lives inside Pivot) | engine + CLI working |
| `depth/` | **Depth** — depth mattes + Fusion template pack | CLI working |
| `site/` | control-z.org (bake: `python3 site/build.py`) | built, undeployed |

Working = verified end-to-end on real footage this side of packaging. Not yet:
signed installers, Windows builds, per-tool UIs beyond Pivot's, Resolve
paste-tests for the Fusion exports/templates. See CHANGELOG.md for honest detail.

Specs live in [`specs/`](specs/) — start with [`00-overview.md`](specs/00-overview.md).

## Development

```sh
python3 -m unittest discover -s tests -t .   # core algorithm tests, no deps needed
pip install -r requirements.txt            # full pipeline deps (decode/detect/render)
```

Every tool follows the suite covenant: free forever (MIT), works with the **free**
version of Resolve, local-only processing, shows its work, honest limitations.

MIT © Weird Machine / Brookline Interactive Group
