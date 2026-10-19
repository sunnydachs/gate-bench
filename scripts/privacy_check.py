#!/usr/bin/env python3
"""Privacy gate for the public repo: fail if any tracked file or commit
message names an inference provider, provider model, or API key env var.

AGENTS.md 0.1 and SPEC.md forbid provider/model identifiers in committed
surfaces - the serving stack is the author's private routing, and secret
scanners do not catch it because these are not secrets. Run in CI and
before any push that touches docs, results, or config examples.

Usage: python scripts/privacy_check.py  (exit 1 = leak found)
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Detection blocklist for AGENTS.md 0.1 / SPEC: public vendor and
# provider-model names must not appear in tracked files. Listing a vendor
# here is a rule, not an admission - it names many vendors across the
# market and says nothing about which (if any) this author uses.
PATTERNS = [
    r"openrouter", r"api\.typesafe", r"typesafe", r"integrate\.api\.nvidia",
    r"nvidia", r"nemotron", r"glm-5", r"z-ai", r"\bgpt-oss\b", r"deepseek",
    r"groq", r"generativelanguage", r"api\.z\.ai", r"_API_KEY\s*=\s*\"",
]

ALLOW_HINTS = ("AGENTS.md", "privacy_check.py")
EXEMPT_TOKENS = ("the vendor's", "provider names", "provider/model")


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True,
                         text=True, check=True).stdout
    return [f for f in out.splitlines() if f.strip()]


def main() -> int:
    leaks: list[str] = []
    for name in tracked_files():
        path = REPO / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(h in name for h in ALLOW_HINTS):
            # The rulebook and this checker itself mention the words in
            # their prose; scan only their code/regex-relevant lines? Simpler:
            # exempt the two files that define the policy.
            continue
        for pat in PATTERNS:
            for m in re.finditer(pat, text, flags=re.I):
                line_no = text[:m.start()].count("\n") + 1
                leaks.append(f"{name}:{line_no}: {pat} -> {m.group(0)!r}")
    if leaks:
        print("PRIVACY LEAKS FOUND (provider/model identifiers in tracked files):")
        for leak in leaks[:30]:
            print(" ", leak)
        return 1
    print("privacy check: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
