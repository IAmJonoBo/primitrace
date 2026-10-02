# Delivery ladder: how it stays current

`state/delivery-ladder.json` is the single ordered list of remaining work. It uses the fleet schema
`cm-delivery-ladder.v1`, with two additive fields: `exit_gates` on each rung, and a top-level
`targets` block holding the milestone 1 exit thresholds and the parameter defaults the owner can
override.

`DELIVERY-LADDER.md` and `DELIVERY-LADDER.html` at the repository root are generated, read-only
views (`mise run ladder:write`). `mise run ladder:check`, which is part of `ci:validate`, refuses
any of the following:

- a malformed ladder, an unknown status, or duplicate or unknown rung ids;
- anything other than exactly one current rung, or a current rung with dependencies not done;
- a dependency on a rung that is not earlier in the ladder;
- a done rung without evidence, or with evidence files missing;
- an open rung with no tasks or no exit gates;
- a reserved rung that names no decision, or a blocked rung without a blocker;
- a rendered view that differs from the JSON;
- a published-page digest that is stale, once `state/delivery-ladder-artifact.json` records one.
  Publishing is optional.

## Advancing a rung

1. Meet every exit gate and write the evidence to `evidence/<rung>-*`. Evidence holds aggregates
   only, never third-party images (ADR 8).
2. Mark the rung `done` and add its `evidence_refs` and `steps`. Mark the next eligible rung
   `current`, and bump `cursor_revision` and `updated_at`.
3. If the rung changes a recorded decision, add a superseding ADR in `docs/adr/`.
4. Run `mise run ladder:write`, then `mise run ci:validate`, and commit them together.
