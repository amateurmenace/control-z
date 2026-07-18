# control-z apps — changelog

## unreleased

### 1.7.0: the wing lands — the record, the languages, the voice — 2026-07-18

Three tools in one release — **Community Memory**, **Community
Interpreter**, **Community Narrator** — built in parallel on their own
lanes and merged home together: the biggest single entry since the
suite began. Said as what a resident can now do: search everything
your town has said across every read meeting and land the tape on the
second it was said; follow an issue for years and be told what changed
the day it comes back; read the meeting in your own language, or in
plain English; and hear what's on screen described aloud when you
can't see it. All of it local, labeled, on your own key or none —
beside the official record, never in its place.

- **Community Memory ships (beta) — the telescope opens.** A meeting's
  captions come straight in the moment you paste the link (Scribe
  listens only when a file has no words of its own), the whole corpus
  is searchable, and every hit is a second to jump to — one search
  across every meeting, and the video lands on the moment. Every
  reading shows its receipts and says it's beta.
- **And the telescope learns to see.** Memory finds the issues that
  recur across meetings — vision zero, the golf course lighting,
  short-term rentals — names each from the record's own words, and
  tracks every appearance. Anchored in the words a meeting actually
  says, never a guess about anyone's position. Follow a thread (star
  an issue, or a search) and the record keeps watch: when it resurfaces
  on a new agenda, Memory tells you what changed since last time — a
  paragraph, generative with your key, extractive without one. The
  long view is a line you can walk: an issue's timeline lays every
  meeting along a time axis, its moments as beads and its votes as
  milestones, and every one is a second to jump to. Steward-tended,
  not machine-final: merge two issues, split one that was fused,
  rename or promote a candidate — the record remembers its own edits.
  And "still watching" is a plain digest of your threads you can copy
  anywhere. No email, no account, nothing sent — the covenant, kept.
- **Community Interpreter ships (beta) — the meeting, carried across.**
  Open anything Highlighter has read and pick from the seven panel
  languages — Español, Simple English (plain language, first-class),
  中文, Português, Kreyòl, Tiếng Việt, Русский. One queue job coalesces
  the rolling captions into sentence-shaped cues, translates them
  chunked on your own key with the town's glossary riding every pass
  (do-not-translate names, vetted civic terms — the Brookline seed
  ships honestly marked *suggested*), and lands timed .srt + .vtt
  beside the meeting. Provenance is UI: every track says its model,
  glossary version and review status on the page and inside the .vtt
  itself; lines the model dropped stay English and say so. Every line
  takes one tap to flag into the review queue; a reviewer's correction
  rewrites the track in place. With the full recording local, tracks
  ride the player's own caption menu. No key? The page says so in a
  sentence and still reads existing tracks.
- **Community Narrator ships (beta) — the picture, spoken.** Audio
  description for community TV, a thing public access has essentially
  never had: open a read meeting with its recording and the pass runs
  in three moves — the pauses and the slides mapped (a [Music] or an
  applause marker counts as air, because it is; a shot that holds
  still is a slide, and slides read aloud are the point), each moment
  drafted by vision on your own key in DCMP style with a lint that
  names camera-talk, interpretation and past tense instead of trusting
  the prompt, and every draft waiting on a human accept — nothing
  unaccepted reaches a track. The render speaks each approved line in
  a local voice, ducks the program under the narration with a
  sidechain compressor, and lands four outputs: the mixed program, the
  mixed audio, a program-length narration track, and a descriptions
  transcript that always carries every approved description —
  wall-to-wall programs get the transcript and the extended mode
  instead of a mix that talks over the meeting, never a silent
  failure. Provenance rides the page and the files alike: vision
  model, voice, review status.
- **The wing speaks with one engine each.** `czcore/mt.py` (cue
  coalescing, chunked N|-protocol translation, glossary constraints —
  grown from Highlighter's translate feature) and `czcore/tts.py`
  (sherpa-onnx VITS voices, found by shape) join the middle of the
  table — translation and speech for whatever the wing carries across
  next.
- **The model store learns that a voice is a directory.** A new
  `archive_dir` mechanism keeps a whole member folder from a release
  tarball — manifest-hashed, one auditable line per file, the same
  pinned-hash covenant as every single-file model — and **vits-ljs**
  takes its card: Apache-2.0, the public-domain LJSpeech corpus,
  CMU-lexicon based so no GPL espeak-ng data rides along. Narrator's
  voice is one click now; any other VITS voice placed by hand still
  works, found by shape.
- **Highlighter's record line names the long view.** Beside prior
  appearances, tonight's topics now show as tracked issues — each
  pill a door straight into the issue's timeline on the Memory page.
- **Both lanes' packages join pyproject's truth** (`memory`,
  `interpreter`, `narrator`, the glossary seeds as package-data), so
  a frozen or installed suite imports what a dev checkout already
  found.

### 1.6.0: the wing doubles on paper, and the kit ships itself — 2026-07-17
- **The wiring is ready for Memory before Memory exists.** Highlighter
  and Publisher both carry **⬛ Send to the Record** — dashed and honest
  today ("Community Memory joins in 1.6"), live against the contract
  route the day lane B's `ready` flips, no further edits needed. Every
  loaded meeting carries the record line: prior appearances of
  tonight's topics once the record answers, the promise of it until
  then. And the chain got its hand-offs: **→ Publish kit** from any
  read meeting (pill on the loaded view, chip on every library row),
  publish + rename doors in the Grabber bin.
- **Publisher is ready.** Clip cards carry real frame thumbnails
  (retrying once if the first decode is cold), every copy field has a
  ⧉ copy-to-clipboard button, and the lower-third's two lines are
  editable per kit with the brand's defaults as placeholders. The
  format ladder learned the difference between "mp4" and "plays
  everywhere": h264 preferred explicitly (YouTube ships AV1 inside mp4,
  which the suite's own frame service can't decode), then any mp4,
  then anything, remuxed.
- **The last name tags fall in line** — coming-pages and About carry
  the Community AI Project tag.
- **The app says its real name.** The window, tab, brand and serve line
  all read **Community AI Project** — "the world's most advanced civic
  media suite" beneath. The rail reorders to the mission: Home, the
  **Civic Media Suite** on top (all seven squares), then **control-z ·
  free pro production tools** with the diamonds. BIG Video Grabber
  signs as **Video Grabber**.
- **Home runs the line.** The centerpiece is a conveyor: search + fetch
  → find the moments → make the kit → keep the record — a package rides
  the dashed belt station to station picking up each stop's color,
  coming stations stand dashed with their date, and ▶ Run the line
  drops you at the search desk.
- **The Grabber becomes the search desk.** One query runs YouTube
  (newest first) and the CivicClerk portal in parallel — events arrive
  with video and Zoom links badged, YouTube rows carry → Highlighter
  and Fetch, fetch-all queues the lot. Direct paste downloads at any
  quality — and the container promise is real: mp4-family codecs
  preferred at every rung, lossless remux catching fallbacks, audio-only
  landing m4a. New: **weekly schedules** ("everything from the last
  week, every Thursday at nine" — runs while the app is open, catches
  up on launch, says so), and the **broadcast re-namer** —
  {title}_{date} patterns to playout-safe names, live preview, sidecars
  traveling with the file. The bin grew publish and rename doors.
- **Index opens on the shelf.** The catalog appears on open — newest
  first, grouped by folder, filter chips (all / with words / missing),
  thumbs, → Highlighter on every row; typing narrows, clearing brings
  the shelf back. (The browse lived in the catalog all along; no UI
  ever called it.)
- **The finder takes Highlighter's front door** — town + board search
  first, the paste field second, the drop zone third.
- **One beautiful face for progress.** czProgress: an accent bar that
  shimmers while a job finds its feet and fills when it knows its
  fraction, stage message in mono, a live clock, green on done, the
  sentence on error — on every Grabber fetch and conform, Index scan,
  Publisher render and bundle. And the static cache token grew an
  mtime tail, so an edited file busts the browser mid-version too.
