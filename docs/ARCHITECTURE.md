# Autonomous Fact-Verification Engine — Architecture

## 1. System Overview

The Fact-Verification Engine verifies factual claims through structured multi-agent debate, hybrid retrieval, and a temporal knowledge graph. It continuously improves by collecting high-quality debate examples and fine-tuning a smaller Skeptic model.

```
┌─────────────┐     ┌──────────────────────────────────────────────────────────┐
│  Next.js    │────▶│                    FastAPI Backend                        │
│  Dashboard  │     │  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐ │
└─────────────┘     │  │   API   │─▶│ Services │─▶│ LangGraph│─▶│  Agents  │ │
                    │  │ Routes  │  │  Layer   │  │ Workflow │  │ A/S/J    │ │
                    │  └─────────┘  └────┬─────┘  └────┬─────┘  └──────────┘ │
                    │                    │              │                      │
                    │         ┌──────────┼──────────────┼──────────┐          │
                    │         ▼          ▼              ▼          ▼          │
                    │   PostgreSQL   Neo4j KG    Retrieval    Training       │
                    │   + pgvector   (temporal)  Pipeline    Pipeline       │
                    │         │          │              │          │          │
                    │         └──────────┴──────────────┴──────────┘          │
                    │                         Redis Cache                      │
                    └──────────────────────────────────────────────────────────┘
```

## 2. Technology Choices

| Technology | Purpose | Rationale |
|------------|---------|-----------|
| **FastAPI** | Backend API | Async-native, OpenAPI auto-docs, type safety, high throughput |
| **Next.js 14** | Frontend | SSR/SSG, React ecosystem, API routes for BFF if needed |
| **PostgreSQL + pgvector** | Primary store + embeddings | ACID, mature, vector similarity for duplicate detection & dense retrieval |
| **Neo4j** | Temporal knowledge graph | Native graph queries, relationship traversal, temporal validity intervals |
| **Redis** | Caching | Sub-ms retrieval cache for evidence, embeddings, session state |
| **LangGraph** | Agent orchestration | Stateful multi-agent workflows, checkpointing, conditional routing |
| **Sentence Transformers** | Embeddings | Open-source, local inference, no API dependency for embeddings |
| **Cross-Encoder** | Reranking | Superior precision vs bi-encoder alone for top-k evidence |
| **MLflow** | Experiment tracking | Model versioning, metrics, artifact storage for fine-tuning |
| **Docker** | Deployment | Independent service deployability, reproducible environments |

## 3. Module Structure

```
backend/
├── app/
│   ├── api/v1/           # REST endpoints (thin controllers)
│   ├── core/             # Config, dependencies, exceptions
│   ├── domain/           # Business entities & interfaces (ports)
│   ├── services/         # Application services (use cases)
│   ├── agents/           # Advocate, Skeptic, Judge + prompts
│   ├── retrieval/        # Dense, sparse, fusion, reranker
│   ├── knowledge_graph/  # Neo4j temporal KG operations
│   ├── workflows/        # LangGraph verification pipeline
│   ├── training/         # Dataset builder, fine-tuning, duplicate detection
│   ├── evaluation/       # Benchmark, metrics, adversarial generator
│   ├── db/               # SQLAlchemy models, repositories
│   └── schemas/          # Pydantic request/response models
frontend/
├── src/
│   ├── app/              # Next.js App Router pages
│   ├── components/       # UI components
│   ├── lib/              # API client, utilities
│   └── types/            # TypeScript types
```

## 4. Data Flow — Claim Verification Pipeline

