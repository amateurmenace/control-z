"""Drafting the descriptions — vision through the user's own key,
DCMP style enforced twice: once in the prompt, once in the lint.

The guarded key lives in czcore.llm and stays there; this module reads
its config (never edits it) and builds the one thing llm.complete can't
yet say — a message with a picture in it. Anthropic and OpenAI both
take base64 JPEG; the provider comes off the key's own shape, exactly
as everywhere else in the suite. No key → a sentence, never a pretend.

The lint is pure and testable: present tense, no interpretation, no
camera talk, fits its gap. A draft that fails lint still lands — marked
— because the reviewer is the editor, not the model.
"""

from __future__ import annotations

import base64
import re
import subprocess
from typing import List

from .gaps import fits

DCMP_SYSTEM = (
    "You write audio description for community television, DCMP style. "
    "Present tense. Concise. Describe only what is visible — never "
    "interpret feelings, intent, or importance. Never say 'we see', "
    "'the camera', 'appears to', or name anyone not identified on "
    "screen. If the frame shows a slide, chart, document or lower-third, "
    "read its actual content — titles, numbers, labels — that is the "
    "whole point. Answer with the description only, no preamble."
)


def frame_jpeg(video: str, t: float, height: int = 720) -> bytes:
    """One frame at t seconds, as JPEG bytes — ffmpeg does the walking."""
    from czcore.tools import ffmpeg_path

    cmd = [ffmpeg_path(), "-hide_banner", "-v", "error", "-nostdin",
           "-ss", f"{max(0.0, float(t)):.3f}", "-i", str(video),
           "-frames:v", "1", "-vf", f"scale=-2:{int(height)}",
           "-f", "image2", "-c:v", "mjpeg", "-q:v", "4", "pipe:1"]
    out = subprocess.run(cmd, capture_output=True, timeout=60)
    if out.returncode != 0 or not out.stdout:
        err = out.stderr.decode("utf-8", "replace").strip().splitlines()
        raise RuntimeError("couldn't pull the frame at "
                           f"{t:.1f}s — {err[-1][:200] if err else 'ffmpeg gave no reason'}")
    return out.stdout


def draft_prompt(kind: str, words_budget: int) -> str:
    if kind == "graphic":
        ask = ("This frame holds a graphic (slide, chart, plan or "
               "document). Read its content into a description.")
    else:
        ask = "Describe this moment for a viewer who cannot see it."
    if words_budget > 0:
        ask += (f" At most {max(3, words_budget)} words — it must fit a "
                "spoken pause.")
    else:
        ask += (" There is no pause here, so this goes to the written "
                "transcript — up to 60 words, still concise.")
    return ask


def describe_frame(jpeg: bytes, kind: str, words_budget: int,
                   timeout: float = 60.0) -> str:
    """One vision call on the user's key — through czcore.llm's multimodal
    door (this module's request shape moved in there for 1.7.1, so the
    tokens land in the suite-wide AI audit). Returns the draft text; raises
    RuntimeError with a sentence on every failure mode."""
    from czcore import llm

    if not llm.enabled():
        raise RuntimeError("descriptions need your API key — Settings → AI")
    b64 = base64.b64encode(jpeg).decode("ascii")
    text = llm.complete_vision(draft_prompt(kind, words_budget), b64,
                               system=DCMP_SYSTEM, max_tokens=300,
                               timeout=timeout)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise RuntimeError("the model answered with no description")
    return text


# -- the lint: DCMP style, checked not assumed -------------------------------

_PAST = re.compile(r"\b(was|were|had|walked|entered|showed|appeared|stood|"
                   r"sat|said|spoke|held|looked)\b", re.I)
_CAMERA = re.compile(r"\b(we see|we can see|the camera|the shot|the frame|"
                     r"the image|this frame|the video|on screen we)\b", re.I)
_INTERP = re.compile(r"\b(seems?|appears? to|probably|likely|clearly|"
                     r"obviously|happy|sad|angry|nervous|important|"
                     r"interesting)\b", re.I)


def lint(text: str, gap_dur: float) -> List[str]:
    """What a reviewer should look at before trusting a draft. Empty list
    means the style holds; each entry is a short reason, not a code."""
    out = []
    t = str(text).strip()
    if not t:
        return ["empty"]
    if _CAMERA.search(t):
        out.append("camera-talk")
    if _INTERP.search(t):
        out.append("interprets")
    if _PAST.search(t):
        out.append("past-tense")
    if gap_dur > 0 and not fits(t, gap_dur):
        out.append("over-budget")
    return out
