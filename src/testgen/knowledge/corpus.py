"""Seeded regulatory corpus for RAG grounding.

IMPORTANT: these clause entries are original, illustrative paraphrases written
for this portfolio demo -- NOT verbatim text from the official standards. ISO
and IEC standards are copyrighted and sold by those bodies; a real product
would license the official text rather than embed paraphrased summaries here.
FDA regulations (21 CFR) and the GDPR are public-domain legal text, but these
entries are still paraphrased, not quoted, since exact wording isn't
reproduced here from a verified primary source. clause_ref values are
illustrative section numbers, chosen to look plausible, not guaranteed to
match the real numbering in every edition of each standard.
"""

from dataclasses import dataclass

from testgen.knowledge.embeddings import EmbeddingPort
from testgen.knowledge.vector_store import ClauseRecord, VectorStorePort, stable_clause_id
from testgen.platform.enums import Standard


@dataclass(frozen=True)
class SeedClause:
    standard: Standard
    clause_ref: str
    text: str


SEED_CORPUS: list[SeedClause] = [
    # FDA (21 CFR Part 820 / Part 11 -- public-domain federal regulation, paraphrased)
    SeedClause(
        Standard.FDA,
        "820.30(g)",
        "Design validation shall demonstrate that device specifications conform to "
        "user needs and intended uses, performed under defined operating conditions "
        "using initial production units or their equivalents.",
    ),
    SeedClause(
        Standard.FDA,
        "820.30(i)",
        "Design changes shall be identified, documented, verified or validated as "
        "appropriate, and reviewed and approved before implementation.",
    ),
    SeedClause(
        Standard.FDA,
        "11.10",
        "Electronic record systems shall employ procedures and controls, including "
        "validation, secure audit trails, and record retention, sufficient to "
        "ensure the authenticity, integrity, and confidentiality of records.",
    ),
    # IEC 62304 (medical device software life cycle)
    SeedClause(
        Standard.IEC_62304,
        "4.3",
        "The manufacturer shall assign a software safety classification (A, B, or "
        "C) to each software item based on the severity of harm that could result "
        "from a failure of that item.",
    ),
    SeedClause(
        Standard.IEC_62304,
        "5.1.1",
        "A software development plan shall be established and kept up to date, "
        "describing the life-cycle model, activities, and deliverables "
        "appropriate to the software item's safety class.",
    ),
    SeedClause(
        Standard.IEC_62304,
        "5.5.3",
        "Software verification shall include testing of the software item under "
        "normal conditions and under anomalous or boundary conditions appropriate "
        "to its assigned safety classification.",
    ),
    # ISO 9001 (quality management systems)
    SeedClause(
        Standard.ISO_9001,
        "8.3",
        "The organization shall plan, control, and review the design and "
        "development of products and services, including verification and "
        "validation activities appropriate to each stage.",
    ),
    SeedClause(
        Standard.ISO_9001,
        "9.1",
        "The organization shall determine what needs to be monitored and "
        "measured, and shall monitor, analyze, and evaluate the performance and "
        "effectiveness of its quality management system.",
    ),
    SeedClause(
        Standard.ISO_9001,
        "10.2",
        "Nonconformities shall be reacted to and evaluated, with corrective "
        "action taken and root causes analyzed to prevent recurrence.",
    ),
    # ISO 13485 (medical device quality management systems)
    SeedClause(
        Standard.ISO_13485,
        "7.3",
        "Design and development planning shall define stages, required reviews, "
        "verification, validation, and responsibilities, appropriate to the risk "
        "associated with the medical device.",
    ),
    SeedClause(
        Standard.ISO_13485,
        "7.5.6",
        "Where the results of a process cannot be verified by subsequent "
        "monitoring or measurement, the process shall be validated, with records "
        "maintained of the validation results.",
    ),
    SeedClause(
        Standard.ISO_13485,
        "8.2.1",
        "The organization shall establish a documented feedback process, "
        "including post-market surveillance, to provide early warning of "
        "quality problems.",
    ),
    # ISO 27001 (information security management)
    SeedClause(
        Standard.ISO_27001,
        "A.9.1",
        "Access to information and information-processing facilities shall be "
        "restricted in accordance with a documented access control policy based "
        "on business and security requirements.",
    ),
    SeedClause(
        Standard.ISO_27001,
        "A.12.1",
        "Operating procedures shall be documented and made available to all "
        "users who need them, and changes to systems and facilities shall be "
        "controlled.",
    ),
    SeedClause(
        Standard.ISO_27001,
        "A.18.1",
        "The organization shall identify, document, and keep up to date all "
        "applicable legal, regulatory, and contractual requirements relevant to "
        "information security.",
    ),
    # GDPR (public-domain EU regulation, paraphrased)
    SeedClause(
        Standard.GDPR,
        "Art.5",
        "Personal data shall be processed lawfully, fairly, and transparently; "
        "collected for specified, explicit purposes; and kept in identifiable "
        "form no longer than necessary.",
    ),
    SeedClause(
        Standard.GDPR,
        "Art.17",
        "Data subjects have the right to obtain erasure of their personal data "
        "without undue delay under specified conditions (the 'right to be "
        "forgotten').",
    ),
    SeedClause(
        Standard.GDPR,
        "Art.32",
        "Controllers and processors shall implement technical and organizational "
        "measures appropriate to the risk, including, where appropriate, "
        "pseudonymization and encryption of personal data.",
    ),
]


def seed_regulatory_corpus(embedder: EmbeddingPort, store: VectorStorePort) -> int:
    """Embeds and upserts the seed corpus into the vector store.

    Idempotent: each clause's id is a deterministic hash of standard+clause_ref,
    so re-running this just overwrites the same rows in place.
    """
    vectors = embedder.embed([clause.text for clause in SEED_CORPUS])
    records = [
        ClauseRecord(
            clause_id=stable_clause_id(f"{clause.standard.value}:{clause.clause_ref}"),
            standard=clause.standard.value,
            clause_ref=clause.clause_ref,
            text=clause.text,
            vector=vector,
        )
        for clause, vector in zip(SEED_CORPUS, vectors, strict=True)
    ]
    store.upsert_clauses(records)
    return len(records)
