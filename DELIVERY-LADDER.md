# primitrace delivery ladder

<!-- Generated from state/delivery-ladder.json by scripts/ladder_check.py --write. Do not edit. -->

- Programme: `primitrace-20261002`
- Ladder revision: 1
- Updated: 2026-10-03T00:00:00+00:00

## Rules

- `state/delivery-ladder.json` is the only list of remaining work; `DELIVERY-LADDER.md` and `DELIVERY-LADDER.html` are generated views (`python3 scripts/ladder_check.py --write`), and `mise run ladder:check` refuses a view that differs from the JSON.
- Exactly one rung is current, and all of its dependencies are done. A rung is done only when every exit gate has passed and its evidence files exist under `evidence/`.
- Every rung also passes `mise run ci:validate`. No rung lowers a threshold, a test count or the noise-floor safety factor.
- Decisions live in `docs/adr/`; a rung that changes one adds a superseding ADR.
- No third-party or trademarked mark enters this repository; real-mark evaluation runs in the private consumer and is reported here as aggregates only.

## Summary

- **M0a** Bench foundations — Done
- **M0b** Noise floor and frozen baseline — Current
- **M0c** Licensed round-trip corpus — Queued
- **M0d** Prevalence audit — Queued
- **M0e** Mastering measurements port — Queued
- **M1a** Sub-pixel contours and sigma — Queued
- **M1b** Primitive fitter — Queued
- **M1c** Non-regression and milestone 1 exit — Queued
- **M2a** Relationship snaps — Queued
- **M2b** Gradients — Queued
- **M2c** Strokes and shared boundaries — Queued
- **M2d** Confidence and assisted learning — Reserved
- **M3** Release — Reserved

## M0a: Bench foundations

Status: Done. Depends on: none.

primitrace exists as a public, fleet-configured package holding the baseline engine and the measuring bench, with nothing third-party in it.

### Tasks

- Move prep, the stacked-potrace trace and fidelity out of Playlust L14 (ADR 2, ADR 10).
- Synthetic marks with exact ground truth; pinned rsvg-convert and independent resvg; shape metrics on resampled sub-pixel contours; pinned svgo 4.1.0 keeping primitives (ADR 7, ADR 8).
- Fail-closed corpus manifest.
- Fleet python_uv configuration, public repository, hosted required verification and nightly macOS.

### Exit gates

- `mise run ci:validate` passes locally and Required verification passes on hosted Linux.
- Trunk reports no issues on every file.
- No image is tracked in the repository.

### Steps

- 2026-10-02: repository created at IAmJonoBo/primitrace (7b953c8); Trunk clean with recorded bandit exceptions (bfe4a62); no-third-party-marks rule recorded (0eb942d). 23 tests; Required verification green.
- The bench's first scoring caught stacked potrace dropping a 9 px sliver counter as a speck.

### Evidence

- `evidence/M0a-foundations.json`

## M0b: Noise floor and frozen baseline

Status: Current. Depends on: M0a.

Every later claim is measured against a frozen, versioned baseline and can never undercut the renderers' own disagreement.

### Tasks

- Run `python -m primitrace.bench baseline` over 40 seeded marks at 64, 128 and 256 px (120 samples) with the potrace and vtracer arms.
- Record tool versions, conventions, the noise floor (p95 per metric, safety 2.0), runtime and peak memory.
- Add a test that asserts the recorded conventions match the code.

### Exit gates

- `bench/baseline.json` is committed, with versions, conventions, noise floor and per-item scores for both arms.
- The svgo primitives-survive assertion passed in the same run (the CLI refuses otherwise).
- A test fails if the conventions in code drift from those in `baseline.json`.

## M0c: Licensed round-trip corpus

Status: Queued. Depends on: M0b.

A local, licence-checked corpus of real vector marks gives a clean round-trip stratum alongside the synthetic one.

### Tasks

- Fetch Simple Icons (CC0), Wikimedia Commons public-domain logo SVGs and OFL glyph outlines into `corpus/cache/` with manifest entries (ADR 8).
- Rasterise each with the synthetic degradations; score the baseline on the round trip.
- Keep everything local; report aggregates only.

### Exit gates

- `corpus.check` passes on the full cache; every file is in the manifest with an allowed licence.
- The baseline is scored on the clean round-trip stratum and the result is recorded in evidence.

## M0d: Prevalence audit

Status: Queued. Depends on: M0b.

We know how often real channel logos contain recoverable primitives, which decides how much fitter to build.

### Tasks

- A detector for recoverable circles, ellipses and fixed-angle straight runs, validated on synthetic truth.
- Playlust (private) runs it over its catalogue logos and returns aggregate counts only.
- Apply the traffic light from ADR 9.

### Exit gates

- The detector reaches recall >= 0.95 on synthetic primitives.
- An aggregate prevalence report with confidence intervals is recorded, and the fitter scope is chosen by the recorded cutoffs.

## M0e: Mastering measurements port

Status: Queued. Depends on: M0a.