- **The community wing grows by four, and Home strings the wire.** The
  Community AI Project specs moved into the repo (specs/12–15: the
  program plan, Publisher, Memory, Interpreter+Narrator), and all four
  new tools stand on the community rail — one already filled in, three
  as honest coming-pages. Home's new centerpiece is **the wire**: two
  chains showing where one tool hands to the next — *the meeting, start
  to finish* (Grabber → Highlighter → Publisher → Memory) and *seen and
  heard by everyone* (Scribe → Interpreter → Narrator) — every step a
  door, coming steps dashed with their date, and a live-count per chain
  that flips itself the moment a tool turns real. A second machine
  builds Memory in parallel; specs/PARALLEL.md is the two-lane law
  (ownership by file, contracts before code, single-line slots).
- **Community Publisher ships (beta) — program in, kit out.** Open
  anything Highlighter can read and the publish kit builds itself:
  3–5 clip candidates with their reasons on them, cut in 16:9 / 1:1 /
  9:16 through one ffmpeg graph with captions burned as image strips
  (the type matches the brand on any ffmpeg build) and Slate's
  lower-third in the station's colors — bottom-left on widescreen,
  top-left on square and vertical, scaled to the short edge. Copy
  arrives extractive and labeled (titles, description with chapter
  stamps, alt text per clip, newsletter blurb, social drafts); ✨
  redraft spends the user's own key, takes a producer instruction, and
  keeps a way back. Renders run as one queue job; export is a named
  bundle + zip with copy.md, transcript and provenance — nothing left
  to rename. Brand kit is config in app support (station, accent,
  third style, voice) — the In-a-Box tenancy pattern. publisher-cli
  mirrors every move; 13 new tests; proven on the June 18 School
  Committee record.
- **The scorer moved to the middle of the table.** Highlighter's
  moment detection is now `czcore/moments.py` — detection-as-a-service
  for the whole wing (Publisher's candidates today, Memory's issue
  inputs next); `highlighter/highlights.py` stays as a re-export shim
  so every old import and test holds untouched.
- **Stale JS lost its lease.** Every static include carries
  `?v={{version}}`, substituted by the server, and the shell ships
  no-cache — a new build busts the browser's cache by URL, in the app
  window and the browser alike (the "⌘R after relaunch" ritual,
  retired).

### 1.5.0: the meeting answers back, and the heavies install themselves — 2026-07-17
- **The summary writes itself.** Pasting a URL opens a terminal in the
  hero — the commands named as they run, every job message a line, the
  cursor blinking until the meeting opens. With a key configured the
  executive brief is generative on arrival: written on load, cited to
  the second, every [MM:SS] a clickable pill, cached beside the
  transcript so one meeting costs one spend. The extractive read stands
  in until it lands, and stands alone without a key. And the key stays:
  it persists in app support, and an **OpenAI key now works everywhere
  an Anthropic one does** — the key's shape picks the provider.
- **The timeline became an editor.** Every clip on the reel has an edit
  row: nudge in/out by half-seconds, set playback speed (0.5–2×, atempo
  keeps the audio honest), check fade for 0.35s in/out — and every
  choice renders into the export, on both paths (local cut and
  download-and-stitch). The three sections stopped hiding: Meeting
  Highlighter, Highlight Video Editor and Meeting Analyzer stack on one
  page and the anchor pills scroll to them.
- **Exports let go of your hands.** Queued work gets a toast card in the
  corner — label, live percent, the message as it changes, green when
  done — and clicking one opens the Queue, where finished jobs finally
  show WHERE they landed (every output path, click to Reveal) and the
  default output folder is yours to change, right there in Settings.
- **The analyzer reached the web app — and every chart is a door.**
  People, Places & Things is one clickable card: "clips" opens every
  mention as a modal (play each, add any or all to the reel), and 🔍
  Investigate looks a name up in the world — live Google News fetched
  server-side, Wikipedia inline, maps out to the browser, and a "Your
  library" tab that searches every other meeting on this machine for
  the same name. The topic coverage map is a clickable heatmap (topics
  × twelve slices of the meeting), moments of disagreement list the
  tension vocabulary with a red edge, question flow gets type chips
  that open into their questions, speakers open into their own moments,
  and the transcript can Investigate any selection.
- **Generate Full Report** writes the AI narrative plus the counted
  record (decisions, entities, participation, questions) beside the
  meeting as markdown AND a real PDF — czcore/pdfout, a zero-dependency
  writer whose text stays selectable. **Translate** ships both ways on
  your key: the summary inline (and saved), the whole transcript
  chunked into timed .srt/.txt, ten languages.
- **Scrubbing stopped waiting.** The 10-second far seek was the frame
  service JPEG-encoding every frame it walked past on a long-GOP seek;
  passed frames now cache only within a dozen of the target. A cold far
  seek on the 5,223-frame test clip answers in 0.07–0.29s.
- **Stencil answers the click.** A click-preview endpoint runs SAM 2.1's
  image predictor on the one frame being clicked and the plum matte
  appears the moment the subject is chosen — ~3s for the first click
  while the model loads, ~0.7s after. Propagation stays the
  follow-through, not the reveal. And when torch + SAM 2 are absent,
  Stencil gates itself center-page: the card names the ~1 GB one-time
  install and carries the button that performs it (frozen builds get
  the honest sentence instead of a dead button).
- **Every optional heavy has a door now.** Settings grew an "optional
  runtimes" card: Stencil's torch + SAM 2 (pip, Meta's own URL — never
  the PyPI stranger) and Clear's DeepFilterNet3 voice-isolation binary
  (downloaded against its published sha256, refused on mismatch), each
  with installed/missing status, a one-click Install that runs as a
  queue job with live progress, and a copyable terminal command.
  Whisper models stay out on purpose: they download themselves in-app.
- **And the install buttons were then run for real**, in a venv that had
  neither heavy — which caught the SAM 2 one broken: Meta renamed their
  package metadata to `sam-2`, so pip discarded our URL pin
  ("inconsistent name") and went looking for the PyPI stranger instead.
  Every written copy of the requirement now pins
  `sam-2 @ git+…` (the import stays `sam2`). Verified end-to-end through
  the buttons themselves: DFN → sha-matched download → `deep_filter
  0.5.6` answering; SAM 2 → pip → `import torch, sam2` clean.
