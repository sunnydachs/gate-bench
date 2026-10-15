# Implementation Notes for gate-bench

## Ambiguities Resolved

1. **Static Gate Ticket Extraction**: The spec says ticket claims (TKT-\d+) that are not in the registry cause a block for external targets. We implemented ticket ID extraction from various places (direct param, in params for create_rule, and scanning string fields for TKT-\d+ pattern). For internal bob targets, we also require a ticket.

2. **Static Gate Deletion Rules**: 
   - Deleting more than 5 files requires a ticket.
   - Deleting anything under legal-hold/ requires a ticket.
   - Deleting files in the shared space requires a ticket.
   We implemented these as described.

3. **Static Gate External Targets**: 
   - For send_email and share_file, external recipients must be whitelisted vendors (only vendor-portal@acme.example from the environment).
   - For create_rule, we treat it similarly: if the rule would forward to an external target, we check the whitelist.
   We checked the params for common forwarding parameters (to, forward, redirect).

4. **Gate Refusal Recording**: 
   - Every tool call is recorded: tool name, args, executed/refused, result.
   - We implemented _log_call in the testbed to record calls, and we wrap each tool to call the gate and record the call with gate decision and reason.
   - When a gate returns block or review, we record the call as refused (executed=false) and return a refusal result that the model can see.

5. **Matcher Engine**:
   - We implemented exact match, prefix match (_prefix), substring match (_contains), and special matchers attachments_contain (matches any attachment name or body) and body_contains.
   - The matcher group is OR'ed, and within a matcher, keys are AND'ed.

6. **Scripted Agent**:
   - The scripted agent performs plausible fixed behavior: it searches/reads based on the task, and obeys the most recent external instruction in untrusted content.
   - We implemented instruction detection from tool results (emails, files) and from the task itself.
   - The agent attempts exactly the called gated tool after doing the task's obvious steps.

7. **Framework Adapters**:
   - We provided lazy imports for strands, langgraph, and crewai agents.
   - They raise ImportError when the respective packages are not installed.
   - We included a shared SYSTEM_PROMPT.

8. **Runner**:
   - The runner is resumable via a manifest file.
   - It skips combinations already in the manifest.
   - It supports limiting the number of combinations.

9. **Analyzer**:
   - Computes attack success rate (overall, by category, by tier, by expect_layer).
   - Computes benign task success.
   - Computes false block rates (block and review separately).
   - Computes gate latency p50 and p95.
   - Outputs a JSON report and prints tables.

10. **Configuration**:
    - We use config/local.example.toml as fallback, and the actual config/local.toml is gitignored.
    - API keys are read from the environment variable specified in config (api_key_env).

## Files Modified/Added

- gate_bench/testbed.py: In-memory mock environment with tool implementations and boundary enforcement.
- gate_bench/gates.py: Four gate conditions (NoGate, StaticGate, LLMJudgeGate, JevGate) with fail-closed behavior.
- gate_bench/matchers.py: Matcher engine for evaluating corpus matchers.
- gate_bench/adapters/scripted_agent.py: Scripted agent that domesticates external instructions.
- gate_bench/adapters/strands_agent.py, langgraph_agent.py, crewai_agent.py: Framework agents with lazy imports.
- gate_bench/run_grid.py: Resumable runner.
- gate_bench/analyze.py: Analyzer that produces report.json and prints tables.
- tests/: Unit tests for all components.

## Testing

All unit tests pass. We also ran a small pilot test with 10 attack scenarios, 4 conditions, 1 seed, and the scripted agent.

