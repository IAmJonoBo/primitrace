# 3. Geometry is analytic; learned parts never touch coordinates

Date: 2026-10-03

## Status

Accepted

## Context

Learned vectorisers (StarVector, OmniSVG, LIVE/DiffVG) can produce plausible SVGs, but their
geometry is not guaranteed to match the source. They also need GPUs beyond a 16 GB Apple Silicon
machine. ML upscalers invent detail. A master must be the brand's own geometry.

## Decision

Every coordinate in an output comes from an analytic fit to the source's own pixels. Learned
components may gate inputs, score confidence and tune hyperparameters, such as the corner
threshold or the penalty weight per class. They never emit or nudge a coordinate, and no ML
upscaler supplies pixels to trace.

## Consequences

Assisted learning (M2) works on labels and parameters, not on shapes. Results are explainable and
run offline. Reversal condition: if a learned component were ever proposed for geometry, it would
need a new ADR with evidence that it never invents shapes absent from the source.
