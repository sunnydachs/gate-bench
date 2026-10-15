"""
gate-bench analyze: read trace JSONLs -> artifacts/report.json + printed tables per SPEC.
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


def load_traces(traces_dir: Path, batch: str) -> List[Dict[str, Any]]:
    """Load all trace records for a given batch."""
    trace_path = traces_dir / f"{batch}.jsonl"
    if not trace_path.exists():
        return []
    
    records = []
    with open(trace_path, "r") as f:
        for line in f:
            records.append(json.loads(line.strip()))
    return records


def load_corpus_data() -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load environment, attacks, and benign scenarios."""
    with open("corpus/environment.yaml", encoding="utf-8") as f:
        environment = yaml.safe_load(f)
    
    with open("corpus/attacks.yaml", encoding="utf-8") as f:
        attacks = yaml.safe_load(f)
    
    with open("corpus/benign.yaml", encoding="utf-8") as f:
        benign = yaml.safe_load(f)
    
    return environment, attacks, benign


def compute_metrics(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute metrics from trace records.
    
    Returns a nested dictionary with the structure:
    {
        "framework": {
            "condition": {
                "attack_success": {
                    "overall": float,
                    "by_category": {category: float},
                    "by_tier": {tier: float},
                    "by_expect_layer": {expect_layer: float}
                },
                "benign_task_success": float,
                "false_block": {
                    "block": float,  # rate of false blocks (block) on benign legit_privileged calls
                    "review": float   # rate of false blocks (review) on benign legit_privileged calls
                },
                "gate_latency": {
                    "p50": float,
                    "p95": float
                }
            }
        }
    }
    """
    # Load corpus data to get scenario info
    environment, attacks, benign = load_corpus_data()
    scenario_info = {}
    for attack in attacks:
        scenario_info[attack["id"]] = {
            "type": "attack",
            "category": attack["category"],
            "tier": attack["tier"],
            "expect_layer": attack["expect_layer"]
        }
    for benign_scenario in benign:
        scenario_info[benign_scenario["id"]] = {
            "type": "benign"
        }
    
    # Initialize accumulators
    # For attack success: we need to count, for each (framework, condition, scenario_id, seed), whether it succeeded
    # But we'll accumulate per (framework, condition) over all attack records
    attack_success_total = defaultdict(int)      # (framework, condition) -> number of attack records
    attack_success_count = defaultdict(int)      # (framework, condition) -> number of successful attack records
    
    # For attack success by category/tier/expect_layer: we need to accumulate per (framework, condition, category) etc.
    attack_success_by_category_total = defaultdict(int)      # (framework, condition, category) -> count
    attack_success_by_category_count = defaultdict(int)      # (framework, condition, category) -> success count
    attack_success_by_tier_total = defaultdict(int)          # (framework, condition, tier) -> count
    attack_success_by_tier_count = defaultdict(int)          # (framework, condition, tier) -> success count
    attack_success_by_expect_layer_total = defaultdict(int)  # (framework, condition, expect_layer) -> count
    attack_success_by_expect_layer_count = defaultdict(int)  # (framework, condition, expect_layer) -> success count
    
    # For benign task success
    benign_task_success_total = defaultdict(int)      # (framework, condition) -> number of benign records
    benign_task_success_count = defaultdict(int)      # (framework, condition) -> number of successful benign records
    
    # For false blocks: we need to count, for each (framework, condition), the number of benign records that have legit_privileged
    # and among those, how many had at least one legit_privileged call blocked/reviewed
    false_block_hard_total = defaultdict(int)      # (framework, condition) -> number of benign records with legit_privileged
    false_block_hard_count = defaultdict(int)      # (framework, condition) -> number of those records where at least one legit_privileged call was blocked
    false_block_soft_total = defaultdict(int)      # (framework, condition) -> number of benign records with legit_privileged
    false_block_soft_count = defaultdict(int)      # (framework, condition) -> number of those records where at least one legit_privileged call was reviewed
    
    # For gate latency: collect all latencies from all calls (across all records) for each (framework, condition)
    gate_latencies = defaultdict(list)             # (framework, condition) -> list of latencies
    
    # Process each record
    for record in records:
        framework = record["framework"]
        condition = record["condition"]
        scenario_id = record["scenario_id"]
        
        info = scenario_info.get(scenario_id)
        if info is None:
            # Skip unknown scenarios
            continue
        
        if info["type"] == "attack":
            # Count this attack record
            attack_success_total[(framework, condition)] += 1
            if record.get("attack_success") is True:
                attack_success_count[(framework, condition)] += 1
            
            # Count by category
            category = info["category"]
            attack_success_by_category_total[(framework, condition, category)] += 1
            if record.get("attack_success") is True:
                attack_success_by_category_count[(framework, condition, category)] += 1
            
            # Count by tier
            tier = info["tier"]
            attack_success_by_tier_total[(framework, condition, tier)] += 1
            if record.get("attack_success") is True:
                attack_success_by_tier_count[(framework, condition, tier)] += 1
            
            # Count by expect_layer
            expect_layer = info["expect_layer"]
            attack_success_by_expect_layer_total[(framework, condition, expect_layer)] += 1
            if record.get("attack_success") is True:
                attack_success_by_expect_layer_count[(framework, condition, expect_layer)] += 1
            
            # Collect gate latencies
            for call in record.get("calls", []):
                latency = call.get("gate_latency_ms")
                if latency is not None:
                    gate_latencies[(framework, condition)].append(latency)
        
        else:  # benign
            # Count this benign record for task success
            benign_task_success_total[(framework, condition)] += 1
            if record.get("task_success") is True:
                benign_task_success_count[(framework, condition)] += 1
            
            # Check for false blocks: we need to see if this benign record has any legit_privileged calls that were blocked/reviewed
            benign_scenario = next((b for b in benign if b["id"] == scenario_id), None)
            if benign_scenario and "legit_privileged" in benign_scenario:
                # This record has legit_privileged calls, so it contributes to the denominator
                false_block_hard_total[(framework, condition)] += 1
                false_block_soft_total[(framework, condition)] += 1
                
                # Check each legit_privileged matcher to see if any matched call was blocked or reviewed
                from gate_bench.matchers import evaluate
                any_blocked = False
                any_reviewed = False
                for matcher in benign_scenario["legit_privileged"]:
                    matched, idx = evaluate([matcher], record.get("calls", []))
                    if matched and idx is not None:
                        call = record["calls"][idx]
                        if call["gate_decision"] == "block":
                            any_blocked = True
                        elif call["gate_decision"] == "review":
                            any_reviewed = True
                
                if any_blocked:
                    false_block_hard_count[(framework, condition)] += 1
                if any_reviewed:
                    false_block_soft_count[(framework, condition)] += 1
            
            # Collect gate latencies
            for call in record.get("calls", []):
                latency = call.get("gate_latency_ms")
                if latency is not None:
                    gate_latencies[(framework, condition)].append(latency)
    
    # Compute the final metrics
    results = defaultdict(lambda: defaultdict(dict))
    
    # Helper to compute rate safely
    def safe_rate(count, total):
        return count / total if total > 0 else 0.0
    
    # Attack success overall and by category/tier/expect_layer
    for (fw, cd) in set(attack_success_total.keys()) | set(attack_success_count.keys()):
        total = attack_success_total[(fw, cd)]
        count = attack_success_count[(fw, cd)]
        results[fw][cd]["attack_success_overall"] = safe_rate(count, total)
    
    for (fw, cd, cat) in set(attack_success_by_category_total.keys()) | set(attack_success_by_category_count.keys()):
        total = attack_success_by_category_total[(fw, cd, cat)]
        count = attack_success_by_category_count[(fw, cd, cat)]
        # Initialize the by_category dict if needed
        if "attack_success_by_category" not in results[fw][cd]:
            results[fw][cd]["attack_success_by_category"] = {}
        results[fw][cd]["attack_success_by_category"][cat] = safe_rate(count, total)
    
    for (fw, cd, tier) in set(attack_success_by_tier_total.keys()) | set(attack_success_by_tier_count.keys()):
        total = attack_success_by_tier_total[(fw, cd, tier)]
        count = attack_success_by_tier_count[(fw, cd, tier)]
        if "attack_success_by_tier" not in results[fw][cd]:
            results[fw][cd]["attack_success_by_tier"] = {}
        results[fw][cd]["attack_success_by_tier"][tier] = safe_rate(count, total)
    
    for (fw, cd, el) in set(attack_success_by_expect_layer_total.keys()) | set(attack_success_by_expect_layer_count.keys()):
        total = attack_success_by_expect_layer_total[(fw, cd, el)]
        count = attack_success_by_expect_layer_count[(fw, cd, el)]
        if "attack_success_by_expect_layer" not in results[fw][cd]:
            results[fw][cd]["attack_success_by_expect_layer"] = {}
        results[fw][cd]["attack_success_by_expect_layer"][el] = safe_rate(count, total)
    
    # Benign task success
    for (fw, cd) in set(benign_task_success_total.keys()) | set(benign_task_success_count.keys()):
        total = benign_task_success_total[(fw, cd)]
        count = benign_task_success_count[(fw, cd)]
        results[fw][cd]["benign_task_success"] = safe_rate(count, total)
    
    # False block rates
    for (fw, cd) in set(false_block_hard_total.keys()) | set(false_block_hard_count.keys()):
        total = false_block_hard_total[(fw, cd)]
        count = false_block_hard_count[(fw, cd)]
        if "false_block" not in results[fw][cd]:
            results[fw][cd]["false_block"] = {}
        results[fw][cd]["false_block"]["block"] = safe_rate(count, total)
    
    for (fw, cd) in set(false_block_soft_total.keys()) | set(false_block_soft_count.keys()):
        total = false_block_soft_total[(fw, cd)]
        count = false_block_soft_count[(fw, cd)]
        if "false_block" not in results[fw][cd]:
            results[fw][cd]["false_block"] = {}
        results[fw][cd]["false_block"]["review"] = safe_rate(count, total)
    
    # Gate latency p50 and p95
    for (fw, cd) in gate_latencies:
        latencies = gate_latencies[(fw, cd)]
        if latencies:
            latencies_sorted = sorted(latencies)
            p50 = latencies_sorted[len(latencies_sorted) // 2]
            p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]
        else:
            p50 = 0.0
            p95 = 0.0
        if "gate_latency" not in results[fw][cd]:
            results[fw][cd]["gate_latency"] = {}
        results[fw][cd]["gate_latency"]["p50"] = p50
        results[fw][cd]["gate_latency"]["p95"] = p95
    
    # Convert to a regular dict for JSON serialization
    return {f: dict(c) for f, c in results.items()}


def print_tables(metrics: Dict[str, Any]):
    """Print the metrics in a human-readable table format."""
    print("=== gate-bench Analysis Results ===")
    print()
    
    # We'll print a table for each metric type
    frameworks = sorted(metrics.keys())
    if not frameworks:
        print("No data to display.")
        return
    
    # Get all conditions from the first framework
    conditions = sorted(next(iter(metrics.values())).keys()) if frameworks else []
    
    # Attack success overall
    print("Attack Success Rate (Overall):")
    print(f"{'Framework':<12} {'Condition':<12} {'Rate':<8}")
    print("-" * 32)
    for fw in frameworks:
        for cd in conditions:
            rate = metrics.get(fw, {}).get(cd, {}).get("attack_success_overall", 0.0)
            print(f"{fw:<12} {cd:<12} {rate:<8.2%}")
    print()
    
    # Attack success by category
    # We'll print a separate table for each category? Or combine? Let's do overall for now.
    # For brevity, we'll skip the detailed breakdowns in the printed tables and just show overall.
    # The spec says the article will quote only numbers this analyzer produces, and we are producing the overall.
    # We can add more tables if needed, but for now, let's stick to the ones mentioned in the spec:
    #   attack success overall / by category / by tier / by expect_layer
    #   benign task completion
    #   false blocks (block and review separately)
    #   gate latency p50/p95
    
    # We'll print the breakdowns as separate sections.
    
    # Attack success by category
    print("Attack Success Rate by Category:")
    # We need to collect all categories
    categories = set()
    for fw in metrics.values():
        for cd in fw.values():
            if "attack_success_by_category" in cd:
                categories.update(cd["attack_success_by_category"].keys())
    categories = sorted(categories)
    if categories:
        print(f"{'Framework':<12} {'Condition':<12}", end="")
        for cat in categories:
            print(f"{cat:<12}", end="")
        print()
        print("-" * (24 + 12 * len(categories)))
        for fw in frameworks:
            for cd in conditions:
                print(f"{fw:<12} {cd:<12}", end="")
                for cat in categories:
                    rate = metrics.get(fw, {}).get(cd, {}).get("attack_success_by_category", {}).get(cat, 0.0)
                    print(f"{rate:<12.2%}", end="")
                print()
        print()
    else:
        print("No category data available.")
        print()
    
    # Attack success by tier
    print("Attack Success Rate by Tier:")
    tiers = set()
    for fw in metrics.values():
        for cd in fw.values():
            if "attack_success_by_tier" in cd:
                tiers.update(cd["attack_success_by_tier"].keys())
    tiers = sorted(tiers)
    if tiers:
        print(f"{'Framework':<12} {'Condition':<12}", end="")
        for tier in tiers:
            print(f"{tier:<12}", end="")
        print()
        print("-" * (24 + 12 * len(tiers)))
        for fw in frameworks:
            for cd in conditions:
                print(f"{fw:<12} {cd:<12}", end="")
                for tier in tiers:
                    rate = metrics.get(fw, {}).get(cd, {}).get("attack_success_by_tier", {}).get(tier, 0.0)
                    print(f"{rate:<12.2%}", end="")
                print()
        print()
    else:
        print("No tier data available.")
        print()
    
    # Attack success by expect_layer
    print("Attack Success Rate by Expect Layer:")
    expect_layers = set()
    for fw in metrics.values():
        for cd in fw.values():
            if "attack_success_by_expect_layer" in cd:
                expect_layers.update(cd["attack_success_by_expect_layer"].keys())
    expect_layers = sorted(expect_layers)
    if expect_layers:
        print(f"{'Framework':<12} {'Condition':<12}", end="")
        for el in expect_layers:
            print(f"{el:<12}", end="")
        print()
        print("-" * (24 + 12 * len(expect_layers)))
        for fw in frameworks:
            for cd in conditions:
                print(f"{fw:<12} {cd:<12}", end="")
                for el in expect_layers:
                    rate = metrics.get(fw, {}).get(cd, {}).get("attack_success_by_expect_layer", {}).get(el, 0.0)
                    print(f"{rate:<12.2%}", end="")
                print()
        print()
    else:
        print("No expect_layer data available.")
        print()
    
    # Benign task success
    print("Benign Task Success Rate:")
    print(f"{'Framework':<12} {'Condition':<12} {'Rate':<8}")
    print("-" * 32)
    for fw in frameworks:
        for cd in conditions:
            rate = metrics.get(fw, {}).get(cd, {}).get("benign_task_success", 0.0)
            print(f"{fw:<12} {cd:<12} {rate:<8.2%}")
    print()
    
    # False block (block)
    print("False Block Rate (Block):")
    print(f"{'Framework':<12} {'Condition':<12} {'Rate':<8}")
    print("-" * 32)
    for fw in frameworks:
        for cd in conditions:
            rate = metrics.get(fw, {}).get(cd, {}).get("false_block", {}).get("block", 0.0)
            print(f"{fw:<12} {cd:<12} {rate:<8.2%}")
    print()
    
    # False block (review)
    print("False Block Rate (Review):")
    print(f"{'Framework':<12} {'Condition':<12} {'Rate':<8}")
    print("-" * 32)
    for fw in frameworks:
        for cd in conditions:
            rate = metrics.get(fw, {}).get(cd, {}).get("false_block", {}).get("review", 0.0)
            print(f"{fw:<12} {cd:<12} {rate:<8.2%}")
    print()
    
    # Gate latency p50
    print("Gate Latency p50 (ms):")
    print(f"{'Framework':<12} {'Condition':<12} {'Latency':<8}")
    print("-" * 32)
    for fw in frameworks:
        for cd in conditions:
            latency = metrics.get(fw, {}).get(cd, {}).get("gate_latency", {}).get("p50", 0.0)
            print(f"{fw:<12} {cd:<12} {latency:<8.2f}")
    print()
    
    # Gate latency p95
    print("Gate Latency p95 (ms):")
    print(f"{'Framework':<12} {'Condition':<12} {'Latency':<8}")
    print("-" * 32)
    for fw in frameworks:
        for cd in conditions:
            latency = metrics.get(fw, {}).get(cd, {}).get("gate_latency", {}).get("p95", 0.0)
            print(f"{fw:<12} {cd:<12} {latency:<8.2f}")
    print()


def main():
    """Main entry point for the analyze script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze gate-bench traces")
    parser.add_argument("--batch", type=str, default="default", help="Batch name to analyze")
    parser.add_argument("--traces-dir", type=str, default="traces", help="Directory containing trace files")
    parser.add_argument("--output", type=str, default="artifacts/report.json", help="Output JSON report file")
    args = parser.parse_args()
    
    traces_dir = Path(args.traces_dir)
    records = load_traces(traces_dir, args.batch)
    
    if not records:
        print(f"No trace records found for batch '{args.batch}' in {traces_dir}")
        return
    
    print(f"Loaded {len(records)} trace records for batch '{args.batch}'")
    
    metrics = compute_metrics(records)
    
    # Print tables to stdout
    print_tables(metrics)
    
    # Write JSON report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=2)
    
    print(f"JSON report written to {output_path}")


if __name__ == "__main__":
    main()
