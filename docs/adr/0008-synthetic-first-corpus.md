# 8. Synthetic-first evaluation and a fail-closed corpus

Date: 2026-10-03

## Status

Accepted

## Context

Ground truth for vectorisation is a known SVG. Real logos are trademarks. The n00bt00b fixtures
and Playlust's originals are held for private household use only, and that permission does not
extend to a public repository.

## Decision

- **Synthetic first.** Seeded marks built from primitives, with exact ground truth, are the
  training, calibration and test corpus.
- **Local cache.** Freely licensed vectors are cached locally only, never committed or
  redistributed. The owner approved Simple Icons (CC0), Wikimedia Commons public-domain logos and
  OFL font glyphs.
- **Fail-closed manifest.** `corpus/manifest.json` must record every cached file with its source,
  licence, sha256 and `redistribute: false`, or the run stops.
- **Real marks stay private.** No third-party or trademarked mark enters this public repository,
  not even as a test fixture. Cross-checks against real marks run in the private consumer
  (Playlust), which vendors the fixtures by hash and runs this package over them. Real channel
  logos are evaluation-only and held out.

## Consequences

The repository can stay public. Results on real marks are reported by the consumer, and this
repository records only aggregate figures.
