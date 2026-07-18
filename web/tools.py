"""The web tool registry — the desk's TOOLS, wearing a public face.

Mirrors suite/static/js/core.js TOOLS (accent hexes from suite/static/app.css
:root) and adds what the web app needs per specs/16 §P0.5:

  surface   "web"  — its page is fully alive here (only Memory / the record)
            "desk" — a LOCKED DOOR: full dignity, a demo, one plain sentence
                     on why it lives at the desk, and the download
  why_desk  the true reason it's a desk tool (your files, your GPU, your
            Resolve) — stated in the failures-are-sentences voice
  beats     the three-beat "what it does" strip
  lives_here  where its WORK shows up in this very edition (the cross-link),
              or None
  slide     a real demo image from the site (site/content/assets/slide-<id>.jpg),
            or None — the community output tools instead point `lives_here` at
            a real artifact this edition already carries, which is truer than a
            marketing still.

Drift from the desk registry is a code-review smell, not a fate (specs/16 §8):
`tests/test_web_bake.py` checks every id/accent here against core.js.
"""

from __future__ import annotations

# accent hexes are the single source's values (app.css :root), carried by hand
# and pinned against core.js in the tests — the web edition can't @import the
# desk's live stylesheet, so it re-declares the same values.
TOOLS = [
    # -- the control-z workbench (diamonds) --
    dict(id="pivot", name="Pivot", accent="#4A6B91", group="cz", surface="desk",
         verb="follows the subject", one="9:16 / 1:1 from your 16:9 masters",
         why_desk="Pivot reframes your own master files — footage that lives "
                  "on your disk, not on the record.",
         beats=["analyze the master", "solve a camera path", "reframe and render"],
         lives_here=None, slide="pivot"),
    dict(id="stencil", name="Stencil", accent="#7E5B8E", group="cz", surface="desk",
         verb="cuts the stencil", one="click an object, get a matte",
         why_desk="Stencil runs SAM 2 on your GPU against your clip — a "
                  "model runtime and footage that never leave the desk.",
         beats=["click an object", "the matte follows it", "bring it into the cut"],
         lives_here=None, slide="stencil"),
    dict(id="scribe", name="Scribe", accent="#64647E", group="cz", surface="desk",
         verb="writes it all down", one="transcripts, captions, text-based cuts",
         why_desk="Scribe listens to your audio on-device — the transcribe "
                  "pass is local compute on files you hold.",
         beats=["listen on-device", "label the speakers", "cut by the words"],
         lives_here={"label": "every transcript you're reading here",
                     "href": "/app/"}, slide="scribe"),
    dict(id="clear", name="Clear", accent="#2E7E6E", group="cz", surface="desk",
         verb="rescues the take", one="de-hum, de-click, voice isolation",
         why_desk="Clear rescues your dialogue with local DSP — it works on "
                  "the audio file in your hand.",
         beats=["hear the hum and clicks", "lift the voice out", "keep what it removed"],
         lives_here=None, slide="clear"),
    dict(id="rise", name="Rise", accent="#A97E22", group="cz", surface="desk",
         verb="restores the detail", one="SD → HD/4K for archives and punch-ins",
         why_desk="Rise upscales your masters with a local model — the frames "
                  "are yours and the compute is on-device.",
         beats=["read the soft master", "add detail, honestly", "deliver at resolution"],
         lives_here=None, slide="rise"),
    dict(id="depth", name="Depth", accent="#4B53A8", group="cz", surface="desk",
         verb="maps the scene", one="depth mattes + fog/rack-focus templates",
         why_desk="Depth reads your footage into a depth map on-device and "
                  "writes Fusion templates for your Resolve.",
         beats=["read the scene's depth", "fog / grade / rack against it", "paste into Fusion"],
         lives_here=None, slide="depth"),
    dict(id="index", name="Index", accent="#96714E", group="cz", surface="desk",
         verb="knows where everything is", one="your footage, searchable in plain words",
         why_desk="Index catalogs the folders on your own drives — it searches "
                  "files only your machine can see.",
         beats=["scan your folders", "search what was said", "open the hit in the editor"],
         lives_here=None, slide="index"),
    dict(id="slate", name="Slate", accent="#B0618F", group="cz", surface="desk",
         verb="makes it official", one="lower thirds, slates, bars, countdowns",
         why_desk="Slate renders broadcast graphics — ProRes and PNG files "
                  "written to your disk for your air chain.",
         beats=["pick the graphic", "set the name and color", "render for air"],
         lives_here=None, slide="slate"),
    # -- the civic media suite (squares) --
    dict(id="highlighter", name="Highlighter", accent="#1E7F63", group="community",
         surface="desk", long="Community Highlighter",
         verb="finds the moments", one="meeting video → highlight reel, in text",
         why_desk="Highlighter reads a meeting on your machine and cuts a reel "
                  "from the tape — the fetch, the read, and the cut are local.",
         beats=["read the meeting in seconds", "score the moments, with reasons",
                "cut a reel or send it to the record"],
         lives_here={"label": "the moments it found, kept in the record",
                     "href": "/app/"}, slide="highlighter"),
    dict(id="grabber", name="Grabber", accent="#2E8FB5", group="community",
         surface="desk", long="Video Grabber",
         verb="brings the meeting home", one="search, fetch, conform civic recordings",
         why_desk="Grabber downloads civic recordings to your disk and conforms "
                  "them for air — a fetch pipeline the browser can't and won't run.",
         beats=["search the town's portals", "fetch at the quality you need",
                "conform it for the record"],
         lives_here={"label": "how every tape here got onto the record",
                     "href": "/app/covenant"}, slide="grabber"),
    dict(id="publisher", name="Publisher", accent="#3A9E8E", group="community",
         surface="desk", long="Community Publisher",
         verb="gets it seen", one="program in → clips, copy and posts out",
         why_desk="Publisher renders clips and burns captions from your program "
                  "file — an ffmpeg pass on footage the web app never uploads.",
         beats=["a program in", "clips, copy, thumbnails", "a kit out the door"],
         lives_here=None, slide=None),
    dict(id="memory", name="Memory", accent="#8E4A55", group="community",
         surface="web", long="Community Memory",
         verb="keeps the record", one="issues tracked across meetings and years",
         why_desk="", beats=[], lives_here=None, slide=None),
    dict(id="interpreter", name="Interpreter", accent="#7E8A3C", group="community",
         surface="desk", long="Community Interpreter",
         verb="carries it across", one="captions in seven languages + simple english",
         why_desk="Interpreter translates a meeting on your own API key, with "
                  "your town's glossary — the making happens at the desk; the "
                  "tracks it makes are served right here.",
         beats=["read a meeting's captions", "translate on your key, with the glossary",
                "land timed tracks beside the tape"],
         lives_here={"label": "the language menu on every meeting page",
                     "href": "/app/"}, slide=None),
    dict(id="narrator", name="Narrator", accent="#A9673A", group="community",
         surface="desk", long="Community Narrator",
         verb="says what's on screen", one="audio description for community TV",
         why_desk="Narrator drafts descriptions with vision on your key and "
                  "speaks them in a local voice — the render is desk work; the "
                  "descriptions it writes read here as text.",
         beats=["map the pauses and slides", "draft each moment, human-approved",
                "speak it and land the transcript"],
         lives_here={"label": "the described transcript on any narrated meeting",
                     "href": "/app/"}, slide=None),
]

BY_ID = {t["id"]: t for t in TOOLS}


def community():
    return [t for t in TOOLS if t["group"] == "community"]


def workbench():
    return [t for t in TOOLS if t["group"] != "community"]
