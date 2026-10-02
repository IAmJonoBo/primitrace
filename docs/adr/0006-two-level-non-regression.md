# 6. Two-level non-regression, no percentage quotas

Date: 2026-10-03

## Status

Accepted

## Context

A quota such as "no more than 5% of items regress" lets a method ship visible regressions on
some marks. Masters are published per channel, so one bad mark is a visible defect.

## Decision

- Each contour chooses its candidate by penalised cost (ADR 4), checked by render-back.
- The whole mark then rolls back to stacked potrace on any composite regression beyond the noise
  floor (ADR 7).
- There are no percentage regression quotas. A milestone's exit requires zero whole-mark
  regressions beyond the floor.

## Consequences

The fitter can only improve on the baseline as published. Effort goes to making wins larger, not
to explaining losses.