- **Clear's slider grew its own door.** When the DeepFilterNet3 binary
  is missing, the voice-isolation hint is no longer a wall of install
  text — it's one sentence and a link that lands on Settings → optional
  runtimes, scrolled to and lit up. (The old terminal line survives as
  the link's tooltip.)
- **The analyzer finished the web app's set** — the three cards that
  were still deferred, each local and labeled:
  - **Framing** — eight civic lenses (financial · safety · community ·
    environmental · legal · equity · infrastructure · process), counted
    from the meeting's own words with word-boundary vocabularies, each
    lens carrying its moments (click → play or add to the reel) and a
    first-half/second-half drift. Live on the March 10 Select Board:
    financial ×460 rising, community ×137 fading.
  - **Cross-Reference Network** — entities and recurring keywords that
    share a sentence get a weighted edge; drag the nodes, hover a name
    to light its connections, click a line for the moments the two share,
    click a node for every mention. Honest empty when fewer than three
    names connect.
  - **Relevant Documents** — the town's own CivicClerk portal, read
    around the meeting's date through the Grabber's reader (the title's
    own date wins over upload date; two half-window queries so a busy
    civic calendar can't page the nearest days away; shared word-pairs
    outrank single words so "Select Board" beats half a town of boards).
    Agendas, packets and minutes arrive as typed rows opening the
    portal's real PDFs. Verified live: the March 10 session found its
    own event — Select Board Regular Meeting, 0 days off, agenda +
    packet + minutes — with the same-day committees beneath it.
- The word cloud, recurring topics, and the network stopped counting
  contractions ("we're", "that's") as vocabulary — stopword stems
  wearing an apostrophe.
- **The Meeting Library** — a new room in the community rail: every
  meeting this machine has read, read together. The web app calls this
  its Knowledge Base and asks a cloud model; here every number is the
  same counted per-meeting reading the analyzer shows, aggregated in
  plain code from the sidecars already on disk. Four cards, each a door:
  - **Framing across meetings** — the eight lenses as a meetings × lens
    grid (each column a meeting, oldest first; each cell shaded in its
    lens's color by share), trend chips comparing the library's older
    half to its newer ("financial framing is rising across meetings ↑"),
    every cell opening that meeting's moments.
  - **Entity tracking** — who appears across which meetings and how
    often; a dot per meeting sized by count, one click traces the name.
  - **Meeting comparison** — two meetings side by side: duration, pace,
    decisions with outcomes, questions, tense moments, framing bars, and
    the topics and names they share (outlined) vs carry alone.
  - **Discourse analysis** — one term traced through every meeting
    oldest-first, bars by per-1k-word rate so a seven-hour meeting can't
    out-shout a one-hour one, with the first moments as receipts and
    every row opening the meeting in the Highlighter.
  Sessions that only have captions get read (and cached) on the
  library's first look; a meeting without words is listed as unread, not
  invented. Span downloads and rendered reels are outputs, not meetings
  — filtered by name shape. Verified live on this machine's seven
  meetings: "override" traced ×49 across 3 of 6 — surging in the March
  10 Select Board (×45, 0.85/1k words), echoing in the June School
  Committee.
- **One person, one row.** Caption misspellings used to split a name
  across the analyzer and the Library ("Councelor Hamilton" beside
  "Council Hamilton"). Entity harvesting now folds spellings under a
  conservative match — same word count, same initials per word, high
  sequence ratio — so "Mayor Jan" can never join "Mayor Dan". The
  winning spelling keeps the seat and lists the others (`also`), the
  Library's tracking folds across meetings too (person↔org may join,
  since that split IS the caption noise; places stay strict), and the
  insight cache carries a real version number now so old readings
  rebuild once.
- **The Library grew two cards.** **Topic evolution** — each meeting's
  recurring topics as a grid over time, every cell tracing the term
  through the full transcripts. And an **AI read across meetings** (BYO
  key, labeled generative): one button sends the counted digest — dates,
  lens counts, topics, names, tallies — never a transcript, and the
  answer names meetings by their dates.
- **The suite answers deep links now** — `/#kb` opens the Library,
  `/#clear` opens Clear, and the hash keeps working after load. Small
  feature, two real uses: rooms are shareable, and the site's slide
  captures can find them.
- **The hero carousel shows all thirteen tools** — the five new slides
  (Highlighter, Grabber, Index, Library, Slate) are the real app,
  captured headlessly through its own deep links with the pages driven
  to show their work: the Grabber mid-search on the town portal, Index
  answering "school committee" with thumbnails, the Library's grids
  live. make_slides.py owns the capture (suite_slides — needs the dev
  server and Chrome; skips itself politely without them).
- **The site tells the truth about what shipped.** control-z.org's
  suitebar now reads v1.1.0 shipped / v1.5.0 in signing with all ten
  tools + the Library chipped on it, the six originals flipped to
  shipped with real download links, and Slate, Community Highlighter,
  BIG Video Grabber, Index, and the Meeting Library each got a full
  card — features, quickstart, honest limitations, technical detail.
- **The civic finder means "latest" now.** Searching a municipality used
  to ride YouTube's relevance index — a smattering of the town's year.
  It now asks YouTube's own date-sorted results page ("brookline" leads
  with the newest School Committee and Select Board meetings), with
  civic-looking rows stably on top so vlogs sink and boards rise. (The
  `ytsearchdate` prefix died in the 2026.07 yt-dlp nightlies; the
  results URL with sp=CAI= is the door that stays open. YouTube's date
  sort is bucketed — the newest leads, neighbors may swap.)
- **Stencil stopped asking Metal for a 62 GB buffer.** SAM 2 preloads
  every frame of a state at its own 1024² working size (~12.6 MB a
  frame), so a static-camera meeting — one shot, thousands of frames —
  was one giant refused allocation ("invalid buffer size: 62 GB",
  measured). Long shots now propagate in 240-frame windows (~3 GB
  each), chained by every object's last mask; short shots are untouched.
  Verified on a 576-frame three-window run: seams continuous, masks
  faithful to what the click selected, and the device cache released
  between windows.
- **And the Montage Maker** — a reel cut ACROSS meetings. Every ➕ on a
  traced moment or a framing cell's list lands in the montage tray;
  Render stages the work honestly: local meetings cut in place, URL
  sessions download only the picked seconds (a span already on disk is
  reused — nothing re-downloads), then one stitch where every clip wears
  a title card naming its own meeting. Clips from different meetings
  arrive in different sizes, so the stitch graph now scales everything
  into the first clip's frame, letterboxed, never stretched (this also
  hardens the single-meeting path). Verified: a Select Board moment
  (1080p, fetched by URL) + a School Committee moment (720p, reused from
  disk) → one 19.28s montage, frame-checked — each card carrying its own
  meeting's name and the moment's own clock.

### 1.4.0: the web app's three rooms, the two doors out — 2026-07-17
- **Highlighter wears the web app's exact shape now**: the three sections
  are **Meeting Highlighter · Highlight Video Editor · Meeting Analyzer**,
  and the local pick-the-moments button reads **✨ Make Highlight Reel**
  beside a new **🤖 Make AI Highlight Reel** (BYO key): the model reads
  the timestamped transcript and proposes moments; every pick is clamped
  to the meeting's own clock, spans under 3 s are refused, and the origin
  line says "picks are generative (model, your key) — timestamps
  validated locally". No key → the button isn't there and nothing changes.
- **One big Export Video button, two doors out** (the web app's contract,
  desktop-sized):
  - **🔗 Share a reel link** — the deployed web player's own URL format
    (`?mode=play&v=…&clips=start-end,…&titles=…`), built entirely
    client-side: the clips live in the link, nothing uploads, nothing
    renders. Verified live: a desktop-built link for the March 10 Select
    Board reel loaded in the deployed player — title bar, 1/5 counter,
    Play Reel transport, five progress segments.
  - **⬇ Download & edit on this computer** — one flow with the progress
    stated stage by stage: "1 · Download 5 clips from YouTube — ✓ 5 clips
    landed, only 29s left YouTube" → "2 · Cut the MP4 with ffmpeg (+ title
    cards)" → "✓ Your video" with a Reveal in Finder button. Spans already
    on disk skip the download honestly ("nothing re-downloads"). Local
    files skip straight to the cut. Verified end-to-end: 5 spans → 5 clips
    → one MP4 with 5 title cards, 36.76 s.
