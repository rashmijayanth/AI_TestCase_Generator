"""Integration test: run_generation_for_requirement against the real Postgres
container, real persistent checkpointer, real Milvus Lite corpus, and a
scripted LLM.

Uses session_scope() (a real, committing session) for setup/teardown rather
than the rolled-back db_session fixture: the function under test reads the
Requirement via its own separate session_scope() call, which -- under Postgres's
READ COMMITTED isolation -- cannot see uncommitted rows from a different,
still-open transaction, no matter that both ultimately share the same cached
engine. Cleans up explicitly afterward since nothing here auto-rolls-back.
"""

import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import delete

from testgen.generation.agents import AgentDeps
from testgen.ingestion.models import Requirement, SourceDocument
from testgen.knowledge.corpus import seed_regulatory_corpus
from testgen.knowledge.embeddings import EMBEDDING_DIMENSION, DeterministicFakeEmbedder
from testgen.knowledge.vector_store import MilvusVectorStore
from testgen.platform.db.session import session_scope
from testgen.platform.enums import DocumentFormat, RequirementStatus
from testgen.platform.models import Organization, Project
from testgen.worker.tasks import run_generation_for_requirement
from tests.fakes import ScriptedChatModelFactory, UnusedEmbedder, UnusedVectorStore
from testgen.generation.agents import AgentDeps
from testgen.generation.models import LLMGenerationRun

_ANALYSIS_RESPONSE = '{"safety_class": "C", "rationale": "Failure could delay treatment."}'
_SUFFICIENT_RESPONSE = '{"sufficient": true, "refined_query": ""}'
_PLAN_RESPONSE = (
    '{"test_types": ["safety_critical"], "rationale": "Class C needs failure-mode coverage."}'
)
_TEST_CASE_RESPONSE = (
    '{"test_cases": [{"title": "Occlusion alarm stops infusion", "test_type": "safety_critical", '
    '"preconditions": "Pump running", "steps": [{"step_no": 1, "action": "Trigger occlusion", '
    '"expected": "Halts within 500ms"}], "expected_result": "Halts", "priority": "critical"}]}'
)
_APPROVED_RESPONSE = '{"approved": true, "feedback": "", "cited_clause_refs": ["5.5.3"]}'


@pytest.fixture
def committed_requirement() -> Iterator[Requirement]:
    with session_scope() as session:
        org = Organization(name=f"Acme Health {uuid.uuid4()}")
        session.add(org)
        session.flush()
        project = Project(organization_id=org.id, name="Infusion Pump Firmware")
        session.add(project)
        session.flush()
        doc = SourceDocument(
            project_id=project.id,
            filename="srs.md",
            file_format=DocumentFormat.MARKDOWN,
            checksum="a" * 64,
            storage_key="k",
        )
        session.add(doc)
        session.flush()
        requirement = Requirement(
            source_document_id=doc.id,
            project_id=project.id,
            external_ref="REQ-001",
            text="The pump shall stop infusion within 500ms of an occlusion alarm.",
            status=RequirementStatus.CLASSIFIED,
        )
        session.add(requirement)
        session.flush()
        requirement_id, document_id, project_id, org_id = (
            requirement.id,
            doc.id,
            project.id,
            org.id,
        )

    yield requirement

    with session_scope() as session:
        # llm_generation_runs has no ON DELETE CASCADE from requirement_id
        # (same as every other FK to requirements.id in this codebase --
        # compliance.models, traceability.models) -- delete child rows first.
        # This fixture is the first to actually populate that table, since
        # nothing wrote to it before persist_llm_usage existed.
        session.execute(
            delete(LLMGenerationRun).where(LLMGenerationRun.requirement_id == requirement_id)
        )
        session.execute(delete(Requirement).where(Requirement.id == requirement_id))
        session.execute(delete(SourceDocument).where(SourceDocument.id == document_id))
        session.execute(delete(Project).where(Project.id == project_id))
        session.execute(delete(Organization).where(Organization.id == org_id))


@pytest.mark.integration
def test_run_generation_for_requirement_reaches_human_approval(
    committed_requirement: Requirement, tmp_path: Path
) -> None:
    embedder = DeterministicFakeEmbedder(dimension=EMBEDDING_DIMENSION)
    store = MilvusVectorStore(uri=str(tmp_path / "worker_test.db"), dimension=EMBEDDING_DIMENSION)
    seed_regulatory_corpus(embedder, store)
    factory = ScriptedChatModelFactory(
        {
            "RequirementAnalysisOutput": [_ANALYSIS_RESPONSE],
            "SufficiencyCheckOutput": [_SUFFICIENT_RESPONSE],
            "TestPlanOutput": [_PLAN_RESPONSE],
            "TestCaseGeneratorOutput": [_TEST_CASE_RESPONSE],
            "ComplianceCritiqueOutput": [_APPROVED_RESPONSE],
        }
    )
    deps = AgentDeps(chat_model_factory=factory, embedder=embedder, vector_store=store)

    result = run_generation_for_requirement(str(committed_requirement.id), deps=deps)

    assert result["awaiting_approval"] is True
    assert result["safety_class"] == "C"


@pytest.mark.integration
def test_run_generation_for_requirement_raises_for_unknown_requirement() -> None:
    # The requirement lookup fails before any node runs, so deps are never
    # touched -- these fakes raise loudly if that assumption is ever wrong.
    deps = AgentDeps(
        chat_model_factory=ScriptedChatModelFactory({}),
        embedder=UnusedEmbedder(),
        vector_store=UnusedVectorStore(),
    )

    with pytest.raises(ValueError, match="No such requirement"):
        run_generation_for_requirement(str(uuid.uuid4()), deps=deps)
