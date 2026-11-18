# backend/app/api/visibility.py
"""AI visibility monitor API."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import get_db
from ..core.security import require_role, require_user
from ..models.brand import Brand
from ..models.visibility import TrackedPrompt, VisibilityConfig, VisibilityRun
from ..services.visibility.runner import run_brand

router = APIRouter(prefix="/visibility", tags=["AI Visibility"], dependencies=[Depends(require_user)])
_editor = require_role("admin", "analyst")


def _clean_names(values: List[str], field_name: str) -> List[str]:
    out, seen = [], set()
    for v in values:
        v = v.strip()
        if not v:
            continue
        if len(v) > 100:
            raise ValueError(f"{field_name} entries must be at most 100 characters")
        if v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    if len(out) > 30:
        raise ValueError(f"At most 30 {field_name}")
    return out


class ConfigIn(BaseModel):
    aliases: List[str] = []
    competitors: List[str] = []

    @field_validator("aliases")
    @classmethod
    def _aliases(cls, v):
        return _clean_names(v, "aliases")

    @field_validator("competitors")
    @classmethod
    def _competitors(cls, v):
        return _clean_names(v, "competitors")


class PromptIn(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def _text(cls, v: str) -> str:
        v = v.strip()
        if not 5 <= len(v) <= 500:
            raise ValueError("Prompt must be 5-500 characters")
        return v


class PromptOut(BaseModel):
    id: str
    text: str
    is_active: bool

    class Config:
        from_attributes = True


async def _get_brand(db: AsyncSession, brand_id: str) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


# --- Configuration -----------------------------------------------------------

@router.get("/brands/{brand_id}/config")
async def get_config(brand_id: str, db: AsyncSession = Depends(get_db)):
    await _get_brand(db, brand_id)
    cfg = await db.get(VisibilityConfig, brand_id)
    return {"brand_id": brand_id, "aliases": cfg.aliases if cfg else [], "competitors": cfg.competitors if cfg else []}


@router.put("/brands/{brand_id}/config", dependencies=[Depends(_editor)])
async def put_config(brand_id: str, body: ConfigIn, db: AsyncSession = Depends(get_db)):
    await _get_brand(db, brand_id)
    cfg = await db.get(VisibilityConfig, brand_id)
    if cfg is None:
        cfg = VisibilityConfig(brand_id=brand_id)
        db.add(cfg)
    cfg.aliases = body.aliases
    cfg.competitors = body.competitors
    await db.commit()
    return {"brand_id": brand_id, "aliases": cfg.aliases, "competitors": cfg.competitors}


# --- Tracked prompts ---------------------------------------------------------

@router.get("/brands/{brand_id}/prompts", response_model=List[PromptOut])
async def list_prompts(brand_id: str, db: AsyncSession = Depends(get_db)):
    await _get_brand(db, brand_id)
    return (await db.execute(
        select(TrackedPrompt).where(TrackedPrompt.brand_id == brand_id).order_by(TrackedPrompt.created_at)
    )).scalars().all()


@router.post("/brands/{brand_id}/prompts", response_model=PromptOut, status_code=201, dependencies=[Depends(_editor)])
async def add_prompt(brand_id: str, body: PromptIn, db: AsyncSession = Depends(get_db)):
    await _get_brand(db, brand_id)
    count = (await db.execute(
        select(func.count(TrackedPrompt.id)).where(TrackedPrompt.brand_id == brand_id, TrackedPrompt.is_active.is_(True))
    )).scalar()
    if count >= settings.visibility_max_prompts:
        raise HTTPException(status_code=400, detail=f"At most {settings.visibility_max_prompts} active prompts per brand")
    prompt = TrackedPrompt(brand_id=brand_id, text=body.text)
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.delete("/brands/{brand_id}/prompts/{prompt_id}", status_code=204, dependencies=[Depends(_editor)])
async def deactivate_prompt(brand_id: str, prompt_id: str, db: AsyncSession = Depends(get_db)):
    prompt = (await db.execute(
        select(TrackedPrompt).where(TrackedPrompt.id == prompt_id, TrackedPrompt.brand_id == brand_id)
    )).scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    prompt.is_active = False  # keep history; runs still reference it
    await db.commit()


# --- Runs --------------------------------------------------------------------

@router.post("/brands/{brand_id}/run", status_code=202, dependencies=[Depends(_editor)])
async def start_run(brand_id: str, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Ask every active prompt to every assistant. Costs API credits - runs in the background."""
    await _get_brand(db, brand_id)
    active = (await db.execute(
        select(func.count(TrackedPrompt.id)).where(TrackedPrompt.brand_id == brand_id, TrackedPrompt.is_active.is_(True))
    )).scalar()
    if not active:
        raise HTTPException(status_code=400, detail="Add at least one prompt first")
    background_tasks.add_task(run_brand, brand_id)
    return {"status": "started", "prompts": active}