- **DaVinci Tools** — a new page in the suite rail: the Node Tree
  PowerGrade, the **Middle Gray Contrast Anchor** (the site's newest
  tool), and the Fusion Template Pack, each with its size, its guide link
  on control-z.org, and a Download that lands in ~/Downloads and reveals
  itself (a dev checkout serves its own bytes; the packaged app fetches
  the same files from the project's GitHub). The OpenFX installer keeps
  its own page, cross-linked. ⌘K knows both pages.
- **The credit footer** — every page now ends with the line that names the
  makers: design + developed by Stephen Walter (weirdmachine.org) with
  Brookline Interactive Group, Neighborhood AI, and Claude Code — part of
  the Community AI Project (communityai.studio).
- 4 new tests (`test_davinci.py`: the three zips exist in the repo, are
  actual zips, guides live on control-z.org, raw URL matches the layout).
  247 pass; the packaging gates remain the signing machine's business.

### 1.3.0: the meeting shows its shape, the reel gets its cards — 2026-07-17
- **The reel can wear title cards now.** One checkbox in the render panel
  and every kept moment gets an ink card before it — the meeting's name
  small, the moment's words big in cream, its timestamp in the brief's
  green pill. Rendered through Pillow with Slate's font discovery at the
  output's own size, and ridden into the SAME concat graph as the cuts
  (`-loop` image inputs + anullsrc silence, every chain normalized to one
  SAR/pix_fmt/48k-stereo so audio stays locked). Works on both paths —
  local-file reels and stitched section downloads, where each `[start-end]`
  clip finds its timeline label by its span. Verified: 5 clips + 5 cards =
  36.76 s, frame-checked. Context, not decoration; hard cuts stay hard.
- **The session has a clock now.** The YouTube embed answers the widget
  "listening" handshake, so URL sessions get what local files always had:
  a ticking time display, the sparkline playhead, and a **follow-along
  transcript** — the row being spoken right now carries a green edge, and
  the *follow* chip scrolls it centered as the meeting plays. Verified
  live: play on the March 10 session → 0:10.2 on the clock and the active
  row tracking the speech. Seeks paint immediately instead of waiting for
  the embed to answer.
- **Analyze shows the meeting's shape — counted, not modeled.**
  - **Meeting pace**: words per minute in 50 bins (the recess is visible
    as a gap in the bars; the March 10 meeting averages 124 wpm).
  - **Discussion dynamics**: three thin lanes — questions asked, decision
    words, tension words — from the same keyword classes the scorer shows
    its reasons with (240 questions counted across that night). Click
    either chart to jump the player there.
- **Agenda, when the upload carries one**: yt-dlp chapters, else timestamp
  lines in the description (the civic upload habit), parsed into a
  clickable agenda card above search. Two items minimum — one timestamp is
  a link, not an agenda — and honest absence otherwise. A fresh re-read
  now MERGES newly scraped fields (title, description) into the session's
  info instead of keeping the thinner one, and when every caption route is
  gated but words are already on disk, the message says exactly that:
  "no caption route today — kept what was already here."
- **8,363 rows stopped being 16,726 event handlers.** The transcript
  renders in 400-row chunks between frames and ONE delegated listener owns
  every keep/seek click. Chart canvases redraw when their tab actually
  shows (a hidden canvas is 0 px wide — it drew into nothing before) and
  on resize.
- **Grabber: a month in one click.** When a CivicClerk search finds more
  than one video, a "⬇ Fetch all N videos" button queues every fetch at
  the chosen quality; the bin fills as they land.
- 8 new tests (`test_meeting_shape.py`: pace bins, dynamics lanes, agenda
  chapters-beat-description / description fallback / one-timestamp-is-not-
  an-agenda, title card lands as a real PNG at size). 246 pass; the same 2
  cv2 packaging gates stand.

### 1.2.0: the meeting reads in seconds, Whisper learns the names — 2026-07-17
- **URL ingest races the web app now — and the routes race each other.**
  YouTube links skip the yt-dlp probe entirely (the id is in the URL), the
  two local caption routes run **concurrently** on threads (first one home
  wins), the metadata rides free on the watch page the caption fetch
  already reads (`captions.parse_video_details`; even a *failed* caption
  fetch hands back the title), and YouTube's empty-200 gate tell breaks
  straight to the community relay instead of waiting out the other doomed
  route. Measured on a 7-hour Select Board meeting from a caption-gated IP:
  **7.4 s** to 8,363 readable segments (the deployed web app, warm, same
  video: 5.2 s — and the desktop's winning route *was* that relay plus two
  honest local attempts; ungated or proxied, the watch page wins in ~2 s).
  **Re-opening a known session: 0.1 s** — a session that's already read
  answers from disk instead of re-asking YouTube. The job message states
  the time and the route: "read in 7.1s — 8363 segments, captions via the
  community service."
- **Whisper gets the names right now — teach it before it listens.**
  faster-whisper's `hotwords` ride through the whole stack (`scribe/
  transcribe.py` → `/api/scribe/transcribe` → both UIs): a comma list of
  people/places/boards the audio likely carries biases the decoder every
  window. Highlighter **harvests the list from the meeting itself**
  (`insight.hotwords()` — entity people first, then places, orgs, names
  scraped from the title; deduped, capped, cut on a comma) and prefills an
  editable field: fix "John Vancoyak" to "John VanScoyoc" before Scribe
  runs and the transcript follows your spelling. Scribe's page grew the
  same field ("teach it the names"). Both model menus add **large-v3 —
  most accurate (names)** above turbo; job labels say "names taught."
- **Downloads say what leaves YouTube.** The Edit panel is now *clips
  first*: one green button — **"⬇ Download highlight clips (N · Ns)"** —
  fetches only the kept spans (merged, keyframe-cut, one file per span,
  named `[start-end].mp4`), with the hint counting what stays behind
  ("only these spans leave YouTube — 5 clips, 29s of a 3:33.0 meeting").
  The **full recording is its own explicit button** below a rule, wearing
  the meeting's duration so nobody grabs 7 hours by accident. Quality
  applies to every fetch and the ladder grew: best / **4K / 1440p** / 1080p
  / 720p / **480p / audio-only** (Grabber's fetch menu got the same rungs,
  and its fetches finally honor a chosen quality instead of always "best").
  Every highlight row grew a **↓ clip** button — fetch just that span.
  Landed clips list themselves under the progress line with **Reveal**
  buttons (`/api/media/reveal` — Finder on the Mac, the file manager
  elsewhere). Verified live: 5 spans → 5 files, each the span's length.
- **AI, bring-your-own-key, never the default** (`czcore/llm.py`). Paste
  an Anthropic key in **Settings → AI** (chmod-600 file, masked to its
  tail, env `ANTHROPIC_API_KEY` wins over the file, a stray
  `ANTHROPIC_BASE_URL` alone activates nothing) and Highlighter grows two
  labeled *generative* buttons: **✨ AI narrative brief** (bulleted, every
  claim carrying its [MM:SS], rendered as the same clickable pills) and
  **✨ AI** beside Ask (answers ONLY from the retrieval passages, cites
  inline, says so when they don't contain the answer). Long meetings
  stride-sample to fit the budget. Without a key nothing changes anywhere;
  errors are sentences ("the API key was refused (401) — check it in
  Settings → AI" — verified live with a fake key). stdlib urllib, zero new
  dependencies, no key ever ships.
- **⌘K jumps anywhere.** A command palette over the whole suite — type a
  few letters of any tool (or Queue, Models, Settings, About), Enter, and
  you're there. Index rows grew **→ Highlighter** (send any cataloged clip
  straight to the moments-finder), and Highlighter answers transport keys:
  space play/pause, ←/→ ±5 s — never while you're typing.
- 13 new tests (`test_llm_names.py`: key precedence/masking/0600, the
  stray-base-URL guard, watch-page videoDetails parsing incl. the
  shape-change case, hotwords harvest/dedupe/cap). 238 pass; the 2
  standing failures are the known cv2-ffmpeg packaging gates.

### 1.1.0 prep: the icon, the DMG's face, and zero-setup captions — 2026-07-17
- **The suite has an icon**: a cream caret over the amber z — *control z* as
  a rebus. `packaging/make_icon.py` renders it (ink squircle, 2× supersample,
  the suite's own font discovery) and compiles `icon.icns`; the spec wires it
  onto the .app, and the DMG volume wears it too (the custom-icon Finder bit
  does NOT survive `hdiutil -srcfolder` — measured — so the script builds RW,
  sets the bit on the mounted root, converts to UDZO).
- **Version 1.1.0** in both truths; the spec names the Make-wave packages +
  Pillow as belt-and-braces hiddenimports.
- **Community caption service**: when YouTube gates a machine and no proxy is
  set, Highlighter's ingest falls back to the community-highlighter web app's
  own public transcript engine (BIG's deployment, its residential proxy
  behind it). Zero setup for download users, only the public video URL is
  sent, and one Settings switch turns it off. Credentials never ship — the
  relay shares the *benefit* of the Webshare account, never the account.
  Verified end-to-end from a caption-gated IP: 60 segments arrived through
  the service after both local routes failed honestly. Per-video failures
  from the service (HTTP-error JSON) are read and relayed as sentences.
- v1.0.0's release page now explains `realesrgan-x4.onnx` (Rise's model,
  self-hosted at its pinned URL — users never download it by hand).
- `packaging/RELEASE-NOTES-1.1.0.md` is written for the signing machine;
  building/signing/notarizing happens there (this keychain has no identity).

### the Webshare workaround comes to the desktop — 2026-07-17
- **Why:** YouTube now gates caption/timedtext delivery by IP reputation.
  Investigated live: the community-highlighter **web app's Webshare
  residential proxy is active and working** (Render reports proxy_enabled,
  and a transcript fetch through the deployment succeeds in seconds), while
  from a bare home IP every yt-dlp caption route is currently walled
  (android_vr lists no tracks, web wants a PO token, tv trips the DRM
  experiment) and the raw timedtext URL answers with YouTube's empty-200
  gate. Video downloads still work; only captions are gated.
- **`czcore/proxy.py`** — the web app's exact configuration, shared: same
  env var names (`WEBSHARE_PROXY_USERNAME/PASSWORD/HOST`, one account serves
  both apps), or a Settings-page file in app support (chmod 600); same URL
  construction (rotating `-1` session suffix, URL-encoded credentials). The
  status surface masks the username and never returns the password.
- **`czcore/captions.py`** — the web app's transcript mechanism in stdlib:
  watch page → captionTracks → timedtext VTT (manual-English beats auto
  beats other-language), through the proxy when configured. YouTube's
  empty-200 is refused as success and named for what it is, with the fix:
  "Configure your Webshare proxy in Settings → fetch network and retry."
- Every YouTube-facing yt-dlp call (probe, search, captions, downloads)
  passes `--proxy` when configured; the nightly self-update never does
  (that's GitHub, not YouTube). Highlighter's ingest chains: yt-dlp
  captions → watch-page timedtext (+ proxy) → honest sentence; the job says
  which path won.
- **Settings → fetch network**: credential fields, live status ("active
  (tes…on @ p.webshare.io:80)"), Save/Remove; env-var deployments are
  reported and locked from UI edits. The yt-dlp chips on Highlighter and
  Grabber append "· webshare" and say in their tooltip that fetches ride
  the user's residential pool — covenant: it's the user's own account,
  user-configured, used only for the fetches they ask for.
- 13 new tests (URL building/suffix/encoding, env-over-file precedence,
  masking, captionTracks parsing/ranking, video-id forms). Verified live:
  config roundtrip through the API and UI, chip state, and the full ingest
  fallback chain ending in the honest gated-IP sentence from a bare IP.

### Highlighter goes web-app-shaped, the suite goes paper — 2026-07-16
- **Community Highlighter now mirrors the web app** (community-highlighter
  v9.5's shape), rebuilt on local reads that say what they are:
  - **URL sessions**: paste a link → the meeting is *readable before any video
    downloads* — metadata + captions land in a session folder, preview streams
    through a YouTube embed (seek/play by postMessage), and a session whose
    video already sits in the library **borrows the local twin's transcript**
    instead of re-asking YouTube.
  - **Executive brief** with clickable green [MM:SS] pills — extractive, the
    meeting's own sentences, spread across the hour (`highlighter/insight.py`).
  - **Highlights → timeline editor**: reel-style presets (Decisions, Public
    comment, Controversial, Budget, Actions, Everything) drive the scorer; the
    top 5 picks auto-load into a **dark NLE strip** — drag to reorder, trim
    in/out, per-clip thumbs, prev/play/next transport — inside the light app.
  - **Search every word** with a 50-bin sparkline, **word cloud** (civic
    stopwords, top-3 glow), **Analyze** cards: decisions with outcomes,
    entities (people/places/organizations/money, pattern-harvested), speaker
    participation bars, question flow typed by its words, recurring topics.
  - **Ask the meeting** — retrieval, labeled as such: best passages with
    timestamps + follow-up suggestions; never invents prose.
  - **Smart downloads**: the full recording at a chosen quality, or **only the
    kept sections** (`--download-sections` + keyframe cuts, one clip per span)
    which **stitch** into a reel (`stitch_files`). Transcript exports (.txt,
    .srt) are built client-side; **Google Translate** button copies the full
    text and opens the site — the web app's own free path for any language.
  - Civic **Meeting Finder**: yt-dlp's own ytsearch — no API key.
- **The suite turned light.** Paper cream chrome (the site's tokens, the web
  app's cues), ink text, white neo-brutalist cards with offset shadows;
  media surfaces (viewer, filmstrip, scopes, the NLE strip) stay dark on
  purpose — footage lives in the dark, the chrome lives on paper. Highlighter
  wears the web app's brand green (#1E7F63 / #22C55E).
- **Home says "Make Something."**
- **Every open-a-clip surface takes a drop now**: drag a file into any
  viewer (or Clear's waveform, or Highlighter's hero) and it opens; a
  **Browse…** button sits in the center of every empty state instead of only
  up in the media bar. In the app window drops carry real paths (pywebview);
  plain browsers explain themselves instead of failing silently.
- czcore/ytdlp grew `probe_url` (metadata, no download), `fetch_captions`
  (transcript-first ingest), `search` (ytsearch), and per-section downloads
  with multi-file result tracking.
- Tests: 20 new for the insight engine (extractive brief never paraphrases,
  entity buckets, question typing, decision outcomes, participation shares,
  retrieval ask hits and honest misses). Verified live: URL ingest, library
  twin borrow, section-only download (two spans → two clips) → stitched reel,
  full local flow (brief/cloud/analyze/ask), light theme across every page.

### the Make wave: four new tools, three doors, an About — 2026-07-16
- **The suite is ten tools.** Two natives from the long-list spec and the two
  community apps that grew up at BIG, rebuilt on czcore — same jobs, no cloud,
  no API keys:
  - **Community Highlighter** (`highlighter/`) — meeting video becomes text,
    text becomes the reel. Fetch via the managed **yt-dlp nightly** (a check
    runs on *every* page open and the chip says what it found); YouTube
    captions seed the transcript instantly (word timing when YT provides tags),
    one click upgrades through Scribe's local pass; the scorer marks moments
    with **its reasons on every pick** (decision/money/community/tension
    keywords, emphasis, optional room-energy blend); keep/drop paragraphs and
    render the reel (one ffmpeg concat graph, hardware encode) or leave with a
    selects EDL through Scribe's own exporter.
  - **BIG Video Grabber** (`grabber/`) — CivicClerk search for any tenant
    (Brookline default; every URL-shaped field harvested and labeled, bare
    `youtubeVideoId`s synthesized into links), fetch through yt-dlp *or* the
    new **zoomshare resolver**: Zoom and **zoomgov.com** share pages resolved
    with four plain HTTP requests — the flow the old app drove Puppeteer
    through, multi-clip aware, every failure a sentence naming the step. Then
    conform for air: constant-rate pass, shared encoder presets, PCM into mov.
  - **Index** (`indexer/`, tool id `index`) — the footage librarian. Folders →
    SQLite catalog (FTS5 with LIKE fallback), incremental rescans, missing
    drives stay listed and say so; plain-word search returns clips *and
    time-coded transcript hits* read from Scribe sidecars; selects leave as a
    **FCPXML stringout** (new `czcore/exports/fcpxml.py` — NTSC-exact
    rationals, percent-encoded file URLs) or CSV.
  - **Slate** (`slate/`) — the station graphics kit. The **lower-third maker**
    renders type at 2× through Pillow and downsamples Lanczos; four styles
    (bar/block/line/clean), slide/rise/fade with cubic easing, live preview
    *through the export code path* on an alpha checker with safe-area cages;
    exports **ProRes 4444 with real alpha**, PNG stills, and animated GIF
    (labeled honestly: 256 colors, web use). Plus SMPTE bars + 1 kHz tone,
    a countdown leader with beeps, and a program-slate card.
- **Home is three doors.** Prep / **Make** / Finish — "What are we creating
  today?" Grabber joins Prep (footage on its way in); Make holds Highlighter,
  Index, Slate. The community pair keeps its own rail corner: square glyphs,
  BIG-blue section header, accent-washed rows — deliberately a little
  different, same covenant.
- **About page** — the suite's story, the covenant with meanings, this build's
  numbers, and the website footer's credits verbatim.
- **Shared plumbing:** `czcore/ytdlp.py` (nightly manager: GitHub check with
  60s cooldown, atomic binary replace, offline = a sentence and the old build
  keeps working; downloads print progress and survive failed caption fetches),
  `czcore/ffrun.py` (ffmpeg with `-progress` parsing + cancel),
  `czcore/paths.py` (outputs land in `~/Movies/control-z/<tool>`), four new
  CLIs, packages/scripts registered, `pillow` added to requirements.
- **Fixed en route:** reel output paths built with `with_suffix()` could
  resolve to the *source* filename (`meeting.reel` → `.mp4` strips `.reel`) —
  outputs are appended now and an equality guard refuses to overwrite the
  source; sidecar discovery used `glob()` on names carrying `[id]`, which glob
  reads as a character class and never matches — replaced with `startswith`
  everywhere; yt-dlp subtitle requests narrowed to `en,en-orig` (asking for
  `en.*` pulls every translated variant and trips YouTube's 429, which used to
  kill the whole fetch — a landed video now survives a failed caption).
- Tests: 42 new (scoring/reel merge sweep/VTT word tags, nightly version
  compare, CivicClerk parsing incl. zoomgov + bare-id synthesis, zoomshare URL
  matching, FCPXML rationals/escaping/offsets, catalog search + FTS quoting,
  lower-third clamping/easing/alpha per style). Verified live end-to-end:
  real YouTube fetch → caption-seeded transcript; real Brookline zoomgov
  Select Board recording resolved to its mp4 (ranged probe, 3.99 GB, `ftypmp42`);
  detect → reel render (hardware h264, audio locked) → selects EDL; Index
  scan/search/FCPXML on disk; Slate ProRes 4444 (`yuva444p12le`) + PNG + GIF.

### the Fusion template pack — ten setups, paste-tested — 2026-07-16
- **The pack is now ten templates, and every one has been pasted into a live
  Fusion comp in free Resolve** (build 21, via the scripting API) — the caveat
  that said "not yet paste-tested" is gone because the test was actually run.
  Real mattes drove each one: `depth-cli run` on the Pexels street clip,
  `stencil-cli run` on the portrait.
- **The existing five were broken in a way the tests couldn't see, and are
  rebuilt.** `fog`, `depth-grade` and `haze-light` used a `Bitmap` node to key
  the matte — but `Bitmap` is not a valid Fusion RegID; Resolve silently turns
  it into a no-op **Dummy** on paste (no image input, no output), so those three
  produced *nothing*. The correct node is **`BitmapMask`**. All three now key
  through BitmapMask, and — because the depth matte is near=white — the fog and
  haze masks are **inverted** so the *far* end mists/glows, which the old ones
  got backwards too.
- **`rack-focus` was wired to an input that isn't there.** Its note said to feed
  the depth matte into `VariBlur.Blur`; VariBlur's blur-map input is actually
  **`BlurImage`**, and driving real focus needs a distance-from-plane map, not
  the raw depth. Replaced the `BrightnessContrast` gain hack with a **`Custom`**
  node computing `max(abs(depth − focal) − tolerance, 0)` — an animatable focal
  plane on `NumberIn1`, feeding `VariBlur.BlurImage`.
- **`depth-grade` shipped masks and no grade.** It was three (Dummy) Bitmaps and
  a note saying "feed these to a ColorCorrector yourself." Now it's a real
  paste-and-go tree: three `BitmapMask` bands (near / mid via a subtract / far
  via invert) each driving its own neutral **`ColorCorrector`**, chained.
- **`parallax` and the tool ids we *assumed* were wrong turned out fine.**
  `Displace` (`Type`, `XRefraction`, `YRefraction`) and `VariBlur` are real
  free-edition nodes with the names we guessed; parallax only needed its
  displacement source actually connected and subtler default refraction. Logged
  so the next person doesn't re-audit them.
- **Five new templates**, built and verified the same way:
  - **`veil-blur`** (the headline): blur *inside* a Stencil matte with a
    grow/feather so edges don't leak — plus a **mosaic** variant in the same
    file, bypassed by default. The mosaic needed a `Scale`-down→`Scale`-up
    (nearest) pair, **not** two `Transform`s: Fusion concatenates adjacent
    Transforms into one clean resample, so the block pixelation vanished until
    Scale (which changes real resolution) forced it. Honest note points at the
    per-frame check.
  - **`cutout`** — Stencil ProRes-4444 alpha over a new `Background`, alpha
    tunable through a `MatteControl` rather than trusted.
  - **`matte-tune`** — `ErodeDilate` + `Blur` on any matte, with two viewer
    outputs: the tuned matte alone, and the matte as a red tint over the image
    (the QC bench the other templates assume).
  - **`confidence-grain`** — `FastNoise` grain merged (SoftLight) through Hush's
    clean-confidence **alpha**, so grain lands where the denoiser averaged
    deepest. Note points at Speak as the better path.
  - **`social-vertical`** — 9:16 canvas, source full-width on a scaled+blurred
    backdrop of itself. Tuned the fit once we saw a 16:9 source lands full-width
    (Size 1.0) in a 1080×1920 comp and the backdrop needs ~3.2× to cover height.
- Every template: `CZ*` node names, exactly one sticky `Note` naming each wire,
  nothing auto-gains (grade/tune nodes are neutral, grain sits at Blend 0.35).
- `depth-cli templates` writes all ten (`--pack depth|stencil|all`, descriptive
  `cz-depth-` / `cz-stencil-` / `cz-hush-` filename prefixes). The zip is
  rebuilt by a reproducible `packs/build_zip.py` (byte-stable). Tests extended:
  per-template balanced braces, expected tool ids present, a `Note` present, and
  **no Studio-only / `Bitmap`-Dummy tool ids** in any file — plus CLI-writes-ten
  and zip-lists-ten. 146 green.

### loose ends — 2026-07-16
- **Speaker labels install themselves now.** Scribe's diarization needed two
  files fetched by hand — one of them buried in a tarball — and because they
  weren't in the registry the Models page could delete them but not bring them
  back. Both are registered, hash-pinned and license-carded like every other
  model; `czcore.models` learned to keep one named member out of a tarball
  (by exact name — never a blanket extractall, which lets an archive write
  where it likes). First use downloads ~44 MB and says whose weights they are.
- **The depth CLI stopped hoarding frames.** `depth-cli run` held a
  full-resolution float32 map for every frame of a shot, the same bug the
  Suite's render had: 845 KB/frame at SD, gigabytes at 4K. It now keeps the
  model's native 256×256 map like the Suite does — 256 KB/frame regardless of
  source resolution, so a 659-frame 4K clip holds 165 MB where it used to ask
  for 21.7 GB.
- Home's doors split by direction of travel rather than by a timeline the
  tools don't follow: Prep is footage on its way into your editor (Clear,
  Stencil, Depth), Finish is the cut coming back out (Pivot, Scribe, Rise).

### suite 0.4.0.dev0 — suite services — 2026-07-16
- **Install OpenFX page** (specs/08 §5): detects Resolve and
  /Library/OFX/Plugins, reads installed Hush/Speak versions from their
  Info.plists, and checks the latest GitHub release on click — one GET to
  the public API, nothing phones home on its own; prerelease-only repos
  (Speak beta) resolve via the release list and wear a beta badge. Install
  downloads the release .pkg to ~/Downloads and opens the system installer
  (which owns the privileges — the plugins dir is root-owned and the page
  says so instead of pretending). One-click OFXPluginCacheV2.xml clear for
  the rescan gotcha; uninstall removes the bundle when the dir is writable
  and otherwise prints the exact sudo command. Verified against this
  machine's real state: Resolve found, Hush 3.3.0 → v3.7.0 update offered,
  Speak not-installed → v0.2.0 beta offered.
- **Models page**: the czcore registry with license + sha-256-pinned badges
  and true on-disk sizes, download (through the queue, hash-verified) and
  remove per model; whisper cache and Stencil runtime status. Verified: yunet
  removed and re-downloaded with its hash checked. Whisper is the one row the
  registry doesn't own — faster-whisper fetches those from Hugging Face
  itself, unpinned, and the page says so rather than implying otherwise.
- **Settings page**: every cache with its real size and a clear button
  (all regenerable — the page says nothing here can lose work), job-history
  clear (active jobs never touched — unit-tested), model store and app-data
  paths, about block.
- Queue page grew a "clear finished" button; czcore JobManager grew
  clear_finished().
- The rail has no coming-soon states left: v0.4 closes the milestone list
  short of v1.0 (packaging, signing, notarization, DMG).
- **v0.2, sound + words.** **Clear**: audio workspace (waveform + amber-on-ink
  spectrogram with before/after A/B), rescue chain from the CLI's own calls
  (de-hum auto-detect, de-click, DF3 isolation when the binary exists — honest
  hint when not, de-ess, loudness presets), video remux against the untouched
  stream, room-tone generator, and the covenant surfaces: a "what was removed"
  monitor chip playing the residual, loudness I/peak meters, and a residual
  by-band null test ("presence band loud = you're eating words"). Verified on
  synthesized degraded dialogue: found the injected 60 Hz hum + harmonics,
  repaired the clicks, presence band read −16.5 dB (quiet).
  **Scribe**: the transcript-first editor — word-click seeks, karaoke follows
  the audio clock with the caption overlaid on video (current word amber),
  low-confidence words tinted (proof those), inline segment edits saved to the
  sidecar, speaker rename everywhere, caption presets, SRT/VTT/TXT/marker-EDL
  exports, and the pull list → CMX3600 selects EDL in source TC. Verified: two
  TTS voices separated perfectly, 23 s transcribed in 16 s (base), selects EDL
  honors embedded TC.
- **v0.3, the GPU pair.** **Depth**: false-color scrub (source/blend/depth),
  click-to-probe crosshair reading the local map, histogram with draggable
  in/out handles, stability meter, matte render (10-bit gray ProRes,
  edge-guided, temporal EMA with cut resets) through the queue, Fusion
  template pack writer. Honest note in the UI: scrub previews are per-frame;
  the render smooths. MiDaS-small fetched hash-verified on first use.
  **Stencil**: click-to-prompt (⌥-click excludes), SAM 2.1 propagation through
  the queue, matte tint + onion skin overlays, the confidence-strip QC loop
  (0.85 threshold line, low frames named), coverage %, post chain
  (grow/feather/despeckle/temporal majority) and luma / ProRes-4444-alpha
  exports. The runtime stays an honest optional — the page says exactly what
  to install when it's missing. The ⌥-click exclude only works at all because
  of the multi-point prompt fix below: on the old engine every click after the
  first was silently discarded, so a prompt ending in an exclude produced an
  empty matte.
- New engine deps into the venv story: faster-whisper, sherpa-onnx, soundfile,
  scipy, pyloudnorm (+ torch/sam2 as Stencil's optional heavies).
- Suite rail: no coming-soon states left among the tools — Install OpenFX,
  Models, Settings remain v0.4.

### czcore.denoise — the Hush core, ported — 2026-07-16
- **Pivot and Rise now carry Hush's denoising**, because both make noise
  worse (punch-ins scale it up; SR models synthesize texture from it).
  `czcore/denoise.py` is a faithful vectorized port of Hush-OpenNR's
  `nr_core.h` reference: the noise estimator (fine + coarse |Laplacian| and
  |temporal diff| medians with Hush's calibration constants, 16-bin
  brightness gain curve), the hard-knee gated 3-frame temporal merge with
  Ghost Guard and per-neighbour exposure offsets, the two-scale residual
  re-measure, and the fine NLM band (bias-corrected, edge-aware Preserve
  Detail). Hush defaults throughout. Honestly NOT ported (still plugin-only):
  shift-search motion tracking, firefly zapper, Render Boost, Deep Clean,
  medium/coarse EQ bands, the refine texture stack — reports say
  "hush-core", never plain "Hush".
- Wiring: Rise cleans BEFORE scaling (suite checkbox default on; CLI
  `--denoise`; preview cleans the patch so the A/B compares scalers on what
  the render will feed them). Pivot cleans the crop before any scaling with
  the temporal neighbours cropped at the CURRENT frame's rect — the stack
  stays registered while the camera path moves (suite checkbox, default
  off). Both paths use a 1-frame lookahead and put the measured σ in the
  report.
- Verified: 9 golden tests (estimator accuracy, +12 dB static-trio PSNR,
  motion no-ghosting, edge survival, near-identity on clean, determinism);
  on the real SD test clip the cleaned ×2 output measures ~45% less luma
  noise (0.39% → 0.22%) and ~54% less chroma than the plain ×2. Cost:
  ~160 ms/frame SD, ~1.6 s/frame 1080p — roughly halves Rise throughput,
  named in the UI.
- Brand line updated everywhere: control-z is "free cleaning, prepping, and
  finishing tools for DaVinci Resolve" (app rails, tool docstrings, README,
  pyproject, site templates + rebake).

### suite 0.1.0.dev0 — 2026-07-16
- **The Suite desktop app lands** (specs/08): one FastAPI + WebSocket server
  over the existing engines, single-page UI (hand-written HTML/CSS/JS, no
  framework) in a pywebview window — `python -m suite`, `--serve` for a
  browser. Grade-room design per spec §6: ink/forest surfaces, cream text,
  amber for measurements only, per-tool accents, node-wire rail indicator.
- Shell: rail with honest coming-in-v0.x pages for the four tools not yet
  moved in, Home with Prep/Finish doors + recents, shared viewer (zoom/pan,
  A/B wipe, canvas overlays, JKL + arrows; nb_frames metadata treated as an
  estimate and clamped to the decodable truth), filmstrip, Easy/Studio
  inspector density remembered per tool, scope rack (histogram + waveform
  on every image tool).
- Jobs: czcore.appshell grew a persistent SQLite queue — FIFO worker,
  cooperative cancel, history survives restarts, jobs killed by a quit are
  recorded as interrupted. WebSocket events + poll fallback; cross-tool
  Queue page. The legacy immediate mode is unchanged (pivot micro-UI still
  green).
- Frame service: PyAV decode → cached JPEGs at viewer height with prefetch
  around the playhead; frame indices derived from pts (frame-accurate on
  CFR, golden-tested against a painted synthetic clip); past-EOF is a 404,
  never an aliased frame.
- Export presets in czcore.media: ProRes 422/HQ (hardware
  `prores_videotoolbox` when present, `prores_ks` fallback), ProRes 4444
  (+alpha), DNxHR HQX, H.264/HEVC (VideoToolbox, libx264/5 fallback) —
  every render reports the encoder that actually ran and passes color tags
  through untouched (and says so). Validated by real encodes.
- **Pivot moved in fully** (old page prints a retirement note, still works):
  analyze warms the scrub cache during its own decode pass, path-trace +
  punch-in scopes, per-shot overrides re-solve in place, render through the
  export panel, Fusion .setting export. Verified end-to-end on the 4K
  reference clip: 659/659 frames of ProRes 4444 (ffprobe-counted), bt709
  tags carried, override → punch verified, 1318-key .setting written.
- **Rise moved in**: probe + interlace guard (combed sources refused with a
  sentence; Studio-only bypass), A/B wipe against honest bicubic, detail
  heatmap = |model − bicubic| with an added-energy readout, model picker
  showing true on-disk availability, batch → queue. Verified: 96/96-frame
  batch through hardware ProRes; a 4K job cancelled mid-run removed its
  partial file. `rise.video.upscale_video` extracted from the CLI (CLI
  behavior unchanged); `resolve_model("auto")` now falls back to lanczos
  when the ONNX isn't converted instead of crashing.
- Tests: 119 green (26 new — job store persistence/cancel/interrupt, frame
  cache accuracy/EOF/mtime-keying, export preset mapping/alpha honesty).
- Honest limitations: previews are proxy JPEGs (native-pixel loupe planned),
  one job runs at a time, jobs are threads not worker processes (isolation
  arrives before Stencil's propagation), no drag-drop into the webview,
  headings fall back to system fonts (Space Grotesk/DM Sans not bundled),
  Windows untested.
- Trap for the file: FastAPI + `from __future__ import annotations` +
  a function-local `WebSocket` import makes every /ws connect 403 silently
  (string annotations resolve against module globals) — keep FastAPI names
  imported at module level.
### stencil — 2026-07-16 (bug fix)
- **Multi-point prompts were broken and silently produced empty mattes.**
  SAM2's `add_new_points_or_box` defaults to `clear_old_points=True`, so
  sending one point per call kept only the last — a prompt ending in an
  exclude point erased the matte entirely (confidence 0.00 on every frame).
  Points are now grouped by (frame, object) and sent in one call:
  the same prompt set went 0.00 → **0.98 mean confidence, 0 frames flagged**.
  Found while re-shooting the site demos; regression test added
  (`TestPromptGrouping`). The old single-point demo worked by luck.

### site (licensed demo footage) — 2026-07-16
- **No member footage on the site.** Every published demo frame was re-shot on
  freely-licensed clips — the previous frames came from private member footage
  we don't hold public rights to. `site/make_slides.py` documents the
  licensing rule at the top so this can't regress. Hush's before/after stays
  its own synthetic validation card.
- The people-images are Pexels clips chosen so each is also a harder demo, and
  so the people shown reflect the communities these tools are for (curly-hair
  portrait for Stencil/Speak, freckled close-up for Rise, city street for
  Pivot/Depth). The Pexels license asks for no attribution; the footer credits
  them anyway, because a project about giving work away should say whose work
  it borrowed. An earlier pass used Tears of Steel (© Blender Foundation,
  CC-BY 3.0); it now stays in Test Footage as a spare scope-format source and
  no longer ships.
- Every frame is still real tool output: Stencil's matte is a genuine SAM 2.1
  propagation (0.98 confidence), Pivot's box is a genuine solved 9:16 crop,
  Depth is the shipping engine, Rise is real Real-ESRGAN vs Lanczos.
- Rise demo re-sourced from an in-focus face crop — the old pair came from a
  defocused region, so reconstruction read as blur; it now reads sharp AND
  denoised, which is the actual behavior.
- Pivot slide centre-crops the 2.4:1 scope frame to a true 16:9 first, so its
  "16:9 → 9:16" label is literally what's drawn.
- **Speak is live**: status `beta` (new status tier), real download links to
  github.com/amateurmenace/Speak v0.2.0, copy/limitations taken from its
  README (early beta, macOS-only binaries, no preset library yet).
- Domain cutover: control-z.org released from Hush-OpenNR and claimed by this
  repo; CNAME is now written by `site/build.py` on every bake so a deploy
  can't drop it. hush-whitepaper.pdf carried alongside whitepaper.html.

### site (single-page rebuild) — 2026-07-16
- One-page architecture: tool pages retired; each tool is a homepage section
  (`#t-<id>`) with its live simulation, feature list, brief how-to, and a
  `<details>` technical expander (architecture, model card, honest limitations,
  replaces). Node tree + chips now anchor-jump. Stale pages cleaned at bake.
- Epic dark hero (white-paper band promoted): philosophy/why + four value
  cards over live grain; CTA row (suite download, tools, design study).
- New sections: Downloads (Suite app card, Hush/Speak OpenFX, white paper —
  carried into the bake from Hush-OpenNR/docs), DaVinci + Premiere guide
  cards, "Who is this for?" (stations section retired into it), free-toolbox
  grid on the homepage (9 tools with blurbs/links).
- Topline: "A Weird Machine project in collaboration with Brookline
  Interactive Group" (linked). Footer: designed/developed credit (Stephen
  Walter × Claude Code · 2026), Weird Machine logo, Community AI Project
  (communityai.studio) + BIG partnership line, MIT license link.
