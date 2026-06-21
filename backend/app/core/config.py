from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "Fact-Verification Engine"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql+asyncpg://fve:fve_secret@localhost:5432/fve"
    database_echo: bool = False

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j_secret"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 3600

    # LLM
    llm_provider: str = "anthropic"  # anthropic | openai
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    llm_model: str = "claude-haiku-4-5"
    teacher_model: str = "claude-haiku-4-5"
    student_model: str = "microsoft/phi-2"
    base_skeptic_model: str = "claude-haiku-4-5"
    finetuned_skeptic_model: str = "claude-sonnet-4-5"
    use_local_skeptic: bool = True  # false = API-only finetuned path (e.g. Sonnet vs Haiku demo)
    llm_temperature: float = 0.1
    use_mock_llm: bool = True  # Use deterministic mock when no API key

    # Embeddings & Reranking
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    embedding_dimension: int = 384

    # Retrieval
    retrieval_top_k: int = 20
    rerank_top_k: int = 5
    min_relevance_score: float = 0.35  # sigmoid-normalized cross-encoder threshold
    bm25_k1: float = 1.5
    bm25_b: float = 0.75
    rrf_k: int = 60

    # Confidence & Escalation
    human_review_threshold: float = 0.6
    training_confidence_threshold: float = 0.85
    duplicate_similarity_threshold: float = 0.92

    # MLflow
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_name: str = "skeptic-finetuning"

    # Evaluation
    benchmark_path: str = "data/benchmark/debates.json"
    benchmark_max_samples: int = 15  # 0 = full set (55); lower = faster demo runs
    adversarial_max_claims: int = 5  # 0 = all (15); 5 = one seed, ~20s with concurrency
    eval_concurrency: int = 5  # parallel LLM calls during eval
    adversarial_miss_rate_threshold: float = 0.15

    # Fine-tuning
    finetuned_skeptic_path: str = "data/models/skeptic-lora"
    use_finetuned_skeptic: bool = False
    training_data_dir: str = "data/training"
    training_block_miss_rate_threshold: float = 0.35  # block QLoRA when eval miss rate exceeds this
    training_min_samples: int = 3  # minimum JSONL rows before fine-tune is allowed


@lru_cache
def get_settings() -> Settings:
    return Settings()