@router.get("/brands/{brand_id}/runs")
async def list_runs(brand_id: str, limit: int = Query(50, ge=1, le=500),
                    prompt_id: Optional[str] = None, provider: Optional[str] = Query(None, max_length=50),
                    db: AsyncSession = Depends(get_db)):
    await _get_brand(db, brand_id)
    q = select(VisibilityRun).where(VisibilityRun.brand_id == brand_id)
    if prompt_id:
        q = q.where(VisibilityRun.prompt_id == prompt_id)
    if provider:
        q = q.where(VisibilityRun.provider == provider)
    runs = (await db.execute(q.order_by(VisibilityRun.created_at.desc()).limit(limit))).scalars().all()
    return [{
        "id": r.id, "prompt_id": r.prompt_id, "provider": r.provider, "model": r.model,
        "created_at": r.created_at, "brand_mentioned": r.brand_mentioned, "mention_order": r.mention_order,
        "list_rank": r.list_rank, "recommended": r.recommended, "sentiment": r.sentiment,
        "sentiment_score": r.sentiment_score, "competitors_mentioned": r.competitors_mentioned,
        "claims": r.claims, "summary": r.summary, "sources": r.sources, "answer_text": r.answer_text,
        "error": r.error,
    } for r in runs]


@router.get("/brands/{brand_id}/summary")
async def summary(brand_id: str, days: int = Query(30, ge=1, le=365), db: AsyncSession = Depends(get_db)):
    """Headline numbers: how often AI assistants mention the brand, how well, and next to whom."""
    brand = await _get_brand(db, brand_id)
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    runs = await _successful_runs(db, brand_id, since)
    previous = await _successful_runs(db, brand_id, since - timedelta(days=days), until=since)

    total = len(runs)
    mentioned = [r for r in runs if r.brand_mentioned]

    per_provider = defaultdict(lambda: {"runs": 0, "mentioned": 0})
    for r in runs:
        per_provider[r.provider]["runs"] += 1
        per_provider[r.provider]["mentioned"] += int(r.brand_mentioned)

    # Share of voice: brand mentions vs. each competitor's mentions across all answers
    voice = Counter({brand.name: len(mentioned)})
    for r in runs:
        voice.update(r.competitors_mentioned or [])
    voice_total = sum(voice.values())

    sources = Counter(s["url"] for r in runs for s in (r.sources or []) if s.get("url"))
    ranks = [r.list_rank for r in mentioned if r.list_rank]

    return {
        "brand_id": brand_id,
        "period_days": days,
        "runs": total,
        "mention_rate": rate(len(mentioned), total),
        # Same-length window right before this one, for "up/down x points" comparisons
        "previous_mention_rate": rate(sum(1 for r in previous if r.brand_mentioned), len(previous)),
        "recommendation_rate": rate(sum(1 for r in runs if r.recommended), total),
        "avg_list_rank": round(sum(ranks) / len(ranks), 2) if ranks else None,
        "sentiment": dict(Counter(r.sentiment for r in mentioned)),
        "avg_sentiment_score": round(sum(r.sentiment_score or 0 for r in mentioned) / len(mentioned), 3) if mentioned else None,
        "by_provider": {p: {**v, "mention_rate": rate(v["mentioned"], v["runs"])} for p, v in per_provider.items()},
        "share_of_voice": {name: rate(n, voice_total) for name, n in voice.most_common()},
        "top_sources": [{"url": u, "count": n} for u, n in sources.most_common(10)],
    }


