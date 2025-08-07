#!/usr/bin/env python3
"""
Test script for the new price fetching functionality.
Tests the updated URL building, CSV parsing, and median calculation.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.service import db_service
from src.logging_config import setup_logging
from src.services.price_service import price_service


async def test_url_building():
    """Test URL building with new parameters."""
    print("Testing URL building...")
    
    target_date = datetime(2025, 8, 7).date()
    url = price_service._build_csv_url(target_date)
    
    print(f"Built URL: {url}")
    
    # Check that URL contains correct parameters
    expected_params = [
        'obexport_start=2025-08-07',
        'obexport_end=2025-08-09',  # Should be day after tomorrow
        'obexport_region=east',
    ]
    
    for param in expected_params:
        if param in url:
            print(f"✅ Found expected parameter: {param}")
        else:
            print(f"❌ Missing expected parameter: {param}")


async def test_database_migration():
    """Test database migration to schema version 2."""
    print("\nTesting database migration...")
    
    try:
        await db_service.init_database()
        print("✅ Database initialization successful")
        
        # Check if the migration worked
        import aiosqlite
        async with aiosqlite.connect(db_service.database_path) as db:
            cursor = await db.execute("PRAGMA table_info(price_records)")
            columns = await cursor.fetchall()
            
            column_names = [col[1] for col in columns]
            if 'median_price' in column_names:
                print("✅ median_price column found in database")
            else:
                print("❌ median_price column not found in database")
                print("Available columns:", column_names)
                
    except Exception as e:
        print(f"❌ Database migration failed: {e}")


async def test_csv_parsing():
    """Test CSV parsing with real data."""
    print("\nTesting CSV parsing...")
    
    # Sample CSV content (from your external context)
    sample_csv = '''Start,Elpris,"Transport og afgifter",Total
"08.08.2025 - 23:00","1,15","1,25","2,40"
"08.08.2025 - 22:00","1,28","1,25","2,53"
"08.08.2025 - 21:00","1,56","1,25","2,81"
"07.08.2025 - 23:00","1,09","1,25","2,34"
"07.08.2025 - 22:00","1,17","1,25","2,42"'''
    
    try:
        records = price_service._parse_danish_csv(sample_csv)
        print(f"✅ Parsed {len(records)} records")
        
        if records:
            first_record = records[0]
            print(f"✅ Sample record: {first_record.timestamp} - {first_record.total_price:.2f} DKK/kWh")
            print(f"✅ Median price: {first_record.median_price:.4f} DKK/kWh")
            print(f"✅ Category: {first_record.category}")
            
            # Check that all records have the same median
            median_prices = [r.median_price for r in records]
            if len(set(median_prices)) == 1:
                print("✅ All records have the same median price")
            else:
                print("❌ Records have different median prices")
                
    except Exception as e:
        print(f"❌ CSV parsing failed: {e}")


async def test_real_fetch():
    """Test fetching real data from Andel Energi."""
    print("\nTesting real data fetch...")
    
    try:
        count = await price_service.fetch_and_store_daily_prices()
        print(f"✅ Successfully fetched and stored {count} records")
        
        # Check some recent records
        recent = await db_service.get_recent_records(hours=6)
        if recent:
            print(f"✅ Found {len(recent)} recent records in database")
            for record in recent[:3]:  # Show first 3
                print(f"   {record.timestamp.strftime('%d.%m.%Y %H:%M')} - "
                      f"{record.total_price:.3f} DKK/kWh (median: {record.median_price:.3f}, "
                      f"category: {record.category})")
        
    except Exception as e:
        print(f"❌ Real fetch failed: {e}")


async def main():
    """Run all tests."""
    setup_logging()
    
    print("🧪 Testing New Price Fetching Functionality")
    print("=" * 50)
    
    await test_url_building()
    await test_database_migration()
    await test_csv_parsing()
    await test_real_fetch()
    
    print("\n" + "=" * 50)
    print("✅ Testing completed!")


if __name__ == "__main__":
    asyncio.run(main())
