# Autonomous Fact-Verification Engine

A production-quality AI system that verifies factual claims through structured multi-agent debate (Advocate, Skeptic, Judge), hybrid retrieval, temporal knowledge graphs, and continuous Skeptic model improvement via fine-tuning.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the complete system design, technology choices, data flow, and module interfaces.

```
User Claim → Atomic Extraction → Knowledge Graph → Hybrid Retrieval → Reranking
    → Advocate → Skeptic → Judge → Confidence → Human Escalation → Training Data
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, LangGraph, SQLAlchemy |
| Frontend | Next.js 14, Tailwind CSS, Recharts |
| Database | PostgreSQL + pgvector |
| Knowledge Graph | Neo4j |
| Cache | Redis |
| Embeddings | Sentence Transformers |
| Reranking | Cross-Encoder |
| Experiment Tracking | MLflow |
| Deployment | Docker Compose |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- (Optional) OpenAI API key for live LLM calls

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env — set OPENAI_API_KEY and USE_MOCK_LLM=false for live LLM
```

### 2. Start all services

```bash
docker compose up --build
```

This starts:
- **Backend API**: http://localhost:8000 (docs at /docs)
- **Frontend Dashboard**: http://localhost:3000
- **Neo4j Browser**: http://localhost:7474
- **MLflow**: http://localhost:5000

### 3. Verify a claim

```bash
curl -X POST http://localhost:8000/api/v1/verify \
  -H "Content-Type: application/json" \
  -d '{"claim": "India won the Cricket World Cup in 2011 under MS Dhoni."}'
```

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── agents/          # Advocate, Skeptic, Judge, prompts
│   │   ├── api/v1/          # REST endpoints
│   │   ├── core/            # Config, logging, exceptions
│   │   ├── db/              # SQLAlchemy models
│   │   ├── domain/          # Business entities & enums
│   │   ├── evaluation/      # Benchmark, adversarial tests
│   │   ├── knowledge_graph/ # Neo4j temporal KG
│   │   ├── retrieval/       # Dense + sparse + reranker
│   │   ├── schemas/         # Pydantic API schemas
│   │   ├── services/        # Application use cases
│   │   └── workflows/       # LangGraph orchestration
│   ├── alembic/             # Database migrations
│   ├── data/                # Benchmark & sample data
│   ├── scripts/             # Seed scripts
│   └── tests/               # Unit, integration, API tests
├── frontend/
│   └── src/                 # Next.js dashboard
├── docs/                    # Architecture documentation
└── docker-compose.yml
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/verify` | Submit claim for verification |
| GET | `/api/v1/debates/{id}` | Get debate details |
| GET | `/api/v1/debates` | List debates |
| GET | `/api/v1/knowledge-graph?entity=` | Query KG subgraph |
| GET | `/api/v1/training` | Training dataset stats |
| GET | `/api/v1/evaluation` | Run evaluation metrics |
| GET | `/api/v1/fine-tuning/status` | Fine-tuning experiments |
| GET | `/api/v1/health` | Health check |

## Development

### Backend (local)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload
```

### Frontend (local)

```bash
cd frontend
npm install
npm run dev
```

### Tests

```bash
cd backend
pytest tests/ -v
```

## Key Design Decisions

1. **Clean Architecture**: Business logic lives in `services/`, not API routes
2. **Mock LLM Mode**: `USE_MOCK_LLM=true` enables full pipeline testing without API keys
3. **Contradiction Handling**: KG edges marked `unresolved` instead of overwriting
4. **Confidence Propagation**: Weighted geometric mean across atomic claims
5. **Training Eligibility**: High judge confidence + no human review required + duplicate check
6. **Insufficient Evidence**: System returns explicit verdict instead of hallucinating

## Fine-Tuning Pipeline

The Skeptic fine-tuning pipeline uses teacher-student distillation:

1. High-confidence debates generate training samples
2. Teacher model (GPT-4o) labels optimal challenges
3. Student model (Phi-2) fine-tuned via QLoRA
4. MLflow tracks experiments and metrics
5. Evaluation compares base vs fine-tuned Skeptic

Install optional dependencies for full training:
```bash
pip install peft transformers bitsandbytes torch
```

## License

MIT
