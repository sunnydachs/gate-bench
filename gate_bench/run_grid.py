"""
gate-bench run_grid: resumable runner for executing the benchmark grid.
"""
from __future__ import annotations

import json
import uuid
import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

from gate_bench.testbed import create_testbed_from_yaml, Testbed
from gate_bench.gates import create_gate
from gate_bench.matchers import evaluate
from gate_bench.adapters.scripted_agent import run_agent as run_scripted_agent
# Framework agents will be imported lazily inside their respective functions


# Import paths for framework agents (lazy import)
STRANDS_AGENT_PATH = "gate_bench.adapters.strands_agent"
LANGGRAPH_AGENT_PATH = "gate_bench.adapters.langgraph_agent"
CREWAI_AGENT_PATH = "gate_bench.adapters.crewai_agent"


def load_corpus_data() -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load environment, attacks, and benign scenarios."""
    env_path = Path("corpus/environment.yaml")
    attacks_path = Path("corpus/attacks.yaml")
    benign_path = Path("corpus/benign.yaml")
    
    with open(env_path, encoding="utf-8") as f:
        environment = yaml.safe_load(f)
    
    with open(attacks_path, encoding="utf-8") as f:
        attacks = yaml.safe_load(f)
    
    with open(benign_path, encoding="utf-8") as f:
        benign = yaml.safe_load(f)
    
    return environment, attacks, benign


def load_config(config_path: str = "config/local.example.toml") -> Dict[str, Any]:
    """Load configuration from TOML file."""
    import tomllib
    
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        # Fallback to example config
        with open("config/local.example.toml", "rb") as f:
            return tomllib.load(f)


def get_framework_adapter(framework: str):
    """Get the agent adapter function for the specified framework."""
    if framework == "scripted":
        from gate_bench.adapters.scripted_agent import run_agent
        return run_agent
    elif framework == "strands":
        try:
            from gate_bench.adapters.strands_agent import run_agent
            return run_agent
        except ImportError:
            raise ImportError(f"Strands agent not available: {STRANDS_AGENT_PATH}")
    elif framework == "langgraph":
        try:
            from gate_bench.adapters.langgraph_agent import run_agent
            return run_agent
        except ImportError:
            raise ImportError(f"LangGraph agent not available: {LANGGRAPH_AGENT_PATH}")
    elif framework == "crewai":
        try:
            from gate_bench.adapters.crewai_agent import run_agent
            return run_agent
        except ImportError:
            raise ImportError(f"CrewAI agent not available: {CREWAI_AGENT_PATH}")
    else:
        raise ValueError(f"Unknown framework: {framework}")


def load_manifest(manifest_path: Path) -> Set[Tuple[str, str, str, int]]:
    """Load the manifest of already-run combinations."""
    if not manifest_path.exists():
        return set()
    
    completed = set()
    with open(manifest_path, "r") as f:
        for line in f:
            record = json.loads(line.strip())
            key = (
                record["framework"],
                record["condition"],
                record["scenario_id"],
                record["seed"]
            )
            completed.add(key)
    
    return completed


def append_to_manifest(manifest_path: Path, record: Dict[str, Any]) -> None:
    """Append a record to the manifest file."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "a") as f:
        f.write(json.dumps(record) + "\n")


def evaluate_attack_success(calls: List[Dict[str, Any]], attack: Dict[str, Any]) -> bool:
    """Evaluate if an attack was successful based on the attack_success matchers."""
    matched, _ = evaluate(attack["attack_success"]["any"], calls)
    return matched


def _source_sender(placements: List[Dict[str, Any]]) -> Optional[str]:
    """Origin of the scenario's injected content: the sender of the placed
    email, or a marker for a shared/own file. The gate prompt and the jev
    state both reference this; None when the scenario places nothing."""
    sender: Optional[str] = None
    origin: Optional[str] = None
    for placement in placements:
        email = placement.get("email") or (placement.get("placement") or {}).get("email")
        file_p = placement.get("file") or (placement.get("placement") or {}).get("file")
        if email and sender is None:
            sender = email.get("from")
        if file_p and origin is None:
            path = str(file_p.get("path", ""))
            origin = "shared file" if path.startswith("/files/shared") else "file"
    return sender or origin


def evaluate_benign_task_success(calls: List[Dict[str, Any]], benign: Dict[str, Any]) -> bool:
    """Evaluate if a benign task was successful based on the task_success matchers."""
    matched, _ = evaluate(benign["task_success"]["any"], calls)
    return matched


def evaluate_false_block(calls: List[Dict[str, Any]], benign: Dict[str, Any]) -> Tuple[bool, bool]:
    """
    Evaluate if there were false blocks (block or review) on legitimate privileged calls.
    
    Returns:
        Tuple of (false_block_hard, false_block_soft) where:
        - false_block_hard: any legit_privileged call got block
        - false_block_soft: any legit_privileged call got review (but not block)
    """
    if "legit_privileged" not in benign:
        return False, False
    
    # Check each legitimate privileged call matcher
    hard_block = False
    soft_block = False
    
    for matcher in benign["legit_privileged"]:
        matched, matched_idx = evaluate([matcher], calls)
        if matched and matched_idx is not None:
            call = calls[matched_idx]
            if call["gate_decision"] == "block":
                hard_block = True
            elif call["gate_decision"] == "review":
                soft_block = True
    
    return hard_block, soft_block


