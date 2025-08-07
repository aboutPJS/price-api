"""
Unified price service - handles data fetching and optimization.
Combines the previous data fetcher, optimizer, and repository into one service.
"""

from datetime import datetime, timedelta
from io import StringIO
from typing import List, Optional
from urllib.parse import urlencode

import httpx
import pandas as pd

from src.config import settings
from src.database.service import db_service
from src.exceptions import DataFetchError, NoPriceDataError, NoSequenceFoundError
from src.logging_config import get_logger
from src.models.price import OptimalTimeResponse, PriceCategory, PriceRecord

logger = get_logger(__name__)


class PriceService:
    """Unified service for price data fetching, storage, and optimization."""
    
    def __init__(self):
        self.base_url = settings.andel_energi_base_url
        self.timeout = 30
    
    async def fetch_and_store_daily_prices(self, target_date: datetime = None) -> int:
        """Fetch daily prices from Andel Energi and store them."""
        if target_date is None:
            target_date = datetime.now().date() + timedelta(days=1)
        
        try:
            # Build URL and fetch data
            url = self._build_csv_url(target_date)
            csv_content = await self._fetch_csv_data(url)
            
            # Parse and store
            records = self._parse_danish_csv(csv_content)
            await db_service.save_price_records(records)
            
            logger.info("Fetched and stored daily prices", date=target_date.isoformat(), count=len(records))
            return len(records)
            
        except Exception as e:
            logger.error("Failed to fetch daily prices", error=str(e), date=target_date.isoformat() if target_date else None)
            raise DataFetchError(f"Failed to fetch prices: {e}")
    
    async def get_cheapest_hour(self, within_hours: Optional[int] = None) -> OptimalTimeResponse:
        """Find the cheapest hour."""
        record = await db_service.get_cheapest_hour(within_hours)
        logger.debug("Found cheapest hour", start_time=record.timestamp.isoformat(), price=record.total_price)
        return OptimalTimeResponse(start_time=record.timestamp)
    
    async def get_cheapest_sequence_start(self, duration: int, within_hours: Optional[int] = None) -> OptimalTimeResponse:
        """Find the start of cheapest consecutive sequence."""
        if duration <= 0:
            raise ValueError("Duration must be positive")
        
        record = await db_service.get_cheapest_sequence_start(duration, within_hours)
        logger.debug("Found cheapest sequence", start_time=record.timestamp.isoformat(), duration=duration)
        return OptimalTimeResponse(start_time=record.timestamp)
    
    async def cleanup_old_data(self) -> int:
        """Clean up old price records."""
        return await db_service.cleanup_old_records(settings.data_retention_days)
    
    def _build_csv_url(self, target_date: datetime) -> str:
        """Build Andel Energi CSV URL."""
        start_date = datetime.combine(target_date, datetime.min.time())
        end_date = start_date + timedelta(days=1)
        
        params = {
            'obexport_format': 'csv',
            'obexport_start': start_date.strftime('%Y-%m-%d'),
            'obexport_end': end_date.strftime('%Y-%m-%d'),
            'obexport_region': settings.andel_energi_region,
            'obexport_tax': settings.andel_energi_tax,
            'obexport_product_id': settings.andel_energi_product_id,
        }
        
        return f"{self.base_url}?{urlencode(params)}"
    
    async def _fetch_csv_data(self, url: str) -> str:
        """Download CSV data."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except httpx.HTTPError as e:
            raise DataFetchError(f"HTTP error: {e}")
        except Exception as e:
            raise DataFetchError(f"Unexpected error: {e}")
    
    def _parse_danish_csv(self, csv_content: str) -> List[PriceRecord]:
        """Parse Danish CSV format into PriceRecord objects."""
        try:
            df = pd.read_csv(
                StringIO(csv_content),
                sep=',',
                decimal=',',
                parse_dates=False,
            )
            
            expected_columns = ['Start', 'Elpris', 'Transport og afgifter', 'Total']
            if not all(col in df.columns for col in expected_columns):
                missing = set(expected_columns) - set(df.columns)
                raise ValueError(f"Missing CSV columns: {missing}")
            
            records = []
            prices_for_categorization = []
            
            # First pass: parse records
            for _, row in df.iterrows():
                timestamp = self._parse_danish_datetime(row['Start'].strip())
                spot_price = float(str(row['Elpris']).replace(',', '.'))
                transport_taxes = float(str(row['Transport og afgifter']).replace(',', '.'))
                total_price = float(str(row['Total']).replace(',', '.'))
                
                record = PriceRecord(
                    timestamp=timestamp,
                    spot_price=spot_price,
                    transport_taxes=transport_taxes,
                    total_price=total_price,
                    category=PriceCategory.CHEAP,  # Will be updated
                )
                
                records.append(record)
                prices_for_categorization.append(total_price)
            
            # Second pass: categorize
            if prices_for_categorization:
                median_price = sorted(prices_for_categorization)[len(prices_for_categorization) // 2]
                min_price = min(prices_for_categorization)
                
                for record in records:
                    if record.total_price == min_price:
                        record.category = PriceCategory.CHEAPEST
                    elif record.total_price <= median_price:
                        record.category = PriceCategory.CHEAP
                    else:
                        record.category = PriceCategory.EXPENSIVE
            
            return records
            
        except Exception as e:
            raise DataFetchError(f"CSV parsing failed: {e}")
    
    def _parse_danish_datetime(self, datetime_str: str) -> datetime:
        """Parse Danish datetime: '07.08.2025 - 23:00'"""
        try:
            date_part, time_part = datetime_str.split(' - ')
            day, month, year = date_part.split('.')
            hour, minute = time_part.split(':')
            
            return datetime(
                year=int(year),
                month=int(month),
                day=int(day),
                hour=int(hour),
                minute=int(minute),
            )
        except Exception as e:
            raise ValueError(f"Invalid Danish datetime format '{datetime_str}': {e}")


# Global price service instance
price_service = PriceService()
