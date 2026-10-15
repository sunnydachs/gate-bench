"""gate-bench LangGraph agent adapter: real create_react_agent loop on an
OpenAI-compatible endpoint (an inference provider)."""
from __future__ import annotations

from typing import Any, Callable

from gate_bench.adapters._common import SYSTEM_PROMPT, agent_config, make_plain_tools


def run_agent(task: str, tools: dict[str, Callable[..., Any]],
              llm: Any = None, config_path: str | None = None) -> list[dict[str, Any]]:
    """Run a LangGraph ReAct agent; the runner scores from the testbed call log."""
    model_id, base_url, key = agent_config(config_path)

    try:
        from langchain_core.tools import tool as lc_tool
        from langchain_openai import ChatOpenAI
        from langgraph.prebuilt import create_react_agent
    except ImportError as e:
        raise ImportError(
            "LangGraph is not installed. Install it with: pip install langgraph langchain-openai"
        ) from e

    chat = ChatOpenAI(model=model_id, base_url=base_url, api_key=key,
                      temperature=0.2)
    lc_tools = [lc_tool(func) for func in make_plain_tools(tools)]
    agent = create_react_agent(chat, lc_tools, prompt=SYSTEM_PROMPT)
    state = agent.invoke({"messages": [("user", task)]})
    messages = state.get("messages", [])
    text = str(messages[-1].content) if messages else ""
    return [{"tool": "_final", "args": {}, "gate_decision": "approve",
             "gate_reason": "adapter", "gate_latency_ms": 0.0,
             "executed": True, "result": {"text": text}}]
