"""Preparing, tracing and measuring a logo on synthetic marks (needs potrace and rsvg-convert)."""

from __future__ import annotations

import shutil
import unittest

import numpy as np
from PIL import Image, ImageDraw

from primitrace import fidelity, prep, trace

TOOLS = shutil.which("potrace") and shutil.which("rsvg-convert")


def _mark(plate: tuple[int, int, int, int] = (255, 255, 255, 255)) -> np.ndarray:
    """A red ring with a blue bar, on a plate: two colours, one counter (the ring's hole)."""
    img = Image.new("RGBA", (300, 200), plate)
    d = ImageDraw.Draw(img)
    d.ellipse((40, 30, 180, 170), fill=(200, 20, 30, 255))
    d.ellipse((80, 70, 140, 130), fill=plate)
    d.rectangle((190, 80, 280, 120), fill=(20, 60, 200, 255))
    return np.asarray(img)


@unittest.skipUnless(TOOLS, "potrace and rsvg-convert are needed")
class TraceTest(unittest.TestCase):
    def test_a_plate_is_keyed_and_the_palette_is_the_marks_colours(self) -> None:
        p = prep.prepare(_mark())
        self.assertEqual(p.keyed, "#ffffff")
        self.assertEqual(len(p.palette), 2)
        self.assertGreaterEqual(min(p.rgba.shape[:2]), prep.TARGET_SIDE)

    def test_colour_trace_is_faithful_and_clean(self) -> None:
        p = prep.prepare(_mark())
        svg = trace.layered_svg(p.rgba, p.palette)
        f = fidelity.measure(svg, p.rgba)
        self.assertGreaterEqual(f.ink_iou, 0.98)
        self.assertLess(f.delta_e or 0, 3)
        self.assertEqual(f.colours, 2)  # exactly the palette: no edge shades
        self.assertEqual(f.paths, 2)  # one path per colour

    def test_mono_is_one_currentcolor_silhouette_that_keeps_the_counter(self) -> None:
        p = prep.prepare(_mark())
        svg = trace.mono_svg(p.ink)
        self.assertIn('fill="currentColor"', svg)
        drawn = fidelity.render(svg, p.ink.shape[1], p.ink.shape[0])[..., 3] >= 128
        h, w = drawn.shape
        self.assertFalse(drawn[int(h * 0.5), int(w * 0.32)])  # the ring's hole stays a hole
        mono_src = np.dstack([np.zeros((*p.ink.shape, 3), np.uint8), p.ink.astype(np.uint8) * 255])
        self.assertGreaterEqual(fidelity.measure(svg, mono_src, mono=True).ink_iou, 0.98)


if __name__ == "__main__":
    unittest.main()
