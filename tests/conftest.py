"""
Test configuration and fixtures for the Energy Price API tests.
Contains shared fixtures and test utilities.
"""

from datetime import datetime, timedelta
from typing import List, Tuple
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from src.main import create_app
from src.models.price import PriceCategory, PriceRecord


def _calculate_percentile(sorted_values: List[float], percentile: float) -> float:
    """
    Calculate percentile using linear interpolation (like numpy.percentile).
    
    Args:
        sorted_values: List of values sorted in ascending order
        percentile: Percentile to calculate (0-100)
    
    Returns:
        Interpolated percentile value
    """
    if not sorted_values:
        return 0.0
    
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    
    # Convert percentile (0-100) to index position
    index = (percentile / 100.0) * (n - 1)
    
    # Get the lower and upper indices
    lower_idx = int(index)
    upper_idx = min(lower_idx + 1, n - 1)
    
    # If index is exactly an integer, return that value
    if lower_idx == upper_idx:
        return sorted_values[lower_idx]
    
    # Linear interpolation between the two nearest values
    fraction = index - lower_idx
    lower_value = sorted_values[lower_idx]
    upper_value = sorted_values[upper_idx]
    
    return lower_value + fraction * (upper_value - lower_value)


def _calculate_tertile_boundaries(prices: List[float]) -> Tuple[float, float]:
    """
    Calculate tertile boundaries (33rd and 67th percentiles) with proper interpolation.
    
    Args:
        prices: List of price values
    
    Returns:
        Tuple of (tertile_low, tertile_high) boundaries
    """
    if not prices:
        return 0.0, 0.0
    
    if len(prices) < 3:
        # For very small datasets, use min/max as boundaries
        min_price = min(prices)
        max_price = max(prices)
        if min_price == max_price:
            return min_price, max_price
        # Split into approximate thirds
        range_third = (max_price - min_price) / 3.0
        return min_price + range_third, min_price + 2 * range_third
    
    sorted_prices = sorted(prices)
    
    # Calculate 33rd and 67th percentiles with interpolation
    tertile_low = _calculate_percentile(sorted_prices, 33.333)
    tertile_high = _calculate_percentile(sorted_prices, 66.667)
    
    return tertile_low, tertile_high


@pytest.fixture
def test_app():
    """
    Create a test instance of the FastAPI application.
    """
    app = create_app()
    return app


@pytest.fixture
def test_client(test_app):
    """
    Create a test client for the FastAPI application.
    """
    return TestClient(test_app)


@pytest.fixture
def sample_price_records() -> List[PriceRecord]:
    """
    Create sample price records for testing.
    """
    base_time = datetime(2025, 8, 7, 0, 0, 0)  # Start at midnight
    
    records = []
    for hour in range(24):
        # Create varied prices for testing optimization logic
        spot_price = 1.0 + (hour * 0.1)  # Gradually increasing
        transport_taxes = 1.25
        total_price = spot_price + transport_taxes
        
        # Make hour 3 the cheapest
        if hour == 3:
            spot_price = 0.5
            total_price = spot_price + transport_taxes
        
        records.append(PriceRecord(
            timestamp=base_time + timedelta(hours=hour),
            spot_price=spot_price,
            transport_taxes=transport_taxes,
            total_price=total_price,
            median_price=0.0,  # Will be calculated below
            category=PriceCategory.OKAY,  # Will be updated based on tertiles
        ))
    
    # Calculate median and tertile thresholds using proper percentile interpolation
    total_prices = [r.total_price for r in records]
    sorted_prices = sorted(total_prices)
    n = len(sorted_prices)
    
    median_price = sorted_prices[n // 2]
    tertile_low, tertile_high = _calculate_tertile_boundaries(total_prices)
    
    # Update all records with median and tertile-based categories
    for record in records:
        record.median_price = median_price
        if record.total_price <= tertile_low:
            record.category = PriceCategory.PREFER  # Bottom 1/3 - cheapest
        elif record.total_price >= tertile_high:
            record.category = PriceCategory.AVOID   # Top 1/3 - most expensive
        else:
            record.category = PriceCategory.OKAY    # Middle 1/3
    
    return records


@pytest.fixture
def mock_price_service():
    """
    Create a mock price service for testing.
    """
    mock_service = AsyncMock()
    return mock_service


@pytest.fixture
def mock_db_service():
    """
    Create a mock database service for testing.
    """
    mock_db = AsyncMock()
    return mock_db
