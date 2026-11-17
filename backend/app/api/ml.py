# backend/app/api/ml.py
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request
from fastapi.responses import StreamingResponse
from typing import List, Dict, Optional
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from sqlalchemy import select
from ..services.ml_service import MLService
from ..core.database import AsyncSessionLocal
from ..models.brand import Brand
from ..models.mention import Mention
from ..core.config import settings
from ..core.security import require_user

logger = logging.getLogger(__name__)

# Realtime streams are closed after this long so idle clients can't hold workers forever
_REALTIME_MAX_SECONDS = 30 * 60

# All ML endpoints run expensive inference -> require an authenticated user (DoS / cost protection)
router = APIRouter(prefix="/ml", tags=["ML Analytics"], dependencies=[Depends(require_user)])


def _validate_text(text) -> str:
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(status_code=400, detail="Text is required")
    if len(text) > settings.max_text_length:
        raise HTTPException(status_code=413, detail=f"Text exceeds {settings.max_text_length} characters")
    return text


def _validate_mentions(mentions) -> list:
    if not isinstance(mentions, list):
        raise HTTPException(status_code=400, detail="mentions must be a list")
    if len(mentions) > settings.max_batch_size:
        raise HTTPException(status_code=413, detail=f"At most {settings.max_batch_size} mentions per request")
    for m in mentions:
        if not isinstance(m, dict):
            raise HTTPException(status_code=400, detail="Each mention must be an object")
        if len(str(m.get("text", ""))) > settings.max_text_length:
            raise HTTPException(status_code=413, detail=f"Mention text exceeds {settings.max_text_length} characters")
    return mentions


def _validate_brand_name(brand_name) -> str:
    if not isinstance(brand_name, str) or not brand_name.strip():
        raise HTTPException(status_code=400, detail="brand_name is required")
    if len(brand_name) > 200:
        raise HTTPException(status_code=400, detail="brand_name too long")
    return brand_name

# Initialize ML service as singleton
ml_service = MLService()

@router.get("/status")
async def get_ml_service_status():
    """Get the status of all ML service components"""
    try:
        status = ml_service.get_service_status()
        return {
            "status": "healthy" if status.get("service_healthy") else "degraded",
            "components": status,
            "message": "All ML components operational" if status.get("service_healthy") 
                      else "Some ML components unavailable"
        }
    except Exception as e:
        logger.error(f"Failed to get ML service status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get ML service status")

