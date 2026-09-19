from datetime import date
from types import SimpleNamespace
from typing import Any

import numpy as np

from backend.agent.qa import AnswerCitation, CorpusQA, GroundedAnswer
from backend.ingestion.schema import PaperRecord


class MappingEmbedder:
    def embed(self, texts: list[str]) -> np.ndarray[Any, Any]:
        vectors = {
            "How are agents attacked?": [1.0, 0.0],
            "Prompt injection manipulates tool-using agents through untrusted documents.": [
                1.0,
                0.0,
            ],
            "Image classifiers can be affected by imperceptible pixel perturbations.": [0.0, 1.0],
        }
        return np.asarray([vectors[text] for text in texts], dtype=np.float32)


class FakeModels:
    def __init__(self, response: GroundedAnswer) -> None:
        self.response = response

    def generate_content(self, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(parsed=self.response, text="")


def paper(canonical_id: str, title: str, abstract: str) -> PaperRecord:
    return PaperRecord(
        canonical_id=canonical_id,
        title=title,
        abstract=abstract,
        authors=["Researcher"],
        published_date=date(2026, 9, 19),
        source_ids={"arxiv": canonical_id},
        source_urls={"arxiv": f"https://example.test/{canonical_id}"},
    )


def test_corpus_qa_retrieves_and_validates_grounded_answer() -> None:
    agent_paper = paper(
        "paper:agent",
        "Agent Injection",
        "Prompt injection manipulates tool-using agents through untrusted documents.",
    )
    vision_paper = paper(
        "paper:vision",
        "Vision Attack",
        "Image classifiers can be affected by imperceptible pixel perturbations.",
    )
    generated = GroundedAnswer(
        answer="Prompt injection manipulates tool-using agents through untrusted documents.",
        citations=[
            AnswerCitation(
                canonical_id="paper:agent",
                title="Agent Injection",
                claim=(
                    "Prompt injection manipulates tool-using agents through untrusted documents."
                ),
                source_span=(
                    "Prompt injection manipulates tool-using agents through untrusted documents."
                ),
            )
        ],
    )
    qa = CorpusQA(
        embedder=MappingEmbedder(),
        api_key="test-key",
        model="test-model",
        top_k=1,
        client=SimpleNamespace(models=FakeModels(generated)),
    )

    answer = qa.ask("How are agents attacked?", [vision_paper, agent_paper])

    assert answer.retrieved_paper_ids == ["paper:agent"]
    assert answer.citations[0].source_url == "https://example.test/paper:agent"


def test_corpus_qa_rejects_span_from_outside_abstract() -> None:
    target = paper(
        "paper:agent",
        "Agent Injection",
        "Prompt injection manipulates tool-using agents through untrusted documents.",
    )
    generated = GroundedAnswer(
        answer="The paper proves every agent is secure against all attacks.",
        citations=[
            AnswerCitation(
                canonical_id="paper:agent",
                title="Agent Injection",
                claim="The paper proves every agent is secure against all attacks.",
                source_span="The paper proves every agent is secure against all attacks.",
            )
        ],
    )
    qa = CorpusQA(
        embedder=MappingEmbedder(),
        api_key="test-key",
        model="test-model",
        top_k=1,
        max_attempts=1,
        client=SimpleNamespace(models=FakeModels(generated)),
    )

    try:
        qa.ask("How are agents attacked?", [target])
    except ValueError as exc:
        assert "not supported" in str(exc)
    else:
        raise AssertionError("ungrounded answer should be rejected")
