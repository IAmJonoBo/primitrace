"""Preparing a raster logo for tracing: key the background, trim, upscale, denoise, quantise.

Tracing straight from a JPEG-artefacted or anti-aliased raster yields hundreds of shades and
noisy paths. Each step here removes one source of noise before the tracer sees the image:

1. **Key**: an opaque image whose border is one colour has that plate keyed to transparency
   (flood fill from the edges within a tolerance), so the tracer draws the mark, not its plate.
2. **Trim** to the ink box plus a small pad.
3. **Upscale** with Lanczos so the shortest side is at least ``TARGET_SIDE`` (never with an ML
   upscaler: those invent detail; the master's geometry must come from the source's pixels).
4. **Denoise** with an edge-preserving filter (mean shift), which flattens JPEG noise inside
   colour regions without softening their edges.
5. **Quantise** to a small palette: k-means in CIELAB over the ink, centres closer than
   ``MERGE_DELTA_E`` merged, then every ink pixel snapped to its nearest palette colour.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

TARGET_SIDE = 1024  # the trace works on a mark at least this long on its short side
MAX_SIDE = 4096
KEY_TOLERANCE = 18.0  # CIELAB distance from the border colour still counted as plate
MERGE_DELTA_E = 12.0  # palette centres closer than this are one colour
MIN_SHARE = 0.005  # a palette colour holding less of the interior ink is an edge shade, not a colour
MAX_COLOURS = 8
ALPHA_INK = 128


@dataclass
class Prepared:
    rgba: np.ndarray  # H×W×4 uint8: quantised ink on a transparent background
    palette: list[tuple[int, int, int]]  # the quantised colours, most ink first
    ink: np.ndarray  # H×W bool: the mark's silhouette
    scale: float  # prepared pixels per source pixel
    keyed: str | None  # "#rrggbb" of the plate keyed away, or None
    origin: tuple[int, int] = (0, 0)  # (x, y) of the prepared image's top-left corner, in source pixels

    def source_transform(self) -> str:
        """SVG transform taking the prepared frame (where traces are drawn) back to source pixels."""
        return f"translate({self.origin[0]} {self.origin[1]}) scale({1 / self.scale:.10g})"


def _lab(rgb: np.ndarray) -> np.ndarray:
    """CIELAB (L 0–100) for RGB pixels; OpenCV's 8-bit LAB stretches L by 255/100, undone here so
    distances are true ΔE."""
    import cv2

    lab = cv2.cvtColor(rgb.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    lab[:, 0] *= 100 / 255
    return lab


def _rgb(lab: np.ndarray) -> np.ndarray:
    import cv2

    cv = lab.astype(np.float32).copy()
    cv[:, 0] *= 255 / 100
    return cv2.cvtColor(np.clip(cv, 0, 255).reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_LAB2RGB).reshape(-1, 3)


def key_background(rgba: np.ndarray) -> tuple[np.ndarray, str | None]:
    """Make a uniform border plate transparent (flood fill from the edges); unchanged otherwise."""
    import cv2

    h, w = rgba.shape[:2]
    if rgba[..., 3].min() < 250:  # already transparent somewhere: keep the source's own alpha
        return rgba, None
    border = np.concatenate([rgba[0, :, :3], rgba[-1, :, :3], rgba[:, 0, :3], rgba[:, -1, :3]])
    lab = _lab(border)
    centre = np.median(lab, axis=0)
    if np.mean(np.linalg.norm(lab - centre, axis=1) < KEY_TOLERANCE) < 0.9:
        return rgba, None  # the border is not one plate colour: nothing safe to key
    img_lab = _lab(rgba[..., :3].reshape(-1, 3)).reshape(h, w, 3)
    near = (np.linalg.norm(img_lab - centre, axis=2) < KEY_TOLERANCE).astype(np.uint8)
    mask = np.zeros((h + 2, w + 2), np.uint8)
    flood = near.copy()
    for y, x in [(0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)]:
        if near[y, x]:
            cv2.floodFill(flood, mask, (x, y), 2)
    out = rgba.copy()
    out[..., 3][flood == 2] = 0
    plate = border[np.argmin(np.linalg.norm(lab - centre, axis=1))]
    return out, "#{:02x}{:02x}{:02x}".format(*(int(c) for c in plate))


def trim(rgba: np.ndarray, pad_frac: float = 0.04) -> np.ndarray:
    return trim_box(rgba, pad_frac)[0]


def trim_box(rgba: np.ndarray, pad_frac: float = 0.04) -> tuple[np.ndarray, tuple[int, int]]:
    """The ink box plus a pad, and its top-left corner (x, y) in the input's pixels."""
    ys, xs = np.nonzero(rgba[..., 3] >= ALPHA_INK)
    if not len(xs):
        return rgba, (0, 0)
    pad = max(2, int(pad_frac * max(np.ptp(xs), np.ptp(ys))))
    y0, y1 = max(0, ys.min() - pad), min(rgba.shape[0], ys.max() + pad + 1)
    x0, x1 = max(0, xs.min() - pad), min(rgba.shape[1], xs.max() + pad + 1)
    return rgba[y0:y1, x0:x1], (int(x0), int(y0))


