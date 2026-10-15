"""gate-bench CrewAI agent adapter: real single-agent crew on an
OpenAI-compatible endpoint (OpenRouter)."""
from __future__ import annotations

from typing import Any, Callable

from gate_bench.adapters._common import SYSTEM_PROMPT, agent_config, make_plain_tools


def run_agent(task: str, tools: dict[str, Callable[..., Any]],
              llm: Any = None, config_path: str | None = None) -> list[dict[str, Any]]:
    """Run a CrewAI agent; the runner scores from the testbed call log."""
    model_id, base_url, key = agent_config(config_path)

    try:
        from crewai import Agent as CrewAgent, Crew, LLM, Task as CrewTask
        from crewai.tools import tool as crew_tool
    except ImportError as e:
        raise ImportError(
            "CrewAI is not installed. Install it with: pip install crewai"
        ) from e

    crew_llm = LLM(model=f"openai/{model_id}", base_url=base_url, api_key=key,
                   temperature=0.2, max_retries=8, timeout=120.0, max_tokens=2000)
    crew_tools = [crew_tool(func.__name__)(func) for func in make_plain_tools(tools)]
    agent = CrewAgent(
        role="Executive assistant",
        goal="Complete the user's task using the available tools.",
        backstory=SYSTEM_PROMPT,
        tools=crew_tools,
        llm=crew_llm,
        verbose=False,
    )
    crew_task = CrewTask(
        description=task,
        expected_output="A short statement of what was done.",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[crew_task], verbose=False)
    result = crew.kickoff()
    return [{"tool": "_final", "args": {}, "gate_decision": "approve",
             "gate_reason": "adapter", "gate_latency_ms": 0.0,
             "executed": True, "result": {"text": str(result)}}]
