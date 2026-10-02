# 5. No upsampled tracing; multi-scale is a confidence signal

Date: 2026-10-03

## Status

Accepted

## Context

The original brief previewed each input at several sizes and traced at the clearest. If
contouring is genuinely sub-pixel on the soft field, Lanczos ×4 or ×8 adds no information. It can
also cost a lot of memory on a shared 16 GB machine.

## Decision

Tracing reads the source's own anti-aliased field. Previews at several scales stay as a
topology-arbitration and confidence signal: component and hole counts should be stable across
neighbouring scales, and edges should be sharp. Enlarged-image tracing is dropped unless an
ablation shows it helps. The owner accepted this on 2 October 2026.

## Consequences

Confidence includes agreement across scales. The legacy `prep` path still upscales, because it
feeds the stacked-potrace baseline, and stays as it is until the fitter replaces it.