- specs/08-suite-app.md: the control-z Suite desktop app scoped (architecture,
  IA, per-tool workspaces, export contract incl. ProRes 4444+alpha, OpenFX
  installer page, design language, milestones, risks, build-session prompt).

### site (interactive redesign) — 2026-07-16
- Rebuilt on the Hush site's actual component vocabulary (studied
  `Hush-OpenNR/site/index.template.html`): Space Grotesk/DM Sans, mono topline,
  amber-period hero, `.pcard` pair cards, `.feat` chips, dark `.ntree` with
  animated wire dots + click/keyboard node selection, `.wipe` before/after
  slider, grain-canvas `.study` bands, auto-cycle-until-click tabs, scroll-
  animated chart bars, numbered install steps, tipcards. Assets baked base64.
- Homepage: live Hush wipe in the hero (real footage); the suite as a clickable
  Resolve-style node tree in true pipeline order (restore→edit→sound→color→
  deliver, Speak last in color); audience tabs auto-cycle and relight the tree;
  Hush×Speak pair cards; grain-band covenant; "money undone" animated chart.
- Per-tool interactive demos, all real data or real math: Hush + Rise wipe
  sliders (actual outputs), Pivot solver playground (the shipping controller
  ported to JS — drag the subject), Scribe paper-edit (its own diarized
  transcript; clicks emit a real CMX3600 EDL), Clear WebAudio room (synthesized
  hum/room/voice with de-hum, isolate mix-back, and "listen to what's removed"),
  Depth probe + depth-shaped fog (real engine data), Stencil confidence-strip
  QC loop, Speak mini node-tree. All verified in-browser.

