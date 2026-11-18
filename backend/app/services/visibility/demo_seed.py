# backend/app/services/visibility/demo_seed.py
"""Fill the database with realistic DEMO visibility data - no AI calls, no costs.

    python -m app.services.visibility.demo_seed

Creates the fictional brand "Kestrel CRM" with fictional competitors and ~13 weeks of
answers from four assistants. Re-running replaces the previous demo data.
All companies and websites are made up (sites use the reserved .example domain).
"""
import asyncio
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from ...core.database import AsyncSessionLocal
from ...core.init_db import create_tables
from ...models.brand import Brand
from ...models.visibility import TrackedPrompt, VisibilityConfig, VisibilityRun
from .analyzer import detect_mentions

BRAND = "Kestrel CRM"
ALIASES = ["Kestrel"]
COMPETITORS = ["Brightdesk", "Orbitly", "Pipewise", "Fernhill"]
WEEKS = 13
RUNS_PER_WEEK = 2

# (prompt, how strongly this question favours the brand: -0.3 .. +0.3)
PROMPTS = [
    ("What is the best CRM for a small B2B company?", 0.10),
    ("Welches CRM eignet sich für kleine Unternehmen in Deutschland?", 0.20),
    ("Affordable CRM with a good mobile app?", 0.05),
    ("DSGVO-konformes CRM mit Hosting in der EU?", 0.30),
    ("Which CRM integrates best with Outlook and Teams?", -0.05),
    ("Best CRM for a sales team of 50 people?", -0.15),
    ("Simple CRM for freelancers and agencies?", 0.00),
    ("Enterprise CRM with advanced forecasting?", -0.30),
]

# provider -> (mention probability at start, at end, typical number of cited sources)
PROVIDERS = {
    "chatgpt": (0.30, 0.52, 1),
    "claude": (0.42, 0.50, 2),
    "gemini": (0.18, 0.30, 3),
    "perplexity": (0.46, 0.66, 5),
}

REASONS = {
    BRAND: ["EU hosting and a strong GDPR story", "a clean mobile app", "fair per-seat pricing",
            "fast onboarding for small teams", "good German-language support"],
    "Brightdesk": ["a huge integration marketplace", "powerful reporting", "enterprise-grade permissions"],
    "Orbitly": ["a generous free tier", "built-in email marketing", "an easy drag-and-drop pipeline"],
    "Pipewise": ["a pipeline-first design for sales teams", "strong forecasting", "deal automation"],
    "Fernhill": ["deep Microsoft 365 integration", "Teams and Outlook add-ins", "flexible custom fields"],
}

CLAIMS_GOOD = ["Offers data hosting in Frankfurt", "Pricing starts around 19 EUR per user/month",
               "Has native iOS and Android apps", "Supports two-factor authentication",
               "Includes a GDPR data-processing agreement"]
CLAIMS_BAD = ["Lacks a native Outlook integration", "Reporting is basic compared to larger tools",
              "Does not offer a free plan"]
CLAIM_WRONG = "Only available in English"  # a factually wrong claim to spot in the UI

SOURCES = ["crm-vergleich.example/kleine-unternehmen", "reviewhub.example/crm/top-10", "techblatt.example/crm-test-2026",
           "saas-radar.example/best-crm", "forum.example/r/sales/crm-recommendations", "kestrel-crm.example/pricing",
           "brightdesk.example/compare", "gruenderszene.example/tools/crm"]


def _answer(rng, prompt, provider, include_brand, progress):
    names = rng.sample(COMPETITORS, k=rng.randint(2, 4))
    if include_brand:
        # Brand moves up the lists over time
        pos = min(len(names), max(0, int(rng.triangular(0, len(names), len(names) * (1 - progress)))))
        names.insert(pos, BRAND)
    lines = [f"{i}. **{n}** - known for {rng.choice(REASONS[n])}." for i, n in enumerate(names, 1)]
    intro = ("Hier sind einige gute Optionen:" if any(w in prompt for w in ("Welches", "DSGVO"))
             else "Here are some strong options:")
    outro = "The right choice depends on team size, budget and the tools you already use."
    return names, "\n".join([intro, "", *lines, "", outro])


