"""Tracing a prepared logo: the colour master with vtracer, the mono master with potrace.

* **Colour** (vtracer): cutout mode, so shapes never overlap and leave seams; spline curves;
  speckle filter scaled to the prepared size; colour settings wide enough that a flat colour is
  never split into layers (the image is already quantised to its palette).
* **Mono** (potrace): the ink mask traced as one colour, which gives the cleanest curves of any
  tracer and keeps counters as holes. Fill is ``currentColor`` so the reader picks the ink.

Both write SVG text; nothing here judges quality (see ``fidelity``).
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile

import numpy as np

# Starting points from the research (vtracer README and parameter descriptions; potrace manual),
# not published presets: tuned on a labelled sample before the first full run.
VTRACER = {
    "colormode": "color",
    "hierarchical": "cutout",
    "mode": "spline",
    "color_precision": 8,
    "layer_difference": 48,
    "corner_threshold": 70,
    "length_threshold": 5.0,
    "max_iterations": 10,
    "splice_threshold": 45,
    "path_precision": 2,
}
POTRACE_ALPHAMAX = 1.0  # 0 = polygon, 1.3334 = no corners
POTRACE_OPTTOLERANCE = 0.3


def speckle(width: int, height: int) -> int:
    """vtracer's speckle filter (pixels a side) scaled to the prepared size: ~0.6% of the short side."""
    return max(4, int(round(0.006 * min(width, height))))


def colour_svg(rgba: np.ndarray) -> str:
    import vtracer

    h, w = rgba.shape[:2]
    pixels = [tuple(int(v) for v in px) for px in rgba.reshape(-1, 4)]
    return vtracer.convert_pixels_to_svg(pixels, size=(w, h), filter_speckle=speckle(w, h), **VTRACER)


def _potrace_paths(mask: np.ndarray, fill: str) -> str:
    """potrace's paths for ``mask`` (True = ink) as one group filled with ``fill``."""
    text = _potrace(mask)
    group = re.search(r"<g transform=\"([^\"]*)\"[^>]*>(.*?)</g>", text, flags=re.S)
    if not group:
        return ""
    return f'<g transform="{group.group(1)}" fill="{fill}" stroke="none">{group.group(2)}</g>'


def layered_svg(rgba: np.ndarray, palette: list[tuple[int, int, int]]) -> str:
    """Colour master by stacked potrace layers: one layer per palette colour, largest first; each
    layer covers its own colour and every colour drawn above it, so layers overlap and never leave
    a seam, and the topmost colour shows where it belongs. Exactly the palette's colours, with
    potrace's clean curves (vtracer's own colour clustering reintroduced hundreds of edge shades)."""
    h, w = rgba.shape[:2]
    ink = rgba[..., 3] >= 128
    rgb = rgba[..., :3].astype(np.int32)
    labels = np.full((h, w), -1, np.int32)
    for i, colour in enumerate(palette):
        labels[ink & (np.abs(rgb - np.array(colour)).sum(axis=2) == 0)] = i
    order = sorted(range(len(palette)), key=lambda i: -(labels == i).sum())
    layers = []
    for pos, i in enumerate(order):
        above = order[pos:]
        mask = np.isin(labels, above)
        if not mask.any():
            continue
        fill = "#{:02x}{:02x}{:02x}".format(*palette[i])
        layers.append(_potrace_paths(mask, fill))
    body = "".join(layers)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{body}</svg>'


def _potrace(mask: np.ndarray) -> str:
    h, w = mask.shape
    turd = max(10, int(0.0002 * h * w))  # specks under ~0.02% of the area are dropped
    with tempfile.TemporaryDirectory(prefix="primitrace-") as tmp:
        pbm, svg = os.path.join(tmp, "ink.pbm"), os.path.join(tmp, "ink.svg")
        packed = np.packbits(mask.astype(np.uint8), axis=1)  # 1 = black = ink
        with open(pbm, "wb") as fh:
            fh.write(f"P4\n{w} {h}\n".encode() + packed.tobytes())
        subprocess.run(
            [
                "potrace",
                pbm,
                "-s",
                "-o",
                svg,
                "--flat",
                "-t",
                str(turd),
                "-a",
                str(POTRACE_ALPHAMAX),
                "-O",
                str(POTRACE_OPTTOLERANCE),
            ],  # fmt: skip
            check=True,
            capture_output=True,
            timeout=120,
        )
        with open(svg, encoding="utf-8") as fh:
            return re.sub(r"<metadata>.*?</metadata>", "", fh.read(), flags=re.S)


def mono_svg(ink: np.ndarray) -> str:
    """Trace the ink mask with potrace; fills become currentColor."""
    return re.sub(r'fill="#000000"', 'fill="currentColor"', _potrace(ink))


def potrace_version() -> str:
    out = subprocess.run(["potrace", "--version"], check=True, capture_output=True, text=True).stdout
    return out.splitlines()[0].strip()
