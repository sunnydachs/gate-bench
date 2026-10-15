"""Tests for gate_bench run_grid functionality."""
import json
import tempfile
from pathlib import Path

from gate_bench.run_grid import (
    load_corpus_data,
    load_config,
    get_framework_adapter,
    run_single_experiment
)


def test_load_corpus_data():
    """Test that corpus data loads correctly."""
    environment, attacks, benign = load_corpus_data()
    
    assert isinstance(environment, dict)
    assert "users" in environment
    assert environment["users"]["alice"]["acts_for"] is True
    
    assert isinstance(attacks, list)
    assert len(attacks) == 50  # From test_corpus.py
    
    assert isinstance(benign, list)
    assert len(benign) == 25  # From test_corpus.py


def test_load_config():
    """Test that config loads correctly."""
    config = load_config()
    assert isinstance(config, dict)
    assert "agent" in config
    assert "judge" in config
    assert "jev" in config
    assert "run" in config


def test_get_framework_adapter():
    """Test that we can get the scripted agent adapter."""
    adapter = get_framework_adapter("scripted")
    assert callable(adapter)
    
    # Test that other frameworks raise ImportError when not available
    # We won't test strands/langgraph/crewai here since they're not installed
    # but we can test that the function exists
    assert callable(get_framework_adapter)


def test_run_single_experiment_scripted():
    """Test running a single experiment with the scripted agent."""
    # Load a simple benign scenario
    _, _, benign = load_corpus_data()
    scenario = benign[0]  # Take the first benign scenario

    # Run a single experiment (config resolves via the standard fallback
    # chain: config/local.toml then config/local.example.toml)
    record = run_single_experiment(
        framework="scripted",
        condition="none",
        scenario_id=scenario["id"],
        seed=1,
        environment={},  # We'll load a minimal environment for testing
        attack_or_benign=scenario,
        is_attack=False,
    )
    
    # Check that we got a record with the expected structure
    assert isinstance(record, dict)
    assert record["framework"] == "scripted"
    assert record["condition"] == "none"
    assert record["scenario_id"] == scenario["id"]
    assert record["seed"] == 1
    assert record["task"] == scenario["task"]
    assert isinstance(record["calls"], list)
    # For benign task with none gate, we expect task_success to be True or False
    assert record["task_success"] in [True, False]
    assert record["false_block_hard"] in [True, False]
    assert record["false_block_soft"] in [True, False]
    assert isinstance(record["final_text"], str)
    assert record["error"] is None or isinstance(record["error"], str)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
