"""Synthetic logo marks with exact ground truth.

A mark is one to five primitives (circle, ellipse, rect, rounded rect, regular polygon, ring,
bar at a designer angle) in one to four flat colours, drawn as native SVG elements in a 256-unit
view box. The SVG is the answer: anything traced from its raster is scored against it.

Each mark is drawn at several source sizes (logo sizes seen in catalogues) and under one of a few
honest degradations: transparent, on an opaque plate, blurred, or plate plus JPEG. Everything is
seeded, so the corpus is identical on every machine and never needs committing.
"""

from __future__ import annotations

import io
import math
import random
from dataclasses import asdict, dataclass, field

import numpy as np

VIEW = 256  # ground-truth view box side, in SVG units
SIZES = (64, 128, 256)  # source raster sides, in pixels
DEGRADATIONS = ("clean", "plate", "blur", "jpeg")
ANGLES = (0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165)  # designer angles (degrees)


@dataclass(frozen=True)
class Primitive:
    kind: str  # circle | ellipse | rect | roundrect | polygon | ring | bar
    colour: str  # "#rrggbb"
    params: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Mark:
    id: str
    primitives: tuple[Primitive, ...]
    svg: str  # ground truth: the mark alone, transparent background

    @property
    def palette(self) -> list[str]:
        return sorted({p.colour for p in self.primitives})


@dataclass(frozen=True)
class Sample:
    id: str  # "<mark id>@<size>/<degradation>"
    mark: Mark
    size: int
    degradation: str
    plate: str | None  # "#rrggbb" of an opaque background, or None


def _lab(rgb: tuple[int, int, int]) -> np.ndarray:
    """CIELAB for one sRGB colour (D65), for keeping palette colours apart."""

    def lin(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    return np.array([116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))])


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _palette(rng: random.Random, n: int, avoid: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    """``n`` colours at least ΔE 30 from each other and from ``avoid`` (the plate)."""
    out: list[tuple[int, int, int]] = []
    while len(out) < n:
        c = (rng.randrange(256), rng.randrange(256), rng.randrange(256))
        if all(np.linalg.norm(_lab(c) - _lab(o)) >= 30 for o in out + avoid):
            out.append(c)
    return out


def _f(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def _element(p: Primitive) -> str:
    q, fill = p.params, f'fill="{p.colour}"'
    if p.kind == "circle":
        return f'<circle cx="{_f(q["cx"])}" cy="{_f(q["cy"])}" r="{_f(q["r"])}" {fill}/>'
    if p.kind == "ellipse":
        rot = f' transform="rotate({_f(q["angle"])} {_f(q["cx"])} {_f(q["cy"])})"' if q["angle"] else ""
        return f'<ellipse cx="{_f(q["cx"])}" cy="{_f(q["cy"])}" rx="{_f(q["rx"])}" ry="{_f(q["ry"])}"{rot} {fill}/>'
    if p.kind in ("rect", "roundrect", "bar"):
        x, y, w, h = q["x"], q["y"], q["w"], q["h"]
        rx = f' rx="{_f(q["rx"])}"' if q.get("rx") else ""
        rot = ""
        if q.get("angle"):
            rot = f' transform="rotate({_f(q["angle"])} {_f(x + w / 2)} {_f(y + h / 2)})"'
        return f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(w)}" height="{_f(h)}"{rx}{rot} {fill}/>'
    if p.kind == "polygon":
        n, cx, cy, r, a0 = int(q["n"]), q["cx"], q["cy"], q["r"], math.radians(q["angle"])
        pts = " ".join(
            f"{_f(cx + r * math.cos(a0 + 2 * math.pi * i / n))},{_f(cy + r * math.sin(a0 + 2 * math.pi * i / n))}"
            for i in range(n)
        )
        return f'<polygon points="{pts}" {fill}/>'
    if p.kind == "ring":  # an annulus: outer circle with a concentric hole (even-odd)
        cx, cy, r, inner = q["cx"], q["cy"], q["r"], q["inner"]

        def circ(rad: float) -> str:
            return (
                f"M{_f(cx - rad)} {_f(cy)}a{_f(rad)} {_f(rad)} 0 1 0 {_f(2 * rad)} 0"
                f"a{_f(rad)} {_f(rad)} 0 1 0 {_f(-2 * rad)} 0z"
            )

        return f'<path d="{circ(r)}{circ(inner)}" fill-rule="evenodd" {fill}/>'
    raise ValueError(p.kind)


def _primitive(rng: random.Random, colour: str) -> Primitive:
    kind = rng.choice(("circle", "ellipse", "rect", "roundrect", "polygon", "ring", "bar"))
    cx, cy = rng.uniform(56, 200), rng.uniform(56, 200)
    if kind == "circle":
        return Primitive(kind, colour, {"cx": cx, "cy": cy, "r": rng.uniform(14, 54)})
    if kind == "ellipse":
        rx = rng.uniform(18, 56)
        return Primitive(kind, colour, {"cx": cx, "cy": cy, "rx": rx, "ry": rx * rng.uniform(0.35, 0.8),
                                        "angle": float(rng.choice(ANGLES))})  # fmt: skip
    if kind in ("rect", "roundrect"):
        w, h = rng.uniform(24, 110), rng.uniform(24, 110)
        q = {"x": cx - w / 2, "y": cy - h / 2, "w": w, "h": h, "angle": 0.0}
        if kind == "roundrect":
            q["rx"] = min(w, h) * rng.uniform(0.12, 0.35)
        return Primitive(kind, colour, q)
    if kind == "polygon":
        return Primitive(kind, colour, {"n": float(rng.randint(3, 8)), "cx": cx, "cy": cy,
                                        "r": rng.uniform(20, 56), "angle": float(rng.choice(ANGLES))})  # fmt: skip
    if kind == "ring":
        r = rng.uniform(26, 56)
        return Primitive(kind, colour, {"cx": cx, "cy": cy, "r": r, "inner": r * rng.uniform(0.45, 0.75)})
    w, h = rng.uniform(70, 170), rng.uniform(10, 26)  # bar: a long stroke-like rect at a designer angle
    return Primitive(kind, colour, {"x": cx - w / 2, "y": cy - h / 2, "w": w, "h": h,
                                    "angle": float(rng.choice(ANGLES))})  # fmt: skip


def mark(index: int, seed: int = 20261002) -> Mark:
    """The ``index``-th synthetic mark (deterministic for a seed)."""
    rng = random.Random(seed * 100_003 + index)
    colours = [_hex(c) for c in _palette(rng, rng.randint(1, 4), [(255, 255, 255)])]
    count = rng.randint(1, 5)
    prims = tuple(_primitive(rng, colours[i % len(colours)]) for i in range(count))
    body = "".join(_element(p) for p in prims)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VIEW} {VIEW}" '
        f'width="{VIEW}" height="{VIEW}">{body}</svg>'
    )
    return Mark(f"syn-{seed}-{index:04d}", prims, svg)