### site — 2026-07-16
- control-z.org rebuilt as the suite site per specs/07: Jinja2 bake to
  `site/docs/`, data-driven from `content/tools.yaml`. Homepage pipeline map
  (lit/breathing nodes, audience filter chips), tool-page template (verbline,
  replaces strip, quick start, model card, honest limitations), roadmap
  (proposed tools live ONLY there), mission/stations/toolbox pages.
  Not yet deployed: CNAME move + Hush-OpenNR/docs redirects happen at launch.

### stencil 0.1.0.dev0 — 2026-07-16
- SAM 2.1 video propagation (torch/MPS), prompt-file CLI, matte post chain
  (temporal majority, grow/feather/despeckle — golden-tested), luma +
  ProRes 4444 alpha exports, per-frame confidence with low-confidence frame
  report (the covenant surface). Verified on 4K footage (~2 fps propagation
  on M1 Max at 720p analysis). Deferred: click UI (v0.2), ONNX diet (v0.3).

### scribe 0.1.0.dev0 — 2026-07-16
- faster-whisper transcription (word timestamps, VAD), sherpa-onnx
  diarization (verified: 2-voice test separated perfectly), SRT/VTT with
  broadcast/social caption presets, TXT, marker EDL (speaker-colored,
  free-Resolve importable), CMX3600 selects EDL from pull lists. NDF
  timecode math golden-tested (23.976 drift documented). Deferred: editor
  UI (the v0.2 centerpiece), FCPXML.

