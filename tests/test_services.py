"""
Unit tests for unified service layer.
Tests the simplified price service and database service.
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.exceptions import NoPriceDataError, NoSequenceFoundError, DataFetchError
from src.models.price import OptimalTimeResponse, PriceCategory, PriceRecord
from src.services.price_service import PriceService


class TestPriceService:
    """Tests for the unified PriceService."""
    
    @pytest.fixture
    def price_service(self):
        """Create a PriceService instance for testing."""
        return PriceService()
    
    def test_build_csv_url(self, price_service):
        """Test CSV URL construction."""
        target_date = datetime(2025, 8, 7).date()
        url = price_service._build_csv_url(target_date)
        
        assert "andelenergi.dk" in url
        assert "obexport_format=csv" in url
        assert "obexport_start=2025-08-07" in url
        assert "obexport_end=2025-08-09" in url  # Updated: now fetches 48 hours (today + tomorrow)
        assert "obexport_region=east" in url
        assert "obexport_product_id=1%231%23TIMEENERGI" in url
    
    def test_parse_danish_datetime(self, price_service):
        """Test Danish datetime format parsing."""
        datetime_str = "07.08.2025 - 23:00"
        result = price_service._parse_danish_datetime(datetime_str)
        assert result == datetime(2025, 8, 7, 23, 0, 0)
    
    def test_parse_danish_datetime_invalid(self, price_service):
        """Test Danish datetime parsing with invalid format."""
        with pytest.raises(ValueError, match="Invalid Danish datetime format"):
            price_service._parse_danish_datetime("invalid format")
    
    def test_parse_danish_csv(self, price_service):
        """Test parsing of Danish CSV format."""
        csv_content = '''Start,Elpris,Transport og afgifter,Total
"07.08.2025 - 00:00","1,50","1,25","2,75"
"07.08.2025 - 01:00","1,00","1,25","2,25"
"07.08.2025 - 02:00","2,00","1,25","3,25"'''
        
        records = price_service._parse_danish_csv(csv_content)
        
        assert len(records) == 3
        assert records[0].timestamp == datetime(2025, 8, 7, 0, 0, 0)
        assert records[0].spot_price == 1.50
        assert records[0].transport_taxes == 1.25
        assert records[0].total_price == 2.75
        
        # Record with price 2.25 should be CHEAPEST
        assert records[1].category == PriceCategory.CHEAPEST
        assert records[1].total_price == 2.25
    
    def test_parse_danish_csv_missing_columns(self, price_service):
        """Test CSV parsing with missing required columns."""
        csv_content = '''Start,Elpris,Total
"07.08.2025 - 00:00","1,50","2,75"'''
        
        with pytest.raises(DataFetchError, match="CSV parsing failed"):
            price_service._parse_danish_csv(csv_content)
    
    @pytest.mark.asyncio
    async def test_fetch_csv_data_success(self, price_service):
        """Test successful CSV data fetching."""
        mock_csv_content = "Start,Elpris,Transport og afgifter,Total\n"
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = mock_csv_content
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await price_service._fetch_csv_data("http://example.com/test.csv")
            assert result == mock_csv_content
    
    @pytest.mark.asyncio
    async def test_fetch_csv_data_http_error(self, price_service):
        """Test CSV data fetching with HTTP error."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = Exception("Network error")
            
            with pytest.raises(DataFetchError, match="Unexpected error"):
                await price_service._fetch_csv_data("http://example.com/test.csv")
    
    @pytest.mark.asyncio
    async def test_get_cheapest_hour_success(self, price_service):
        """Test successful cheapest hour request."""
        mock_record = PriceRecord(
            timestamp=datetime(2025, 8, 7, 14, 0, 0),
            spot_price=1.0,
            transport_taxes=1.25,
            total_price=2.25,
            median_price=2.50,
            category=PriceCategory.CHEAPEST
        )
        
        with patch('src.database.service.db_service.get_cheapest_hour', new=AsyncMock(return_value=mock_record)) as mock_method:
            result = await price_service.get_cheapest_hour(within_hours=24)
            
            assert isinstance(result, OptimalTimeResponse)
            assert result.start_time == datetime(2025, 8, 7, 14, 0, 0)
            mock_method.assert_called_once_with(24)
    
    @pytest.mark.asyncio
    async def test_get_cheapest_sequence_start_success(self, price_service):
        """Test successful cheapest sequence request."""
        mock_record = PriceRecord(
            timestamp=datetime(2025, 8, 7, 23, 0, 0),
            spot_price=1.0,
            transport_taxes=1.25,
            total_price=2.25,
            median_price=2.50,
            category=PriceCategory.CHEAP
        )
        
        with patch('src.database.service.db_service.get_cheapest_sequence_start', new=AsyncMock(return_value=mock_record)) as mock_method:
            result = await price_service.get_cheapest_sequence_start(duration=3, within_hours=12)
            
            assert isinstance(result, OptimalTimeResponse)
            assert result.start_time == datetime(2025, 8, 7, 23, 0, 0)
            mock_method.assert_called_once_with(3, 12)
    
    @pytest.mark.asyncio
    async def test_get_cheapest_sequence_start_invalid_duration(self, price_service):
        """Test cheapest sequence with invalid duration."""
        with pytest.raises(ValueError, match="Duration must be positive"):
            await price_service.get_cheapest_sequence_start(duration=0)
        
        with pytest.raises(ValueError, match="Duration must be positive"):
            await price_service.get_cheapest_sequence_start(duration=-1)
