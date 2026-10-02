"""primitrace: designer-grade vectorisation of logos and flat graphics.

A raster mark is rebuilt the way a designer redraws it: recognise the shapes, then fit the fewest
primitives (lines, arcs, circles, ellipses, rectangles, then Bézier curves) that reproduce the
pixels within their own anti-aliasing, and prove the result against the source.

Modules:

* ``prep``: key the plate, trim, denoise and quantise a raster to its flat palette.
* ``trace``: the stacked-potrace baseline (colour) and the mono silhouette.
* ``fidelity``: render-back fidelity of a trace against its prepared source.
* ``bench``: the evaluation bench (synthetic ground truth, pinned renderers, metrics).

The primitive fitter arrives in milestone 1; until then the baseline trace is the product.
"""

__version__ = "0.1.0"
