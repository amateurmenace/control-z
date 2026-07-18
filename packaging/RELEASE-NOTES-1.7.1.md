# control-z Suite 1.7.1 — the community wing lands, and the record opens

Sign and ship THIS one — it supersedes the unreleased 1.6.0 and 1.7.0
(their changelog entries stay for the record; don't tag or sign them).
Everything since **1.5.0** ships here. Tag `v1.7.1`. The app now calls
itself the **Community AI Project** — fifteen tools on one rail, seven
of them the civic wing. Highlights since 1.5.0:

- **The suite has a name and a front.** Window, tab, brand and serve
  line read *Community AI Project — the world's most advanced civic
  media suite*. Home is a conveyor: **the line** (search → moments →
  kit → record) and **seen and heard** (captions → languages → the
  picture, spoken), every station lighting solid as its tool goes live.
  Statics cache-bust on version + mtime, so hard-refresh rituals are
  dead. (1.6.0)

- **Community Publisher (beta) — the kit that gets it seen.** A program
  in, clips in three frames with real thumbnails, per-field copy, an
  editable lower third, and a bundle out. The fetch ladder learned that
  mp4 is a container not a codec (h264 preferred by name — YouTube ships
  AV1-in-mp4 the frame service can't read). **Send to the Record** and
  the prior-appearances line stand in Highlighter and Publisher, live
  against Memory's contract. **Grabber** became a search desk: one query
  runs YouTube and the CivicClerk portal in parallel, with weekly
  schedules and a broadcast re-namer. (1.6.0)

- **Community Memory (beta) — the telescope opens.** A meeting's
  captions come straight in, the whole corpus is searchable, and every
  hit lands the tape on the second it was said. And it learns to see:
  Memory finds the issues that recur across meetings — vision zero, the
  golf-course lighting, short-term rentals — names each from the
  record's own words, and tracks every appearance. Follow a thread and
  it tells you what changed when the issue resurfaces; walk an issue's
  timeline, its votes as milestones; steward-merge, split, rename. All
  local, all labeled, beside the official record and never in its place.
  (1.7.0)

- **Community Interpreter (beta) — the meeting, carried across.** Any
  meeting Highlighter has read becomes timed caption tracks in the seven
  panel languages plus Simple English, translated on your own key with
  the town's glossary riding every pass, provenance inside the .vtt
  itself, and a one-tap flag → review-queue → correction loop. (1.7.0)

- **Community Narrator (beta) — the picture, spoken.** Audio description
  for community TV, a thing public access has essentially never had: the
  pauses and slides mapped, each moment drafted by vision on your key in
  DCMP style with a lint that catches camera-talk and interpretation,
  every draft waiting on a human accept, then spoken in a local voice
  and ducked under the program — four outputs, provenance on every one.
  (1.7.0)

- **Two engines moved to the middle of the table.** `czcore/mt.py`
  (chunked translation, town glossaries) and `czcore/tts.py`
  (sherpa-onnx VITS voices, found by shape) — translation and speech for
  whatever the wing carries next. The model store learned that a voice
  is a *directory*: the new `archive_dir` mechanism keeps a whole
  tarball member folder under the same pinned-hash covenant, and
  **vits-ljs** takes its card (Apache-2.0, public-domain LJSpeech,
  lexicon-based so no GPL espeak data rides along). (1.7.0)

- **One reel timeline, suite-wide; the record drawn readable; the spend
  in view.** Moments picked anywhere — analytics grids, the record's
  search, an issue's beads — land on one persistent timeline along the
  bottom of every page; ▶ Render cuts one montage across every meeting
  on it. The standalone Library retired: its cross-meeting analytics
  moved into Highlighter's analyzer and Memory's new **Analytics** view,
  rebuilt with color-vision-validated charts where every mark opens its
  receipts. And an **AI audit** in Settings counts every API call from
  the provider's own token numbers, attributes it to the tool that spent
  it, and estimates the dollars — the covenant's honesty applied to
  spend. The can't-scroll-to-the-top bug is fixed. (1.7.1)

## Build notes for the signing operator

**No required-dependency changes since 1.5.0.** The wing's engines ride
what was already there: `czcore/llm.py` is stdlib `urllib` (BYO key,
never bundled), `czcore/tts.py` rides **sherpa-onnx** (already a suite
dep for Scribe's diarization — the sign pass already handles its
symlink). Narrator's `vits-ljs` voice and every other model download on
first use; the **frozen build bundles none of them** — same posture as
Real-ESRGAN and MiDaS. Interpreter's translation and Narrator's vision
drafts need the user's own API key and say so honestly without one.
torch/SAM 2 and DeepFilterNet stay OPTIONAL and unbundled exactly as in
1.5.0 (the frozen app refuses the pip route with a sentence — expected).

**One load-bearing spec change you should know about** (already in this
tree): `packaging/suite.spec` now names the community packages
(`publisher`, `memory`, `interpreter`, `narrator`) and the lazily
imported `czcore.mt` / `czcore.tts` as hiddenimports, and — the fix that
matters — ships `interpreter/glossaries/*.json` as `datas`. PyInstaller
doesn't read pyproject's package-data, so without that entry a frozen
Interpreter would find no seed glossary and every town would open empty.
`build_suite.sh` now gates on the seed's presence like it gates on the
Scribe VAD model. A stale 1.6/1.7 freeze would have shipped a hollow
Interpreter; this one won't.

## The ritual (run on the signing Mac)

    git pull
    # rebuild the repo's own venv if pyproject changed since your last freeze:
    .venv/bin/pip install -e '.[packaging]'
    .venv/bin/python -m unittest discover -s tests -t .   # packaging gates must pass HERE
    packaging/build_ffmpeg.sh   # only if vendor/ffmpeg is not already built
    packaging/build_suite.sh    # freezes onedir; fails loudly on any missing asset
    packaging/sign_suite.sh     # Developer ID, hardened runtime, zero entitlements
    packaging/notarize_suite.sh # staples the app, builds + notarizes the DMG
    # Then the gate that CANNOT run on a dev machine (specs/09 §7):
    #   spctl -a -vvv on a Mac that has never seen a dev cert or Homebrew.
    # Only after that verdict: GitHub release v1.7.1, DMG attached, this file
    # as the body.

Everything the frozen build needs is now declared. If `build_suite.sh`
stops with a FATAL, it is telling you exactly which asset didn't make it
— that is the guard doing its job, not a bug to route around.
