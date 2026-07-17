# control-z Suite 1.2.0 — reads in seconds, knows the names

The Make wave learns speed and speech. Meetings become readable as fast as
the web app answers, Whisper can be taught this meeting's proper names
before it listens, and downloads finally say — in numbers — what leaves
YouTube and what stays behind.

## New since 1.1.0

- **The read is seconds now.** Paste a YouTube link: the probe is gone
  (the id is in the URL), the two caption routes race on threads, the
  title arrives on the same request as the captions, and a gated IP skips
  straight to the community relay instead of waiting out doomed routes.
  A 7-hour Select Board meeting: 7.4 s to 8,363 readable segments from a
  caption-gated IP. Re-opening a meeting the suite already read: 0.1 s.
- **Whisper, taught the names.** Highlighter harvests the people, places
  and boards from the meeting's own captions and title, prefills an
  editable "names to teach" field, and biases the decoder toward them —
  so Councilor Vitolo stops landing as "counselor of it all." Scribe's
  page has the same field. Both menus add **large-v3 — most accurate
  (names)**.
- **Downloads, clips first.** One green button fetches only the kept
  spans — one file per span, named with its seconds — while the hint
  counts the fraction ("5 clips, 29 s of a 3:33 meeting"). The full
  recording is its own explicit button wearing the duration. The quality
  ladder runs best/4K/1440/1080/720/480/audio, on Highlighter and Grabber
  both. Every highlight row can fetch just itself (**↓ clip**), and landed
  files list themselves with **Reveal** buttons.
- **AI, your key, optional.** Settings → AI takes your own Anthropic key
  (stored chmod-600, masked, env wins, removable in one click). With it,
  Highlighter grows two labeled generative buttons — narrative brief and
  grounded AI answers — whose every claim carries a clickable [MM:SS].
  Without it, nothing anywhere changes. No key ships in this app.
- **⌘K.** Type a few letters, land on any tool. Index sends clips straight
  to Highlighter; Highlighter answers space and arrow keys like an NLE.

## Build & sign (on this machine)

Nothing new to vendor: `czcore/llm.py` is stdlib urllib; no dependency
changes since 1.1.0 (`faster-whisper` was already pinned ≥1.0; hotwords
needs 1.0.2+, the venv carries 1.2.1).

    git pull
    .venv/bin/python -m unittest discover -s tests -t .   # 2 known cv2 gates pass here
    packaging/build_suite.sh && packaging/sign_suite.sh && packaging/notarize_suite.sh
    # then attach the DMG to the v1.2.0 release

The two `test_packaging` failures seen on the dev Mac (cv2 wheel's second
ffmpeg) are the gates this machine exists to make pass — they must be
green here before signing.
