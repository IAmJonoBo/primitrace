"""The corpus manifest fails closed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from primitrace import corpus


def _setup(tmp_path: Path, entries: list[dict], files: dict[str, bytes]) -> tuple[str, str]:
    cache = tmp_path / "cache"
    cache.mkdir()
    for name, data in files.items():
        (cache / name).write_bytes(data)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": 1, "entries": entries}))
    return str(manifest), str(cache)


def _entry(name: str, data: bytes, **over: object) -> dict:
    e = {"path": name, "source": "https://example.org/a.svg", "licence": "CC0-1.0",
         "sha256": hashlib.sha256(data).hexdigest(), "redistribute": False}  # fmt: skip
    e.update(over)
    return e


def test_a_recorded_licensed_file_passes(tmp_path: Path) -> None:
    m, c = _setup(tmp_path, [_entry("a.svg", b"x")], {"a.svg": b"x"})
    assert [e.path for e in corpus.check(m, c)] == ["a.svg"]


@pytest.mark.parametrize(
    ("entries", "files", "needle"),
    [
        ([], {"a.svg": b"x"}, "not in the manifest"),
        ([_entry("a.svg", b"x")], {}, "not in the cache"),
        ([_entry("a.svg", b"x")], {"a.svg": b"y"}, "sha256"),
        ([_entry("a.svg", b"x", licence="CC-BY-NC-4.0")], {"a.svg": b"x"}, "not allowed"),
        ([_entry("a.svg", b"x", redistribute=True)], {"a.svg": b"x"}, "redistribute"),
    ],
)
def test_anything_unrecorded_or_changed_fails(tmp_path: Path, entries: list, files: dict, needle: str) -> None:
    m, c = _setup(tmp_path, entries, files)
    with pytest.raises(corpus.CorpusError, match=needle):
        corpus.check(m, c)


def test_the_committed_manifest_is_valid() -> None:
    root = Path(__file__).resolve().parents[1] / "corpus"
    assert corpus.load(str(root / "manifest.json")) == []