### clear 0.1.0.dev0 — 2026-07-16
- De-hum (auto 50/60 Hz detect + harmonic notches, >20 dB kill golden-tested),
  de-click (second-difference detector — IIR ringing bug found and fixed;
  rarity guard so speech never counts as clicks), DF3 voice isolation via the
  official deep-filter binary (PyPI package is unmaintained — learned the hard
  way), room tone (random-phase PSD resynthesis, loop-safe), loudness
  normalize (BS.1770, refuses to hide peak conflicts), residual export
  ("listen to what was removed"). Deferred: UI, video remux, Demucs deep
  mode, nih-plug VST3.

### rise 0.1.0.dev0 — 2026-07-16
- Real-ESRGAN x4 converted from official BSD-3 weights to our pinned ONNX
  (rise.convert), tiled inference with seam-free overlap blending
  (golden-tested vs whole-frame), beats-bicubic golden test, honest lanczos
  fallback, CLI with interlace guard (refuses combed sources) and flow-gated
  temporal stabilization. Engine live inside Pivot's --enhance.

### depth 0.1.0.dev0 — 2026-07-16
- MiDaS-small ONNX backend (MIT) behind a model-agnostic engine (VDA-Small
  planned), temporal EMA with shot-boundary resets, per-shot robust
  normalization, He-et-al guided-filter edge-aware upsampling, 10-bit gray
  ProRes matte export, false-color previews, five-template Fusion pack
  (fog / rack focus / depth grade / parallax / haze light). Verified on 4K
  footage. (Pack later paste-tested + rebuilt + grown to ten — see the
  unreleased entry at the top.)

