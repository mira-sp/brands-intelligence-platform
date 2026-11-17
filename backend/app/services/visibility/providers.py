# backend/app/services/visibility/providers.py
"""AI assistants we ask the tracked prompts.

Each provider sends the prompt the way a normal user would (no system prompt) and
returns the answer text plus any web sources it cited. Add OpenAI / Perplexity /
Gemini by implementing ``AssistantProvider`` and registering it in ``get_providers``.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol

import anthropic

from ...core.config import settings

logger = logging.getLogger(__name__)

_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_MAX_CONTINUATIONS = 5


@dataclass
class AssistantAnswer:
    text: str
    sources: List[Dict[str, str]] = field(default_factory=list)


class AssistantProvider(Protocol):
    name: str
    model: str
    web_search: bool

    async def ask(self, prompt: str) -> AssistantAnswer: ...


_client: Optional[anthropic.AsyncAnthropic] = None


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    """Shared async client. Without ANTHROPIC_API_KEY in settings the SDK resolves
    credentials itself (ANTHROPIC_API_KEY env var, `ant auth login` profile, ...)."""
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key or None)
    return _client


def _collect_sources(content) -> List[Dict[str, str]]:
    """URLs from web search results and from citations on text blocks, de-duplicated."""
    seen: Dict[str, str] = {}
    for block in content:
        btype = getattr(block, "type", None)
        if btype == "web_search_tool_result":
            results = getattr(block, "content", None)
            if isinstance(results, list):  # an error result is an object, not a list
                for r in results:
                    url = getattr(r, "url", None)
                    if url:
                        seen.setdefault(url, getattr(r, "title", "") or "")
        elif btype == "text":
            for c in getattr(block, "citations", None) or []:
                url = getattr(c, "url", None)
                if url:
                    seen.setdefault(url, getattr(c, "title", "") or "")
    return [{"url": u, "title": t} for u, t in seen.items()]


class ClaudeProvider:
    name = "claude"

    def __init__(self, model: str, web_search: bool):
        self.model = model
        self.web_search = web_search

    async def ask(self, prompt: str) -> AssistantAnswer:
        client = get_anthropic_client()
        tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}] if self.web_search else []
        messages = [{"role": "user", "content": prompt}]
        content: list = []

        for _ in range(_MAX_CONTINUATIONS + 1):
            kwargs = dict(
                model=self.model,
                max_tokens=16000,
                messages=messages,
                betas=[_FALLBACK_BETA],
                fallbacks="default",  # re-run on a fallback model if the request is declined
            )
            if tools:
                kwargs["tools"] = tools
            response = await client.beta.messages.create(**kwargs)
            content.extend(response.content)

            if response.stop_reason == "pause_turn":
                # Server-side web search loop paused - resend so the server resumes it
                messages = [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": response.content},
                ]
                continue
            if response.stop_reason == "refusal":
                category = getattr(getattr(response, "stop_details", None), "category", None)
                raise RuntimeError(f"Assistant declined to answer (category: {category})")
            break

        text = "".join(getattr(b, "text", "") for b in content if getattr(b, "type", None) == "text").strip()
        return AssistantAnswer(text=text, sources=_collect_sources(content))


def get_providers() -> List[AssistantProvider]:
    """Assistants to query. Currently Claude; extend with other providers here."""
    return [ClaudeProvider(model=settings.visibility_model, web_search=settings.visibility_web_search)]
