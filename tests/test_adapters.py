"""Tests for gate_bench adapters."""
import pytest

def test_scripted_agent_import():
    """Test that scripted agent can be imported and has the expected function."""
    from gate_bench.adapters.scripted_agent import run_agent
    assert callable(run_agent)

def test_strands_agent_import():
    """Test that strands agent raises ImportError when strands is not available."""
    from gate_bench.adapters.strands_agent import run_agent
    # Now calling run_agent should trigger the import and raise ImportError
    with pytest.raises(ImportError):
        run_agent("dummy task", {})

def test_langgraph_agent_import():
    """Test that langgraph agent raises ImportError when langgraph is not available."""
    from gate_bench.adapters.langgraph_agent import run_agent
    with pytest.raises(ImportError):
        run_agent("dummy task", {})

def test_crewai_agent_import():
    """Test that crewai agent raises ImportError when crewai is not available."""
    from gate_bench.adapters.crewai_agent import run_agent
    with pytest.raises(ImportError):
        run_agent("dummy task", {})

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
