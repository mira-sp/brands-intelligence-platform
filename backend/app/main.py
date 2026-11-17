# backend/app/main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .core.database import get_db
from .core.config import settings
from .core.security import require_user
from .models.brand import Brand
from .models.mention import Mention
from typing import List
from pydantic import BaseModel
import uuid

# Import API routers
from .api import brands, mentions, analytics, demo
from .api.auth import router as auth_router
from .api.ml import router as ml_router
from .core.rate_limit import RateLimitMiddleware

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    debug=settings.debug,
    # Don't expose interactive API docs / OpenAPI schema outside debug mode
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

# Middleware order: the LAST one added runs FIRST (outermost).
# Request flow: CORS -> security headers -> rate limit -> routes, so 429s still get CORS + headers.

# Per-IP rate limiting (stricter for /auth/token and /ml)
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


# CORS middleware for frontend (origins configured via CORS_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# Public endpoints (no auth) - registered BEFORE the routers so router paths such as
# "/{mention_id}" can't shadow them.
@app.get("/")
async def read_root():
    return {
        "message": "Brand Intelligence Platform API",
        "version": settings.version,
        "status": "healthy"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.version,
        "database": "connected",
        "ml_service": "available"
    }

# Basic data endpoints (require a logged-in user)
@app.get("/api/brands", dependencies=[Depends(require_user)])
async def get_brands(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Brand).limit(10))
    brands = result.scalars().all()
    return [{"id": brand.id, "name": brand.name, "industry": brand.industry} for brand in brands]

@app.get("/api/mentions", dependencies=[Depends(require_user)])
async def get_mentions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Mention).limit(10))
    mentions = result.scalars().all()
    return [{"id": mention.id, "content": mention.content, "platform": mention.platform, "sentiment_score": mention.sentiment_score} for mention in mentions]

@app.get("/api/demo/sample-data", dependencies=[Depends(require_user)])
async def get_sample_data(db: AsyncSession = Depends(get_db)):
    # Get brands
    brands_result = await db.execute(select(Brand))
    brands = brands_result.scalars().all()
    
    # Get mentions
    mentions_result = await db.execute(select(Mention).limit(5))
    mentions = mentions_result.scalars().all()
    
    return {
        "brands": [{"id": b.id, "name": b.name, "industry": b.industry} for b in brands],
        "mentions": [{"id": m.id, "content": m.content, "sentiment_score": m.sentiment_score} for m in mentions],
        "message": "Sample data loaded successfully!"
    }


# Include API routers (after the app-level routes above)
app.include_router(auth_router)
app.include_router(brands.router)
app.include_router(mentions.router)
app.include_router(analytics.router)
app.include_router(demo.router)
app.include_router(ml_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
