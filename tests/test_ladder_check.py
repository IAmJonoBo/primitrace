"""Delivery-ladder gate: scripts/ladder_check.py refuses stale or malformed ladders."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("ladder_check", ROOT / "scripts" / "ladder_check.py")
assert _SPEC and _SPEC.loader
ladder_check = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ladder_check)


def _rung(rid: str, status: str, depends_on: list[str] | None = None, **extra) -> dict:
    rung = {
        "id": rid,
        "title": f"Rung {rid}",
        "status": status,
        "outcome": "An outcome.",
        "tasks": ["Do the thing."],
        "blockers": [],
        "depends_on": depends_on or [],
        "decision": None,
        "steps": [],
        "evidence_refs": [],
        "exit_gates": ["The thing is done."],
    }
    rung.update(extra)
    return rung


def _ladder() -> dict:
    return {
        "schema_version": "cm-delivery-ladder.v1",
        "programme_id": "test-programme",
        "cursor_revision": 1,
        "updated_at": "2026-09-30T00:00:00Z",
        "rules": ["One rule."],
        "rungs": [
            _rung("L0", "done", evidence_refs=["evidence/L0.json"]),
            _rung("L1", "current", ["L0"]),
            _rung("L2", "queued", ["L1"]),
            _rung("L3", "reserved", ["L1"], decision="Owner picks a model."),
        ],
    }


class LadderCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "evidence").mkdir()
        (self.root / "evidence" / "L0.json").write_text("{}", encoding="utf-8")
        (self.root / "state").mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, ladder: dict) -> None:
        (self.root / "state" / "delivery-ladder.json").write_text(json.dumps(ladder), encoding="utf-8")

    def _errors(self, ladder: dict) -> list[str]:
        return ladder_check.validate(ladder, self.root)

    def _publish(self) -> None:
        self.assertEqual(ladder_check.write_views(self.root), [])
        self.assertEqual(ladder_check.record_artifact(self.root, "https://claude.ai/artifact/abc123"), [])

    def test_valid_ladder_passes_full_check(self) -> None:
        self._write(_ladder())
        self._publish()
        self.assertEqual(ladder_check.check(self.root), [])

    def test_repository_ladder_is_valid(self) -> None:
        ladder = json.loads((ROOT / "state" / "delivery-ladder.json").read_text(encoding="utf-8"))
        self.assertEqual(ladder_check.validate(ladder, ROOT), [])

    def test_two_current_rungs_refused(self) -> None:
        ladder = _ladder()
        ladder["rungs"][2]["status"] = "current"
        self.assertTrue(any("exactly one rung must be current" in e for e in self._errors(ladder)))

    def test_no_current_rung_refused(self) -> None:
        ladder = _ladder()
        ladder["rungs"][1]["status"] = "next"
        self.assertTrue(any("exactly one rung must be current" in e for e in self._errors(ladder)))

    def test_current_with_open_dependency_refused(self) -> None:
        ladder = _ladder()
        ladder["rungs"][0]["status"] = "queued"
        self.assertTrue(any("dependencies not done" in e for e in self._errors(ladder)))

    def test_done_without_evidence_refused(self) -> None:
        ladder = _ladder()
        ladder["rungs"][0]["evidence_refs"] = []
        self.assertTrue(any("cites no evidence" in e for e in self._errors(ladder)))

    def test_missing_evidence_file_refused(self) -> None:
        ladder = _ladder()
        ladder["rungs"][0]["evidence_refs"] = ["evidence/absent.json"]
        self.assertTrue(any("evidence file missing" in e for e in self._errors(ladder)))

    def test_reserved_without_decision_refused(self) -> None:
        ladder = _ladder()
        ladder["rungs"][3]["decision"] = None
        self.assertTrue(any("names no decision" in e for e in self._errors(ladder)))

    def test_blocked_without_blocker_refused(self) -> None:
        ladder = _ladder()
        ladder["rungs"][2]["status"] = "blocked"
        self.assertTrue(any("no live blocker" in e for e in self._errors(ladder)))

    def test_blockers_on_unblocked_rung_refused(self) -> None:
        ladder = _ladder()
        ladder["rungs"][2]["blockers"] = ["Upstream outage."]
        self.assertTrue(any("mark it blocked" in e for e in self._errors(ladder)))

    def test_unknown_status_refused(self) -> None:
        ladder = _ladder()
        ladder["rungs"][2]["status"] = "in-progress"
        self.assertTrue(any("unknown status" in e for e in self._errors(ladder)))

    def test_open_rung_without_gates_refused(self) -> None:
        ladder = _ladder()
        ladder["rungs"][2]["exit_gates"] = []
        self.assertTrue(any("no exit gates" in e for e in self._errors(ladder)))

    def test_forward_or_unknown_dependency_refused(self) -> None:
        ladder = _ladder()
        ladder["rungs"][1]["depends_on"] = ["L0", "L2"]
        ladder["rungs"][2]["depends_on"] = ["L9"]
        errors = self._errors(ladder)
        self.assertTrue(any("not earlier in the ladder" in e for e in errors))
        self.assertTrue(any("unknown rung L9" in e for e in errors))

    def test_duplicate_ids_and_missing_keys_refused(self) -> None:
        ladder = _ladder()
        ladder["rungs"][2]["id"] = "L1"
        self.assertTrue(any("duplicate rung id" in e for e in self._errors(ladder)))
        broken = _ladder()
        del broken["rungs"][2]["exit_gates"]
        self.assertTrue(any("missing keys" in e for e in self._errors(broken)))

    def test_wrong_schema_version_refused(self) -> None:
        ladder = _ladder()
        ladder["schema_version"] = "v0"
        self.assertTrue(any("schema_version" in e for e in self._errors(ladder)))

    def test_view_drift_refused(self) -> None:
        self._write(_ladder())
        self._publish()
        (self.root / "DELIVERY-LADDER.md").write_text("hand edited\n", encoding="utf-8")
        self.assertTrue(any("DELIVERY-LADDER.md differs" in e for e in ladder_check.check(self.root)))

    def test_unpublished_change_refused(self) -> None:
        ladder = _ladder()
        self._write(ladder)
        self._publish()
        changed = copy.deepcopy(ladder)
        changed["rungs"][2]["title"] = "Renamed rung"
        self._write(changed)
        self.assertEqual(ladder_check.write_views(self.root), [])
        self.assertTrue(any("published page is stale" in e for e in ladder_check.check(self.root)))

    def test_absent_artifact_record_is_allowed(self) -> None:
        self._write(_ladder())
        self.assertEqual(ladder_check.write_views(self.root), [])
        self.assertEqual(ladder_check.check(self.root), [])

    def test_record_refuses_non_artifact_url_and_stale_page(self) -> None:
        self._write(_ladder())
        self.assertEqual(ladder_check.write_views(self.root), [])
        self.assertTrue(ladder_check.record_artifact(self.root, "https://example.com/x"))
        changed = _ladder()
        changed["rungs"][2]["title"] = "Changed"
        self._write(changed)
        self.assertTrue(
            any("stale" in e for e in ladder_check.record_artifact(self.root, "https://claude.ai/artifact/abc123"))
        )

    def test_html_escapes_content(self) -> None:
        ladder = _ladder()
        ladder["rungs"][2]["title"] = "<script>alert(1)</script> and `code`"
        page = ladder_check.render_html(ladder)
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("<code>code</code>", page)


if __name__ == "__main__":
    unittest.main()
