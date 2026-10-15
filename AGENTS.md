# AGENTS.md

> Rules for AI Agents (Hermes, Codex, Claude Code, Cursor) working in this repository.

---

## 0. Security & Secret Management (HARDLINE)

- **Zero Secrets in Git**: Never commit API keys, tokens, passwords, private keys, or actual credentials (`.env`, `credentials.json`, `token_*.json`).
- **Environment Variables Only**: All credentials must be loaded via process environment variables (`process.env` / `os.environ.get(...)`).
- **No Hardcoded Secrets**: Do not write key strings in code, comments, `.env.example`, or commit messages.
- **No Absolute Paths**: Do not use local absolute paths (e.g., `/home/username/...`).
- **Gitleaks Protection**: Do not bypass gitleaks pre-commit checks with `--no-verify`.

### 0.1 Personal-Environment Non-Disclosure (HARDLINE)

A public repo must not reveal the author's machine, accounts or setup. This
applies to **every** surface — code, comments, docstrings, test fixtures,
commit messages, PR descriptions and recorded artifacts — because an agent can
leak through any of them.

Never commit, in any form:

- The local OS username as a bare word, or any absolute path containing it
  (`/home/<user>/…`, `/Users/<user>/…`, `/mnt/c/Users/<user>/…`, `C:\Users\<user>\…`).
- A personal (non-noreply) email address — use the provider's noreply alias.
- The names or counts of the agents/tools/models *the author personally runs*;
  an example output must be labelled illustrative, with invented numbers.
- Names of the author's private projects or private infrastructure.
- References to a personal notes vault, key files (`~/.ssh/…`), or agent
  scratch/cache directories.
- Which provider/model/key-env a pipeline runs on, when that is the author's
  personal route rather than the repo's subject.

An example block that claims to be real machine output is the most common leak:
label it `illustrative — counts depend on the machine it runs on` and invent
the values. When a string is sometimes a legitimate subject (an agent being
audited, a model being evaluated, the repo's own name), it belongs in a
per-repo allowlist or the pre-push audit — never in a blanket global rule.

Enforcement (defense in depth): the fleet pre-commit / commit-msg / pre-push
hooks and this repo's `.gitleaks.toml` block the mechanical cases at commit
time and in CI. They are a backstop, not a substitute for judgement — if you
are about to write something a stranger could use to identify the author's
machine, stop.

---

## 1. Project Discipline

- **TDD / Testing**: Verify logic changes with unit tests before declaring completion.
- **Debugging**: Follow systematic debugging (Understand -> Minimal Repro -> Fix -> Verify).
- **Commits**: Small, atomic commits with concise messages.
