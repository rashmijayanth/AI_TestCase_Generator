"""Deterministic, rule-based splitting of normalized text into candidate requirements.

This is the "requirement-parser" tool the Requirement Analyst agent (generation
phase, DESIGN.md §3) uses as a starting point — intentionally mechanical
(paragraph + keyword regex), not LLM-based. The agent does the semantic
disambiguation and IEC 62304 safety classification on top of what this produces;
this module only needs to get candidate requirement boundaries roughly right.
"""

import re
from dataclasses import dataclass

_REQUIREMENT_KEYWORD = re.compile(r"\b(shall|must|should|will)\b", re.IGNORECASE)
_LEADING_IDENTIFIER = re.compile(r"^\s*([A-Z][A-Z0-9]*-\d+|\d+(?:\.\d+)+)[:.]?\s+")


@dataclass(frozen=True)
class CandidateRequirement:
    text: str
    span_start: int
    span_end: int
    external_ref: str = ""


def split_into_candidate_requirements(text: str) -> list[CandidateRequirement]:
    """Splits on blank lines into paragraphs, keeps ones containing a requirement
    modal keyword, and extracts a leading identifier (e.g. "REQ-001" or "3.2.1")
    into external_ref when present. Span offsets point back into `text`.
    """
    candidates: list[CandidateRequirement] = []
    cursor = 0
    for paragraph in text.split("\n\n"):
        start = text.index(paragraph, cursor)
        end = start + len(paragraph)
        cursor = end

        stripped = paragraph.strip()
        if not stripped or not _REQUIREMENT_KEYWORD.search(stripped):
            continue

        external_ref = ""
        body = stripped
        match = _LEADING_IDENTIFIER.match(stripped)
        if match:
            external_ref = match.group(1)
            body = stripped[match.end() :].strip()

        candidates.append(
            CandidateRequirement(
                text=body, span_start=start, span_end=end, external_ref=external_ref
            )
        )
    return candidates
