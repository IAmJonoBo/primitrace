# 10. A public, standalone repository consumed by commit

Date: 2026-10-03

## Status

Accepted

## Context

The engine began as `engine/logo_masters` in Playlust. The owner wanted a standalone project and,
on 2 October 2026, approved a public repository under IAmJonoBo. Public code uses GitHub-hosted
runners under fleet policy.

## Decision

- **Home.** primitrace lives at `IAmJonoBo/primitrace`, under Apache-2.0, with the fleet
  `python_uv` configuration: mise tasks, `ci:validate`, Ruff, Trunk, Renovate and the portability
  policy.
- **CI.** "Required verification" runs on hosted Linux, and macOS compatibility runs nightly.
- **Consumption.** Playlust depends on primitrace pinned by commit and no longer carries a copy.
- **What stays in Playlust.** The logo-masters manifest contract, the originals and every
  real-mark evaluation stay there (ADR 8).

## Consequences

Releases are by commit until a PyPI release is decided, which is a reserved rung in the ladder.
Ownership (personal or a house venture) and fleet registry entry are open owner decisions.
