"""The export bundle — every asset named, nothing left to wrangle.

One folder per kit under the publisher media dir: clips/, thumbs/,
copy.md, transcript.txt, kit.json — and a zip of the lot. Acceptance is
specs/13 §P0.6: correctly named, branded, platform-sized, no manual file
work after export.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import List, Optional

from czcore.paths import media_dir

from .kit import segments as kit_segments


def slug(text: str, limit: int = 60) -> str:
    s = re.sub(r"[^\w\s-]", "", str(text)).strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)      # "Meeting - May 12" is one break, not three
    return (s[:limit].rstrip("-")) or "program"


def copy_markdown(kit: dict) -> str:
    """The kit's words as one readable file — origin lines kept, because
    provenance travels with the copy or it doesn't count."""
    c = kit.get("copy", {}) or {}
    meta = kit.get("meta", {}) or {}
    lines = [f"# {meta.get('title', 'Program')} — publish kit", ""]
    if meta.get("date"):
        lines += [f"*Program date: {meta['date']}*", ""]
    lines += [f"> {c.get('origin', 'origin unknown')}", ""]
    if c.get("titles"):
        lines += ["## Titles"] + [f"- {t}" for t in c["titles"]] + [""]
    if c.get("description"):
        lines += ["## Description", "", c["description"], ""]
    if c.get("chapters"):
        from .kit import fmt_t
        lines += ["## Chapters"] + [
            f"- {fmt_t(ch['t'])} — {ch['label']}" for ch in c["chapters"]] + [""]
    if c.get("newsletter"):
        lines += ["## Newsletter blurb", "", c["newsletter"], ""]
    social = c.get("social") or {}
    if social:
        lines += ["## Social drafts"]
        for k, v in social.items():
            lines += [f"**{k}**: {v}", ""]
    alts = c.get("alt_text") or []
    if alts:
        lines += ["## Alt text (one per clip)"] + [f"- {a}" for a in alts] + [""]
    clips = [cl for cl in kit.get("clips", []) if cl.get("keep")]
    if clips:
        lines += ["## Clips in this kit"] + [
            f"- {cl.get('label', '')} — {cl['start']:.0f}s→{cl['end']:.0f}s "
            f"({', '.join(cl.get('ratios', []))})" for cl in clips] + [""]
    lines += ["---", "Made with Community Publisher (control-z) — local, "
              "labeled, checkable."]
    return "\n".join(lines)


def transcript_text(source: str, max_chars: int = 400_000) -> str:
    out, total = [], 0
    for seg in kit_segments(source):
        t = float(seg.get("start", 0))
        line = f"[{int(t // 60)}:{int(t % 60):02d}] " \
               + " ".join(str(seg.get('text', '')).split())
        out.append(line)
        total += len(line)
        if total > max_chars:
            out.append("… (truncated)")
            break
    return "\n".join(out)


def kit_name(kit: dict) -> str:
    """`<date>-<title-slug>` — the stem every file in a kit shares."""
    meta = kit.get("meta", {}) or {}
    name = slug(meta.get("title", "")) or "program"
    if meta.get("date"):
        # slugged too: a "/" in a date would nest folders
        name = f"{slug(str(meta['date']), 20)}-{name}"
    return name


MARKER = ".kit-source"


def kit_dir(kit: dict, out_root: Optional[str] = None,
            source: Optional[str] = None) -> Path:
    """The ONE folder a meeting's kit lives in: renders land straight in
    its clips/ and thumbs/, the bundle adds the words and zips it.

    Two meetings can share a title and a date (or both be untitled): the
    folder remembers whose it is (MARKER), and a different meeting gets
    `…-kit-2` rather than wiping the first one's clips."""
    root = Path(out_root) if out_root else media_dir("publisher")
    base = f"{kit_name(kit)}-kit"
    if not source:
        return root / base
    for k in range(1, 50):
        cand = root / (base if k == 1 else f"{base}-{k}")
        try:
            owner = (cand / MARKER).read_text().strip()
        except OSError:
            owner = None
        if owner is None or owner == str(source):
            return cand          # free (or pre-marker, first come), or ours
    return root / f"{base}-{abs(hash(str(source))) % 10**6}"


def claim(kdir: Path, source: str):
    """Mark the folder as this meeting's (the render job calls this)."""
    kdir.mkdir(parents=True, exist_ok=True)
    (kdir / MARKER).write_text(str(source))


def assemble(source: str, kit: dict, rendered: List[dict],
             thumbs: Optional[List[dict]] = None,
             out_root: Optional[str] = None) -> dict:
    """Finish the kit folder + zip it. Renders already inside the folder
    (the render job writes there) stay put under their own names; anything
    rendered elsewhere (an older kit) is copied in."""
    name = kit_name(kit)
    kdir = kit_dir(kit, out_root, source)
    claim(kdir, source)
    (kdir / "clips").mkdir(parents=True, exist_ok=True)
    (kdir / "thumbs").mkdir(exist_ok=True)

    def inside(p: Path, sub: str) -> bool:
        try:
            return p.parent.resolve() == (kdir / sub).resolve()
        except OSError:
            return False

    files = []
    for i, r in enumerate(rendered, 1):
        src = Path(r.get("out") or r.get("path", ""))
        if not src.is_file():
            continue
        if inside(src, "clips"):
            files.append(str(src))
            continue
        dst = kdir / "clips" / f"{name}-clip{i:02d}-{r['ratio']}{src.suffix}"
        shutil.copy2(src, dst)
        files.append(str(dst))
    for i, r in enumerate(thumbs or [], 1):
        src = Path(r.get("out") or r.get("path", ""))
        if not src.is_file():
            continue
        if inside(src, "thumbs"):
            files.append(str(src))
            continue
        dst = kdir / "thumbs" / f"{name}-thumb{i:02d}-{r['ratio']}.png"
        shutil.copy2(src, dst)
        files.append(str(dst))
    (kdir / "copy.md").write_text(copy_markdown(kit))
    tx = transcript_text(source)
    if tx:
        (kdir / "transcript.txt").write_text(tx)
    (kdir / "kit.json").write_text(json.dumps(kit, indent=1))
    files += [str(kdir / "copy.md"), str(kdir / "kit.json")]

    # the ownership marker is bookkeeping, not part of what's handed off
    marker = (kdir / MARKER).read_text() if (kdir / MARKER).exists() else None
    (kdir / MARKER).unlink(missing_ok=True)
    try:
        zip_path = shutil.make_archive(str(kdir), "zip",
                                       root_dir=kdir.parent, base_dir=kdir.name)
    finally:
        if marker is not None:
            (kdir / MARKER).write_text(marker)
    return {"dir": str(kdir), "zip": zip_path, "files": files,
            "clips": sum(1 for f in files if "/clips/" in f),
            "thumbs": sum(1 for f in files if "/thumbs/" in f)}
