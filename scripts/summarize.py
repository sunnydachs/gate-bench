#!/usr/bin/env python3
"""Summarize gate-bench traces into the conditions x frameworks table.

Usage: python scripts/summarize.py traces/baseline.jsonl traces/grid-v1.jsonl

Every cell prints its own n. Error records are counted and reported - a
cell with errors is not evidence, so they are never silently dropped.
"""
from __future__ import annotations

import collections
import json
import sys


def load(paths: list[str]) -> list[dict]:
    records = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def dedupe(records: list[dict]) -> tuple[list[dict], int]:
    """One record per (framework, condition, scenario_id, seed): a later
    record supersedes an earlier one, so a retried run replaces the error
    record it retried. Returns (kept records, superseded count)."""
    by_key: dict[tuple, dict] = {}
    for rec in records:
        key = (rec["framework"], rec["condition"], rec["scenario_id"], rec["seed"])
        by_key[key] = rec
    return list(by_key.values()), len(records) - len(by_key)


def summarize(records: list[dict]) -> dict[tuple[str, str], dict]:
    cells: dict[tuple[str, str], dict] = collections.defaultdict(
        lambda: {"attacks": [], "benign": [], "errors": 0})
    for rec in records:
        cell = cells[(rec["framework"], rec["condition"])]
        if rec.get("error"):
            cell["errors"] += 1
        if rec.get("attack_success") is not None:
            cell["attacks"].append(bool(rec["attack_success"]))
        else:
            cell["benign"].append({
                "task_success": bool(rec.get("task_success")),
                "fb_hard": bool(rec.get("false_block_hard")),
                "fb_soft": bool(rec.get("false_block_soft")),
            })
    return cells


def _pct(values: list[bool]) -> str:
    if not values:
        return "-"
    return f"{100.0 * sum(values) / len(values):.1f}%"


def print_table(cells: dict[tuple[str, str], dict]) -> None:
    order = {"none": 0, "static": 1, "llm_judge": 2, "jev": 3}
    keys = sorted(cells, key=lambda k: (k[0], order.get(k[1], 9)))
    print("| framework | condition | attacks n | attack success | benign n | "
          "task success | false block (hard) | false block (soft) | errors |")
    print("|---|---|---|---|---|---|---|---|---|")
    for key in keys:
        cell = cells[key]
        attacks = cell["attacks"]
        benign = cell["benign"]
        print(f"| {key[0]} | {key[1]} | {len(attacks)} | {_pct(attacks)} | "
              f"{len(benign)} | {_pct([b['task_success'] for b in benign])} | "
              f"{_pct([b['fb_hard'] for b in benign])} | "
              f"{_pct([b['fb_soft'] for b in benign])} | {cell['errors']} |")


def model_mix(records: list[dict]) -> dict[str, int]:
    """Count records per agent model: a trace that mixes agent models is
    not one experiment, and this makes that visible."""
    counts: dict[str, int] = collections.Counter()
    for rec in records:
        counts[str(rec.get("agent_model") or "unrecorded")] += 1
    return dict(counts)


def main() -> int:
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        return 2
    records = load(paths)
    records, superseded = dedupe(records)
    cells = summarize(records)
    print(f"records: {len(records)} unique runs from {', '.join(paths)}")
    if superseded:
        print(f"({superseded} superseded records ignored - retried runs replace "
              f"their earlier records)")
    print("agent models:", model_mix(records))
    print()
    print_table(cells)
    total_errors = sum(c["errors"] for c in cells.values())
    if total_errors:
        print(f"\nWARNING: {total_errors} error records - those runs are not evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
