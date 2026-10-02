# primitrace

Designer-grade vectorisation of logos and flat graphics.

primitrace rebuilds a raster mark the way a designer redraws it. It recognises the shapes first,
then fits the fewest primitives (lines, arcs, circles, ellipses, rectangles, then Bézier curves)
that reproduce the pixels within their own anti-aliasing. Every result is rendered back and scored
against its source, and a whole mark falls back to the baseline trace if the new fit is worse
anywhere beyond measurement noise.

## Status

| Milestone | Scope | State |
| --- | --- | --- |
| M0 | Evaluation bench: synthetic ground truth, pinned renderers, noise floor, frozen stacked-potrace baseline, licence manifest, prevalence audit | in progress |
| M1 | Primitive fitter for flat-colour marks (σ-normalised BIC on sub-pixel contours, two-level non-regression) | planned |
| M2 | Relationship snaps, gradients, centreline strokes, shared boundaries, review UI | planned |

Photographs and gradient marks are refused, not traced badly. Learned components may gate inputs,
score confidence and tune settings. They never move or invent geometry.

## Requirements

- Python 3.13 with [uv](https://docs.astral.sh/uv/), and [mise](https://mise.jdx.dev/) for tasks
- `potrace` and `rsvg-convert` (macOS: `brew install potrace librsvg`; Debian or Ubuntu:
  `apt install potrace librsvg2-bin`)
- Node, for the pinned svgo in `tools/svgo` (complexity is counted on its output)

## Use

```bash
mise run bootstrap
mise run ci:validate
```

```python
import numpy as np
from PIL import Image

from primitrace import fidelity, prep, trace

rgba = np.asarray(Image.open("mark.png").convert("RGBA"))
p = prep.prepare(rgba)
svg = trace.layered_svg(p.rgba, p.palette)  # colour master
mono = trace.mono_svg(p.ink)  # one currentColor silhouette
print(fidelity.measure(svg, p.rgba))
```

## Corpus and licensing

Code is Apache-2.0. Images are not part of the repository. Evaluation corpora (synthetic marks,
Simple Icons, Wikimedia Commons public-domain logos, OFL font glyphs) are cached locally under
`corpus/cache/` and recorded in `corpus/manifest.json`. They are never redistributed, and logos
remain their owners' trademarks. See [corpus/README.md](corpus/README.md).
