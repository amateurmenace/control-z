# control-z Suite 1.5.0 — the meeting answers back, and the heavies install themselves

Sign and ship THIS one — it supersedes the unreleased 1.2.0, 1.3.0, and
1.4.0 (their notes files stay for the record; don't tag or sign them).
Everything since 1.1.0 ships here. Tag `v1.5.0`. Highlights since 1.1.0:

- **Highlighter = the web app, desktop-sized.** Three stacked sections
  with anchor pills (Meeting Highlighter · Highlight Video Editor ·
  Meeting Analyzer), a 7-hour meeting reads in seconds, loading terminal
  in the hero, session clock + follow-along transcript, ✨ local +
  🤖 BYO-key AI highlight reels, and the executive summary writes itself
  on load when a key is configured (Anthropic or OpenAI — the key's
  shape picks the provider; cached, one spend per meeting).
- **The analyzer is the web app's, and every chart is a door**: People,
  Places & Things → clips modal + 🔍 Investigate (live news, Wikipedia,
  maps, cross-meeting "Your library" search), topic heatmap, framing
  (eight civic lenses, counted), cross-reference network (drag it, click
  an edge for the moments together), relevant documents (the town's own
  CivicClerk agendas/packets/minutes, found by date + name),
  disagreements, question chips, speaker moments. Generate Full Report
  → markdown + selectable-text PDF. Translate summary + whole
  transcript (timed .srt) in ten languages.
- **The timeline is an editor**: per-clip nudge / speed (0.5–2×) /
  fades, rendered on both export paths. **Export Video, two doors**: a
  share link the deployed web player opens (clips encoded in the URL,
  nothing uploaded), or a staged download-and-cut into one MP4 with
  optional title cards. Exports run in the background with corner toast
  cards; the Queue shows every output path (click to Reveal) and the
  output folder is user-changeable.
- **Speed and honesty**: far scrubs answer in ~0.1–0.3s (was 10s);
  Stencil shows the matte at click time (SAM 2.1 image preview) and
  gates itself center-page when its runtime is absent. **Settings →
  optional runtimes** installs the two heavies in-app: torch + SAM 2
  (pip, Meta's repo URL) and the DeepFilterNet3 binary
  (sha256-verified). Whisper taught the names (hotwords, editable;
  large-v3 in the menus). DaVinci Tools page. Credit footer. ⌘K.

Build: no required-dependency changes since 1.1.0. torch/SAM 2 and
DeepFilterNet stay OPTIONAL — the app installs them itself from
Settings; the signed build must NOT bundle them (the frozen app refuses
the pip route with an honest sentence — expected, not a bug). One pin
is load-bearing: SAM 2 must be written `sam-2 @ git+…` (Meta's own
metadata name; plain `sam2` makes pip resolve the PyPI stranger) —
already fixed everywhere in this tree, both install buttons verified
end-to-end in a bare venv on this machine.

    git pull
    .venv/bin/python -m unittest discover -s tests -t .   # packaging gates must pass HERE
    packaging/build_suite.sh && packaging/sign_suite.sh && packaging/notarize_suite.sh
    # GitHub release v1.5.0, DMG attached, this file as the body
