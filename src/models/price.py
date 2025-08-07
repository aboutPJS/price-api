"""
Pydantic data models for price data and API responses.
Defines the structure for price records and API response formats.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PriceCategory(str, Enum):
    """
    Price categorization based on 48-hour median total price (today + tomorrow).
    """
    CHEAPEST = "CHEAPEST"  # Single cheapest hour of the 48-hour period
    CHEAP = "CHEAP"        # Below median total_price
    EXPENSIVE = "EXPENSIVE"  # Above median total_price


class PriceRecord(BaseModel):
    """
    Represents a single hourly price record from Andel Energi.
    
    Based on CSV format:
    "Start","Elpris","Transport og afgifter","Total"
    "07.08.2025 - 23:00","1,09","1,25","2,34"
    """
    timestamp: datetime = Field(
        description="Parsed timestamp from 'Start' field (Danish format: DD.MM.YYYY - HH:MM)"
    )
    spot_price: float = Field(
        description="Raw energy price from 'Elpris' field (DKK/kWh)",
        ge=0.0
    )
    transport_taxes: float = Field(
        description="Grid costs and taxes from 'Transport og afgifter' field (DKK/kWh)",
        ge=0.0
    )
    total_price: float = Field(
        description="Final price per kWh from 'Total' field (DKK/kWh)",
        ge=0.0
    )
    median_price: float = Field(
        description="48-hour median price (today + tomorrow) used for categorization (DKK/kWh)",
        ge=0.0
    )
    category: PriceCategory = Field(
        description="Price category based on 48-hour median comparison"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class OptimalTimeResponse(BaseModel):
    """
    API response for optimal timing endpoints.
    Returns the start time for optimal energy usage.
    """
    start_time: datetime = Field(
        description="ISO format timestamp for optimal start time"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class HealthResponse(BaseModel):
    """
    Health check response model.
    """
    status: str = Field(description="Health status")
    timestamp: datetime = Field(description="Health check timestamp")
    details: Optional[dict] = Field(default=None, description="Additional health details")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
