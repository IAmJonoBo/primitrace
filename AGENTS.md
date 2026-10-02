# AGENTS.md

primitrace is a Python library for designer-grade vectorisation. The design record is Consensus
topic `personal/logo-vectoriser`, P1 and its decision.

## Rules

- Gate: `mise run ci:validate` must pass before any commit; chain the commit to its success.
- Oxford English in documentation, comments and commit messages; conventional commits.
- Never force-push or use `--no-verify`.
- Geometry is analytic. No learned component emits or nudges coordinates, and no ML upscaler
  supplies pixels to trace.
- Non-regression has two levels. Each contour picks its best candidate by penalised cost with
  render-back, and the whole mark rolls back to stacked potrace on any regression beyond the
  pinned noise floor. Thresholds are never lowered to pass a gate.
- The renderer is part of the measurement. Metrics use the pinned rasteriser, and its
  disagreement with the independent renderer is the floor no claim may undercut.
- Corpus images are never committed. `corpus/manifest.json` is fail-closed.
- This repository is public, so no third-party or trademarked mark may enter it, not even as a
  test fixture. That covers broadcaster logos, n00bt00b's logo-mastering fixtures, Playlust's
  originals and any master traced from them. Tests here use synthetic or freely licensed marks only.
  Cross-checks against real marks (for example `logo-mastering-cases.v1.json`) run in Playlust,
  which is private: it vendors the fixtures by sha256 and runs this package over them. Case files
  holding only verdicts and numbers may be vendored here.
- Heavy runs (large corpora, ×8 renders) must bound their memory. The development machine has
  16 GB and shares it with other work.

## Layout

| Path                         | Purpose                                                                  |
| ---------------------------- | ------------------------------------------------------------------------ |
| `src/primitrace/prep.py`     | Key, trim, denoise and quantise a raster                                 |
| `src/primitrace/trace.py`    | Stacked potrace (baseline) and mono silhouette                           |
| `src/primitrace/fidelity.py` | Render-back fidelity against the prepared source                         |
| `src/primitrace/bench/`      | Synthetic marks, renderers, shape metrics, noise floor and baseline      |
| `tools/svgo/`                | Pinned svgo and its committed config (primitives kept, hex colours kept) |
| `corpus/`                    | Licence manifest; local cache is ignored                                 |
