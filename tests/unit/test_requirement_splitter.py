import pytest

from testgen.ingestion.requirement_splitter import split_into_candidate_requirements


@pytest.mark.unit
def test_splits_paragraphs_containing_requirement_keywords() -> None:
    text = (
        "Introduction\n\nThis document describes the pump.\n\n"
        "REQ-001: The system shall stop infusion within 500ms of an occlusion alarm.\n\n"
        "3.2.1 The system must log every alarm event with a timestamp.\n\n"
        "Appendix: revision history."
    )

    candidates = split_into_candidate_requirements(text)

    assert len(candidates) == 2
    assert candidates[0].external_ref == "REQ-001"
    assert candidates[0].text.startswith("The system shall stop infusion")
    assert candidates[1].external_ref == "3.2.1"
    assert candidates[1].text.startswith("The system must log")


@pytest.mark.unit
def test_span_offsets_point_back_into_the_original_text() -> None:
    text = "Notes.\n\nREQ-1: The device shall beep on error."

    [candidate] = split_into_candidate_requirements(text)

    assert (
        text[candidate.span_start : candidate.span_end] == "REQ-1: The device shall beep on error."
    )


@pytest.mark.unit
def test_no_requirement_keyword_yields_no_candidates() -> None:
    text = "Just some background context.\n\nNo modal verbs here."

    assert split_into_candidate_requirements(text) == []


@pytest.mark.unit
def test_paragraph_without_identifier_has_empty_external_ref() -> None:
    [candidate] = split_into_candidate_requirements("The pump shall alarm on occlusion.")

    assert candidate.external_ref == ""
    assert candidate.text == "The pump shall alarm on occlusion."
