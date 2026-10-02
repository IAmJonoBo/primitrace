"""How faithful and how clean a traced logo is: render it back and compare with its source.

A trace is accepted only if it looks like the source and is not noisy. Rendered at the prepared
size with ``rsvg-convert`` (librsvg, the renderer n00bt00b's sharp uses too), it is compared with
the prepared raster it was traced from:

* ``ink_iou``: intersection over union of the two ink masks (shape fidelity);
* ``edge_f1``: F1 of Canny edges matched within 2 px (outline fidelity);
* ``delta_e``: mean CIELAB ΔE over the shared ink (colour fidelity; 1 ≈ a just-noticeable step);
* ``paths``, ``nodes``, ``colours``: complexity, the measure of noise (a clean mark has few).

Thresholds live in ``ACCEPT`` and are fixed from a labelled sample before the first full run.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass

import numpy as np

ALPHA_INK = 128


@dataclass(frozen=True)
class Fidelity:
    ink_iou: float
    edge_f1: float
    delta_e: float | None  # None for a mono trace (one ink colour)
    paths: int
    nodes: int
    colours: int

    def as_dict(self) -> dict[str, float | int | None]:
        return asdict(self)


def render(svg: str, width: int, height: int) -> np.ndarray:
    """RGBA pixels of ``svg`` drawn at ``width``×``height`` by rsvg-convert."""
    import io

    from PIL import Image

    png = subprocess.run(
        ["rsvg-convert", "-w", str(width), "-h", str(height), "-f", "png"],
        input=svg.encode("utf-8"),
        check=True,
        capture_output=True,
        timeout=60,
    ).stdout
    return np.asarray(Image.open(io.BytesIO(png)).convert("RGBA"))


def _edges(mask: np.ndarray) -> np.ndarray:
    import cv2

    return cv2.Canny(mask.astype(np.uint8) * 255, 50, 150) > 0


def edge_f1(a: np.ndarray, b: np.ndarray, tolerance: int = 2) -> float:
    import cv2

    ea, eb = _edges(a), _edges(b)
    if not ea.any() and not eb.any():
        return 1.0
    kernel = np.ones((2 * tolerance + 1, 2 * tolerance + 1), np.uint8)
    da, db = cv2.dilate(ea.astype(np.uint8), kernel) > 0, cv2.dilate(eb.astype(np.uint8), kernel) > 0
    precision = (eb & da).sum() / max(1, eb.sum())
    recall = (ea & db).sum() / max(1, ea.sum())
    return float(2 * precision * recall / max(1e-9, precision + recall))


def complexity(svg: str) -> tuple[int, int, int]:
    """(paths, nodes, distinct fill colours) of an SVG."""
    paths = re.findall(r"<path\b[^>]*>", svg)
    nodes = sum(len(re.findall(r"[MLHVCSQTAZmlhvcsqtaz]", m)) for m in re.findall(r'\bd="([^"]*)"', svg))
    colours = {c.lower() for c in re.findall(r'fill="(#[0-9a-fA-F]{3,6}|currentColor)"', svg)}
    return len(paths), nodes, len(colours)


def measure(svg: str, source: np.ndarray, *, mono: bool = False) -> Fidelity:
    """Fidelity of ``svg`` against the prepared ``source`` (H×W×4) it was traced from."""
    import cv2

    h, w = source.shape[:2]
    drawn = render(svg, w, h)
    ink_s, ink_d = source[..., 3] >= ALPHA_INK, drawn[..., 3] >= ALPHA_INK
    union = (ink_s | ink_d).sum()
    iou = float((ink_s & ink_d).sum() / union) if union else 1.0
    delta = None
    if not mono:
        both = ink_s & ink_d
        if both.any():
            lab_s = cv2.cvtColor(source[..., :3], cv2.COLOR_RGB2LAB).astype(np.float32)[both]
            lab_d = cv2.cvtColor(np.ascontiguousarray(drawn[..., :3]), cv2.COLOR_RGB2LAB).astype(np.float32)[both]
            # OpenCV's 8-bit LAB scales L by 255/100; undo it so ΔE is in CIELAB units.
            scale = np.array([100 / 255, 1, 1], np.float32)
            delta = float(np.mean(np.linalg.norm((lab_s - lab_d) * scale, axis=1)))
    paths, nodes, colours = complexity(svg)
    return Fidelity(round(iou, 4), round(edge_f1(ink_s, ink_d), 4), None if delta is None else round(delta, 2),
                    paths, nodes, colours)  # fmt: skip
