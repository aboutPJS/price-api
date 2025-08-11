"""
Pydantic data models for price data and API responses.
Defines the structure for price records and API response formats.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field


class PriceCategory(str, Enum):
    """
    Price categorization based on 48-hour tertiles (today + tomorrow).
    """
    AVOID = "AVOID"      # Top 1/3 most expensive (highest total costs)
    OKAY = "OKAY"        # Middle 1/3 
    PREFER = "PREFER"    # Bottom 1/3 least expensive (lowest total costs)


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
    spot_price: Decimal = Field(
        description="Raw energy price from 'Elpris' field (DKK/kWh) - can be negative in some markets",
        decimal_places=6
    )
    transport_taxes: Decimal = Field(
        description="Grid costs and taxes from 'Transport og afgifter' field (DKK/kWh)",
        ge=0.0,  # Transport taxes should always be non-negative
        decimal_places=6
    )
    total_price: Decimal = Field(
        description="Final price per kWh from 'Total' field (DKK/kWh) - can be negative with very low spot prices",
        decimal_places=6
    )
    median_price: Decimal = Field(
        description="48-hour median price (today + tomorrow) for reference (DKK/kWh)",
        decimal_places=6
    )
    category: PriceCategory = Field(
        description="Price category based on 48-hour tertiles (AVOID/OKAY/PREFER)"
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
    time_until: Union[str, int] = Field(
        description="Time until start_time in 'HH:MM' format or minutes (based on format parameter)"
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
