import pytest

from testgen.knowledge.embeddings import DeterministicFakeEmbedder, GeminiEmbedder, _extract_vectors


@pytest.mark.unit
def test_fake_embedder_is_deterministic() -> None:
    embedder = DeterministicFakeEmbedder(dimension=16)

    v1 = embedder.embed(["The pump shall alarm on occlusion."])[0]
    v2 = embedder.embed(["The pump shall alarm on occlusion."])[0]

    assert v1 == v2
    assert len(v1) == 16


@pytest.mark.unit
def test_fake_embedder_differs_for_different_text() -> None:
    embedder = DeterministicFakeEmbedder(dimension=16)

    v1, v2 = embedder.embed(["First requirement.", "A completely different requirement."])

    assert v1 != v2


@pytest.mark.unit
def test_fake_embedder_values_are_bounded() -> None:
    embedder = DeterministicFakeEmbedder(dimension=32)

    [vector] = embedder.embed(["Some text."])

    assert all(-1.0 <= value <= 1.0 for value in vector)


@pytest.mark.unit
def test_gemini_embedder_requires_api_key() -> None:
    with pytest.raises(ValueError, match="required"):
        GeminiEmbedder(api_key="")


@pytest.mark.unit
def test_extract_vectors_maps_sdk_response_shape() -> None:
    """Verifies our mapping of the google-genai SDK's response shape -- NOT a
    live test of the real API (no credentials available in this environment;
    see docs/PROGRESS.md). The shape itself was confirmed by introspecting the
    installed google-genai 2.20.0 SDK's EmbedContentResponse/ContentEmbedding.
    """

    class FakeEmbedding:
        def __init__(self, values: list[float]) -> None:
            self.values = values

    class FakeResult:
        def __init__(self, embeddings: list[FakeEmbedding]) -> None:
            self.embeddings = embeddings

    result = FakeResult([FakeEmbedding([0.1, 0.2]), FakeEmbedding([0.3, 0.4])])

    assert _extract_vectors(result) == [[0.1, 0.2], [0.3, 0.4]]


@pytest.mark.unit
def test_extract_vectors_handles_empty_result() -> None:
    class FakeResult:
        embeddings: None = None

    assert _extract_vectors(FakeResult()) == []
