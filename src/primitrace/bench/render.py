"""The pinned rasteriser and an independent renderer.

Every metric renders an SVG to pixels, so the renderer is part of the measurement. One renderer is
pinned (``rsvg-convert``, librsvg: the renderer sharp, and so n00bt00b, uses), and its version is
recorded in ``baseline.json``. A second, independent implementation (resvg) draws the same SVGs; how
far the two disagree is the noise floor, below which no gate may claim a difference.
"""

from __future__ import annotations

import functools
import io
import subprocess

import numpy as np


@functools.cache
def pinned_version() -> str:
    out = subprocess.run(["rsvg-convert", "--version"], check=True, capture_output=True, text=True).stdout
    return out.strip()


def independent_version() -> str:
    from importlib.metadata import version

    return f"resvg-py {version('resvg-py')}"


def _png(data: bytes) -> np.ndarray:
    from PIL import Image

    return np.asarray(Image.open(io.BytesIO(data)).convert("RGBA")).copy()


def pinned(svg: str, width: int, height: int) -> np.ndarray:
    """RGBA pixels of ``svg`` at ``width``×``height`` drawn by rsvg-convert."""
    png = subprocess.run(
        ["rsvg-convert", "-w", str(width), "-h", str(height), "-f", "png"],
        input=svg.encode("utf-8"),
        check=True,
        capture_output=True,
        timeout=60,
    ).stdout
    return _png(png)


def independent(svg: str, width: int, height: int) -> np.ndarray:
    """RGBA pixels of ``svg`` at ``width``×``height`` drawn by resvg."""
    import resvg_py

    png = resvg_py.svg_to_bytes(svg_string=svg, width=width, height=height, skip_system_fonts=True)
    return _png(bytes(png))
