# 9. Milestone 1 covers flat-colour marks only

Date: 2026-10-03

## Status

Accepted

## Context

Tracing photos or gradients produces noise, not masters. A tight first milestone proves the
fitter against the baseline before anything harder is attempted.

## Decision

- **Scope.** M1 reconstructs flat-colour masters. Photographs and gradient marks are refused at
  the gate and keep their current raster or trace. The owner chose refusal over flattening to a
  mean colour.
- **Deferred to M2:** relationship snaps, gradient fitting, centreline strokes, shared-boundary
  fitting, the review interface and assisted learning.
- **M1 exit:**
  - paired per-item deltas against `baseline.json`, with bootstrap intervals;
  - zero whole-mark regressions beyond the noise floor;
  - synthetic primitive recall of at least 0.95, with Hausdorff of at most 0.5 px;
  - on the clean licensed round trip, median nodes of at most 1.4× the source and IoU of at least
    0.99.
- Calibration (ECE, risk-coverage) is reported, not gated, until labels exist.

## Consequences

Gradient-heavy brands wait for M2. The milestone 0 prevalence audit decides how much of the
fitter M1 builds:

- 30% or more of audited marks with a recoverable circle, ellipse or fixed-angle run: build the
  fitter;
- 20–30%: build the per-contour fitter and hold the arc and ellipse dynamic programme behind its
  ablation;
- below 20%: retire the fitter in favour of a potrace snap post-pass.

The owner can override these cutoffs.