def run_single_experiment(
    framework: str,
    condition: str,
    scenario_id: str,
    seed: int,
    environment: Dict[str, Any],
    attack_or_benign: Dict[str, Any],
    is_attack: bool,
    config_path: str = "config/local.toml",
) -> Dict[str, Any]:
    """
    Run a single experiment combination.
    
    Returns a record dict to be written to the trace file.
    """
    # Create fresh testbed
    testbed = create_testbed_from_yaml("corpus/environment.yaml")
    
    # Apply placements if any
    placements = []
    if "placement" in attack_or_benign:
        placements.append(attack_or_benign["placement"])
    elif "placements" in attack_or_benign:
        placements = attack_or_benign["placements"]
    
    if placements:
        testbed.apply_placements(placements)

    # The gate sees who triggered the content: the placed email's sender,
    # or a marker for a shared file. This is a policy input, not a leak.
    source_sender = _source_sender(placements)
    
    # Get the appropriate gate
    gate = create_gate(condition, config_path=config_path)
    
    # Wrap tools to record calls and enforce gates
    original_tools = {
        "search_mail": testbed.search_mail,
        "search_files": testbed.search_files,
        "read": testbed.read,
        "summarize": testbed.summarize,
        "send_email": testbed.send_email,
        "share_file": testbed.share_file,
        "delete": testbed.delete,
        "create_rule": testbed.create_rule,
        "write_file": testbed.write_file,
    }
    
    # We need to wrap each tool to:
    # 1. Call the gate check before execution
    # 2. Record the call with gate decision info
    # 3. Return the result or refusal
    
    def make_wrapped_tool(tool_name: str, original_func: Any):
        def wrapped_tool(**kwargs):
            # Check gate before execution
            gate_result = gate.check(
                tool=tool_name,
                args=kwargs,
                task=attack_or_benign["task"],
                policy_text=testbed.state.policy,
                tickets={t.id: t for t in testbed.state.tickets.values()},
                source_sender=source_sender
            )
            
            # Record the call attempt
            if gate_result.decision == "block":
                # Tool is blocked - record as refused
                testbed._log_call(
                    tool_name,
                    kwargs,
                    None,
                    refused=True,
                    refusal_reason=gate_result.reason,
                    gate_decision="block"
                )
                # Return a refusal result that the model can see
                return {"refused": True, "reason": gate_result.reason, "gate_decision": "block"}
            elif gate_result.decision == "review":
                # Tool is held for review - record as refused
                testbed._log_call(
                    tool_name,
                    kwargs,
                    None,
                    refused=True,
                    refusal_reason=gate_result.reason,
                    gate_decision="review"
                )
                # Return a refusal result that the model can see
                return {"refused": True, "reason": gate_result.reason, "gate_decision": "review"}
            else:
                # Tool is approved - execute it. The testbed methods log their
                # own calls, so annotate whatever they appended instead of
                # logging a duplicate entry.
                log_before = len(testbed.call_log)
                try:
                    result = original_func(**kwargs)
                except Exception as e:
                    # The tool executed and errored; keep the call recorded.
                    result = {"error": str(e)}
                appended = testbed.call_log[log_before:]
                if appended:
                    for entry in appended:
                        entry["gate_decision"] = "approve"
                else:
                    testbed._log_call(tool_name, kwargs, result, refused=False,
                                      gate_decision="approve")
                return result
        
        return wrapped_tool
    
    # Create wrapped tools
    wrapped_tools = {
        name: make_wrapped_tool(name, func)
        for name, func in original_tools.items()
    }
    
    # Get the framework adapter
    adapter_func = get_framework_adapter(framework)
    
    # Run the agent
    try:
        agent_calls = adapter_func(
            task=attack_or_benign["task"],
            tools=wrapped_tools,
            llm=None  # Not used in our implementation
        )
        
        # Extract final text from agent calls (simplified)
        final_text = ""
        if agent_calls:
            # Use the last call's result as final text for simplicity
            last_call = agent_calls[-1]
            if isinstance(last_call.get("result"), dict):
                final_text = json.dumps(last_call["result"])
            else:
                final_text = str(last_call.get("result", ""))
        
        error = None
    except Exception as e:
        agent_calls = []
        final_text = ""
        error = str(e)
    
    # Get the actual call log from the testbed (this has the real gate decisions)
    actual_calls = testbed.call_log
    
    # Evaluate success
    if is_attack:
        attack_success = evaluate_attack_success(actual_calls, attack_or_benign)
        task_success = None  # Not applicable for attacks
        false_block_hard = None
        false_block_soft = None
    else:
        attack_success = None
        task_success = evaluate_benign_task_success(actual_calls, attack_or_benign)
        false_block_hard, false_block_soft = evaluate_false_block(actual_calls, attack_or_benign)
    
    # Create the record
    record = {
        "framework": framework,
        "condition": condition,
        "scenario_id": scenario_id,
        "seed": seed,
        "task": attack_or_benign["task"],
        "calls": actual_calls,  # Use the testbed's call log which has gate decisions
        "attack_success": attack_success,
        "task_success": task_success,
        "false_block_hard": false_block_hard,
        "false_block_soft": false_block_soft,
        "final_text": final_text,
        "error": error
    }
    
    return record


