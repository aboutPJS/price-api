"""
FastAPI route handlers for the main API endpoints.
Implements the two core endpoints specified in the PRD.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.database.service import db_service
from src.exceptions import NoPriceDataError, NoSequenceFoundError, PriceAPIException
from src.logging_config import get_logger
from src.models.price import HealthResponse, OptimalTimeResponse
from src.services.price_service import price_service

logger = get_logger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    Returns health status with last fetch timestamp to monitor data freshness.
    
    The last_fetch timestamp shows when the most recent price data was inserted
    into the database, helping monitor if the daily data fetching is working properly.
    """
    try:
        # Get the latest record timestamp to check data freshness
        last_fetch = await db_service.get_latest_record_timestamp()
        
        # Convert to Copenhagen time if available
        last_fetch_copenhagen = None
        if last_fetch:
            # PostgreSQL typically stores CURRENT_TIMESTAMP as UTC
            # Convert to Copenhagen time for better readability
            import pytz
            copenhagen_tz = pytz.timezone('Europe/Copenhagen')
            
            # If timestamp is timezone-naive, assume it's UTC
            if last_fetch.tzinfo is None:
                last_fetch_utc = last_fetch.replace(tzinfo=pytz.UTC)
            else:
                last_fetch_utc = last_fetch.astimezone(pytz.UTC)
            
            last_fetch_copenhagen = last_fetch_utc.astimezone(copenhagen_tz)
        
        # Calculate data freshness
        data_age_hours = None
        data_status = "unknown"
        
        if last_fetch_copenhagen:
            now_copenhagen = datetime.now(copenhagen_tz)
            data_age = now_copenhagen - last_fetch_copenhagen
            data_age_hours = round(data_age.total_seconds() / 3600, 1)
            
            # Classify data freshness
            if data_age_hours <= 3:
                data_status = "fresh"  # Very recent
            elif data_age_hours <= 25:
                data_status = "acceptable"  # Within daily update cycle
            else:
                data_status = "stale"  # More than a day old
        
        details = {
            "service": "energy-price-api",
            "last_fetch": last_fetch_copenhagen.isoformat() if last_fetch_copenhagen else None,
            "last_fetch_utc": last_fetch.isoformat() if last_fetch else None,
            "data_age_hours": data_age_hours,
            "data_status": data_status
        }
        
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now(),
            details=details
        )
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.now(),
            details={"service": "energy-price-api", "error": str(e)}
        )


@router.get("/cheapest-hour", response_model=OptimalTimeResponse)
async def get_cheapest_hour(
    within_hours: Optional[int] = Query(
        default=None,
        description="Look ahead window in hours. If not specified, uses all available predictions.",
        ge=1,
        le=168  # Max 1 week ahead
    ),
    format: str = Query(
        default="hours",
        description="Time format: 'hours' for HH:MM format, 'minutes' for integer minutes",
        pattern="^(hours|minutes)$"
    )
):
    """
    Find the single cheapest hour within the specified timeframe.
    
    This endpoint returns the start time of the single hour with the lowest 
    total energy price within the given time window.
    
    Args:
        within_hours: Optional look ahead window in hours. Defaults to all available data.
        
    Returns:
        OptimalTimeResponse with the start time of the cheapest hour.
        
    Raises:
        HTTPException: 404 if no data is available, 500 for server errors.
    """
    try:
        result = await price_service.get_cheapest_hour(within_hours, format)
        return result
        
    except NoPriceDataError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PriceAPIException as e:
        logger.error("Price API error", error=str(e), within_hours=within_hours)
        raise HTTPException(status_code=500, detail="Internal server error")
    except Exception as e:
        logger.error("Unexpected error", error=str(e), within_hours=within_hours)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/cheapest-sequence-start", response_model=OptimalTimeResponse)
async def get_cheapest_sequence_start(
    duration: int = Query(
        description="Length of sequence in hours (required)",
        ge=1,
        le=24  # Max 24 hours sequence
    ),
    within_hours: Optional[int] = Query(
        default=None,
        description="Look ahead window in hours. If not specified, uses all available predictions.",
        ge=1,
        le=168  # Max 1 week ahead
    ),
    format: str = Query(
        default="hours",
        description="Time format: 'hours' for HH:MM format, 'minutes' for integer minutes",
        pattern="^(hours|minutes)$"
    )
):
    """
    Find the start time of the cheapest consecutive sequence of specified duration.
    
    This endpoint finds the optimal start time for a sequence of consecutive hours
    that minimizes the total energy cost for the specified duration.
    
    Args:
        duration: Length of sequence in hours (required, 1-24 hours).
        within_hours: Optional look ahead window in hours. Defaults to all available data.
        
    Returns:
        OptimalTimeResponse with the start time of the cheapest sequence.
        
    Raises:
        HTTPException: 400 for invalid parameters, 404 if no data available, 500 for server errors.
    """
    try:
        # Business logic validation
        if within_hours is not None and duration > within_hours:
            raise HTTPException(
                status_code=400,
                detail="Duration cannot be longer than the look ahead window"
            )
        
        result = await price_service.get_cheapest_sequence_start(duration, within_hours, format)
        return result
        
    except HTTPException:
        raise
    except NoSequenceFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PriceAPIException as e:
        logger.error("Price API error", error=str(e), duration=duration, within_hours=within_hours)
        raise HTTPException(status_code=500, detail="Internal server error")
    except Exception as e:
        logger.error("Unexpected error", error=str(e), duration=duration, within_hours=within_hours)
        raise HTTPException(status_code=500, detail="Internal server error")