@router.post("/analyze/sentiment")
async def analyze_sentiment(data: Dict):
    """Analyze sentiment of a single text"""
    try:
        text = _validate_text(data.get("text", ""))
        use_bert = bool(data.get("use_bert", True))

        result = await ml_service.analyze_mention_sentiment(text, use_bert=use_bert)
        return {
            "success": True,
            "data": result,
            "processing_time": result.get("processing_time_ms", 0)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Sentiment analysis failed")

@router.post("/analyze/crisis")
async def analyze_crisis(data: Dict):
    """Analyze crisis indicators in mentions for a brand"""
    try:
        mentions = _validate_mentions(data.get("mentions", []))
        brand_name = _validate_brand_name(data.get("brand_name", ""))

        if not mentions:
            raise HTTPException(status_code=400, detail="Mentions and brand_name are required")

        result = await ml_service.analyze_crisis(mentions, brand_name)
        return {
            "success": True,
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Crisis analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Crisis analysis failed")

@router.post("/analyze/brand-health")
async def analyze_brand_health(data: Dict):
    """Comprehensive brand health analysis"""
    try:
        brand_name = _validate_brand_name(data.get("brand_name", ""))
        mentions = _validate_mentions(data.get("mentions", []))
        try:
            time_window_hours = int(data.get("time_window_hours", 24))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="time_window_hours must be an integer")
        if not 1 <= time_window_hours <= 24 * 365:
            raise HTTPException(status_code=400, detail="time_window_hours out of range")

        result = await ml_service.analyze_brand_health(brand_name, mentions, time_window_hours)
        return {
            "success": True,
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Brand health analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Brand health analysis failed")

@router.post("/analyze/batch")
async def batch_analyze_mentions(data: Dict):
    """Analyze multiple mentions for sentiment and crisis indicators"""
    try:
        mentions = _validate_mentions(data.get("mentions", []))
        brand_name = _validate_brand_name(data.get("brand_name", ""))
        include_bert = bool(data.get("include_bert", True))

        if not mentions:
            raise HTTPException(status_code=400, detail="Mentions and brand_name are required")

        result = await ml_service.batch_analyze_mentions(mentions, brand_name, include_bert)
        return {
            "success": True,
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Batch analysis failed")

@router.get("/analyze/realtime/{brand_name}")
async def realtime_brand_analysis(brand_name: str, request: Request):
    """Real-time streaming analysis for a brand (Server-Sent Events)"""
    brand_name = _validate_brand_name(brand_name)
    try:
        async def generate_analysis():
            """Generate real-time analysis stream"""
            deadline = time.monotonic() + _REALTIME_MAX_SECONDS
            while time.monotonic() < deadline:
                if await request.is_disconnected():
                    break
                try:
                    # Short-lived async session per poll: the request-scoped session from
                    # Depends(get_db) is already closed once streaming starts.
                    async with AsyncSessionLocal() as session:
                        brand = (await session.execute(
                            select(Brand).where(Brand.name == brand_name)
                        )).scalar_one_or_none()
                        recent_mentions = []
                        if brand:
                            recent_mentions = (await session.execute(
                                select(Mention)
                                .where(
                                    Mention.brand_id == brand.id,
                                    Mention.created_at >= datetime.utcnow() - timedelta(hours=1),
                                )
                                .limit(50)
                            )).scalars().all()

                    if recent_mentions:
                        mention_data = [
                            {
                                "id": str(mention.id),
                                "text": mention.content,
                                "source": mention.platform,
                                "timestamp": mention.created_at.isoformat() if mention.created_at else None,
                            }
                            for mention in recent_mentions
                        ]
                        analysis = await ml_service.analyze_brand_health(brand_name, mention_data)
                        yield f"data: {json.dumps(analysis, default=str)}\n\n"
                    else:
                        yield ": keep-alive\n\n"

                    await asyncio.sleep(30)  # Update every 30 seconds

                except Exception as e:
                    logger.error(f"Realtime analysis error: {e}")
                    # Don't leak internal exception details to clients
                    yield f"data: {json.dumps({'error': 'analysis temporarily unavailable'})}\n\n"
                    await asyncio.sleep(60)  # Wait longer on error

        return StreamingResponse(
            generate_analysis(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
        
    except Exception as e:
        logger.error(f"Realtime analysis setup failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to setup realtime analysis")

@router.post("/process/mention")
async def process_new_mention(
    mention_data: Dict,
    background_tasks: BackgroundTasks,
):
    """Process a new mention through the ML pipeline"""
    try:
        text = _validate_text(mention_data.get("text", ""))
        brand_name = _validate_brand_name(mention_data.get("brand_name", ""))
        source = mention_data.get("source", "unknown")
        
        # Quick sentiment analysis for immediate response
        sentiment_result = await ml_service.analyze_mention_sentiment(text, use_bert=False)
        
        # Add background processing for full analysis
        background_tasks.add_task(
            process_mention_background,
            mention_data,
        )
        
        return {
            "success": True,
            "mention_id": mention_data.get("id", "generated"),
            "quick_sentiment": sentiment_result.get("final_sentiment", {}),
            "message": "Mention processed, full analysis in progress"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mention processing failed: {e}")
        raise HTTPException(status_code=500, detail="Mention processing failed")

async def process_mention_background(mention_data: Dict):
    """Background task for full mention processing"""
    try:
        text = mention_data.get("text", "")
        brand_name = mention_data.get("brand_name", "")
        
        # Full sentiment analysis with BERT
        sentiment_result = await ml_service.analyze_mention_sentiment(text, use_bert=True)
        
        # Crisis detection
        crisis_result = await ml_service.analyze_crisis([mention_data], brand_name)
        
        # Store results in database (simplified)
        # In a real implementation, you'd store these results properly
        logger.info(f"Background analysis completed for mention: {mention_data.get('id')}")
        logger.info(f"Sentiment: {sentiment_result.get('final_sentiment', {}).get('sentiment_label')}")
        logger.info(f"Crisis Level: {crisis_result.get('overall_crisis_level')}")
        
    except Exception as e:
        logger.error(f"Background mention processing failed: {e}")

@router.get("/test/demo")
async def demo_ml_analysis():
    """Demo endpoint showing ML capabilities"""
    try:
        # Demo data
        demo_mentions = [
            {
                "id": "demo_1",
                "text": "I absolutely love this brand! Amazing quality and customer service.",
                "source": "twitter",
                "timestamp": datetime.now().isoformat()
            },
            {
                "id": "demo_2", 
                "text": "This product is terrible and dangerous! Major safety issues reported.",
                "source": "facebook",
                "timestamp": datetime.now().isoformat()
            },
            {
                "id": "demo_3",
                "text": "Lawsuit filed against company for fraud and data breach!",
                "source": "news",
                "timestamp": datetime.now().isoformat()
            }
        ]
        
        # Perform comprehensive analysis
        analysis_result = await ml_service.analyze_brand_health("DemoBrand", demo_mentions)
        
        return {
            "success": True,
            "demo_data": demo_mentions,
            "analysis": analysis_result,
            "message": "Demo analysis completed successfully"
        }
        
    except Exception as e:
        logger.error(f"Demo analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Demo analysis failed")

@router.post("/extract/features")
async def extract_text_features(data: Dict):
    """Extract features from text for analysis"""
    try:
        text = _validate_text(data.get("text", ""))

        features = await ml_service.extract_features(text)
        return {
            "success": True,
            "features": features,
            "text_length": len(text)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Feature extraction failed: {e}")
        raise HTTPException(status_code=500, detail="Feature extraction failed")
