"""The milestone 0 bench: ground truth, conventions, renderers and the baseline frame."""

from __future__ import annotations

import shutil

import pytest

from primitrace import prep
from primitrace.bench import __main__ as cli
from primitrace.bench import render as R
from primitrace.bench import run, shape, synthetic

TOOLS = shutil.which("potrace") and shutil.which("rsvg-convert")
needs_tools = pytest.mark.skipif(not TOOLS, reason="potrace and rsvg-convert are needed")


def test_marks_are_deterministic_and_native() -> None:
    a, b = synthetic.mark(3), synthetic.mark(3)
    assert a.svg == b.svg and a.id == b.id
    assert synthetic.mark(4).svg != a.svg
    assert "<path" not in a.svg or "evenodd" in a.svg  # only rings are paths
    assert 1 <= len(a.primitives) <= 5 and 1 <= len(a.palette) <= 4


def test_every_size_appears_once_per_mark() -> None:
    samples = synthetic.samples(4)
    assert len(samples) == 4 * len(synthetic.SIZES)
    assert {s.degradation for s in samples} <= set(synthetic.DEGRADATIONS)
    assert all((s.plate is None) == (s.degradation in ("clean", "blur")) for s in samples)


@pytest.mark.parametrize(
    ("d", "segments"),
    [
        ("M0 0L10 0L10 10z", 2),
        ("M0 0l1 2 3 4", 2),  # implicit repeat
        ("M0 0 10 0 10 10z", 2),  # moveto's extra pairs are linetos
        ("M0 0h5v5H0z", 3),
        ("M0 0c1 1 2 2 3 3s4 4 5 5", 2),
        ("M10 5a5 5 0 1 0 10 0a5 5 0 1 0-10 0z", 2),
        ("M10 5a5 5 0 1010 0", 1),  # packed arc flags
    ],
)
def test_path_segments_counts_drawing_segments(d: str, segments: int) -> None:
    assert shape.path_segments(d) == segments


def test_complexity_counts_primitives_once() -> None:
    svg = '<svg><circle r="1"/><rect width="1" height="1"/><polygon points="0,0 1,0 1,1"/><path d="M0 0L1 1"/></svg>'
    assert shape.complexity(svg) == (1 + 1 + 3 + 1, 3, 1)


@needs_tools
def test_svgo_keeps_primitives() -> None:
    assert cli.primitives_survive() == []


@needs_tools
def test_renderers_agree_closely_on_ground_truth() -> None:
    m = synthetic.mark(1)
    s = shape.score(m.svg, m.svg, 64, renderer=R.independent, truth_renderer=R.pinned, optimise_candidate=False)
    assert s.iou > 0.98 and s.hausdorff < 0.5


@needs_tools
def test_a_trace_is_scored_in_the_truths_frame() -> None:
    sample = next(s for s in synthetic.samples(8) if s.degradation == "clean" and s.size == 128)
    p = prep.prepare(synthetic.raster(sample))
    cand = run.in_truth_frame(run.ARMS["potrace"](p), p, sample.size)
    s = shape.score(cand, sample.mark.svg, sample.size)
    # A misplaced frame would score near zero on both. Hausdorff is not asserted: on this mark the
    # baseline drops a 9 px sliver counter as a speck, which is a measured weakness, not a frame error.
    assert s.iou > 0.95, s
    assert s.chamfer < 0.5, s
