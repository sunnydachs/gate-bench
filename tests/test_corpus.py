"""Corpus integrity checks: the grid is only as good as its scenario data."""
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLS = {"search_mail", "search_files", "read", "summarize",
         "send_email", "share_file", "delete", "create_rule", "write_file"}
MATCHER_KEYS = {"tool", "to", "path", "path_prefix", "attachments_contain",
                "body_contains", "action", "target"}
CATEGORIES = {"privilege_escalation", "data_exfiltration", "direct_harm",
              "persistence_spread", "gate_evasion", "benign_search", "benign_privileged"}


def load(name):
    return yaml.safe_load((ROOT / "corpus" / name).read_text())


def check_matcher(m, where):
    assert m.get("tool") in TOOLS, f"{where}: unknown tool {m.get('tool')}"
    extra = set(m) - MATCHER_KEYS
    assert not extra, f"{where}: unknown matcher keys {extra}"


def test_environment_shape():
    env = load("environment.yaml")
    assert set(env["users"]) == {"alice", "bob"}
    assert env["users"]["alice"]["acts_for"] is True
    assert env["users"]["bob"]["acts_for"] is False
    assert len(env["policy"]) > 200, "policy text must be substantial"
    tickets = {t["id"] for t in env["tickets"]}
    assert tickets == {"TKT-0042", "TKT-0043", "TKT-0044"}
    assert "vendor-portal@acme.example" in env["contacts"]["external_whitelisted"]
    assert any(p.startswith("/files/alice/private/") for p in env["files"])
    assert any(str(env["files"][p].get("sensitive")) == "True" for p in env["files"])
    assert "/mail/alice" in env["mailboxes"] and "/mail/bob" in env["mailboxes"]


def test_attacks():
    attacks = load("attacks.yaml")
    assert len(attacks) == 50, f"expected 50 attacks, got {len(attacks)}"
    ids = [a["id"] for a in attacks]
    assert len(set(ids)) == 50, "duplicate attack ids"
    per_cat = {}
    for a in attacks:
        where = a["id"]
        assert a["category"] in CATEGORIES - {"benign_search", "benign_privileged"}, where
        assert a["tier"] in (1, 2, 3), where
        assert a["expect_layer"] in ("static", "gate"), where
        assert ("placement" in a) ^ ("placements" in a), f"{where}: exactly one of placement(s)"
        assert a["task"].strip(), where
        assert "any" in a["attack_success"], where
        for m in a["attack_success"]["any"]:
            check_matcher(m, where)
        per_cat[a["category"]] = per_cat.get(a["category"], 0) + 1
    assert per_cat == {"privilege_escalation": 12, "data_exfiltration": 12,
                       "direct_harm": 10, "persistence_spread": 8, "gate_evasion": 8}


def test_benign():
    benign = load("benign.yaml")
    assert len(benign) == 25, f"expected 25 benign, got {len(benign)}"
    ids = [b["id"] for b in benign]
    assert len(set(ids)) == 25, "duplicate benign ids"
    n_priv = 0
    for b in benign:
        where = b["id"]
        assert b["category"] in {"benign_search", "benign_privileged"}, where
        assert b["task"].strip(), where
        assert "any" in b["task_success"], where
        for m in b["task_success"]["any"]:
            check_matcher(m, where)
        for m in b.get("legit_privileged", []):
            check_matcher(m, where)
            n_priv += 1
    assert n_priv >= 15, "need enough gate-passing benign calls to measure false blocks"


def test_placement_targets_are_fictional():
    for group, entries in (("attacks.yaml", load("attacks.yaml")),):
        for a in entries:
            for p in a.get("placements", []) or ([a["placement"]] if "placement" in a else []):
                for kind, data in p.items():
                    addr = data.get("from", "") if kind == "email" else ""
                    assert not addr or addr.endswith(".example"), f"{a['id']}: non-.example sender {addr}"
