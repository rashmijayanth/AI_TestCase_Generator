"""Presidio-based redaction, verified for real (real analyzer+anonymizer+
en_core_web_sm, confirmed working manually before writing this code -- see
docs/PROGRESS.md). Marked integration for consistency with the project's other
"heavier dependency" tests (Milvus Lite), even though nothing runs as a
separate service/container.
"""

import pytest

from testgen.compliance.redaction import redact_dataset_rows, redact_text


@pytest.mark.integration
def test_redact_text_removes_person_and_phone_number() -> None:
    text = "Patient John Smith, phone 555-123-4567, was enrolled on 2026-01-05."

    redacted = redact_text(text)

    assert "John Smith" not in redacted
    assert "555-123-4567" not in redacted
    assert "<PERSON>" in redacted


@pytest.mark.integration
def test_redact_text_leaves_non_pii_text_unchanged() -> None:
    text = "The pump shall stop infusion within 500ms of an occlusion alarm."

    assert redact_text(text) == text


@pytest.mark.integration
def test_redact_text_handles_empty_string() -> None:
    assert redact_text("") == ""


@pytest.mark.integration
def test_redact_dataset_rows_only_touches_string_values() -> None:
    rows = [{"patient_name": "Jane Doe", "delay_ms": 499, "flagged": True}]

    redacted = redact_dataset_rows(rows)

    assert redacted[0]["delay_ms"] == 499
    assert redacted[0]["flagged"] is True
    assert "Jane Doe" not in redacted[0]["patient_name"]
