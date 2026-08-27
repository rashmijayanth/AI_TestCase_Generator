"""PHI/PII redaction via Presidio, before any text reaches Gemini (DESIGN.md §7).

Uses en_core_web_sm (small spaCy model, ~13MB) rather than Presidio's default
en_core_web_lg (~560MB) -- much faster to install/load, at some cost to entity-
detection accuracy (confirmed directly: it correctly caught PERSON/DATE_TIME/
PHONE_NUMBER in a manual smoke test, but also mislabeled "DOB" as ORGANIZATION).
Acceptable for a portfolio demo; a production deployment handling real PHI at
scale should evaluate en_core_web_lg or a domain-tuned NER model instead.
"""

from functools import lru_cache
from typing import Any

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

_NLP_CONFIG = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
}


@lru_cache
def _get_analyzer() -> AnalyzerEngine:
    provider = NlpEngineProvider(nlp_configuration=_NLP_CONFIG)
    return AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["en"])


@lru_cache
def _get_anonymizer() -> AnonymizerEngine:
    return AnonymizerEngine()  # type: ignore[no-untyped-call]  # presidio_anonymizer ships a py.typed marker but AnonymizerEngine.__init__ itself has no annotations


def redact_text(text: str) -> str:
    if not text:
        return text
    results = _get_analyzer().analyze(text=text, language="en")
    if not results:
        return text
    # presidio_analyzer.RecognizerResult and presidio_anonymizer's own same-named
    # class are structurally identical (duck-type compatible -- confirmed working
    # end-to-end by manual smoke test) but nominally different classes across the
    # two separately-typed packages, which mypy correctly flags as incompatible.
    return str(
        _get_anonymizer().anonymize(text=text, analyzer_results=results).text  # type: ignore[arg-type]
    )


def redact_dataset_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Redacts string values in each row; non-string values pass through unchanged."""
    return [
        {
            key: (redact_text(value) if isinstance(value, str) else value)
            for key, value in row.items()
        }
        for row in rows
    ]