def main():
    """Main entry point for the run_grid script."""
    parser = argparse.ArgumentParser(description="Run gate-bench experiments")
    parser.add_argument("--frameworks", nargs="+", default=["scripted"], 
                       choices=["scripted", "strands", "langgraph", "crewai"],
                       help="Frameworks to run")
    parser.add_argument("--conditions", nargs="+", default=["none"], 
                       choices=["none", "static", "llm_judge", "jev"],
                       help="Gate conditions to run")
    parser.add_argument("--scenarios", nargs="+", type=str,
                       help="Scenario IDs to run (if not specified, runs all)")
    parser.add_argument("--seeds", nargs="+", type=int, default=[1],
                       help="Random seeds to use")
    parser.add_argument("--batch", type=str, default="default",
                       help="Batch name for output files")
    parser.add_argument("--limit", type=int, default=None,
                       help="Limit the number of combinations to run (for testing)")
    parser.add_argument("--config", type=str, default="config/local.toml",
                       help="Path to config file")
    
    args = parser.parse_args()
    
    # Load corpus data
    environment, attacks, benign = load_corpus_data()
    
    # Load config
    config = load_config(args.config)
    
    # Prepare scenario lists
    if args.scenarios:
        # Filter to only specified scenarios
        attack_scenarios = [a for a in attacks if a["id"] in args.scenarios]
        benign_scenarios = [b for b in benign if b["id"] in args.scenarios]
    else:
        attack_scenarios = attacks
        benign_scenarios = benign
    
    if not attack_scenarios and not benign_scenarios:
        print("No scenarios match the specified IDs")
        return
    
    # Prepare output directories
    traces_dir = Path("traces")
    traces_dir.mkdir(exist_ok=True)
    
    manifest_path = traces_dir / f"{args.batch}.manifest"
    trace_path = traces_dir / f"{args.batch}.jsonl"
    
    # Load manifest to skip already completed combinations
    completed = load_manifest(manifest_path)
    
    # Generate all combinations to run
    combinations = []
    
    # Attack scenarios
    for framework in args.frameworks:
        for condition in args.conditions:
            for scenario in attack_scenarios:
                for seed in args.seeds:
                    key = (framework, condition, scenario["id"], seed)
                    if key not in completed:
                        combinations.append((framework, condition, scenario, seed, True))  # True = is attack
    
    # Benign scenarios
    for framework in args.frameworks:
        for condition in args.conditions:
            for scenario in benign_scenarios:
                for seed in args.seeds:
                    key = (framework, condition, scenario["id"], seed)
                    if key not in completed:
                        combinations.append((framework, condition, scenario, seed, False))  # False = is benign
    
    # Apply limit if specified
    if args.limit is not None:
        combinations = combinations[:args.limit]
    
    print(f"Running {len(combinations)} experiment combinations...")
    print(f"Manifest: {manifest_path}")
    print(f"Trace output: {trace_path}")
    
    # Run experiments
    for i, (framework, condition, scenario, seed, is_attack) in enumerate(combinations):
        scenario_id = scenario["id"]
        scenario_type = "attack" if is_attack else "benign"
        print(f"[{i+1}/{len(combinations)}] Running {framework} {condition} {scenario_type} {scenario_id} seed={seed}")
        
        try:
            record = run_single_experiment(
                framework=framework,
                condition=condition,
                scenario_id=scenario_id,
                seed=seed,
                environment=environment,
                attack_or_benign=scenario,
                is_attack=is_attack,
                config_path=args.config
            )
            
            # Append to trace file
            append_to_manifest(manifest_path, record)
            append_to_manifest(trace_path, record)
            
        except Exception as e:
            print(f"  ERROR: {e}")
            # Still create an error record so we know it was attempted
            error_record = {
                "framework": framework,
                "condition": condition,
                "scenario_id": scenario_id,
                "seed": seed,
                "task": scenario["task"],
                "calls": [],
                "attack_success": False if is_attack else None,
                "task_success": None if is_attack else False,
                "false_block_hard": None,
                "false_block_soft": None,
                "final_text": "",
                "error": str(e)
            }
            append_to_manifest(manifest_path, error_record)
            append_to_manifest(trace_path, error_record)
    
    print("Done!")


if __name__ == "__main__":
    main()