n00bt00b's mastering measurements (keyAndTrim, analyse, classify) exist in Python and agree with its 37 cases.

### Tasks

- Port the three measurements from n00bt00b e8abe33f; the case file (verdicts and numbers) may be vendored here.
- Synthetic tests here; the cross-check on the real fixtures runs in Playlust, which vendors them by sha256 (ADR 8).

### Exit gates

- Playlust's cross-check agrees with `logo-mastering-cases.v1.json` on every case, or each difference is a recorded, owner-accepted case.
- No fixture image enters this repository.

## M1a: Sub-pixel contours and sigma

Status: Queued. Depends on: M0b, M0d.

Contours come from the soft field with a measured anti-alias width, and multi-scale agreement is a confidence signal.

### Tasks

- Iso-contours per colour region from the anti-aliased field; sigma estimated, median-filtered and clamped to 0.2-2.0 px (ADR 4).
- Multi-scale previews for topology arbitration and confidence; ablation of enlarged-image tracing (ADR 5).

### Exit gates

- On synthetic marks, contour Hausdorff to truth is within 2x the noise floor before any fitting.
- The ablation result for enlarged tracing is recorded, and the tracing source is chosen from it.

## M1b: Primitive fitter

Status: Queued. Depends on: M1a.

Each contour is rebuilt from the fewest primitives the evidence supports.

### Tasks

- Per-segment candidates: line, circular arc, elliptical arc, quadratic and cubic Bezier; whole-contour circle, ellipse, rect, rounded rect and regular polygon.
- Sigma-normalised BIC with lambda = 1; bounded moment-prefix DP (W = 64) behind an ablation switch against a seeded corner-split; per-mark budget 2.0 s median, 5.0 s p95, under 2 GB (ADR 4).

### Exit gates

- Synthetic primitive recall >= 0.95 with Hausdorff <= 0.5 px.
- The DP versus corner-split default is chosen from the recorded ablation within the budget.

## M1c: Non-regression and milestone 1 exit

Status: Queued. Depends on: M1b, M0c.

The fitter ships only where it beats stacked potrace, and never makes a published mark worse.

### Tasks

- Two-level non-regression: per-contour choice with render-back, whole-mark rollback to stacked potrace (ADR 6).
- A gate refusing photographs and gradient marks (ADR 9).
- Paired per-item deltas with bootstrap intervals against `baseline.json`.

### Exit gates

- Zero whole-mark regressions beyond the noise floor.
- Clean licensed round trip: median nodes <= 1.4x the source and IoU >= 0.99.
- Playlust's held-out real-mark evaluation is reported (aggregates only).

## M2a: Relationship snaps

Status: Queued. Depends on: M1c.

Masters carry a designer's regularity: parallels, equal radii, concentric arcs, symmetry and repeated shapes.

### Tasks

- Detect relations; accept a snap only when the residual stays within the 0.35 source px rail; re-fit after each accepted snap until description length stops falling.
- Instancing of repeated shapes via `<use>`.

### Exit gates

- No snap moves geometry beyond the rail, asserted on synthetic truth.
- Description length falls with no whole-mark regression beyond the noise floor.

## M2b: Gradients

Status: Queued. Depends on: M1c.

Linear and radial gradient marks are fitted rather than refused.

### Tasks

- Fit linear and radial ramps per region within a Delta E bound; emit `<linearGradient>`/`<radialGradient>`.
- Lift the M1 refusal for gradients that fit.

### Exit gates

- Mean Delta E00 <= 3 on gradient regions of synthetic truth.
- Marks that do not fit stay refused.

## M2c: Strokes and shared boundaries

Status: Queued. Depends on: M1c.

Line-art marks keep uniform stroke widths, and adjacent regions share one boundary with no hairline seams.

### Tasks

- Centreline recovery for uniform-width strokes.
- Shared-boundary fitting between adjacent regions (region adjacency graph).

### Exit gates

- No hairline seams at any display size in the render-back check.
- Stroke widths are recovered within the noise floor on synthetic truth.

## M2d: Confidence and assisted learning

Status: Reserved. Depends on: M1c.

Confidence is calibrated against human judgement, and a reviewer sees only the cases the engine doubts.

Decision held by the owner: The owner sets the label budget (for example 200 initially, then about 20 a week).

### Tasks

- An uncertainty-ranked review page: accept, reject or pick an alternative fit.
- Labels retrain the gate, the per-class parameters and isotonic calibration; learned parts never touch coordinates (ADR 3).

### Exit gates

- ECE <= 0.05 on the labelled set.
- Every learned component is reversible, and the engine runs offline without it.

## M3: Release

Status: Reserved. Depends on: M1c.

primitrace is installable as a versioned package with a stable API.

Decision held by the owner: The owner decides PyPI publication, and whether primitrace is personal or a house venture (with a fleet registry entry).

### Tasks

- A stable API: `vectorise(rgba) -> Result{svg, mono_svg, confidence, report}`.
- Versioned releases with a changelog.

### Exit gates

- The API is documented and covered by tests.
- The release process is recorded and repeatable.
