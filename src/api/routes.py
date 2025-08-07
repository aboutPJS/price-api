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
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        details={"service": "energy-price-api"}
    )


@router.get("/cheapest-hour", response_model=OptimalTimeResponse)
async def get_cheapest_hour(
    within_hours: Optional[int] = Query(
        default=None,
        description="Look ahead window in hours. If not specified, uses all available predictions.",
        ge=1,
        le=168  # Max 1 week ahead
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
        result = await price_service.get_cheapest_hour(within_hours)
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
        
        result = await price_service.get_cheapest_sequence_start(duration, within_hours)
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
