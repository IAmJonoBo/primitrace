# 2. Stacked potrace is the baseline and the fallback

Date: 2026-10-03

## Status

Accepted

## Context

The L14 prototype traced eleven real channel logos with vtracer and with stacked potrace layers
(one potrace mask per palette colour, largest first, each layer covering its own colour and every
colour drawn above it). On one mark, stacked potrace drew 2 paths and 274 nodes at ink IoU 0.995.
vtracer drew 50 paths and 2,474 nodes at 0.982. vtracer's own colour clustering also brought back
hundreds of edge shades. Stacked layers overlap, so they leave no seams.

## Decision

Stacked potrace over the prepared, quantised raster is the product until a fitter beats it. It is
frozen as an arm of `baseline.json`, with vtracer kept as a second arm for reference. Every fitted
mark falls back to it (ADR 6).

## Consequences

Any new method is judged item by item against a strong, cheap baseline rather than against
nothing. potrace's limits are what the fitter must beat. It only knows Bézier chains, so circles
drift, stems bow and small counters can be dropped as specks; the M0 bench already caught a 9 px
sliver counter lost this way.
