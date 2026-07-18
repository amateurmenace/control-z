# control-z Suite 1.9.0 — the record grows teeth, and learns to draw

Sign and ship **THIS** one. It supersedes the unreleased **1.8.0** (whose
changelog entry stays for the record; don't tag or sign it). Everything since
the last signed release, **1.7.1**, ships here. Tag `v1.9.0`.

The civic wing went from a searchable record to the most complete civic memory
a non-government entity has assembled — the town's own paper beside what was
said, who voted how, and the whole thing drawn as a picture anyone can open in a
browser. And the eight production tools got the connective tissue the civic wing
already had.

## Highlights since 1.7.1

- **The town's own paper joins the record (Documents).** Memory now pulls a
  meeting's agendas, minutes, and packets straight from the town's CivicClerk
  portal, extracts and chunks the text, embeds each chunk, and links it to the
  same issues the transcript joins. The written record interleaves onto every
  issue timeline with page-level citations. (1.8.0)

- **The Vote Ledger.** Roll calls read straight off the transcript — verbatim,
  timestamped, never inferred — and surfaced as a per-issue ledger and a
  per-member **"The votes"** accountability page, every cell linking to the
  moment on the tape. Officials only, by construction: a roll call is the board
  voting, and the town's own agenda supplies the roster that cleans the ASR's
  misheard names. (1.8.0)

- **The web edition breathes and draws.** *Publish the record* presses the
  public edition from the desk as a job with an edition diff and a push ritual.
  The edition gained the documents, the roll-call ledgers, an accountability
  page, **still watching** (follows in your browser, export/import as JSON), and
  an **offline PWA**. Then it grew the desk's analytical eye: every meeting page
  now carries the **eight civic framing lenses**, the **questions asked** typed
  by kind, and tension moments; **"The record, drawn"** (`/app/analytics`) is
  the cross-meeting picture — a framing heatmap, recurring topics, recurring
  names; and **the issue graph** (`/app/graph`) draws issues as the network they
  are. All static, all JS-off readable, all under one strict CSP. (1.8.0, 1.9.0)

- **The last two API doors have local hinges.** Interpreter's translation and
  Narrator's descriptions now try an on-device model first and fall back to your
  key, labeling every track by what actually drew it. Discovered by folder shape
  in the model store; they spend no API tokens and add nothing to the AI audit.
  When no model is installed the status line says so and the key path is
  unchanged. (1.8.0)

- **The desk gets what the record got.** Index now reads the sidecar law
  (`czcore/sidecars.py`) — one table of every mark the tools leave beside a
  clip — counts the library in the dashboard grammar, and turns the one real gap
  into one click. **The road** walks ticked clips through the tools (words ·
  rescue · reframe) as one clip-major queue job, skipping what's already made
  with the reason said. (1.9.0)

## Build notes for the signing operator

**One new required dependency since 1.7.1: `pypdf`** — pure-Python, no native
libraries, MIT. It powers Memory's document ingestion (extract + chunk agendas/
minutes/packets). It is declared in `requirements.txt`, the pyproject `suite`
extra, and — because Memory imports it lazily inside a function — as a
`suite.spec` hiddenimport. No other required dep changed: the local-model
engines ride runtimes already present (`ctranslate2` and `tokenizers` came in
with faster-whisper; `onnxruntime`, `pillow`, `numpy` were already suite deps).
`sentencepiece` was deliberately NOT added — the local translator reads a
`tokenizer.json` fast tokenizer instead.

**Spec changes already in this tree** (`packaging/suite.spec`): the hiddenimports
list gained `pypdf`, `czcore.vision`, and `czcore.mt_local` (all lazy,
function-level imports the static walk misses). `czcore/sidecars.py` needs no
entry — it's a module-top static import in `indexer/catalog.py`, so PyInstaller
follows it. No new `datas`.

**Models stay unbundled, downloaded on first use** — same posture as 1.7.1
(Real-ESRGAN, MiDaS, the vits-ljs voice). The two new local-model engines are
covenant-clean but their pinned Models-page cards are a follow-up, so nothing
new is bundled or downloaded by this build. **One decision owed to you before a
local-translation card ships:** NLLB-200 is CC-BY-NC-4.0 (non-commercial),
which collides with `czcore/models.py`'s permissive-only rule — a shipped MT
card is a deliberate licence call (MADLAD-400 is Apache-2.0 if you want
permissive). The engine mechanism is in; the model is your choice.

**The web edition is not part of the frozen app.** It presses to `site/docs/app`
and deploys via the site's gh-pages ritual, independent of the DMG. It is
already deployed at control-z.org/app for this release.

## The ritual (run on the signing Mac)

    git pull
    # rebuild the repo's own venv because pyproject changed (pypdf added):
    .venv/bin/pip install -e '.[packaging]'
    .venv/bin/pip install -r requirements.txt      # picks up pypdf
    .venv/bin/python -m unittest discover -s tests -t .   # gates must pass HERE (500 tests)
    packaging/build_ffmpeg.sh   # only if vendor/ffmpeg is not already built
    packaging/build_suite.sh    # freezes onedir; fails loudly on any missing asset
    packaging/sign_suite.sh     # Developer ID, hardened runtime, zero entitlements
    packaging/notarize_suite.sh # staples the app, builds + notarizes the DMG
    # Then the gate that CANNOT run on a dev machine (specs/09 §7):
    #   spctl -a -vvv on a Mac that has never seen a dev cert or Homebrew.
    # Only after that verdict: GitHub release v1.9.0, DMG attached, this file
    # as the body.

If `build_suite.sh` stops with a FATAL, it is telling you exactly which asset
didn't make it — that is the guard doing its job, not a bug to route around.
Two `tests/test_packaging.py` skips are environmental (an unbuilt vendor FFmpeg
in a fresh checkout) and clear once `build_ffmpeg.sh` has run.
