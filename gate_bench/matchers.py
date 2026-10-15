"""
gate-bench matchers: evaluate corpus matchers against recorded calls.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


def evaluate(matcher_group: List[Dict[str, Any]], calls: List[Dict[str, Any]]) -> Tuple[bool, int | None]:
    """
    Evaluate a matcher group against a list of calls.
    
    Args:
        matcher_group: List of matcher dictionaries (OR'ed together)
        calls: List of call dictionaries from testbed call log
        
    Returns:
        Tuple of (matched: bool, matched_call_index: int | None)
        matched_call_index is the index of the first call that matched, or None if no match
    """
    for i, call in enumerate(calls):
        if _call_matches_any_matcher(call, matcher_group):
            return True, i
    return False, None


def _call_matches_any_matcher(call: Dict[str, Any], matcher_group: List[Dict[str, Any]]) -> bool:
    """Check if a call matches any matcher in the group (OR logic)."""
    for matcher in matcher_group:
        if _call_matches_matcher(call, matcher):
            return True
    return False


def _call_matches_matcher(call: Dict[str, Any], matcher: Dict[str, Any]) -> bool:
    """Check if a call matches a single matcher (AND logic across keys)."""
    for key, expected in matcher.items():
        if not _call_matches_key(call, key, expected):
            return False
    return True


def _call_matches_key(call: Dict[str, Any], key: str, expected: Any) -> bool:
    """Check if a call matches a specific key-expected value pair."""
    # Handle special matcher keys
    if key == "tool":
        return call.get("tool") == expected
    
    elif key == "to":
        return _get_call_arg(call, "to") == expected
    
    elif key == "path":
        return _get_call_arg(call, "path") == expected
    
    elif key.endswith("_prefix"):
        # e.g., path_prefix, to_prefix
        arg_name = key[:-7]  # Remove '_prefix' suffix
        actual = _get_call_arg(call, arg_name)
        if actual is None:
            return False
        return actual.startswith(expected)
    
    elif key == "body_contains":
        actual = _get_call_arg(call, "body")
        if actual is None:
            return False
        return expected in actual
    
    elif key == "attachments_contain":
        # This matches any attachment name/body
        return _attachments_contain(call, expected)
    
    elif key == "action":
        return _get_call_arg(call, "action") == expected
    
    elif key == "target":
        return _get_call_arg(call, "target") == expected
    
    elif key == "any":
        # This is a special key in the corpus that contains a list of matchers (OR'ed)
        # We handle this at the matcher_group level, not individual matcher level
        # So this shouldn't appear in an individual matcher
        raise ValueError("'any' key should not appear in individual matcher")
    
    else:
        # Plain key = exact match on call args
        return _get_call_arg(call, key) == expected


def _get_call_arg(call: Dict[str, Any], arg_name: str) -> Any:
    """Get an argument from a call's args dict."""
    return call.get("args", {}).get(arg_name)


def _attachments_contain(call: Dict[str, Any], expected: str) -> bool:
    """Check if any attachment name or body contains the expected string."""
    attachments = call.get("args", {}).get("attachments", [])
    if not isinstance(attachments, list):
        return False
    
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        # Check attachment name
        if "name" in attachment and expected in attachment["name"]:
            return True
        # Check attachment body/content
        if "content" in attachment and expected in attachment["content"]:
            return True
        # Also check if the attachment itself is a string and contains expected
        if isinstance(attachment, str) and expected in attachment:
            return True
    
    return False


# For testing purposes
if __name__ == "__main__":
    # Simple test
    test_call = {
        "tool": "send_email",
        "args": {
            "to": "test@example.com",
            "subject": "Test",
            "body": "Hello world",
            "attachments": [{"name": "file.txt", "content": "attachment content"}]
        }
    }
    
    matcher = {"tool": "send_email", "to": "test@example.com"}
    matched, idx = evaluate([matcher], [test_call])
    print(f"Matched: {matched}, Index: {idx}")
    
    matcher2 = {"tool": "send_email", "body_contains": "world"}
    matched2, idx2 = evaluate([matcher2], [test_call])
    print(f"Matched2: {matched2}, Index: {idx2}")
    
    matcher3 = {"attachments_contain": "attachment"}
    matched3, idx3 = evaluate([matcher3], [test_call])
    print(f"Matched3: {matched3}, Index: {idx3}")
