# Brand Intelligence Platform: AI Visibility Monitor

**Know what AI assistants tell your customers about your brand.**

More and more people ask ChatGPT, Claude, Perplexity or Gemini *"Which CRM should I use?"* or *"Best hotel in Munich for families?"* instead of searching Google. If the assistants don't mention your brand, or describe it wrongly, you lose customers without ever seeing it in your analytics.

This platform tracks that:

- **Do the assistants mention you?** Mention rate per assistant, per question, over time.
- **How do they rank you?** Position in recommendation lists, and whether you are actively recommended.
- **What do they say?** Sentiment and the concrete claims made about you (prices, features, weaknesses), so you can spot wrong information.
- **Who wins instead?** Share of voice against your competitors.
- **Which sources shape the answers?** The websites the assistants cite. These are the places to improve your presence.

> **Status (November 2026):** early stage. The visibility monitor backend works and has tests, with Claude as the first assistant. The dashboard UI for it, more assistants, scheduling and alerts are next (see [Roadmap](#roadmap)).

---

## How it works

```
Tracked prompts ──► AI assistants ──────► Answer + cited sources
("Best CRM for     (Claude with web        │
 startups?")        search; more coming)   ▼
                                     Rule-based detection ── brand mentioned? order? competitors?
                                           │ (only if mentioned)
                                           ▼
                                     LLM judge (structured output) ── recommended? list rank?
                                           │                          sentiment? claims?
                                           ▼
                                     Stored run ──► Summary: mention rate, share of voice,
                                                    sentiment, top sources, per assistant
```

- **Detection is deterministic.** Whether the brand appears is decided by name/alias matching, not by an LLM, so the core metric can't be hallucinated.
- **The judge only runs when the brand is mentioned**, which keeps costs down.
- **Each run is stored with the full answer**, so every number can be traced back to what the assistant actually said.

## Quick start (local development)

Requirements: Python 3.12, Node 22, an [Anthropic API key](https://platform.claude.com/) for live runs.

```bash
# Backend
cd backend
python -m venv .venv && .venv/Scripts/activate      # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env    # then set DEBUG=true, ADMIN_EMAIL, ADMIN_PASSWORD, ANTHROPIC_API_KEY
python -c "import asyncio; from app.core.init_db import init_database; asyncio.run(init_database())"
uvicorn app.main:app --reload --port 8000          # API docs: http://localhost:8000/docs (DEBUG only)
pytest                                             # 17 tests, no API calls

# Frontend
cd frontend
npm ci
npm run dev                                        # http://localhost:3000
```

### Try the visibility monitor

```bash
# 1. Log in (returns a bearer token, valid 30 minutes)
curl -X POST localhost:8000/auth/token -d "username=$ADMIN_EMAIL&password=$ADMIN_PASSWORD"

# 2. Tell it who the brand is and who to compare against
curl -X PUT localhost:8000/visibility/brands/$BRAND_ID/config -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"aliases": ["TechCorp GmbH"], "competitors": ["Salesforce", "HubSpot", "Pipedrive"]}'

# 3. Add the questions your customers ask
curl -X POST localhost:8000/visibility/brands/$BRAND_ID/prompts -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" -d '{"text": "What is the best CRM for a small company in Germany?"}'

# 4. Run (in the background; costs API credits) and read the results
curl -X POST localhost:8000/visibility/brands/$BRAND_ID/run     -H "Authorization: Bearer $TOKEN"
curl         localhost:8000/visibility/brands/$BRAND_ID/summary -H "Authorization: Bearer $TOKEN"
```

For regular tracking, schedule the runner daily (cron, Windows Task Scheduler):

```bash
cd backend && python -m app.services.visibility.runner            # all brands with active prompts
```

## API

All endpoints except `/` and `/health` require a bearer token (`POST /auth/token`) or the service key (`X-API-Key`).

| Area | Endpoint | Role |
|---|---|---|
| Auth | `POST /auth/token`, `GET /auth/me` | any |
| | `GET/POST /auth/users`, `POST /auth/users/{id}/deactivate` | admin |
| **AI visibility** | `GET/PUT /visibility/brands/{id}/config` (aliases, competitors) | read: any · write: admin, analyst |
| | `GET/POST /visibility/brands/{id}/prompts`, `DELETE .../prompts/{prompt_id}` | read: any · write: admin, analyst |
| | `POST /visibility/brands/{id}/run` | admin, analyst |
| | `GET /visibility/brands/{id}/runs`, `GET /visibility/brands/{id}/summary?days=30` | any |
| Brands & mentions | `GET /api/brands`, `GET /api/mentions`, `POST /` (create brand) | create: admin, analyst |
| Legacy sentiment ML | `/ml/*` (BERT sentiment, keyword crisis detection) | any |

## Configuration

Set in `backend/.env` (see `backend/.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | (none) | Needed for live visibility runs |
| `VISIBILITY_MODEL` | `claude-opus-5-5` | The assistant whose answers are monitored |
| `VISIBILITY_JUDGE_MODEL` | `claude-opus-5-5` | Analyses the answers. `claude-haiku-5-5` costs far less, so test whether quality holds |
| `VISIBILITY_WEB_SEARCH` | `true` | Let the assistant search the web, like the consumer apps do |
| `VISIBILITY_MAX_PROMPTS` | `50` | Active prompts per brand (each one costs credits on every run) |
| `SECRET_KEY`, `API_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `CORS_ORIGINS` | | Security, see `.env.example` |

**Cost:** each run asks every active prompt once per assistant, plus one judge call when the brand is mentioned. With web search on, search usage is billed on top of tokens. Start with a handful of prompts and check the bill before scaling up.

## Security

Login with roles (admin / analyst / viewer), JWT plus service API key, per-IP rate limiting, input limits, security headers, non-root containers, secrets only via environment, and a hardened production compose (`infrastructure/docker/docker-compose.prod.yml`). Details are in the commit history from November 2026.

## Production (Docker)

```bash
cp infrastructure/docker/.env.example infrastructure/docker/.env   # fill in all values
docker compose -f infrastructure/docker/docker-compose.prod.yml up -d --build
docker compose -f infrastructure/docker/docker-compose.prod.yml exec backend \
  python -c "import asyncio; from app.core.init_db import init_database; asyncio.run(init_database())"
```

Backend and frontend listen on `127.0.0.1` only. Put a reverse proxy with HTTPS in front and set `FORWARDED_ALLOW_IPS` to the proxy's IP.

## Project structure

```
backend/
  app/
    api/            auth, visibility, brands, mentions, analytics, ml, demo
    core/           config, database, security (JWT/roles), rate limiting, init_db
    models/         user, brand, mention, visibility (config, tracked prompts, runs)
    services/
      visibility/   providers (AI assistants), analyzer (detection + judge), runner
      ml_service.py legacy BERT sentiment + keyword crisis detection
  tests/            pytest suite (auth, roles, limits, visibility end-to-end with fake assistants)
frontend/           Next.js 15 dashboard (legacy sentiment views; visibility UI not built yet)
infrastructure/     docker-compose for dev and production
```

## Roadmap

The 2025 plan (social media crisis monitoring with BERT) was built as a prototype, but real data ingestion was never connected. In November 2026 the project changed direction to **AI visibility monitoring**, a newer need that this codebase fits well.

**Done**
- ✅ Backend, database, auth with roles, rate limiting, hardened Docker setup
- ✅ Visibility monitor: tracked prompts, Claude with web search, mention/rank/competitor detection, LLM judge, summary API
- ✅ Test suite (17 tests, runs without API keys)

**Next**
1. **More assistants:** OpenAI (ChatGPT), Perplexity, Gemini, implemented as providers in `services/visibility/providers.py`. Comparing assistants is the core value.
2. **Dashboard:** visibility overview, trend over time, per-prompt answer history, competitor comparison, top sources.
3. **Scheduling and alerts:** daily runs, plus an email or Slack/Teams alert when the mention rate drops, a competitor overtakes you, or an assistant states something wrong.
4. **Prompt suggestions:** generate the questions real customers ask, per industry and language (German first).
5. **Stable measurements:** answers vary from run to run, so repeat each prompt several times and report rates with confidence ranges.
6. **Engineering:** Postgres with Alembic migrations, CI with GitHub Actions, and dropping the 3 GB torch dependency once the legacy ML is retired.

**Later:** multi-tenant accounts and billing, a public "AI visibility check" landing page as a lead magnet, recommendations on which sources to improve.

## License

MIT, see [LICENSE](LICENSE).
