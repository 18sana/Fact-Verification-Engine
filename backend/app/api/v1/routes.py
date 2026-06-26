from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.evaluation.benchmark import EvaluationService, FineTuningPipeline
from app.knowledge_graph import TemporalKnowledgeGraph
from app.schemas.api import (
    AdversarialHistoryResponse,
    AdversarialRunResponse,
    AgentResponseSchema,
    AtomicClaimResponse,
    DebateDetailResponse,
    DebateListResponse,
    DebateSummary,
    EvaluationCompareResponse,
    EvaluationMetricsResponse,
    EvidenceSchema,
    FineTuningStartRequest,
    FineTuningStartResponse,
    FineTuningStatusResponse,
    HealthResponse,
    HumanReviewActionRequest,
    HumanReviewItem,
    HumanReviewListResponse,
    KnowledgeGraphResponse,
    TrainingStatsResponse,
    VerifyClaimRequest,
    VerifyClaimResponse,
)
from app.services.debate_logging import DebateLoggingService
from app.services.human_review import HumanReviewService
from app.services.training import TrainingDatasetBuilder
from app.services.verification import VerificationService

router = APIRouter()
settings = get_settings()


def _map_agent_response(response) -> AgentResponseSchema:
    return AgentResponseSchema(
        agent=response.agent.value,
        reasoning=response.reasoning,
        confidence=response.confidence,
        sources=response.sources,
        challenges=[{"type": c.challenge_type.value, "description": c.description} for c in response.challenges],
        evidence_used=response.evidence_used,
        verdict=response.verdict.value if response.verdict else None,
        latency_ms=response.latency_ms,
        cost_usd=response.cost_usd,
    )


@router.post("/verify", response_model=VerifyClaimResponse)
async def verify_claim(
    request: VerifyClaimRequest,
    session: AsyncSession = Depends(get_db_session),
):
    service = VerificationService(session)
    result = await service.verify_claim(request.claim, request.user_id)

    return VerifyClaimResponse(
        claim_id=result.claim_id,
        debate_id=result.debate_id,
        overall_verdict=result.overall_verdict,
        overall_confidence=result.overall_confidence,
        requires_human_review=result.requires_human_review,
        atomic_claims=[
            AtomicClaimResponse(
                id=ac.id,
                subject=ac.subject,
                predicate=ac.predicate,
                object=ac.object,
                confidence=ac.confidence,
                verification_status=ac.verification_status.value,
            )
            for ac in result.atomic_claims
        ],
        advocate=_map_agent_response(result.advocate),
        skeptic=_map_agent_response(result.skeptic),
        judge=_map_agent_response(result.judge),
        evidence=[
            EvidenceSchema(
                id=e.id,
                content=e.content,
                source_title=e.source_title,
                source_url=e.source_url,
                credibility=e.credibility,
                rerank_score=e.rerank_score,
            )
            for e in result.evidence
        ],
    )