def samples(count: int, seed: int = 20261002, sizes: tuple[int, ...] = SIZES) -> list[Sample]:
    """Every mark at every size, each under one degradation chosen per (mark, size)."""
    out = []
    for i in range(count):
        m = mark(i, seed)
        for size in sizes:
            rng = random.Random(f"{m.id}@{size}")
            degradation = DEGRADATIONS[(i + sizes.index(size)) % len(DEGRADATIONS)]
            plate = None
            if degradation in ("plate", "jpeg"):
                plate = _hex(_palette(rng, 1, [_lab_rgb(c) for c in m.palette])[0])
            out.append(Sample(f"{m.id}@{size}/{degradation}", m, size, degradation, plate))
    return out


def _lab_rgb(colour: str) -> tuple[int, int, int]:
    return tuple(int(colour[i : i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def raster(sample: Sample) -> np.ndarray:
    """The sample's source raster (H×W×4 uint8), drawn by the pinned rasteriser then degraded."""
    from PIL import Image, ImageFilter

    from primitrace.bench.render import pinned

    rgba = pinned(sample.mark.svg, sample.size, sample.size)
    img = Image.fromarray(rgba, "RGBA")
    if sample.plate is not None:
        plate = Image.new("RGBA", img.size, (*_lab_rgb(sample.plate), 255))
        img = Image.alpha_composite(plate, img)
    if sample.degradation == "blur":
        img = img.filter(ImageFilter.GaussianBlur(0.6))
    if sample.degradation == "jpeg":
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=70)
        img = Image.open(io.BytesIO(buf.getvalue())).convert("RGBA")
    return np.asarray(img).copy()
