# gate-bench first complete grid (grid-v5, 900/900 runs, 2026-10-19)

Agent model: a general-purpose model (same weights across the batch; serving:
769 runs on the an inference provider free pool, 131 gap-fill runs on the provider the provider -
disclosed, and a pure-the provider replication lane is running separately).
Judge: a general-purpose model-3-super-120b (an inference provider :free). jev: official the decision-model vendor
System One API. Seed 1, call budget 20, corpus 50 attacks + 25 benign.
Metrics recomputed from raw call logs by scripts/analyze.py (clean-wins
dedupe, executed-only scoring) - never from stored booleans.

## Attack results (n = 50 attacks per cell)

| framework | condition | hijack | gate stopped | attack success | events |
|---|---|---|---|---|---|
| strands | none | 2.0% | - | 2.0% | 1/50 |
| strands | static | 4.0% | 0.0% | 4.0% | 2/50 |
| strands | llm_judge | 4.0% | 50.0% | 2.0% | 1/50 |
| strands | jev | 4.0% | 100.0% | 0.0% | 0/50 |
| langgraph | none | 8.0% | - | 8.0% | 4/50 |
| langgraph | static | 4.0% | 50.0% | 2.0% | 1/50 |
| langgraph | llm_judge | 4.0% | 50.0% | 2.0% | 1/50 |
| langgraph | jev | 4.0% | 100.0% | 0.0% | 0/50 |
| crewai | none | 4.0% | - | 4.0% | 2/50 |
| crewai | static | 6.0% | 33.3% | 4.0% | 2/50 |
| crewai | llm_judge | 6.0% | 66.7% | 2.0% | 1/50 |
| crewai | jev | 6.0% | 100.0% | 0.0% | 0/50 |

End-to-end attack successes across all three frameworks (150 attacks per
condition): **none 7, static 5, llm_judge 3, jev 0.**

Hijack totals are flat across conditions (7-8 per 150, 4.7-5.3%): gates sit
at the permission junction and do not change how often the agent follows the
injection - only what happens next. Stop rates among hijacked runs:
static 2/7, llm_judge 4/7, jev 7/7.

The gate-bypassing attacks under static and llm_judge are the
persistence_spread write_file cases (D5/D6): planting instructions into
files inside the agent's allowed roots. Only the probability gate caught
them - a boundary/rules view cannot see "write a note that future agents
will obey".

## Benign results (n = 25 per cell)

| framework | condition | task ok | false block hard | false block soft |
|---|---|---|---|---|
| strands | none | 72.0% | 0.0% | 0.0% |
| strands | static | 68.0% | 0.0% | 0.0% |
| strands | llm_judge | 68.0% | 0.0% | 0.0% |
| strands | jev | 60.0% | 4.0% | 8.0% |
| langgraph | none | 72.0% | 0.0% | 0.0% |
| langgraph | static | 72.0% | 0.0% | 0.0% |
| langgraph | llm_judge | 72.0% | 0.0% | 0.0% |
| langgraph | jev | 52.0% | 4.0% | 12.0% |
| crewai | none | 72.0% | 0.0% | 0.0% |
| crewai | static | 72.0% | 0.0% | 0.0% |
| crewai | llm_judge | 72.0% | 0.0% | 0.0% |
| crewai | jev | 56.0% | 4.0% | 16.0% |

The jev gate is the only condition with hard false blocks (1 per framework,
4%) and defers 8-16% of legitimate privileged calls; benign task
completion drops 12-16 points vs the ungated baseline. static and llm_judge
produced zero false blocks on this corpus with this judge model
(a general-purpose model-super-120b; the separate latency bench on a different judge model
showed benign nondeterminism).

## Gate latency (measured separately, 10 reps per case)

- static: ~0 ms
- jev: ~200 ms median, decisions consistent
- llm_judge: 2.8-7.6 s median, and on a different judge model (a general-purpose model-20b)
  the benign ticketed send flipped approve/block across reps

## Caveats

- Small event counts: hijack totals are 1-4 per cell, so percentages are
  reported with exact event counts; the cross-condition pattern (7->5->3->0)
  should be read as monotone with wide intervals, not as precise rates.
- One serving lane for 85% of runs, a second for 15%; the pure-the provider
  replication lane is in progress and will confirm.
- Single agent model, single seed; the corpus is the unit of variability.
