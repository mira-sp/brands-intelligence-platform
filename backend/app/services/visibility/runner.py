# backend/app/services/visibility/runner.py
"""Run every active tracked prompt of a brand against every assistant and store the results.

Schedule it (cron / Windows Task Scheduler / a k8s CronJob), e.g. daily:
    python -m app.services.visibility.runner            # all brands
    python -m app.services.visibility.runner <brand_id> # one brand
"""
import asyncio
import logging
import sys
from typing import Callable, List, Optional, Sequence

from sqlalchemy import select

from ...core.config import settings
from ...core.database import AsyncSessionLocal
from ...models.brand import Brand
from ...models.visibility import TrackedPrompt, VisibilityConfig, VisibilityRun
from .analyzer import JudgeResult, detect_mentions, judge_answer
from .providers import AssistantProvider, get_providers

logger = logging.getLogger(__name__)

JudgeFn = Callable[..., "asyncio.Future[JudgeResult]"]


async def _run_one(provider: AssistantProvider, prompt: TrackedPrompt, brand: Brand, aliases: List[str],
                   competitors: List[str], judge: JudgeFn, sem: asyncio.Semaphore) -> VisibilityRun:
    run = VisibilityRun(brand_id=brand.id, prompt_id=prompt.id, provider=provider.name,
                        model=provider.model, web_search=provider.web_search)
    async with sem:
        try:
            answer = await provider.ask(prompt.text)
            run.answer_text = answer.text
            run.sources = answer.sources

            detection = detect_mentions(answer.text, [brand.name, *aliases], competitors)
            run.brand_mentioned = detection.brand_mentioned
            run.mention_order = detection.mention_order
            run.competitors_mentioned = detection.competitors_mentioned

            if detection.brand_mentioned:
                verdict = await judge(prompt.text, answer.text, brand.name, aliases, competitors)
                run.recommended = verdict.recommended
                run.list_rank = verdict.list_rank
                run.sentiment = verdict.sentiment
                run.sentiment_score = verdict.sentiment_score
                run.claims = verdict.claims
                run.summary = verdict.summary
            else:
                # Not mentioned at all - no need to pay for a judge call
                run.recommended = False
                run.sentiment = "not_mentioned"
                run.sentiment_score = 0.0
                run.claims = []
        except Exception as e:  # keep going; the failure is recorded on the run
            logger.error("Visibility run failed (brand=%s prompt=%s provider=%s): %s",
                         brand.id, prompt.id, provider.name, e)
            run.error = f"{type(e).__name__}: {e}"[:500]
    return run


async def run_brand(brand_id: str, providers: Optional[Sequence[AssistantProvider]] = None,
                    judge: Optional[JudgeFn] = None) -> int:
    """Returns the number of runs stored."""
    providers = list(providers) if providers is not None else get_providers()
    judge = judge or judge_answer

    async with AsyncSessionLocal() as session:
        brand = (await session.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
        if not brand:
            raise ValueError(f"Brand {brand_id} not found")
        config = (await session.execute(
            select(VisibilityConfig).where(VisibilityConfig.brand_id == brand_id))).scalar_one_or_none()
        prompts = (await session.execute(
            select(TrackedPrompt).where(TrackedPrompt.brand_id == brand_id, TrackedPrompt.is_active.is_(True))
        )).scalars().all()

    aliases = list(config.aliases) if config else []
    competitors = list(config.competitors) if config else []
    sem = asyncio.Semaphore(settings.visibility_concurrency)

    runs = await asyncio.gather(*[
        _run_one(p, prompt, brand, aliases, competitors, judge, sem)
        for prompt in prompts for p in providers
    ])

    async with AsyncSessionLocal() as session:
        session.add_all(runs)
        await session.commit()
    logger.info("Stored %d visibility runs for brand %s", len(runs), brand_id)
    return len(runs)


async def run_all_brands() -> int:
    async with AsyncSessionLocal() as session:
        brand_ids = (await session.execute(
            select(TrackedPrompt.brand_id).where(TrackedPrompt.is_active.is_(True)).distinct()
        )).scalars().all()
    total = 0
    for brand_id in brand_ids:
        total += await run_brand(brand_id)
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = asyncio.run(run_brand(sys.argv[1]) if len(sys.argv) > 1 else run_all_brands())
    print(f"Stored {count} runs")