def _sentiment(rng, rank):
    roll = rng.random()
    if roll < 0.08:
        return "negative", round(rng.uniform(-0.7, -0.2), 2)
    if roll < 0.28 or (rank and rank > 3):
        return "neutral", round(rng.uniform(-0.1, 0.3), 2)
    return "positive", round(rng.uniform(0.4, 0.9), 2)


async def seed(seed_value: int = 7) -> str:
    rng = random.Random(seed_value)
    await create_tables()
    async with AsyncSessionLocal() as s:
        brand = (await s.execute(select(Brand).where(Brand.name == BRAND))).scalar_one_or_none()
        if brand is None:
            brand = Brand(name=BRAND, industry="Software / CRM", website="https://kestrel-crm.example")
            s.add(brand)
            await s.flush()
        brand_id = brand.id

        # Replace earlier demo data for this brand
        await s.execute(delete(VisibilityRun).where(VisibilityRun.brand_id == brand_id))
        await s.execute(delete(TrackedPrompt).where(TrackedPrompt.brand_id == brand_id))
        await s.execute(delete(VisibilityConfig).where(VisibilityConfig.brand_id == brand_id))
        s.add(VisibilityConfig(brand_id=brand_id, aliases=ALIASES, competitors=COMPETITORS))

        now = datetime.now(timezone.utc).replace(microsecond=0)
        start = now - timedelta(weeks=WEEKS)
        prompts = []
        for i, (text, _) in enumerate(PROMPTS):
            p = TrackedPrompt(brand_id=brand_id, text=text, created_at=start + timedelta(minutes=i))
            prompts.append(p)
            s.add(p)
        await s.flush()

        runs = []
        for week in range(WEEKS):
            for k in range(RUNS_PER_WEEK):
                when = start + timedelta(weeks=week, days=1 + 3 * k, hours=rng.randint(5, 9))
                if when > now:
                    continue
                progress = week / (WEEKS - 1)
                for prompt, (text, bias) in zip(prompts, PROMPTS):
                    for provider, (p0, p1, n_sources) in PROVIDERS.items():
                        p_mention = max(0.02, min(0.95, p0 + (p1 - p0) * progress + bias))
                        include = rng.random() < p_mention
                        names, answer = _answer(rng, text, provider, include, progress)
                        det = detect_mentions(answer, [BRAND, *ALIASES], COMPETITORS)
                        rank = names.index(BRAND) + 1 if include else None
                        run = VisibilityRun(
                            brand_id=brand_id, prompt_id=prompt.id, provider=provider,
                            model=f"demo-{provider}", web_search=True, answer_text=answer,
                            sources=[{"url": f"https://{u}", "title": u.split("/")[0]}
                                     for u in rng.sample(SOURCES, k=min(len(SOURCES), max(0, n_sources + rng.randint(-1, 1))))],
                            brand_mentioned=det.brand_mentioned, mention_order=det.mention_order,
                            competitors_mentioned=det.competitors_mentioned, created_at=when,
                        )
                        if include:
                            sentiment, score = _sentiment(rng, rank)
                            claims = rng.sample(CLAIMS_GOOD, k=2)
                            if sentiment != "positive":
                                claims.append(rng.choice(CLAIMS_BAD))
                            if provider == "gemini" and rng.random() < 0.3:
                                claims.append(CLAIM_WRONG)
                            run.recommended = sentiment == "positive" and rank <= 2
                            run.list_rank = rank
                            run.sentiment, run.sentiment_score = sentiment, score
                            run.claims = claims
                            run.summary = (f"Listed {BRAND} at #{rank}, " +
                                           {"positive": "with a clear recommendation for smaller teams.",
                                            "neutral": "as one option among several, without a recommendation.",
                                            "negative": "but pointed out limitations compared to the others."}[sentiment])
                        else:
                            run.recommended, run.sentiment, run.sentiment_score = False, "not_mentioned", 0.0
                            run.claims = []
                        runs.append(run)
        s.add_all(runs)
        await s.commit()
    print(f"Demo data ready: brand '{BRAND}' ({brand_id}) with {len(prompts)} prompts and {len(runs)} runs")
    return brand_id


if __name__ == "__main__":
    asyncio.run(seed())
