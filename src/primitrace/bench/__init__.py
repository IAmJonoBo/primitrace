"""The evaluation bench (milestone 0).

Decided in Consensus ``personal/logo-vectoriser`` P1 (session s-ce513c776105, operator decision
2026-10-02): before any new fitter is built, a synthetic-first bench proves what "better than
stacked potrace" means.

* ``synthetic``: deterministic marks built from primitives, each with its ground-truth SVG, drawn
  to rasters at logo sizes with honest degradations (plate, blur, JPEG).
* ``render``: one pinned rasteriser (rsvg-convert) and one independent renderer (resvg); their
  disagreement on the same SVG is the noise floor no gate may undercut.
* ``shape``: metrics against the ground truth (IoU, Hausdorff and Chamfer on resampled contours,
  SSIM at display sizes, ΔE) and complexity counted on the pinned svgo's output.
* ``baseline``: the noise floor, then stacked potrace frozen to ``baseline.json``.

Nothing here edits a published master; the bench only measures.
"""
