"""A tiny PDF writer — selectable text, zero dependencies.

The suite's reports deserve to leave as real files, and a report PDF is
text, not pictures: this writes letter pages with Helvetica from the PDF
base-14 set, so nothing downloads and the text stays selectable. Blocks
in, pages out. Non-Latin characters fall back to '?' (the base fonts are
Latin-1); translations ship as .txt/.srt where every script survives.
"""

from __future__ import annotations

from typing import List, Tuple

W, H = 612, 792                 # US letter, points
MARGIN = 56

STYLES = {                      # (font, size, leading, space-before)
    "h1": ("F2", 21.0, 26.0, 10.0),
    "h2": ("F2", 13.5, 18.0, 14.0),
    "p":  ("F1", 10.5, 15.0, 4.0),
    "li": ("F1", 10.5, 15.0, 2.0),
    "small": ("F1", 8.5, 12.0, 3.0),
}


def _latin(s: str) -> str:
    return s.encode("latin-1", "replace").decode("latin-1")


def _esc(s: str) -> str:
    return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _wrap(text: str, size: float, width: float) -> List[str]:
    """Greedy wrap on an average-width estimate — Helvetica averages just
    over half an em per glyph; 0.52 keeps long lines safely inside."""
    max_chars = max(8, int(width / (size * 0.52)))
    out, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if len(trial) > max_chars and line:
            out.append(line)
            line = word
        else:
            line = trial
    if line:
        out.append(line)
    return out or [""]


def write_pdf(path: str, blocks: List[Tuple[str, str]],
              footer: str = "") -> str:
    """blocks: [(style, text), …] with style in STYLES. Returns path."""
    pages, ops, y = [], [], H - MARGIN

    def close_page():
        nonlocal ops, y
        if footer:
            ops.append(f"BT /F1 8 Tf {MARGIN} {MARGIN - 22} Td "
                       f"({_esc(_latin(footer))}) Tj ET")
        pages.append("\n".join(ops))
        ops, y = [], H - MARGIN

    for style, text in blocks:
        font, size, lead, before = STYLES.get(style, STYLES["p"])
        indent = MARGIN + (14 if style == "li" else 0)
        width = W - indent - MARGIN
        lines = _wrap(_latin(text), size, width)
        if style == "li" and lines:
            lines[0] = "• " + lines[0] if False else "- " + lines[0]
        y -= before
        for ln in lines:
            if y < MARGIN + 30:
                close_page()
            ops.append(f"BT /{font} {size} Tf {indent} {y:.1f} Td "
                       f"({_esc(ln)}) Tj ET")
            y -= lead
    close_page()

    # assemble: 1 catalog, 2 pages-tree, then per page (page, stream), fonts
    objs: List[bytes] = []
    n_pages = len(pages)
    first_page_obj = 3
    font1_obj = first_page_obj + 2 * n_pages
    font2_obj = font1_obj + 1
    kids = " ".join(f"{first_page_obj + 2 * i} 0 R" for i in range(n_pages))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>"
                .encode())
    for i, content in enumerate(pages):
        stream = content.encode("latin-1", "replace")
        objs.append((f"<< /Type /Page /Parent 2 0 R "
                     f"/MediaBox [0 0 {W} {H}] "
                     f"/Resources << /Font << /F1 {font1_obj} 0 R "
                     f"/F2 {font2_obj} 0 R >> >> "
                     f"/Contents {first_page_obj + 2 * i + 1} 0 R >>")
                    .encode())
        objs.append(b"<< /Length " + str(len(stream)).encode()
                    + b" >>\nstream\n" + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n").encode()
    with open(path, "wb") as f:
        f.write(bytes(out))
    return path


def md_blocks(md: str) -> List[Tuple[str, str]]:
    """The report writes markdown; the PDF reads this subset of it."""
    blocks: List[Tuple[str, str]] = []
    for raw in md.splitlines():
        s = raw.strip()
        if not s:
            continue
        s = s.replace("**", "").replace("###", "##")
        if s.startswith("## "):
            blocks.append(("h2", s[3:]))
        elif s.startswith("# "):
            blocks.append(("h1", s[2:]))
        elif s.startswith(("- ", "* ")):
            blocks.append(("li", s[2:]))
        else:
            blocks.append(("p", s))
    return blocks
