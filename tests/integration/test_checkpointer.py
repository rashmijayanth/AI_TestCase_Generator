"""Integration test: postgres_checkpointer against the real local Postgres
container. Confirms setup() succeeds and, critically, that a paused interrupt
genuinely survives across two SEPARATE checkpointer instances/connections --
simulating the real scenario this exists for: the request that triggers
generation and the later, separate request where a human approves it are not
the same process. First verified manually with a throwaway script before
writing this wrapper (see docs/PROGRESS.md); this is that same verification,
now a real, permanent, automated test.
"""

from typing import Any, TypedDict

import pytest
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from testgen.generation.checkpointer import postgres_checkpointer


class _State(TypedDict):
    value: int
    approved: bool | None


def _worker(state: _State) -> dict[str, Any]:
    return {"value": state["value"] + 1}


def _human(state: _State) -> dict[str, Any]:
    decision = interrupt({"current_value": state["value"]})
    return {"approved": bool(decision.get("approved"))}


def _build_graph(checkpointer: PostgresSaver) -> Any:
    graph = StateGraph(_State)
    graph.add_node("worker", _worker)
    graph.add_node("human", _human)
    graph.add_edge(START, "worker")
    graph.add_edge("worker", "human")
    graph.add_edge("human", END)
    return graph.compile(checkpointer=checkpointer)


@pytest.mark.integration
def test_postgres_checkpointer_setup_succeeds() -> None:
    with postgres_checkpointer() as checkpointer:
        assert isinstance(checkpointer, PostgresSaver)


@pytest.mark.integration
def test_interrupt_survives_across_separate_checkpointer_connections() -> None:
    config = {"configurable": {"thread_id": "checkpointer-test-thread"}}

    with postgres_checkpointer() as checkpointer:
        graph = _build_graph(checkpointer)
        result = graph.invoke({"value": 0, "approved": None}, config)
        assert "__interrupt__" in result

    # A brand new checkpointer/connection -- simulating a wholly separate
    # process resuming later, exactly the real API-then-worker-then-API
    # scenario this module exists for.
    with postgres_checkpointer() as checkpointer2:
        graph2 = _build_graph(checkpointer2)
        pending = graph2.get_state(config)
        assert pending.next == ("human",)

        final = graph2.invoke(Command(resume={"approved": True}), config)
        assert final == {"value": 1, "approved": True}
