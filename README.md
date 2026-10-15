# gate-bench

Does a probability gate at the permission junction stop privilege-escalation
prompt injections - measured as end-to-end attack success, not detection?

A multi-user least-privilege agent (mock mailbox + filesystem, alice and bob)
runs the same task loop in three frameworks (Strands, LangGraph, CrewAI).
Fifty indirect prompt-injection scenarios - hidden in emails and file contents -
try to hijack the agent into privileged tool calls (send email, share files,
delete, create mail rules, write files). Four gate conditions sit at the
permission junction: none, static rules, an LLM judge, and the official
three-value decision-model gate (approve / block / review on question
probabilities with fixed thresholds, fail-closed).

The measured questions:

1. When the injection has already captured the model's reasoning, does the
   gate at the call boundary still stop the privileged action?
2. Does it depend on where each framework lets the gate live?
3. What do the gates cost in false blocks, review deferrals, and latency?

The corpus also carries 25 benign tasks (legitimate external sends with
approved tickets, internal shares, small deletions) to measure what the
gates break on the way.

## Layout

- `SPEC.md` - the full experiment spec (testbed, gates, runner, analyzer)
- `corpus/environment.yaml` - the evidence corpus: users, policy, tickets,
  files, mailboxes
- `corpus/attacks.yaml` - 50 injection scenarios across 5 categories and
  3 sophistication tiers
- `corpus/benign.yaml` - 25 legitimate tasks (false-block control)

## Status

Implementation complete; validated by live smoke runs on all three
frameworks. The first full grid is running: 900 runs (3 frameworks x 4
conditions x 50 attacks + 25 benign, seed 1) plus a 450-run scripted
baseline. Results land in `traces/*.jsonl`; `scripts/summarize.py` renders
the table (per-cell n and error counts included, never hidden).

```
uv venv --python 3.12 .venv && uv pip install -e ".[all,test]"
cp config/local.example.toml config/local.toml   # model ids + key env names
python -m gate_bench.run_grid --frameworks strands langgraph crewai \
    --conditions none static llm_judge jev --seeds 1 --batch grid-v1 --workers 6
python scripts/summarize.py traces/grid-v1.jsonl
python -m pytest tests/ -q
```

Model ids, endpoints and key env-var names are experiment inputs read from
`config/local.toml` (gitignored) - the agent model, the judge model and the
jev decision endpoint are all swappable. The gates refuse to run without a
real key and fail closed on API errors; they never fall back to a
heuristic.

Known limitation, measured not assumed: the scripted (no-LLM) adapter is a
plumbing baseline. Its instruction-following is regex-keyed, so across the
50 attack scenarios it attempted zero privileged calls - 0% attack success
by construction, not by defense. Its benign runs still carry signal: the
static gate produced zero false blocks on the legitimate privileged calls
it did make. Attack numbers must come from the framework agents.

## Attribution anchors

The attack taxonomy follows the shapes used by the indirect-injection
benchmark literature (tool-integrated agents, untrusted content channels,
attack success measured on executed actions), and the decision-model gate
follows the vendor's official per-call gate recipe (thresholded question
probabilities, fail-closed, reasons logged).

## License

MIT
