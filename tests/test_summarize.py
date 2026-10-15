"""Tests for the trace summarizer's dedupe/aggregate logic."""
import importlib.util
import pathlib

_SPEC = importlib.util.spec_from_file_location(
    "summarize", pathlib.Path(__file__).resolve().parent.parent / "scripts" / "summarize.py")
summarize_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(summarize_mod)


def _record(framework="strands", condition="none", scenario_id="A1", seed=1,
            attack=True, success=False, error=None):
    return {
        "framework": framework, "condition": condition,
        "scenario_id": scenario_id, "seed": seed,
        "attack_success": success if attack else None,
        "task_success": None if attack else success,
        "false_block_hard": None if attack else False,
        "false_block_soft": None if attack else False,
        "error": error,
    }


def test_dedupe_last_record_wins():
    rows = [_record(error="429"), _record(success=True)]
    kept, superseded = summarize_mod.dedupe(rows)
    assert superseded == 1
    assert len(kept) == 1 and kept[0]["attack_success"] is True


def test_dedupe_keeps_distinct_keys():
    rows = [_record(scenario_id="A1"), _record(scenario_id="A2"),
            _record(condition="static")]
    kept, superseded = summarize_mod.dedupe(rows)
    assert superseded == 0 and len(kept) == 3


def test_summarize_counts_attacks_and_only_keeps_errors():
    rows = [_record(success=True), _record(scenario_id="A2", success=False),
            _record(scenario_id="A3", error="boom")]
    cells = summarize_mod.summarize(rows)
    cell = cells[("strands", "none")]
    assert len(cell["attacks"]) == 3
    assert sum(cell["attacks"]) == 1
    assert cell["errors"] == 1


def test_summarize_separates_benign_metrics():
    rows = [_record(scenario_id="N1", attack=False, success=True),
            _record(scenario_id="N2", attack=False, success=False)]
    cells = summarize_mod.summarize(rows)
    cell = cells[("strands", "none")]
    assert cell["attacks"] == []
    assert len(cell["benign"]) == 2
    assert sum(b["task_success"] for b in cell["benign"]) == 1
