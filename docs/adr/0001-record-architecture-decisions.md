# 1. Record architecture decisions

Date: 2026-10-03

## Status

Accepted

## Context

primitrace started inside Playlust (ladder rung L14) and was planned through a multi-model
Consensus run. The reasons behind its shape will matter to anyone extending the fitter, and they
are easy to lose once the code moves.

## Decision

Significant decisions are recorded here as numbered ADRs. The delivery ladder
(`state/delivery-ladder.json`) cites them. Where a decision came from Consensus, the ADR names the
topic and session.

## Consequences

Changing a recorded decision needs a new ADR that supersedes the old one, and the ladder must stay
consistent with both.