@router.get("/debates/{debate_id}", response_model=DebateDetailResponse)
async def get_debate(debate_id: UUID, session: AsyncSession = Depends(get_db_session)):
    logger_service = DebateLoggingService(session)
    debate = await logger_service.get_debate(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    turns = [
        {
            "agent": t.agent,
            "claim_text": t.claim_text,
            "response": t.response,
            "confidence": t.confidence,
            "latency_ms": t.latency_ms,
            "cost_usd": t.cost_usd,
            "created_at": t.created_at.isoformat(),
        }
        for t in debate.turns
    ]

    return DebateDetailResponse(
        id=debate.id,
        claim_id=debate.claim_id,
        verdict=debate.verdict,
        confidence=debate.confidence,
        requires_human_review=debate.requires_human_review,
        turns=turns,
        created_at=debate.created_at,
    )


@router.get("/debates", response_model=DebateListResponse)
async def list_debates(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    logger_service = DebateLoggingService(session)
    debates = await logger_service.list_debates(skip, limit)
    total = await logger_service.get_debate_count()

    return DebateListResponse(
        debates=[
            DebateSummary(
                id=d.id,
                claim_id=d.claim_id,
                verdict=d.verdict,
                confidence=d.confidence,
                requires_human_review=d.requires_human_review,
                total_latency_ms=d.total_latency_ms,
                total_cost_usd=d.total_cost_usd,
                created_at=d.created_at,
            )
            for d in debates
        ],
        total=total,
    )


@router.get("/human-reviews", response_model=HumanReviewListResponse)
async def list_human_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    service = HumanReviewService(session)
    await service.sync_missing_reviews()
    reviews = await service.list_pending(skip, limit)
    total = await service.count_pending()
    return HumanReviewListResponse(
        reviews=[
            HumanReviewItem(
                id=r.id,
                debate_id=r.debate_id,
                claim_text=r.claim_text,
                judge_confidence=r.judge_confidence,
                status=r.status,
                created_at=r.created_at,
            )
            for r in reviews
        ],
        total=total,
    )


@router.post("/human-reviews/{review_id}/approve")
async def approve_human_review(
    review_id: UUID,
    body: HumanReviewActionRequest,
    session: AsyncSession = Depends(get_db_session),
):
    service = HumanReviewService(session)
    try:
        review = await service.approve(review_id, body.notes)
        await session.commit()
        return {"id": str(review.id), "status": review.status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/human-reviews/{review_id}/reject")
async def reject_human_review(
    review_id: UUID,
    body: HumanReviewActionRequest,
    session: AsyncSession = Depends(get_db_session),
):
    service = HumanReviewService(session)
    try:
        review = await service.reject(review_id, body.notes)
        await session.commit()
        return {"id": str(review.id), "status": review.status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/knowledge-graph", response_model=KnowledgeGraphResponse)
async def get_knowledge_graph(entity: str = Query(..., min_length=1)):
    kg = TemporalKnowledgeGraph()
    try:
        await kg.connect()
        subgraph = await kg.get_subgraph(entity)
        return KnowledgeGraphResponse(nodes=subgraph["nodes"], edges=subgraph["edges"])
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Knowledge graph unavailable: {e}")
    finally:
        await kg.close()


@router.get("/training", response_model=TrainingStatsResponse)
async def get_training_stats(session: AsyncSession = Depends(get_db_session)):
    builder = TrainingDatasetBuilder(session)
    stats = await builder.get_stats()
    return TrainingStatsResponse(**stats)


@router.post("/training/export")
async def export_training_data(session: AsyncSession = Depends(get_db_session)):
    builder = TrainingDatasetBuilder(session)
    path = f"{settings.training_data_dir}/skeptic_train.jsonl"
    records = await builder.export_jsonl(path)
    return {"path": path, "count": len(records)}


@router.get("/evaluation", response_model=EvaluationMetricsResponse)
async def get_evaluation_metrics(session: AsyncSession = Depends(get_db_session)):
    """Return the most recent benchmark result without re-running."""
    evaluator = EvaluationService(session)
    metrics = await evaluator.get_latest_metrics()
    if not metrics:
        raise HTTPException(status_code=404, detail="No benchmark results yet. Use POST /evaluation/run.")
    return EvaluationMetricsResponse(**metrics.model_dump())


@router.post("/evaluation/run", response_model=EvaluationMetricsResponse)
async def run_evaluation_benchmark(session: AsyncSession = Depends(get_db_session)):
    """Run benchmark (parallel, capped by BENCHMARK_MAX_SAMPLES)."""
    evaluator = EvaluationService(session)
    metrics = await evaluator.run_benchmark()
    await session.commit()
    return EvaluationMetricsResponse(**metrics.model_dump())


@router.get("/evaluation/compare", response_model=EvaluationCompareResponse)
async def compare_evaluation(session: AsyncSession = Depends(get_db_session)):
    evaluator = EvaluationService(session)
    return await evaluator.compare_models()


@router.post("/evaluation/chart")
async def generate_evaluation_chart(session: AsyncSession = Depends(get_db_session)):
    """Generate before/after PNG from the two most recent benchmark runs."""
    evaluator = EvaluationService(session)
    path = await evaluator.generate_charts()
    if path in ("matplotlib not installed", "no evaluation data"):
        raise HTTPException(status_code=400, detail=path)
    return {"chart_path": path}


@router.post("/evaluation/adversarial/run", response_model=AdversarialRunResponse)
async def run_adversarial_evaluation(session: AsyncSession = Depends(get_db_session)):
    evaluator = EvaluationService(session)
    result = await evaluator.run_adversarial_eval()
    await session.commit()
    return AdversarialRunResponse(**result)


@router.get("/evaluation/adversarial/history", response_model=AdversarialHistoryResponse)
async def adversarial_history(
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    evaluator = EvaluationService(session)
    runs = await evaluator.get_adversarial_history(limit)
    return AdversarialHistoryResponse(runs=runs)


@router.get("/fine-tuning/status", response_model=FineTuningStatusResponse)
async def get_finetuning_status(session: AsyncSession = Depends(get_db_session)):
    pipeline = FineTuningPipeline(session)
    status = await pipeline.get_status()
    return FineTuningStatusResponse(**status)


@router.post("/fine-tuning/start", response_model=FineTuningStartResponse)
async def start_finetuning(
    request: FineTuningStartRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
):
    pipeline = FineTuningPipeline(session)
    try:
        experiment = await pipeline.start_experiment(request.name)
        await session.commit()

        async def _run_training(exp_id):
            from app.db.session import async_session_factory
            async with async_session_factory() as bg_session:
                bg_pipeline = FineTuningPipeline(bg_session)
                await bg_pipeline.run_finetuning(exp_id)
                await bg_session.commit()

        background_tasks.add_task(_run_training, experiment.id)

        tracking_note = (
            " (MLflow tracking unavailable — training will continue without experiment logs)"
            if not experiment.mlflow_run_id
            else ""
        )
        return FineTuningStartResponse(
            experiment_id=str(experiment.id),
            status="running",
            message=f"Fine-tuning started in background{tracking_note}",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/health", response_model=HealthResponse)
async def health_check():
    services = {"api": "healthy", "database": "unknown", "neo4j": "unknown", "redis": "unknown"}
    return HealthResponse(status="healthy", services=services)