@router.get("/brands/{brand_id}/trend")
async def trend(brand_id: str, days: int = Query(90, ge=7, le=365), db: AsyncSession = Depends(get_db)):
    """Weekly mention rate per assistant (and overall), oldest week first."""
    await _get_brand(db, brand_id)
    runs = await _successful_runs(db, brand_id, datetime.now(timezone.utc) - timedelta(days=days))

    buckets: dict = defaultdict(lambda: defaultdict(lambda: [0, 0]))  # week -> provider -> [mentioned, runs]
    for r in runs:
        created = _as_utc(r.created_at)
        week = (created - timedelta(days=created.weekday())).date()  # Monday of that week
        for key in (r.provider, "__all__"):
            buckets[week][key][0] += int(r.brand_mentioned)
            buckets[week][key][1] += 1

    providers = sorted({r.provider for r in runs})
    return {
        "providers": providers,
        "weeks": [
            {
                "week": week.isoformat(),
                "overall": rate(*buckets[week]["__all__"]),
                "by_provider": {p: rate(*buckets[week][p]) if p in buckets[week] else None for p in providers},
            }
            for week in sorted(buckets)
        ],
    }


@router.get("/brands/{brand_id}/matrix")
async def matrix(brand_id: str, days: int = Query(30, ge=1, le=365), db: AsyncSession = Depends(get_db)):
    """Question x assistant grid: mention rate per cell plus the latest answer's headline facts."""
    await _get_brand(db, brand_id)
    prompts = (await db.execute(
        select(TrackedPrompt).where(TrackedPrompt.brand_id == brand_id, TrackedPrompt.is_active.is_(True))
        .order_by(TrackedPrompt.created_at)
    )).scalars().all()
    runs = await _successful_runs(db, brand_id, datetime.now(timezone.utc) - timedelta(days=days))

    cells: dict = defaultdict(list)
    for r in runs:
        cells[(r.prompt_id, r.provider)].append(r)
    providers = sorted({r.provider for r in runs})

    rows = []
    for p in prompts:
        row_cells = {}
        for prov in providers:
            cell_runs = sorted(cells.get((p.id, prov), []), key=lambda r: _as_utc(r.created_at))
            if not cell_runs:
                row_cells[prov] = None
                continue
            last = cell_runs[-1]
            row_cells[prov] = {
                "runs": len(cell_runs),
                "mention_rate": rate(sum(r.brand_mentioned for r in cell_runs), len(cell_runs)),
                "last_run_id": last.id,
                "last_mentioned": last.brand_mentioned,
                "last_list_rank": last.list_rank,
                "last_sentiment": last.sentiment,
            }
        rows.append({"prompt_id": p.id, "text": p.text, "cells": row_cells})
    return {"providers": providers, "rows": rows}


# --- helpers -------------------------------------------------------------------

def rate(n: int, d: int) -> Optional[float]:
    return round(n / d, 3) if d else None


def _as_utc(dt: datetime) -> datetime:
    """SQLite returns naive datetimes (stored as UTC); Postgres returns aware ones."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


async def _successful_runs(db: AsyncSession, brand_id: str, since: datetime,
                           until: Optional[datetime] = None) -> List[VisibilityRun]:
    q = select(VisibilityRun).where(VisibilityRun.brand_id == brand_id, VisibilityRun.created_at >= since,
                                    VisibilityRun.error.is_(None))
    if until is not None:
        q = q.where(VisibilityRun.created_at < until)
    return list((await db.execute(q)).scalars().all())
