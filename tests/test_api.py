"""
Unit tests for API endpoints.
Tests the FastAPI route handlers and response formats.
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.exceptions import NoPriceDataError, NoSequenceFoundError
from src.models.price import OptimalTimeResponse


class TestHealthEndpoint:
    """Tests for the health check endpoint."""
    
    def test_health_check_success(self, test_client):
        """Test that health check returns successful response."""
        response = test_client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["details"]["service"] == "energy-price-api"


class TestCheapestHourEndpoint:
    """Tests for the cheapest hour endpoint."""
    
    @patch("src.api.routes.price_service")
    def test_cheapest_hour_success(self, mock_price_service, test_client):
        """Test successful cheapest hour request."""
        # Mock the service response
        mock_price_service.get_cheapest_hour = AsyncMock(return_value=OptimalTimeResponse(
            start_time=datetime(2025, 8, 7, 14, 0, 0),
            time_until="03:30"
        ))
        
        response = test_client.get("/api/v1/cheapest-hour")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "start_time" in data
        assert data["start_time"] == "2025-08-07T14:00:00"
        mock_price_service.get_cheapest_hour.assert_called_once_with(None, "hours")
    
    @patch("src.api.routes.price_service")
    def test_cheapest_hour_with_within_hours(self, mock_price_service, test_client):
        """Test cheapest hour request with within_hours parameter."""
        mock_price_service.get_cheapest_hour = AsyncMock(return_value=OptimalTimeResponse(
            start_time=datetime(2025, 8, 7, 14, 0, 0),
            time_until="03:30"
        ))
        
        response = test_client.get("/api/v1/cheapest-hour?within_hours=12")
        
        assert response.status_code == 200
        mock_price_service.get_cheapest_hour.assert_called_once_with(12, "hours")
    
    @patch("src.api.routes.price_service")
    def test_cheapest_hour_no_data(self, mock_price_service, test_client):
        """Test cheapest hour request when no data is available."""
        mock_price_service.get_cheapest_hour = AsyncMock(side_effect=NoPriceDataError("No data available"))
        
        response = test_client.get("/api/v1/cheapest-hour")
        
        assert response.status_code == 404
        data = response.json()
        assert "No data available" in data["detail"]
    
    def test_cheapest_hour_invalid_within_hours(self, test_client):
        """Test cheapest hour with invalid within_hours parameter."""
        # Test negative value
        response = test_client.get("/api/v1/cheapest-hour?within_hours=-1")
        assert response.status_code == 422
        
        # Test value too large
        response = test_client.get("/api/v1/cheapest-hour?within_hours=200")
        assert response.status_code == 422


class TestCheapestSequenceStartEndpoint:
    """Tests for the cheapest sequence start endpoint."""
    
    @patch("src.api.routes.price_service")
    def test_cheapest_sequence_success(self, mock_price_service, test_client):
        """Test successful cheapest sequence request."""
        mock_price_service.get_cheapest_sequence_start = AsyncMock(return_value=OptimalTimeResponse(
            start_time=datetime(2025, 8, 7, 23, 0, 0),
            time_until="09:00"
        ))
        
        response = test_client.get("/api/v1/cheapest-sequence-start?duration=3")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "start_time" in data
        assert data["start_time"] == "2025-08-07T23:00:00"
        mock_price_service.get_cheapest_sequence_start.assert_called_once_with(3, None, "hours")
    
    @patch("src.api.routes.price_service")
    def test_cheapest_sequence_with_within_hours(self, mock_price_service, test_client):
        """Test cheapest sequence request with within_hours parameter."""
        mock_price_service.get_cheapest_sequence_start = AsyncMock(return_value=OptimalTimeResponse(
            start_time=datetime(2025, 8, 7, 23, 0, 0),
            time_until="09:00"
        ))
        
        response = test_client.get("/api/v1/cheapest-sequence-start?duration=3&within_hours=12")
        
        assert response.status_code == 200
        mock_price_service.get_cheapest_sequence_start.assert_called_once_with(3, 12, "hours")
    
    @patch("src.api.routes.price_service")
    def test_cheapest_sequence_no_data(self, mock_price_service, test_client):
        """Test cheapest sequence request when no suitable sequence is found."""
        mock_price_service.get_cheapest_sequence_start = AsyncMock(side_effect=NoSequenceFoundError("No suitable sequence found"))
        
        response = test_client.get("/api/v1/cheapest-sequence-start?duration=3")
        
        assert response.status_code == 404
        data = response.json()
        assert "No suitable sequence found" in data["detail"]
    
    def test_cheapest_sequence_missing_duration(self, test_client):
        """Test cheapest sequence request without required duration parameter."""
        response = test_client.get("/api/v1/cheapest-sequence-start")
        
        assert response.status_code == 422  # Validation error
    
    def test_cheapest_sequence_invalid_duration(self, test_client):
        """Test cheapest sequence with invalid duration parameter."""
        # Test zero duration
        response = test_client.get("/api/v1/cheapest-sequence-start?duration=0")
        assert response.status_code == 422
        
        # Test negative duration
        response = test_client.get("/api/v1/cheapest-sequence-start?duration=-1")
        assert response.status_code == 422
        
        # Test duration too large
        response = test_client.get("/api/v1/cheapest-sequence-start?duration=25")
        assert response.status_code == 422
    
    def test_cheapest_sequence_duration_longer_than_window(self, test_client):
        """Test cheapest sequence when duration is longer than within_hours."""
        response = test_client.get("/api/v1/cheapest-sequence-start?duration=10&within_hours=5")
        
        assert response.status_code == 400
        data = response.json()
        assert "Duration cannot be longer than the look ahead window" in data["detail"]
