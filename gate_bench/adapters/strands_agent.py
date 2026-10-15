"""gate-bench Strands agent adapter: real Strands agent on an
OpenAI-compatible endpoint (an inference provider)."""
from __future__ import annotations

from typing import Any, Callable

from gate_bench.adapters._common import SYSTEM_PROMPT, agent_config, make_plain_tools


def run_agent(task: str, tools: dict[str, Callable[..., Any]],
              llm: Any = None, config_path: str | None = None) -> list[dict[str, Any]]:
    """Run a Strands agent; the runner scores from the testbed call log."""
    model_id, base_url, key = agent_config(config_path)

    try:
        from strands import Agent
        from strands.models.openai import OpenAIModel
    except ImportError as e:
        raise ImportError(
            "Strands is not installed. Install it with: pip install strands-agents"
        ) from e

    model = OpenAIModel(
        client_args={"api_key": key, "base_url": base_url,
                     "max_retries": 8, "timeout": 120.0},
        model_id=model_id,
        params={"temperature": 0.2, "max_tokens": 2000},
    )
    try:
        from strands.tools import tool as strands_tool
    except ImportError as e:
        raise ImportError("strands.tools.tool not available in this strands version") from e
    agent = Agent(model=model,
                  tools=[strands_tool(func) for func in make_plain_tools(tools)],
                  system_prompt=SYSTEM_PROMPT)
    try:
        result = agent(task)
    except Exception as e:
        # A max-token stop is a harness cap, not a failed experiment: the
        # tool calls already happened and were logged, so keep the run.
        if "maximum token" in str(e).lower():
            return [{"tool": "_final", "args": {}, "gate_decision": "approve",
                     "gate_reason": "adapter", "gate_latency_ms": 0.0,
                     "executed": True,
                     "result": {"text": f"stopped at token cap: {e}"}}]
        raise
    text = getattr(getattr(result, "message", None), "content", None) or str(result)
    return [{"tool": "_final", "args": {}, "gate_decision": "approve",
             "gate_reason": "adapter", "gate_latency_ms": 0.0,
             "executed": True, "result": {"text": str(text)}}]
