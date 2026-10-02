# 7. Pinned renderer, noise floor and complexity conventions

Date: 2026-10-03

## Status

Accepted

## Context

Every metric renders SVG to pixels, so the renderer is part of the measurement. svgo's default
preset converts circles and rectangles to paths and renames colours. That would hide primitives
and corrupt both the complexity counts and the palette read-back.

## Decision

- **Renderers.** `rsvg-convert` (librsvg) is the pinned rasteriser, and its version is recorded.
  resvg is the independent renderer.
- **Noise floor.** Per metric and evaluation size, the floor is the p95 disagreement between the
  two renderers over the corpus. No gate may claim a difference smaller than 2× the floor.
- **svgo.** It is pinned (4.1.0) with a committed config that keeps native primitives and
  `#rrggbb` colours. Complexity is counted on its output:
  - nodes are path segments plus one per circle, ellipse or rect, plus one per polygon vertex;
  - primitive share is primitives divided by (primitives plus paths).
- **Freezing.** `baseline.json` is frozen only after an assertion passes: native primitives must
  survive svgo and draw identically.
- **Units.** Distances are in source pixels. SSIM is taken at display sizes 16, 32, 64 and 256 px.

## Consequences

Results are reproducible and comparable across machines. A tool upgrade means re-measuring the
floor and the baseline, recorded together.
