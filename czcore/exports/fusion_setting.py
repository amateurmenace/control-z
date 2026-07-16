"""Fusion .setting generators — the free-Resolve roundtrip for keyframed effects.

Free Resolve can't accept keyframes through FCPXML transforms or the (Studio-only)
scripting API, but pasting a .setting onto the Fusion page works everywhere.
We author Number-input BezierSplines with one key per frame, so Fusion's
interpolation never matters: the solved path IS the animation.

Used by Pivot (animated Crop) and Depth (the template pack).
"""

from __future__ import annotations

from typing import Iterable, List, Sequence


def _lua_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def bezier_spline(name: str, values: Sequence[float], start_frame: int = 0) -> str:
    """A BezierSpline op with one keyframe per frame (values may be int-ish)."""
    keys = ",\n".join(
        f"\t\t\t\t[{start_frame + i}] = {{ {v:.6g} }}" for i, v in enumerate(values)
    )
    return (
        f'\t\t{name} = BezierSpline {{\n'
        f"\t\t\tKeyFrames = {{\n{keys}\n\t\t\t}}\n"
        f"\t\t}}"
    )


def animated_crop_setting(
    rects: Iterable[tuple],  # per-frame (x, y, w, h) source pixels
    src_w: int,
    src_h: int,
    start_frame: int = 0,
    comment: str = "",
) -> str:
    """A paste-ready .setting: Crop tool with per-frame XOffset/YOffset keys.

    Paste onto the clip's Fusion comp in free Resolve; the crop follows the
    solved Pivot path. Crop sizes are constant per solve, so only offsets
    animate. Set the timeline/output resolution to the crop size (or add a
    Transform after to fit) — the tool page recipe shows both.
    """
    rects = list(rects)
    if not rects:
        raise ValueError("no rects to export")
    xs: List[float] = [r[0] for r in rects]
    ys: List[float] = [r[1] for r in rects]
    w, h = rects[0][2], rects[0][3]
    note = _lua_escape(
        comment or f"Pivot path — {len(rects)} frames, crop {w}x{h} from {src_w}x{src_h}"
    )
    parts = [
        "{",
        "\tTools = ordered() {",
        "\t\tPivotCrop = Crop {",
        "\t\t\tCtrlWZoom = false,",
        "\t\t\tNameSet = true,",
        "\t\t\tInputs = {",
        f"\t\t\t\tXSize = Input {{ Value = {w}, }},",
        f"\t\t\t\tYSize = Input {{ Value = {h}, }},",
        '\t\t\t\tXOffset = Input { SourceOp = "PivotPathX", Source = "Value", },',
        '\t\t\t\tYOffset = Input { SourceOp = "PivotPathY", Source = "Value", },',
        f'\t\t\t\tComments = Input {{ Value = "{note}", }},',
        "\t\t\t},",
        "\t\t\tViewInfo = OperatorInfo { Pos = { 220, 45 } },",
        "\t\t},",
        bezier_spline("PivotPathX", xs, start_frame) + ",",
        bezier_spline("PivotPathY", ys, start_frame) + ",",
        "\t},",
        '\tActiveTool = "PivotCrop"',
        "}",
    ]
    return "\n".join(parts) + "\n"
