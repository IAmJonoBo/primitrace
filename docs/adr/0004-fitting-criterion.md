# 4. Fit by σ-normalised BIC on sub-pixel contours

Date: 2026-10-03

## Status

Accepted

## Context

A designer redraws a mark with the fewest primitives that match it. Fixed tolerances are
scale-dependent and invite tuning until a gate passes. AIC penalises complexity too lightly and
over-fits; cross-validation over contour points is costly.

## Decision

- **Contours** are sub-pixel iso-contours of the anti-aliased field (alpha or colour boundary), not
  the hard mask.
- **Resampling.** Fitting resamples each contour to one point per source pixel of arclength, so n
  in the (k/2)·ln n term is canonical. Reported Hausdorff and Chamfer distances resample both
  curves at four points per source pixel.
- **Criterion.** Candidates (line, circular arc, elliptical arc, quadratic and cubic Bézier per
  segment; circle, ellipse, rectangle, rounded rectangle and regular polygon per whole contour) are
  chosen by dimensionless penalised likelihood:
  - residuals are normalised by σ, the local anti-alias ramp width, median-filtered and clamped to
    0.2–2.0 px;
  - the complexity penalty is pure BIC (λ = 1).
- **Segmentation** is a bounded moment-prefix dynamic programme seeded by curvature extrema, with a
  span window of 64 resampled points and whole-contour detectors running in parallel. It sits
  behind an ablation switch against a seeded corner-split. Which one becomes the default is
  decided by the ablation, within a per-mark budget of 2.0 s median, 5.0 s p95 and under 2 GB peak
  memory, which the owner can override. Exceeding the budget falls back to the seeded split and
  logs it.

## Consequences

Over- and under-fitting are traded explicitly in one currency instead of by tuned thresholds. The
conventions are recorded in `baseline.json` and asserted by tests. Reversal condition: synthetic
evidence that iso-contour fitting cannot beat stacked potrace.
