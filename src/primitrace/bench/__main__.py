"""``python -m primitrace.bench``: measure the noise floor and freeze the baseline.

    python -m primitrace.bench baseline --count 40 --out bench/baseline.json
    python -m primitrace.bench floor --count 40

``baseline`` refuses to write unless the pinned svgo keeps native circles, ellipses and rects
intact and drawn the same (the M0 precondition: complexity is counted on its output).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from primitrace.bench import render as R
from primitrace.bench import run, shape, synthetic

SEED = 20261002


def primitives_survive() -> list[str]:
    """Problems with svgo's treatment of native primitives; empty when they survive intact."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">'
        '<circle cx="30" cy="30" r="20" fill="#d01020"/><ellipse cx="70" cy="30" rx="20" ry="10" fill="#1040c0"/>'
        '<rect x="10" y="60" width="30" height="30" fill="#20a040"/>'
        '<rect x="55" y="60" width="35" height="30" rx="6" fill="#802080"/></svg>'
    )
    out = shape.optimise(svg)
    problems = []
    for tag, n in (("circle", 1), ("ellipse", 1), ("rect", 2)):
        if out.count(f"<{tag}") != n:
            problems.append(f"svgo changed the number of <{tag}> elements")
    a, b = R.pinned(svg, 200, 200), R.pinned(out, 200, 200)
    if int(abs(a.astype(int) - b.astype(int)).max()) > 2:
        problems.append("svgo output draws differently from its input")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m primitrace.bench")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("floor", "baseline"):
        p = sub.add_parser(name)
        p.add_argument("--count", type=int, default=40, help="synthetic marks (each drawn at every size)")
        p.add_argument("--seed", type=int, default=SEED)
        p.add_argument("--out", help="write JSON here (default: stdout)")
    args = ap.parse_args(argv)

    problems = primitives_survive()
    if problems:
        print("refusing: " + "; ".join(problems), file=sys.stderr)
        return 2
    marks = [synthetic.mark(i, args.seed) for i in range(args.count)]
    doc: dict[str, object] = {
        "version": 1,
        "measured_at": run.stamp(),
        "seed": args.seed,
        "count": args.count,
        "versions": run.versions(),
        "conventions": run.conventions(),
        "noise_floor": run.noise_floor(marks),
    }
    if args.cmd == "baseline":
        doc["baseline"] = run.baseline(args.count, args.seed, progress=lambda s: print(s, file=sys.stderr))
    text = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
