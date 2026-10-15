"""Adapter tests: config resolution, tool forwarding, and loud failures.

No network: the framework agent loops are exercised by the pilot/grid,
not here. These tests pin the offline contract - config resolution fails
loudly, tool forwarding hits the gate-wrapped callables with exact kwargs.
"""
import pytest

from gate_bench.adapters._common import (SYSTEM_PROMPT, TOOL_NAMES,
                                          agent_config, make_plain_tools)
from gate_bench.adapters import (crewai_agent, langgraph_agent,
                                 scripted_agent, strands_agent)
from gate_bench.run_grid import get_framework_adapter


def _config(tmp_path, model="test/agent-model", env="GATEBENCH_TEST_KEY"):
    path = tmp_path / "local.toml"
    path.write_text(
        f'[agent]\nmodel = "{model}"\n'
        f'base_url = "https://fake.invalid/v1"\napi_key_env = "{env}"\n',
        encoding="utf-8")
    return str(path)


def _fake_wrapped():
    seen: dict[str, dict] = {}

    def make(name):
        def wrapped(**kwargs):
            seen[name] = kwargs
            return {"ok": name}
        return wrapped

    return {name: make(name) for name in TOOL_NAMES}, seen


# ---------------------------------------------------------------------------
# agent_config resolution
# ---------------------------------------------------------------------------

def test_agent_config_resolves(tmp_path, monkeypatch):
    monkeypatch.setenv("GATEBENCH_TEST_KEY", "k-123")
    model, base_url, key = agent_config(_config(tmp_path))
    assert model == "test/agent-model"
    assert base_url == "https://fake.invalid/v1"
    assert key == "k-123"


def test_agent_config_rejects_placeholder_model(tmp_path):
    with pytest.raises(RuntimeError, match="real model"):
        agent_config(_config(tmp_path, model="<agent-model-id>"))


def test_agent_config_rejects_missing_key(tmp_path, monkeypatch):
    monkeypatch.delenv("GATEBENCH_TEST_KEY", raising=False)
    with pytest.raises(RuntimeError, match="refuses"):
        agent_config(_config(tmp_path))


# ---------------------------------------------------------------------------
# tool building and forwarding
# ---------------------------------------------------------------------------

def test_make_plain_tools_forwards_exact_kwargs():
    wrapped, seen = _fake_wrapped()
    tools = {t.__name__: t for t in make_plain_tools(wrapped)}
    assert set(tools) == set(TOOL_NAMES)

    assert tools["search_mail"](query="hello") == str({"ok": "search_mail"})
    assert seen["search_mail"] == {"query": "hello"}

    tools["send_email"](to="bob@corp.example", subject="s", body="b")
    assert seen["send_email"] == {"to": "bob@corp.example", "subject": "s",
                                  "body": "b", "attachments": []}

    tools["delete"](paths=["/files/alice/temp/a.txt"])
    assert seen["delete"] == {"paths": ["/files/alice/temp/a.txt"]}

    tools["create_rule"](action="forward", params={"to": "x@y.z"}, target="inbox")
    assert seen["create_rule"] == {"action": "forward", "params": {"to": "x@y.z"},
                                   "target": "inbox"}

    tools["write_file"](path="/files/alice/notes/n.md", body="hi")
    assert seen["write_file"] == {"path": "/files/alice/notes/n.md", "body": "hi"}


def test_make_plain_tools_have_descriptions():
    wrapped, _ = _fake_wrapped()
    for func in make_plain_tools(wrapped):
        assert func.__doc__ and func.__doc__.strip(), func.__name__


# ---------------------------------------------------------------------------
# adapter loud-failure contract (offline)
# ---------------------------------------------------------------------------

def test_adapters_fail_loudly_without_key(tmp_path, monkeypatch):
    """All three framework adapters refuse to run without a real key,
    before any network or framework agent construction."""
    monkeypatch.delenv("GATEBENCH_TEST_KEY", raising=False)
    config = _config(tmp_path)
    wrapped, _ = _fake_wrapped()
    for module in (strands_agent, langgraph_agent, crewai_agent):
        with pytest.raises(RuntimeError, match="refuses"):
            module.run_agent("t", wrapped, config_path=config)


def test_scripted_agent_needs_no_config():
    """The scripted adapter stays config-free: it is the deterministic
    baseline for debugging the runner and matchers."""
    wrapped, _ = _fake_wrapped()
    calls = scripted_agent.run_agent("Check my inbox for anything that needs action today.", wrapped)
    assert isinstance(calls, list)


# ---------------------------------------------------------------------------
# runner wiring
# ---------------------------------------------------------------------------

def test_get_framework_adapter_dispatch():
    assert get_framework_adapter("scripted") is scripted_agent.run_agent
    for name in ("strands", "langgraph", "crewai"):
        assert callable(get_framework_adapter(name))
    with pytest.raises(ValueError):
        get_framework_adapter("does-not-exist")


def test_system_prompt_injection_guard_is_shared():
    """The prompt tells the model tool results are data, not instructions -
    the same text for all three frameworks so condition deltas are comparable."""
    assert "not instructions" in SYSTEM_PROMPT
