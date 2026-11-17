# backend/tests/test_visibility.py
"""AI visibility monitor - uses fake assistants and a fake judge, so no API calls or costs."""
import asyncio
import uuid

from app.core.database import AsyncSessionLocal
from app.models.brand import Brand
from app.services.visibility.analyzer import JudgeResult, detect_mentions
from app.services.visibility.providers import AssistantAnswer, _collect_sources
from app.services.visibility.runner import run_brand


# --- Rule-based detection ----------------------------------------------------

def test_detects_brand_alias_and_order():
    text = "Top picks: 1. HubSpot 2. Tech Corp GmbH 3. Salesforce. HubSpot is cheapest."
    d = detect_mentions(text, ["TechCorp", "Tech Corp GmbH"], ["Salesforce", "HubSpot", "Zoho"])
    assert d.brand_mentioned is True
    assert d.mention_order == 2
    assert d.competitors_mentioned == ["HubSpot", "Salesforce"]


def test_case_insensitive_and_word_boundaries():
    assert detect_mentions("we recommend techcorp.", ["TechCorp"], []).brand_mentioned
    # "Apple" must not match inside "Pineapple"
    assert not detect_mentions("Pineapple juice", ["Apple"], []).brand_mentioned
    # Names with punctuation
    assert detect_mentions("Try C&A for basics", ["C&A"], []).brand_mentioned


def test_not_mentioned():
    d = detect_mentions("Salesforce leads the market.", ["TechCorp"], ["Salesforce"])
    assert d.brand_mentioned is False and d.mention_order is None
    assert d.competitors_mentioned == ["Salesforce"]


def test_collect_sources_from_search_results_and_citations():
    class Obj:
        def __init__(self, **kw):
            self.__dict__.update(kw)
    content = [
        Obj(type="web_search_tool_result", content=[Obj(url="https://a.com", title="A"), Obj(url="https://b.com", title="B")]),
        Obj(type="web_search_tool_result", content=Obj(error_code="max_uses_exceeded")),  # error shape
        Obj(type="text", text="x", citations=[Obj(url="https://a.com", title="A again"), Obj(url="https://c.com", title="C")]),
        Obj(type="text", text="y", citations=None),
    ]
    assert _collect_sources(content) == [
        {"url": "https://a.com", "title": "A"},
        {"url": "https://b.com", "title": "B"},
        {"url": "https://c.com", "title": "C"},
    ]


# --- End to end with fakes -----------------------------------------------------

class FakeAssistant:
    def __init__(self, name, answers):
        self.name, self.model, self.web_search = name, f"fake-{name}", False
        self._answers = answers

    async def ask(self, prompt):
        answer = self._answers[prompt]
        if isinstance(answer, Exception):
            raise answer
        return AssistantAnswer(text=answer, sources=[{"url": "https://review-site.com", "title": "Reviews"}])


judge_calls = []


async def fake_judge(question, answer, brand_name, aliases, competitors):
    judge_calls.append(question)
    return JudgeResult(recommended=True, list_rank=1, sentiment="positive", sentiment_score=0.8,
                       claims=["Easy to use"], summary="Recommended as the top option.")


def _create_brand() -> str:
    brand_id = str(uuid.uuid4())

    async def go():
        async with AsyncSessionLocal() as s:
            s.add(Brand(id=brand_id, name="TechCorp", industry="Software"))
            await s.commit()
    asyncio.run(go())
    return brand_id


def test_visibility_flow(client, admin_headers):
    brand_id = _create_brand()
    base = f"/visibility/brands/{brand_id}"

    r = client.put(f"{base}/config", headers=admin_headers,
                   json={"aliases": ["Tech Corp", "tech corp", " "], "competitors": ["Salesforce", "HubSpot"]})
    assert r.status_code == 200
    assert r.json()["aliases"] == ["Tech Corp"]  # trimmed and de-duplicated

    assert client.post(f"{base}/run", headers=admin_headers).status_code == 400  # no prompts yet
    q1, q2, q3 = "Best CRM for startups?", "Cheapest CRM in Germany?", "Which CRM has the best API?"
    for q in (q1, q2, q3):
        assert client.post(f"{base}/prompts", headers=admin_headers, json={"text": q}).status_code == 201
    assert client.post(f"{base}/prompts", headers=admin_headers, json={"text": "hi"}).status_code == 422

    assistants = [
        FakeAssistant("alpha", {q1: "I recommend TechCorp, then Salesforce.", q2: "HubSpot is cheapest.",
                                q3: RuntimeError("upstream timeout")}),
        FakeAssistant("beta", {q1: "Salesforce or HubSpot.", q2: "Tech Corp has a free tier.", q3: "TechCorp."}),
    ]
    judge_calls.clear()
    stored = asyncio.run(run_brand(brand_id, providers=assistants, judge=fake_judge))
    assert stored == 6
    assert len(judge_calls) == 3  # judge only runs when the brand was mentioned

    runs = client.get(f"{base}/runs", headers=admin_headers).json()
    assert len(runs) == 6
    failed = [r for r in runs if r["error"]]
    assert len(failed) == 1 and "upstream timeout" in failed[0]["error"]

    s = client.get(f"{base}/summary", headers=admin_headers).json()
    assert s["runs"] == 5                      # failed run excluded
    assert s["mention_rate"] == 0.6            # 3 of 5
    assert s["by_provider"]["alpha"]["mention_rate"] == 0.5
    assert s["by_provider"]["beta"]["mention_rate"] == round(2 / 3, 3)
    assert s["share_of_voice"]["TechCorp"] == round(3 / 7, 3)  # TechCorp 3, Salesforce 2, HubSpot 2
    assert s["sentiment"] == {"positive": 3}
    assert s["top_sources"][0]["url"] == "https://review-site.com"


def test_viewer_cannot_change_config_or_run(client, admin_headers):
    brand_id = _create_brand()
    client.post("/auth/users", headers=admin_headers,
                json={"email": "viewer2@example.com", "password": "viewer-password-2", "role": "viewer"})
    token = client.post("/auth/token", data={"username": "viewer2@example.com", "password": "viewer-password-2"}).json()["access_token"]
    viewer = {"Authorization": f"Bearer {token}"}
    base = f"/visibility/brands/{brand_id}"
    assert client.get(f"{base}/summary", headers=viewer).status_code == 200
    assert client.put(f"{base}/config", headers=viewer, json={}).status_code == 403
    assert client.post(f"{base}/prompts", headers=viewer, json={"text": "Best CRM?"}).status_code == 403
    assert client.post(f"{base}/run", headers=viewer).status_code == 403