### pivot 0.2.0.dev0 — 2026-07-16
- Web UI (czcore.appshell: FastAPI + local page): open clip, analyze with
  progress, scrub preview with crop overlay + subject dot, path-trace sparkline
  (targets vs solved path), per-shot mode overrides (re-solve in place),
  render + Fusion export from the page. Verified end-to-end in a browser.
- Fusion `.setting` export: animated Crop with one keyframe per frame
  (czcore.exports.fusion_setting) — the free-Resolve keyframe roundtrip.
  NEEDS a paste-test in Resolve before release.
- YOLOX-s person detection (Apache-2.0, hash-pinned), lazy "auto" mode: runs
  only on frames with no face; per-shot subject falls back face → person.
- rise.engine seed: frozen upscale API, tiled ONNX runner ready, honest
  `lanczos` fallback backend (labeled, never claims synthesis). `--enhance`
  wired into render + UI.
- Sidecar v1 now stores raw targets per aspect (enables instant re-solve).

### pivot 0.1.0.dev0 — 2026-07-16
- Path solver (punch/follow, deadzone+hysteresis, lookahead anticipation,
  jerk-limited motion; overshoot pinned at ≤4·a_max by golden tests) + presets
  (calm/standard/attentive).
- Shot detection (adaptive luma-diff, czcore.shots), greedy face tracker
  (YuNet, MIT, hash-pinned auto-download), per-shot subject selection.
- Renderer: frame-accurate (EOF flush handled), native-res crops (no silent
  upscale), audio stream-copy or honest skip, h264/hevc/prores.
- CLI: analyze / render / auto with per-shot QC report; sidecar JSON v1.
- Verified end-to-end on 4K ProRes footage (659/659 frames). Known v0.1 limits:
  faces-only detection (subjects lost when the face is undetectable — persons
  model lands in v0.2), no y-axis eyeline offset yet, no Fusion export yet.

### czcore 0.1.0.dev0 — 2026-07-16
- shots (pure cut detector + PyAV diffs), media probe parser, model store with
  sha256 pinning + license cards. 51 tests green (stdlib-only run).