def upscale(rgba: np.ndarray) -> tuple[np.ndarray, float]:
    import cv2

    h, w = rgba.shape[:2]
    scale = min(MAX_SIDE / max(h, w), max(1.0, TARGET_SIDE / max(1, min(h, w))))
    if scale <= 1.0:
        return rgba, 1.0
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    return cv2.resize(rgba, size, interpolation=cv2.INTER_LANCZOS4), scale


def quantise(rgba: np.ndarray, max_colours: int = MAX_COLOURS) -> tuple[np.ndarray, list[tuple[int, int, int]]]:
    """Denoise the ink (mean shift), fit a small CIELAB palette, snap every ink pixel to it."""
    import cv2
    from sklearn.cluster import KMeans

    ink = rgba[..., 3] >= ALPHA_INK
    rgb = cv2.pyrMeanShiftFiltering(np.ascontiguousarray(rgba[..., :3]), sp=6, sr=18)
    if not ink.any():
        return rgba, []
    # Fit the palette on interior pixels only: upscaling blends every edge into in-between shades
    # that are not brand colours (they still snap to the nearest real colour below).
    interior = cv2.erode(ink.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    grey = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    flat = cv2.morphologyEx(grey, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) < 12
    fit = interior & flat
    if fit.sum() < 50:
        fit = ink
    lab_fit = _lab(rgb[fit])
    sample = lab_fit[np.random.default_rng(7).choice(len(lab_fit), min(len(lab_fit), 50_000), replace=False)]
    k = min(max_colours, len(np.unique(sample.round(), axis=0)))
    km = KMeans(n_clusters=max(1, k), n_init=4, random_state=7).fit(sample)
    shares = np.bincount(km.labels_, minlength=len(km.cluster_centers_)) / len(sample)
    merged: list[np.ndarray] = []
    for i in np.argsort(-shares):
        c = km.cluster_centers_[i]
        if shares[i] >= MIN_SHARE and all(np.linalg.norm(c - m) >= MERGE_DELTA_E for m in merged):
            merged.append(c)
    palette_lab = np.array(merged, dtype=np.float32)
    lab = _lab(rgb[ink])
    nearest = np.argmin(np.linalg.norm(lab[:, None, :] - palette_lab[None, :, :], axis=2), axis=1)
    palette_rgb = _rgb(palette_lab)
    out = np.zeros_like(rgba)
    out[ink, :3] = palette_rgb[nearest]
    out[ink, 3] = 255
    counts = np.bincount(nearest, minlength=len(palette_rgb))
    order = np.argsort(-counts)
    return out, [tuple(int(v) for v in palette_rgb[i]) for i in order if counts[i]]


def prepare(rgba: np.ndarray) -> Prepared:
    keyed, plate = key_background(rgba)
    trimmed, origin = trim_box(keyed)
    big, scale = upscale(trimmed)
    quantised, palette = quantise(big)
    if plate is not None and palette:
        # Anything left in the plate's own colour is the plate showing through (a letter's counter
        # enclosed by the mark, which the edge flood cannot reach): transparent in the colour
        # master and a hole in the mono silhouette.
        plate_lab = _lab(np.array([[int(plate[i : i + 2], 16) for i in (1, 3, 5)]]))[0]
        lab = _lab(np.array(palette))
        hit = int(np.argmin(np.linalg.norm(lab - plate_lab, axis=1)))
        if float(np.linalg.norm(lab[hit] - plate_lab)) <= KEY_TOLERANCE:
            colour = np.array(palette[hit])
            quantised[(np.abs(quantised[..., :3].astype(np.int32) - colour).sum(axis=2) == 0)] = 0
            palette = [c for i, c in enumerate(palette) if i != hit]
    return Prepared(quantised, palette, quantised[..., 3] >= ALPHA_INK, scale, plate, origin)
