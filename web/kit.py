"""Publisher's reading half, pressed (specs/20 §6, §7.9 P2).

The desk's Publisher takes a program file and hands a producer a kit: the
clips worth cutting, and draft copy to ship them with. Everything in that kit
that can be *read* — the candidate clips, the extractive titles and
description, the chapter list — is a pure function of the transcript, and the
transcript is already on the record. So the press assembles the same kit here,
out of the moments plane the bake already wrote, and pages it at `/app/k/<pid>`
for anyone who wants to see what a meeting's publish kit would hold.

What stays at the desk is exactly what the covenant says stays there: the
render. `files` is empty and the page says why — cutting the clips, burning
captions and choosing ratios happen in Publisher, on the producer's own
machine, against local media the web app never uploaded. The emitted
`kit.json` is a real Publisher kit: a producer downloads it, opens it at the
desk, and continues from the draft rather than a blank page.

No model runs here. The copy is `czcore.kit.copy_extractive` — assembled from
the transcript, labeled so — the same core the desk uses, so a kit read on the
record and a kit opened at the desk are the same object. Pure over the pressed
meeting → the edition stays byte-idempotent.
"""

from __future__ import annotations

from typing import Optional

from czcore.kit import kit_from_parts


def kit_from_meeting(m: dict) -> Optional[dict]:
    """The publish kit for one pressed meeting, or None when there is nothing
    to publish yet.

    A kit needs two things the reader can act on: clips to cut, and a video to
    cut them from. A meeting with no `video_id` has no tape a desk Publisher
    could render against; a meeting with no moments has no clips to offer. In
    either case there is no honest kit, so none is pressed — and the
    `/app/press` Publisher line stays "nothing yet" for that edition rather
    than pointing at an empty page.
    """
    moments = m.get("moments") or []
    video_id = m.get("video_id") or ""
    if not video_id or not moments:
        return None

    # Candidates ARE the moments plane — the ranked, gated clips the meeting
    # page already shows — carried in chronological order with their receipts.
    # `t` (the anchor) and `kind` ride along so the clip identity a reader sees
    # on the record (kind, t) is the identity the desk render and the cite
    # sheet key on — the reel model's contract, unchanged.
    cands = []
    for mo in sorted(moments, key=lambda x: float(x.get("start") or 0)):
        reason = str(mo.get("reason") or "")
        cands.append({
            "start": float(mo.get("start") or 0),
            "end": float(mo.get("end") or 0),
            "text": str(mo.get("quote") or ""),
            "score": float(mo.get("score") or 0),
            "reasons": [reason] if reason else [],
            "t": float(mo.get("t") if mo.get("t") is not None else mo.get("start") or 0),
            "kind": str(mo.get("kind") or ""),
        })

    an = m.get("analysis") or {}
    # The insight shim the copy writer reads: entities as the bake pressed them,
    # and the meeting's extractive summary as the brief. `copy_extractive`
    # handles a plain-string brief, so the summary drops straight in.
    insight = {"entities": an.get("entities") or {}, "brief": m.get("summary") or ""}

    meta = {
        "title": m.get("title") or "",
        "date": m.get("date") or "",
        "source": m.get("url") or "",
        # extra handles the record's page and the desk render want; harmless to
        # the desk kit, which reads its own meta from the sidecar
        "pid": m.get("pid") or "",
        "video_id": video_id,
        "url": m.get("url") or "",
        "town": m.get("town") or "",
        "body": m.get("body") or "",
        "duration": m.get("duration") or 0,
        "thumb": m.get("thumb") or "",
    }

    kit = kit_from_parts(meta, cands, insight)
    kit["slug"] = m.get("pid") or ""
    return kit
