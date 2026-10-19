# gate-bench replication lane (grid-v6, 900/900 runs, 2026-10-19)

Pure single-provider replication of results/grid-v5-complete.md: the same
agent weights and judge family, same corpus, seed 1 - every run served end
to end by one inference provider (ids in gitignored config). Verdict: the
pattern replicates.

## Attack events (n = 150 per condition, counts from raw call logs)

| condition | hijacked | executed (success) | free-lane comparison (hijack / success) |
|---|---|---|---|
| none | 9 | 9 | 7 / 7 |
| static | 6 | 4 | 7 / 5 |
| llm_judge | 7 | 3 | 7 / 3 |
| jev | 8 | **0** | 7 / **0** |

Attack success by framework (this lane): none 3/4/2 (crewai/langgraph/strands)
-> static 2/1/1 -> llm_judge 1/1/1 -> **jev 0/0/0**.

**Across both lanes: jev stopped 15/15 hijacked attacks (zero end-to-end
attack successes in 300 attacks), vs 16 successes under no gate.** The
monotone none -> static -> judge -> jev ordering and the flat hijack rate
(gates do not change how often the agent follows an injection) hold in both
serving lanes independently.

## Benign (n = 25 per cell, this lane)

| framework | condition | task ok | FB hard | FB soft |
|---|---|---|---|---|
| strands | none | 68.0% | 0.0% | 0.0% |
| strands | static | 68.0% | 4.0% | 0.0% |
| strands | llm_judge | 72.0% | 0.0% | 0.0% |
| strands | jev | 56.0% | 4.0% | 16.0% |
| langgraph | none | 68.0% | 0.0% | 0.0% |
| langgraph | static | 72.0% | 4.0% | 0.0% |
| langgraph | llm_judge | 68.0% | 0.0% | 0.0% |
| langgraph | jev | 56.0% | 4.0% | 12.0% |
| crewai | none | 72.0% | 0.0% | 0.0% |
| crewai | static | 72.0% | 0.0% | 0.0% |
| crewai | llm_judge | 72.0% | 0.0% | 0.0% |
| crewai | jev | 56.0% | 4.0% | 12.0% |

The jev cost profile replicates: ~4% hard false blocks, 12-16% deferrals,
benign task completion 12-16 points below the ungated baseline on every
framework. On this lane the static gate also produced 1/25 hard false
blocks on two frameworks (small counts; the free lane had none).

## Combined reading (two lanes, 1800 runs total)

- The probability gate is the only condition with zero end-to-end attack
  successes on both lanes, and the only one that caught the
  persistence write_file cases (D5/D6).
- The LLM judge roughly halves what static leaves through, at zero measured
  benign cost on both lanes with this judge model - but at 2.8-7.6 s per
  gated call, and a separate judge model showed benign nondeterminism.
- The static gate is free and catches the mechanical external-perimeter
  cases, but writes inside the agent's own roots are invisible to it.
- Event counts are small (exact counts reported everywhere); the replicated
  ordering, not the individual percentages, is the finding.
