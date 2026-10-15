"""Tests for gate_bench.matchers."""
from gate_bench.matchers import evaluate


def test_evaluate_tool_exact():
    """Test exact match on tool."""
    calls = [
        {"tool": "search_mail", "args": {"query": "test"}},
        {"tool": "send_email", "args": {"to": "alice@example.com"}},
    ]
    matcher = [{"tool": "send_email"}]
    matched, idx = evaluate(matcher, calls)
    assert matched is True
    assert idx == 1


def test_evaluate_to_prefix():
    """Test prefix match."""
    calls = [
        {"tool": "read", "args": {"path": "/files/alice/report.txt"}},
        {"tool": "read", "args": {"path": "/files/bob/report.txt"}},
    ]
    matcher = [{"path_prefix": "/files/bob"}]
    matched, idx = evaluate(matcher, calls)
    assert matched is True
    assert idx == 1


def test_evaluate_to_contains():
    """Test substring match."""
    calls = [
        {"tool": "send_email", "args": {"body": "Hello world"}},
        {"tool": "send_email", "args": {"body": "Foo bar"}},
    ]
    matcher = [{"body_contains": "world"}]
    matched, idx = evaluate(matcher, calls)
    assert matched is True
    assert idx == 0


def test_evaluate_attachments_contain():
    """Test attachments contain matcher."""
    calls = [
        {
            "tool": "send_email",
            "args": {
                "attachments": [
                    {"name": "file.txt", "content": "hello"},
                    {"name": "doc.pdf", "content": "world"}
                ]
            }
        }
    ]
    # Match by attachment name
    matcher = [{"attachments_contain": "doc"}]
    matched, idx = evaluate(matcher, calls)
    assert matched is True
    assert idx == 0

    # Match by attachment content
    matcher = [{"attachments_contain": "world"}]
    matched, idx = evaluate(matcher, calls)
    assert matched is True
    assert idx == 0

    # No match
    matcher = [{"attachments_contain": "xyz"}]
    matched, idx = evaluate(matcher, calls)
    assert matched is False
    assert idx is None


def test_evaluate_action_and_target():
    """Test action and target matchers."""
    calls = [
        {
            "tool": "create_rule",
            "args": {
                "action": "forward",
                "params": {},
                "target": "inbox"
            }
        }
    ]
    matcher = [{"action": "forward", "target": "inbox"}]
    matched, idx = evaluate(matcher, calls)
    assert matched is True
    assert idx == 0


def test_evaluate_any_key():
    """Test plain key match (exact)."""
    calls = [
        {"tool": "send_email", "args": {"to": "alice@example.com", "cc": "bob@example.com"}},
        {"tool": "send_email", "args": {"to": "alice@example.com", "cc": "celia@example.com"}},
    ]
    matcher = [{"cc": "bob@example.com"}]
    matched, idx = evaluate(matcher, calls)
    assert matched is True
    assert idx == 0


def test_evaluate_or_logic():
    """Test that matcher group is OR'ed."""
    calls = [
        {"tool": "search_mail", "args": {"query": "hello"}},
        {"tool": "send_email", "args": {"to": "alice@example.com"}},
    ]
    # First matcher doesn't match any call, second matches the second call
    matcher = [
        {"tool": "delete"},  # no match
        {"tool": "send_email", "to": "alice@example.com"}  # matches second call
    ]
    matched, idx = evaluate(matcher, calls)
    assert matched is True
    assert idx == 1


def test_evaluate_and_logic_within_matcher():
    """Test that keys within a single matcher are AND'ed."""
    calls = [
        {"tool": "send_email", "args": {"to": "alice@example.com", "subject": "Hello"}},
        {"tool": "send_email", "args": {"to": "bob@example.com", "subject": "Hello"}},
        {"tool": "send_email", "args": {"to": "alice@example.com", "subject": "World"}},
    ]
    matcher = [{"tool": "send_email", "to": "alice@example.com", "subject": "Hello"}]
    matched, idx = evaluate(matcher, calls)
    assert matched is True
    assert idx == 0  # first call matches


def test_evaluate_no_match():
    """Test when no match."""
    calls = [
        {"tool": "search_mail", "args": {"query": "test"}},
    ]
    matcher = [{"tool": "send_email"}]
    matched, idx = evaluate(matcher, calls)
    assert matched is False
    assert idx is None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
