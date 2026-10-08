"""Per-project LLM cost/token usage view (closes the observability gap
docs/PROGRESS.md's Decision log flags: llm_generation_runs existed in the
schema from Phase 1 but nothing populated or surfaced it until now).
"""

import uuid
from typing import Any

from fastapi import APIRouter

from testgen.api.deps import CurrentUser, DbSession
from testgen.api.routers.documents import get_owned_project
from testgen.generation.orchestration import project_llm_usage_summary

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["usage"])


@router.get("/llm-usage")
def llm_usage(project_id: uuid.UUID, user: CurrentUser, db: DbSession) -> list[dict[str, Any]]:
    get_owned_project(db, user, project_id)
    rows = project_llm_usage_summary(db, project_id=project_id)
    return [
        {
            "agent_name": row.agent_name,
            "call_count": row.call_count,
            "total_input_tokens": row.total_input_tokens,
            "total_output_tokens": row.total_output_tokens,
            "total_cost_usd": row.total_cost_usd,
            "avg_latency_ms": row.avg_latency_ms,
        }
        for row in rows
    ]
