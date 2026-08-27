"""The LangGraph StateGraph wiring DESIGN.md §3's seven agents into a fixed,
deterministic topology -- not a free-form agent conversation. The only bounded
non-determinism is the Compliance Critic -> Test Case Generator retry loop
(gated by max_retries) and the Regulatory Researcher's own internal retrieval
loop (inside its node, not visible at the graph level).

Human approval is a genuine LangGraph `interrupt()`: the graph cannot reach
`traceability_agent`/END without a resume value being supplied from outside.
Uses InMemorySaver here (Phase 4's own tests only need a checkpointer to exist,
not to survive a process restart) -- Phase 7 (API/worker) should swap in a
persistent, Postgres-backed checkpointer, since a real deployment needs the
paused interrupt to survive between the request that triggers generation and
the later request where a human actually approves it.
"""

from functools import partial
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from testgen.generation.agents import (
    AgentDeps,
    case_generator_node,
    compliance_critic_node,
    data_synthesizer_node,
    regulatory_researcher_node,
    requirement_analyst_node,
    strategist_node,
    traceability_agent_node,
)
from testgen.generation.state import GenerationState


def human_approval_node(state: GenerationState, *, deps: AgentDeps) -> dict[str, Any]:
    del deps  # this node needs no LLM/retrieval access, kept for a uniform signature
    decision = interrupt(
        {
            "requirement_text": state["requirement_text"],
            "safety_class": state["safety_class"],
            "draft_test_cases": state["draft_test_cases"],
            "draft_test_datasets": state["draft_test_datasets"],
            "critic_approved": state["critic_approved"],
            "critic_feedback": state["critic_feedback"],
        }
    )
    return {
        "human_approved": bool(decision.get("approved", False)),
        "human_approver_id": decision.get("approver_id"),
    }


def route_after_critic(state: GenerationState) -> str:
    if state["critic_approved"] or state["retry_count"] >= state["max_retries"]:
        return "human_approval"
    return "test_case_generator"


def build_generation_graph(
    deps: AgentDeps, checkpointer: BaseCheckpointSaver[Any] | None = None
) -> CompiledStateGraph[GenerationState, None, GenerationState, GenerationState]:
    graph: StateGraph[GenerationState, None, GenerationState, GenerationState] = StateGraph(
        GenerationState
    )

    graph.add_node("requirement_analyst", partial(requirement_analyst_node, deps=deps))
    graph.add_node("regulatory_researcher", partial(regulatory_researcher_node, deps=deps))
    graph.add_node("test_strategist", partial(strategist_node, deps=deps))
    graph.add_node("test_case_generator", partial(case_generator_node, deps=deps))
    graph.add_node("test_data_synthesizer", partial(data_synthesizer_node, deps=deps))
    graph.add_node("compliance_critic", partial(compliance_critic_node, deps=deps))
    graph.add_node("human_approval", partial(human_approval_node, deps=deps))
    graph.add_node("traceability_agent", partial(traceability_agent_node, deps=deps))

    graph.add_edge(START, "requirement_analyst")
    graph.add_edge("requirement_analyst", "regulatory_researcher")
    graph.add_edge("regulatory_researcher", "test_strategist")
    graph.add_edge("test_strategist", "test_case_generator")
    graph.add_edge("test_case_generator", "test_data_synthesizer")
    graph.add_edge("test_data_synthesizer", "compliance_critic")
    graph.add_conditional_edges(
        "compliance_critic", route_after_critic, ["test_case_generator", "human_approval"]
    )
    graph.add_edge("human_approval", "traceability_agent")
    graph.add_edge("traceability_agent", END)

    return graph.compile(checkpointer=checkpointer)
