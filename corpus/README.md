# Corpus

The bench is synthetic-first: its marks are generated from a seed and never stored. Real images
are optional and local:

- They live in `corpus/cache/`, which git ignores, and are never redistributed.
- Each one must be recorded in `manifest.json`: source, licence, sha256, and
  `"redistribute": false`.
- `primitrace.corpus.check()` fails closed. Any cached file missing from the manifest, any hash
  mismatch, or any licence outside `ALLOWED_LICENCES` stops a run.

Approved sources (operator decision, 2 October 2026):

| Source | Licence | Use |
| --- | --- | --- |
| Synthetic marks | generated | training, calibration, tests |
| Simple Icons | CC0-1.0 (some icons carry their own caveats) | round-trip ground truth |
| Wikimedia Commons PD logos | public domain (trademarks remain) | round-trip ground truth, local only |
| OFL font glyphs | OFL-1.1 | curve ground truth |

Real channel or brand logos are evaluation-only, held out and never used for fitting.
