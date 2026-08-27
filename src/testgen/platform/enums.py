"""Enums shared across bounded contexts (avoids circular imports between them)."""

import enum


class SafetyClass(enum.StrEnum):
    """IEC 62304 software safety classification."""

    A = "A"
    B = "B"
    C = "C"


class DocumentFormat(enum.StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    XML = "xml"
    REQIF = "reqif"
    MARKDOWN = "markdown"


class RequirementStatus(enum.StrEnum):
    EXTRACTED = "extracted"
    CLASSIFIED = "classified"
    NEEDS_REVIEW = "needs_review"


class TestType(enum.StrEnum):
    FUNCTIONAL = "functional"
    NEGATIVE = "negative"
    BOUNDARY = "boundary"
    SAFETY_CRITICAL = "safety_critical"
    PERFORMANCE = "performance"
    SECURITY = "security"
    PRIVACY = "privacy"
    DATA_DRIVEN = "data_driven"


class TestPriority(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TestCaseStatus(enum.StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class Standard(enum.StrEnum):
    FDA = "fda"
    IEC_62304 = "iec_62304"
    ISO_9001 = "iso_9001"
    ISO_13485 = "iso_13485"
    ISO_27001 = "iso_27001"
    GDPR = "gdpr"


class ALMSystem(enum.StrEnum):
    JIRA = "jira"
    AZURE_DEVOPS = "azure_devops"
    POLARION = "polarion"


class SyncStatus(enum.StrEnum):
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"
