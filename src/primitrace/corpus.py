"""The corpus licence manifest, checked fail-closed.

Real images are cached locally (``corpus/cache/``, ignored by git) and are never redistributed.
Every cached file must be recorded in ``corpus/manifest.json`` with its source, an allowed
licence, its sha256 and ``"redistribute": false``. ``check`` refuses a run when anything does not
match. An unrecorded file is an error, not a warning.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

ALLOWED_LICENCES = frozenset({"CC0-1.0", "PD", "PD-textlogo", "PD-shape", "OFL-1.1", "synthetic"})
REQUIRED = ("path", "source", "licence", "sha256", "redistribute")


class CorpusError(Exception):
    """The corpus does not match its manifest; nothing may run on it."""


@dataclass(frozen=True)
class Entry:
    path: str  # relative to the cache directory
    source: str  # URL or generator id
    licence: str
    sha256: str
    redistribute: bool


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(manifest_path: str) -> list[Entry]:
    with open(manifest_path, encoding="utf-8") as fh:
        doc = json.load(fh)
    if doc.get("version") != 1 or not isinstance(doc.get("entries"), list):
        raise CorpusError(f"{manifest_path}: expected version 1 with an entries list")
    entries = []
    for i, raw in enumerate(doc["entries"]):
        missing = [k for k in REQUIRED if k not in raw]
        if missing:
            raise CorpusError(f"entry {i}: missing {', '.join(missing)}")
        entries.append(Entry(**{k: raw[k] for k in REQUIRED}))
    return entries


def check(manifest_path: str, cache_dir: str) -> list[Entry]:
    """The manifest's entries, once every cached file is recorded, licensed and unchanged."""
    entries = load(manifest_path)
    problems = []
    by_path = {}
    for e in entries:
        if e.path in by_path:
            problems.append(f"{e.path}: recorded twice")
        by_path[e.path] = e
        if e.licence not in ALLOWED_LICENCES:
            problems.append(f"{e.path}: licence {e.licence!r} is not allowed")
        if e.redistribute is not False:
            problems.append(f"{e.path}: redistribute must be false")
        full = os.path.join(cache_dir, e.path)
        if not os.path.isfile(full):
            problems.append(f"{e.path}: recorded but not in the cache")
        elif _sha256(full) != e.sha256:
            problems.append(f"{e.path}: sha256 does not match the manifest")
    if os.path.isdir(cache_dir):
        for root, _dirs, files in os.walk(cache_dir):
            for name in files:
                rel = os.path.relpath(os.path.join(root, name), cache_dir)
                if rel not in by_path and not name.startswith("."):
                    problems.append(f"{rel}: in the cache but not in the manifest")
    if problems:
        raise CorpusError("corpus check failed:\n  " + "\n  ".join(sorted(problems)))
    return entries
