#!/usr/bin/env python3
"""Run Skeptic evaluation benchmark and generate comparison charts."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logging import setup_logging
from app.db.session import async_session_factory
from app.evaluation.benchmark import EvaluationService


async def main():
    setup_logging()
    async with async_session_factory() as session:
        evaluator = EvaluationService(session)
        print("Running benchmark evaluation...")
        metrics = await evaluator.run_benchmark()
        print(f"  Model: {metrics.model_name}")
        print(f"  F1: {metrics.challenge_f1:.3f}")
        print(f"  Recall: {metrics.challenge_recall:.3f}")
        print(f"  Precision: {metrics.challenge_precision:.3f}")
        print(f"  Miss Rate: {metrics.miss_rate:.3f}")
        print(f"  Avg Latency: {metrics.avg_latency_ms:.1f}ms")
        print(f"  Samples: {metrics.sample_count}")

        chart = await evaluator.generate_charts()
        print(f"  Chart saved: {chart}")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
