#!/usr/bin/env python3
"""Delivery-ladder gate for the primitrace programme.

`state/delivery-ladder.json` is the single ordered list of remaining work.
`DELIVERY-LADDER.md` and `DELIVERY-LADDER.html` are generated, read-only views
of it. When the HTML page is published as a claude.ai artifact, its digest is
recorded in `state/delivery-ladder-artifact.json` and the check keeps it current;
without a record, publishing is simply not in use.

This is the Playlust port (itself a stdlib port of the constellation programme's
`programme-ladder-check.mjs`), keeping the `cm-delivery-ladder.v1` schema so
fleet tooling can read either ladder. It refuses:

- a malformed ladder, an unknown status, duplicate or unknown rung ids;
- anything other than exactly one current rung, or a current rung whose
  dependencies are not all done;
- a dependency on a later rung (the ladder must be ordered);
- a done rung that cites no evidence, or cites evidence files that do not exist;
- an open rung with no tasks or no exit gates;
- a reserved rung that names no decision, or a blocked rung with no blocker;
- rendered views that differ from the JSON;
- a recorded artifact digest that differs from the page the ladder renders now
  (only when a record exists).

Usage:
  python3 scripts/ladder_check.py                    # check (CI gate)
  python3 scripts/ladder_check.py --write            # re-render the views
  python3 scripts/ladder_check.py --record-artifact URL   # after publishing
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "cm-delivery-ladder.v1"
STATUSES = ("done", "current", "next", "blocked", "queued", "reserved")
OPEN_STATUSES = frozenset(STATUSES) - {"done"}
RUNG_KEYS = (
    "id",
    "title",
    "status",
    "outcome",
    "tasks",
    "blockers",
    "depends_on",
    "decision",
    "steps",
    "evidence_refs",
    "exit_gates",
)
LIST_KEYS = ("tasks", "blockers", "depends_on", "steps", "evidence_refs", "exit_gates")

LADDER_PATH = Path("state/delivery-ladder.json")
ARTIFACT_PATH = Path("state/delivery-ladder-artifact.json")
MD_PATH = Path("DELIVERY-LADDER.md")
HTML_PATH = Path("DELIVERY-LADDER.html")

STATUS_LABEL = {
    "done": "Done",
    "current": "Current",
    "next": "Next",
    "blocked": "Blocked",
    "queued": "Queued",
    "reserved": "Reserved",
}


# --------------------------------------------------------------------------- validation


def validate(ladder: Any, root: Path) -> list[str]:
    """Return every rule violation; an empty list means the ladder is sound."""
    errors: list[str] = []
    if not isinstance(ladder, dict):
        return ["ladder: top level must be an object"]
    if ladder.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"ladder: schema_version must be {SCHEMA_VERSION!r}")
    for key in ("programme_id", "updated_at"):
        if not isinstance(ladder.get(key), str) or not ladder.get(key):
            errors.append(f"ladder: {key} must be a non-empty string")
    if not isinstance(ladder.get("cursor_revision"), int) or ladder["cursor_revision"] < 1:
        errors.append("ladder: cursor_revision must be a positive integer")
    if not isinstance(ladder.get("rules"), list) or not ladder["rules"]:
        errors.append("ladder: rules must be a non-empty list")
    rungs = ladder.get("rungs")
    if not isinstance(rungs, list) or not rungs:
        errors.append("ladder: rungs must be a non-empty list")
        return errors

    seen: dict[str, int] = {}
    for index, rung in enumerate(rungs):
        label = f"rung[{index}]"
        if not isinstance(rung, dict):
            errors.append(f"{label}: must be an object")
            continue
        missing = [k for k in RUNG_KEYS if k not in rung]
        if missing:
            errors.append(f"{label}: missing keys {', '.join(missing)}")
            continue
        rid = rung["id"]
        label = f"{rid}" if isinstance(rid, str) and rid else label
        if not isinstance(rid, str) or not rid:
            errors.append(f"{label}: id must be a non-empty string")
        elif rid in seen:
            errors.append(f"{label}: duplicate rung id")
        else:
            seen[rid] = index
        for key in ("title", "outcome"):
            if not isinstance(rung[key], str) or not rung[key].strip():
                errors.append(f"{label}: {key} must be a non-empty string")
        for key in LIST_KEYS:
            value = rung[key]
            if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
                errors.append(f"{label}: {key} must be a list of non-empty strings")
        if rung["decision"] is not None and not (isinstance(rung["decision"], str) and rung["decision"].strip()):
            errors.append(f"{label}: decision must be null or a non-empty string")
        if rung["status"] not in STATUSES:
            errors.append(f"{label}: unknown status {rung['status']!r} (allowed: {', '.join(STATUSES)})")
    if errors:
        return errors

    by_id = {r["id"]: r for r in rungs}
    current = [r for r in rungs if r["status"] == "current"]
    if len(current) != 1:
        errors.append(f"ladder: exactly one rung must be current (found {len(current)})")

    for index, rung in enumerate(rungs):
        rid, status = rung["id"], rung["status"]
        for dep in rung["depends_on"]:
            if dep not in by_id:
                errors.append(f"{rid}: depends on unknown rung {dep}")
            elif seen[dep] >= index:
                errors.append(f"{rid}: depends on {dep}, which is not earlier in the ladder")
        if status == "current":
            pending = [d for d in rung["depends_on"] if d in by_id and by_id[d]["status"] != "done"]
            if pending:
                errors.append(f"{rid}: current rung has dependencies not done: {', '.join(pending)}")
        if status == "done":
            if not rung["evidence_refs"]:
                errors.append(f"{rid}: done rung cites no evidence")
            for ref in rung["evidence_refs"]:
                if not (root / ref).is_file():
                    errors.append(f"{rid}: evidence file missing: {ref}")
        if status in OPEN_STATUSES:
            if not rung["tasks"]:
                errors.append(f"{rid}: open rung carries no tasks")
            if not rung["exit_gates"]:
                errors.append(f"{rid}: open rung has no exit gates")
        if status == "reserved" and not rung["decision"]:
            errors.append(f"{rid}: reserved rung names no decision")
        if status == "blocked" and not rung["blockers"]:
            errors.append(f"{rid}: blocked rung has no live blocker")
        if status != "blocked" and status != "done" and rung["blockers"] and status != "reserved":
            errors.append(f"{rid}: rung lists blockers but is {status}; mark it blocked or clear them")
    return errors


# --------------------------------------------------------------------------- rendering


def render_markdown(ladder: dict) -> str:
    out: list[str] = []
    out.append("# primitrace delivery ladder")
    out.append("")
    out.append("<!-- Generated from state/delivery-ladder.json by scripts/ladder_check.py --write. Do not edit. -->")
    out.append("")
    out.append(f"- Programme: `{ladder['programme_id']}`")
    out.append(f"- Ladder revision: {ladder['cursor_revision']}")
    out.append(f"- Updated: {ladder['updated_at']}")
    out.append("")
    out.append("## Rules")
    out.append("")
    out.extend(f"- {rule}" for rule in ladder["rules"])
    out.append("")
    out.append("## Summary")
    out.append("")
    for rung in ladder["rungs"]:
        out.append(f"- **{rung['id']}** {rung['title']} — {STATUS_LABEL[rung['status']]}")
    targets = ladder.get("targets") or {}
    for group in targets.get("groups", []):
        out.append("")
        out.append(f"## {group['title']}")
        out.append("")
        out.append("| Measure | Baseline | Target | Gate rung |")
        out.append("| --- | --- | --- | --- |")
        for row in group["rows"]:
            out.append(f"| {row['measure']} | {row['baseline']} | {row['target']} | {row['rung']} |")
    for rung in ladder["rungs"]:
        out.append("")
        out.append(f"## {rung['id']}: {rung['title']}")
        out.append("")
        deps = ", ".join(rung["depends_on"]) or "none"
        out.append(f"Status: {STATUS_LABEL[rung['status']]}. Depends on: {deps}.")
        out.append("")
        out.append(rung["outcome"])
        if rung["decision"]:
            out.append("")
            out.append(f"Decision held by the owner: {rung['decision']}")
        for key, heading in (
            ("tasks", "Tasks"),
            ("exit_gates", "Exit gates"),
            ("blockers", "Blockers"),
            ("steps", "Steps"),
            ("evidence_refs", "Evidence"),
        ):
            if rung[key]:
                out.append("")
                out.append(f"### {heading}")
                out.append("")
                if key == "evidence_refs":
                    out.extend(f"- `{item}`" for item in rung[key])
                else:
                    out.extend(f"- {item}" for item in rung[key])
    out.append("")
    return "\n".join(out)


_CODE_RE = re.compile(r"`([^`]+)`")


def _h(text: str) -> str:
    """Escape text and render `code` spans."""
    parts = _CODE_RE.split(text)
    rendered = []
    for i, part in enumerate(parts):
        rendered.append(f"<code>{html.escape(part)}</code>" if i % 2 else html.escape(part))
    return "".join(rendered)


_HTML_HEAD = """<title>primitrace Delivery Ladder</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
/* Layout: a single reading column; a rung track up top, then targets, then one block per rung. */
:root {
  --bg: #f4f6f7; --surface: #ffffff; --ink: #14212b; --muted: #55646f; --line: #d6dde2;
  --accent: #0b7a75; --accent-soft: #dcefed;
  --done: #2f7d3b; --done-soft: #e1f0e3; --current: #0b7a75; --current-soft: #d6eeec;
  --reserved: #8a5a00; --reserved-soft: #f6ead2; --blocked: #b23a2e; --blocked-soft: #f7e0dc;
  --queued: #5b6873; --queued-soft: #e7ecef;
  --font-body: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, "SF Mono", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #0f171d; --surface: #16212a; --ink: #e3eaee; --muted: #9aa9b3; --line: #2a3945;
  --accent: #4cc3bb; --accent-soft: #143534;
  --done: #7ccf88; --done-soft: #183423; --current: #4cc3bb; --current-soft: #143534;
  --reserved: #e7b454; --reserved-soft: #3a2d12; --blocked: #f08b7f; --blocked-soft: #3d1e1a;
  --queued: #a3b1bb; --queued-soft: #22303a; color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #0f171d; --surface: #16212a; --ink: #e3eaee; --muted: #9aa9b3; --line: #2a3945;
  --accent: #4cc3bb; --accent-soft: #143534;
  --done: #7ccf88; --done-soft: #183423; --current: #4cc3bb; --current-soft: #143534;
  --reserved: #e7b454; --reserved-soft: #3a2d12; --blocked: #f08b7f; --blocked-soft: #3d1e1a;
  --queued: #a3b1bb; --queued-soft: #22303a; color-scheme: dark; }
body { background: var(--bg); color: var(--ink); font: 15px/1.6 var(--font-body); }
.wrap { max-width: 60rem; margin: 0 auto; padding-inline: 16px; padding-block: 2.5rem 4rem; display: grid; gap: 2.5rem; }
header { display: grid; gap: .5rem; }
.eyebrow { font: 500 .75rem/1 var(--font-mono); letter-spacing: .08em; text-transform: uppercase; color: var(--accent); }
h1 { font-size: 2rem; line-height: 1.2; margin: 0; font-weight: 600; text-wrap: balance; }
h2 { font-size: 1.15rem; margin: 0; font-weight: 600; text-wrap: balance; }
h3 { font: 500 .72rem/1 var(--font-mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); margin: 0; }
p { margin: 0; max-width: 68ch; }
.meta { display: flex; flex-wrap: wrap; gap: .25rem 1.5rem; color: var(--muted); font: .82rem/1.5 var(--font-mono); }
code { font: .86em var(--font-mono); background: var(--queued-soft); padding: .05em .3em; border-radius: 3px; overflow-wrap: anywhere; }
section { display: grid; gap: 1rem; min-width: 0; }
ul { margin: 0; padding-left: 1.2rem; display: grid; gap: .3rem; }
.rules li { color: var(--muted); }
.track { list-style: none; padding: 0; display: grid; gap: 0; border-top: 1px solid var(--line); }
.track li { display: grid; grid-template-columns: 3.2rem 1fr auto; gap: .75rem; align-items: baseline; padding: .6rem 0; border-bottom: 1px solid var(--line); }
.track a { color: inherit; text-decoration: none; min-width: 0; }
.track a:hover, .track a:focus-visible { color: var(--accent); text-decoration: underline; }
.rid { font: 500 .9rem var(--font-mono); color: var(--muted); }
.chip { font: 500 .7rem/1 var(--font-mono); letter-spacing: .06em; text-transform: uppercase; padding: .35rem .55rem; border-radius: 999px; white-space: nowrap; }
.s-done { color: var(--done); background: var(--done-soft); }
.s-current, .s-next { color: var(--current); background: var(--current-soft); }
.s-reserved { color: var(--reserved); background: var(--reserved-soft); }
.s-blocked { color: var(--blocked); background: var(--blocked-soft); }
.s-queued { color: var(--queued); background: var(--queued-soft); }
.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); }
table { border-collapse: collapse; width: 100%; font-size: .88rem; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: .55rem .8rem; border-bottom: 1px solid var(--line); vertical-align: top; }
th { font: 500 .7rem var(--font-mono); letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }
tr:last-child td { border-bottom: 0; }
td.num { font-family: var(--font-mono); white-space: nowrap; }
.rung { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 1.25rem; display: grid; gap: 1rem; scroll-margin-top: 1rem; }
.rung.is-current { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
.rung-head { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem 1rem; justify-content: space-between; }
.rung-head h2 { display: flex; gap: .75rem; align-items: baseline; min-width: 0; }
.deps { color: var(--muted); font: .8rem var(--font-mono); }
.decision { border-left: 3px solid var(--reserved); background: var(--reserved-soft); padding: .6rem .8rem; border-radius: 0 4px 4px 0; }
.cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr)); gap: 1rem 1.5rem; }
.cols > div { display: grid; gap: .5rem; align-content: start; min-width: 0; }
.gates li::marker { content: "▢  "; color: var(--accent); }
.rung[data-status="done"] .gates li::marker { content: "☑  "; color: var(--done); }
footer { color: var(--muted); font-size: .82rem; }
@media (max-width: 480px) { .track li { grid-template-columns: 2.6rem 1fr; } .track .chip { grid-column: 2; justify-self: start; } }
</style>
"""


def render_html(ladder: dict) -> str:
    rungs = ladder["rungs"]
    counts = {s: sum(1 for r in rungs if r["status"] == s) for s in STATUSES}
    current = next((r for r in rungs if r["status"] == "current"), None)
    out: list[str] = [_HTML_HEAD, '<main class="wrap">']
    out.append("<header>")
    out.append('<span class="eyebrow">Gated roadmap</span>')
    out.append("<h1>primitrace delivery ladder</h1>")
    lead = ladder.get("summary", "")
    if lead:
        out.append(f"<p>{_h(lead)}</p>")
    out.append('<div class="meta">')
    out.append(f"<span>{html.escape(ladder['programme_id'])}</span>")
    out.append(f"<span>revision {ladder['cursor_revision']}</span>")
    out.append(f"<span>updated {html.escape(ladder['updated_at'])}</span>")
    done_total = f"{counts['done']} of {len(rungs)} rungs done"
    out.append(f"<span>{done_total}</span>")
    if current:
        out.append(f"<span>current: {html.escape(current['id'])}</span>")
    out.append("</div></header>")

    out.append('<section aria-labelledby="track-h"><h3 id="track-h">Rungs</h3><ol class="track">')
    for r in rungs:
        out.append(
            f'<li><span class="rid">{html.escape(r["id"])}</span>'
            f'<a href="#{html.escape(r["id"].lower())}">{_h(r["title"])}</a>'
            f'<span class="chip s-{r["status"]}">{STATUS_LABEL[r["status"]]}</span></li>'
        )
    out.append("</ol></section>")

    for group in (ladder.get("targets") or {}).get("groups", []):
        gid = re.sub(r"[^a-z0-9]+", "-", group["title"].lower()).strip("-")
        out.append(f'<section aria-labelledby="{gid}"><h3 id="{gid}">{html.escape(group["title"])}</h3>')
        if group.get("note"):
            out.append(f"<p>{_h(group['note'])}</p>")
        out.append(
            '<div class="table-wrap"><table><thead><tr><th>Measure</th><th>Baseline</th>'
            "<th>Target</th><th>Gate</th></tr></thead><tbody>"
        )
        for row in group["rows"]:
            out.append(
                f'<tr><td>{_h(row["measure"])}</td><td class="num">{_h(row["baseline"])}</td>'
                f'<td class="num">{_h(row["target"])}</td><td class="num">{_h(row["rung"])}</td></tr>'
            )
        out.append("</tbody></table></div></section>")

    out.append('<section aria-labelledby="rules-h"><h3 id="rules-h">Rules</h3><ul class="rules">')
    out.extend(f"<li>{_h(rule)}</li>" for rule in ladder["rules"])
    out.append("</ul></section>")

    for r in rungs:
        cls = "rung is-current" if r["status"] == "current" else "rung"
        out.append(f'<article class="{cls}" id="{html.escape(r["id"].lower())}" data-status="{r["status"]}">')
        deps = ", ".join(r["depends_on"]) or "none"
        out.append(
            f'<div class="rung-head"><h2><span class="rid">{html.escape(r["id"])}</span>{_h(r["title"])}</h2>'
            f'<span class="chip s-{r["status"]}">{STATUS_LABEL[r["status"]]}</span></div>'
        )
        out.append(f'<div class="deps">depends on: {html.escape(deps)}</div>')
        out.append(f"<p>{_h(r['outcome'])}</p>")
        if r["decision"]:
            out.append(f'<div class="decision"><strong>Owner decision:</strong> {_h(r["decision"])}</div>')
        out.append('<div class="cols">')
        for key, heading, css in (
            ("exit_gates", "Exit gates", "gates"),
            ("tasks", "Tasks", ""),
            ("blockers", "Blockers", ""),
            ("steps", "Steps", ""),
            ("evidence_refs", "Evidence", ""),
        ):
            if r[key]:
                items = (
                    "".join(f"<li><code>{html.escape(v)}</code></li>" for v in r[key])
                    if key == "evidence_refs"
                    else "".join(f"<li>{_h(v)}</li>" for v in r[key])
                )
                cls_attr = f' class="{css}"' if css else ""
                out.append(f"<div><h3>{heading}</h3><ul{cls_attr}>{items}</ul></div>")
        out.append("</div></article>")

    out.append(
        "<footer>Generated from <code>state/delivery-ladder.json</code> by "
        "<code>scripts/ladder_check.py --write</code>. The JSON is the source of truth; "
        "evidence lives in <code>evidence/</code>.</footer>"
    )
    out.append("</main>")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- orchestration


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_ladder(root: Path) -> Any:
    return json.loads((root / LADDER_PATH).read_text(encoding="utf-8"))


def check(root: Path) -> list[str]:
    try:
        ladder = load_ladder(root)
    except FileNotFoundError:
        return [f"ladder: {LADDER_PATH} not found"]
    except json.JSONDecodeError as exc:
        return [f"ladder: invalid JSON ({exc})"]
    errors = validate(ladder, root)
    if errors:
        return errors
    md, page = render_markdown(ladder), render_html(ladder)
    for path, expected in ((MD_PATH, md), (HTML_PATH, page)):
        target = root / path
        if not target.is_file():
            errors.append(f"view: {path} missing; run --write")
        elif target.read_text(encoding="utf-8") != expected:
            errors.append(f"view: {path} differs from the ladder JSON; run --write")
    record_path = root / ARTIFACT_PATH
    if record_path.is_file():  # publishing is optional; once recorded, it must stay current
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if record.get("published_html_sha256") != sha256_text(page):
            errors.append(
                "artifact: the published page is stale; republish "
                f"{HTML_PATH} to {record.get('url')} and run --record-artifact"
            )
    return errors


def write_views(root: Path) -> list[str]:
    ladder = load_ladder(root)
    errors = validate(ladder, root)
    if errors:
        return errors
    (root / MD_PATH).write_text(render_markdown(ladder), encoding="utf-8")
    (root / HTML_PATH).write_text(render_html(ladder), encoding="utf-8")
    return []


def record_artifact(root: Path, url: str) -> list[str]:
    if not re.match(r"^https://claude\.ai/(code/)?artifact/[A-Za-z0-9-]+$", url):
        return [f"artifact: {url!r} is not a claude.ai artifact URL"]
    page = (root / HTML_PATH).read_text(encoding="utf-8")
    ladder = load_ladder(root)
    if page != render_html(ladder):
        return [f"artifact: {HTML_PATH} is stale; run --write and republish before recording"]
    record = {
        "url": url,
        "published_html_sha256": sha256_text(page),
        "published_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "ladder_revision": ladder["cursor_revision"],
    }
    (root / ARTIFACT_PATH).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Delivery-ladder gate for the primitrace programme.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="re-render DELIVERY-LADDER.md and .html")
    mode.add_argument("--record-artifact", metavar="URL", help="record the digest of the published page")
    args = parser.parse_args(argv)

    if args.write:
        errors = write_views(args.root)
        ok_message = f"ladder: rendered {MD_PATH} and {HTML_PATH}"
    elif args.record_artifact:
        errors = record_artifact(args.root, args.record_artifact)
        ok_message = f"ladder: recorded artifact digest in {ARTIFACT_PATH}"
    else:
        errors = check(args.root)
        ok_message = "ladder: OK"
    if errors:
        for error in errors:
            print(f"ladder-check: {error}", file=sys.stderr)
        return 1
    print(ok_message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
