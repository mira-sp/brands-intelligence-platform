# backend/app/models/visibility.py
"""AI visibility monitoring: what AI assistants answer when people ask about a market."""
import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from ..core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class VisibilityConfig(Base):
    """Per-brand settings: other names the brand goes by, and the competitors to compare against."""
    __tablename__ = "visibility_configs"

    brand_id = Column(String, ForeignKey("brands.id"), primary_key=True)
    aliases = Column(JSON, nullable=False, default=list)       # e.g. ["TechCorp", "Tech Corp GmbH"]
    competitors = Column(JSON, nullable=False, default=list)   # e.g. ["Salesforce", "HubSpot"]
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TrackedPrompt(Base):
    """A question real customers might ask an AI assistant, e.g. 'Best CRM for small businesses?'"""
    __tablename__ = "tracked_prompts"

    id = Column(String, primary_key=True, default=_uuid)
    brand_id = Column(String, ForeignKey("brands.id"), index=True, nullable=False)
    text = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class VisibilityRun(Base):
    """One answer from one assistant to one tracked prompt, plus its analysis."""
    __tablename__ = "visibility_runs"

    id = Column(String, primary_key=True, default=_uuid)
    brand_id = Column(String, ForeignKey("brands.id"), index=True, nullable=False)
    prompt_id = Column(String, ForeignKey("tracked_prompts.id"), index=True, nullable=False)
    provider = Column(String, nullable=False)          # "claude", later "openai", "perplexity", ...
    model = Column(String, nullable=False)
    web_search = Column(Boolean, nullable=False, default=False)

    answer_text = Column(Text)
    sources = Column(JSON, nullable=False, default=list)              # [{"url", "title"}]

    # Rule-based (deterministic) detection
    brand_mentioned = Column(Boolean, nullable=False, default=False)
    mention_order = Column(Integer)                    # 1 = first entity named in the answer
    competitors_mentioned = Column(JSON, nullable=False, default=list)

    # LLM-judge analysis
    recommended = Column(Boolean)                      # answer actively recommends the brand
    list_rank = Column(Integer)                        # position if the answer is a ranked list
    sentiment = Column(String)                         # positive | neutral | negative | not_mentioned
    sentiment_score = Column(Float)                    # -1.0 .. 1.0
    claims = Column(JSON, nullable=False, default=list)  # statements made about the brand
    summary = Column(Text)

    error = Column(Text)                               # set when the run failed
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
