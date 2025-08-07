"""
Test configuration and fixtures for the Energy Price API tests.
Contains shared fixtures and test utilities.
"""

from datetime import datetime, timedelta
from typing import List
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from src.main import create_app
from src.models.price import PriceCategory, PriceRecord


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
            category=PriceCategory.CHEAP,  # Will be updated based on median
        ))
    
    # Calculate median and update categories
    total_prices = [r.total_price for r in records]
    median_price = sorted(total_prices)[len(total_prices) // 2]
    min_price = min(total_prices)
    
    for record in records:
        if record.total_price == min_price:
            record.category = PriceCategory.CHEAPEST
        elif record.total_price <= median_price:
            record.category = PriceCategory.CHEAP
        else:
            record.category = PriceCategory.EXPENSIVE
    
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
