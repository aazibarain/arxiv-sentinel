"""Runtime configuration and domain reference material."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str | None = None
    openalex_mailto: str | None = None
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    relevance_threshold: float = Field(default=0.50, ge=-1.0, le=1.0)
    source_request_timeout_seconds: float = Field(default=30.0, gt=0)
    chroma_path: Path = Path("data/chroma")
    chroma_collection: str = "arxiv_sentinel_papers"
    novelty_incremental_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    novelty_duplicate_threshold: float = Field(default=0.92, ge=0.0, le=1.0)
    novelty_top_k: int = Field(default=5, ge=1, le=100)
    gemini_model: str = "gemini-3.5-flash-lite"
    summary_max_attempts: int = Field(default=3, ge=1, le=5)
    grounding_span_similarity_threshold: float = Field(default=0.90, ge=0.5, le=1.0)
    dedupe_title_similarity_threshold: float = Field(default=0.90, ge=0.0, le=1.0)
    dedupe_author_overlap_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    dedupe_date_window_days: int = Field(default=30, ge=0, le=365)
    digest_db_path: Path = Path("data/arxiv_sentinel.db")
    qa_top_k: int = Field(default=5, ge=1, le=10)
    qa_max_attempts: int = Field(default=3, ge=1, le=5)
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        """Return configured browser origins without accepting wildcard credentials."""

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process."""

    return Settings()


# These are embedded once and act as positive semantic prototypes. They deliberately
# cover both classical adversarial ML and modern generative-AI security.
AI_SECURITY_REFERENCE_TOPICS: tuple[str, ...] = (
    "Adversarial examples designed to evade image, audio, or text classifiers.",
    "Defenses and certified robustness guarantees against adversarial perturbations.",
    "Data poisoning and backdoor attacks against machine learning training pipelines.",
    "Model extraction, model stealing, and intellectual-property attacks on AI systems.",
    "Membership inference and training-data reconstruction attacks on learned models.",
    "Privacy leakage and unintended memorization in foundation models.",
    "Prompt injection attacks that manipulate large language model applications.",
    "Jailbreak attacks and alignment bypasses against large language models.",
    "Indirect prompt injection through tools, retrieval systems, or external content.",
    "Security of autonomous AI agents that call tools or act on external systems.",
    "Adversarial attacks on retrieval-augmented generation and vector databases.",
    "Supply-chain attacks involving machine learning models, datasets, or checkpoints.",
    "Detection and mitigation of malicious or deceptive model behavior.",
    "Red teaming, safety evaluation, and security benchmarks for generative AI.",
    "Robustness of multimodal and embodied AI systems under adversarial inputs.",
)


# Source APIs need a broad retrieval query; the semantic filter remains the final
# judge. Multiple short queries are used because no provider exposes a reliable
# unfiltered stream of every daily AI paper.
DISCOVERY_QUERIES: tuple[str, ...] = (
    "adversarial machine learning",
    "AI security",
    "language model security",
    "machine learning privacy",
)