```
1. POST /api/v1/verify
   └─▶ VerificationService.verify_claim(claim_text)
       ├─▶ ClaimExtractionService.extract_atomic_claims()
       │   └─▶ Store AtomicClaims in PostgreSQL
       ├─▶ KnowledgeGraphService.upsert_claims()
       │   └─▶ Create/update nodes & edges in Neo4j (contradictions → unresolved)
       ├─▶ For each atomic claim:
       │   ├─▶ HybridRetrievalService.retrieve(query)
       │   │   ├─▶ DenseRetriever (pgvector cosine)
       │   │   ├─▶ SparseRetriever (BM25 via rank_bm25)
       │   │   ├─▶ ScoreFusion (RRF)
       │   │   └─▶ CrossEncoderReranker
       │   └─▶ If no evidence → verdict = INSUFFICIENT_EVIDENCE
       ├─▶ LangGraph Workflow:
       │   ├─▶ AdvocateAgent.defend(claim, evidence)
       │   ├─▶ SkepticAgent.challenge(claim, evidence, advocate_response)
       │   └─▶ JudgeAgent.evaluate(claim, evidence, advocate, skeptic)
       ├─▶ ConfidenceService.aggregate(atomic_confidences)
       ├─▶ If judge_confidence < threshold → HumanReviewQueue
       ├─▶ DebateLoggingService.log_turns()
       └─▶ TrainingDatasetBuilder.maybe_create_sample()
           └─▶ DuplicateDetector.check() → store if eligible
```

## 5. Domain Interfaces (Ports)

```python
class IClaimExtractor(Protocol):
    async def extract(self, claim_text: str) -> list[AtomicClaim]: ...

class IRetriever(Protocol):
    async def retrieve(self, query: str, top_k: int) -> list[Evidence]: ...

class IKnowledgeGraph(Protocol):
    async def upsert_claim(self, claim: AtomicClaim) -> None: ...
    async def find_contradictions(self, claim: AtomicClaim) -> list[Contradiction]: ...

class IAgent(Protocol):
    async def run(self, context: AgentContext) -> AgentResponse: ...

class ITrainingDatasetBuilder(Protocol):
    async def maybe_create_sample(self, debate: Debate) -> TrainingSample | None: ...
```

## 6. Confidence Propagation

Overall claim confidence uses **weighted geometric mean** of atomic claim confidences:

```
C_overall = (∏ C_i^w_i)^(1/Σw_i)
```

Where `w_i` is the importance weight of atomic claim `i` (default 1.0, higher for temporal/causal claims).

Judge confidence is independent and used for escalation decisions.

## 7. Database Schema (PostgreSQL)

- **users** — authentication, roles
- **claims** — original user-submitted claims
- **atomic_claims** — decomposed SPO triples with verification status
- **sources** — provenance metadata, credibility scores
- **evidence** — retrieved passages with embeddings (pgvector)
- **debates** — debate sessions linked to claims
- **debate_turns** — per-agent turns with prompts, responses, latency, cost
- **training_samples** — eligible fine-tuning examples
- **human_reviews** — escalation queue
- **evaluation_results** — benchmark metrics per experiment
- **experiments** — MLflow experiment metadata

Neo4j stores: Entity nodes, Relationship edges with `valid_from`, `valid_to`, `confidence`, `status`, `evidence_refs`.

## 8. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/verify` | Submit claim for verification |
| GET | `/api/v1/debates/{id}` | Get debate details |
| GET | `/api/v1/debates` | List debates (paginated) |
| GET | `/api/v1/knowledge-graph` | Query KG subgraph |
| GET | `/api/v1/training` | Training dataset stats |
| GET | `/api/v1/evaluation` | Evaluation metrics |
| GET | `/api/v1/fine-tuning/status` | Fine-tuning job status |
| GET | `/api/v1/health` | Health check |

## 9. Deployment Topology

```yaml
services:
  postgres:    # PostgreSQL 16 + pgvector
  neo4j:       # Neo4j 5 Community
  redis:       # Redis 7
  mlflow:      # MLflow tracking server
  backend:     # FastAPI (uvicorn)
  frontend:    # Next.js
```

Each service has its own Dockerfile and can be deployed independently.

## 10. Testing Strategy

- **Unit tests**: Domain logic, confidence math, duplicate detection, score fusion
- **Integration tests**: DB repositories, Neo4j KG, retrieval pipeline
- **API tests**: FastAPI TestClient with mocked agents
- **Evaluation scripts**: 50+ held-out benchmark debates, chart generation
