#!/usr/bin/env python3
"""
Development helper scripts for the Energy Price API.
Provides utilities for testing, database management, and manual operations.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.database.service import db_service
from src.logging_config import setup_logging
from src.scheduler.simple_scheduler import simple_scheduler
from src.services.price_service import price_service


async def init_db():
    """Initialize the database with required tables."""
    print("Initializing database...")
    setup_logging()
    await db_service.init_database()
    print(f"Database initialized at: {settings.database_path}")


async def fetch_prices_manual():
    """Manually fetch and store price data."""
    print("Starting manual price fetch...")
    setup_logging()
    await db_service.init_database()
    
    await simple_scheduler.run_manual_fetch()
    print("Manual price fetch completed")


async def show_recent_prices():
    """Display recent price data from the database."""
    print("Fetching recent price data...")
    setup_logging()
    
    records = await db_service.get_recent_records(hours=48)
    
    if not records:
        print("No price data found in database")
        return
    
    print(f"\nFound {len(records)} recent price records:")
    print("-" * 80)
    print(f"{'Timestamp':<20} {'Spot Price':<12} {'Transport':<12} {'Total':<12} {'Category':<12}")
    print("-" * 80)
    
    for record in records:
        print(f"{record.timestamp.strftime('%Y-%m-%d %H:%M'):<20} "
              f"{record.spot_price:>8.3f} DKK {record.transport_taxes:>8.3f} DKK "
              f"{record.total_price:>8.3f} DKK {record.category.value:<12}")


async def test_optimization():
    """Test price optimization algorithms with current data."""
    print("Testing price optimization...")
    setup_logging()
    
    try:
        # Test cheapest hour
        print("\n1. Finding cheapest hour in next 24 hours:")
        cheapest_hour = await price_service.get_cheapest_hour(within_hours=24)
        print(f"   Cheapest hour starts at: {cheapest_hour.start_time}")
    except Exception as e:
        print(f"   Error: {e}")
    
    try:
        # Test cheapest sequence
        print("\n2. Finding cheapest 3-hour sequence:")
        sequence_start = await price_service.get_cheapest_sequence_start(duration=3, within_hours=24)
        print(f"   Cheapest 3-hour sequence starts at: {sequence_start.start_time}")
    except Exception as e:
        print(f"   Error: {e}")


async def cleanup_old_data():
    """Clean up old price data based on retention settings."""
    print(f"Cleaning up data older than {settings.data_retention_days} days...")
    setup_logging()
    
    deleted_count = await price_service.cleanup_old_data()
    print(f"Deleted {deleted_count} old records")


def show_config():
    """Display current configuration settings."""
    print("Current Configuration:")
    print("-" * 40)
    print(f"API Host: {settings.api_host}")
    print(f"API Port: {settings.api_port}")
    print(f"Debug Mode: {settings.api_debug}")
    print(f"Database Path: {settings.database_path}")
    print(f"Fetch Schedule: {settings.fetch_hour}:{settings.fetch_minute:02d} {settings.fetch_timezone}")
    print(f"Data Retention: {settings.data_retention_days} days")
    print(f"Log Level: {settings.log_level}")
    print(f"Andel Energi Region: {settings.andel_energi_region}")


async def test_api_connection():
    """Test connection to Andel Energi API."""
    print("Testing Andel Energi API connection...")
    setup_logging()
    
    try:
        target_date = datetime.now().date()
        record_count = await price_service.fetch_and_store_daily_prices(target_date)
        
        print(f"Successfully fetched {record_count} price records")
        
        # Show recent records
        records = await db_service.get_recent_records(hours=2)
        if records:
            print(f"First record: {records[0].timestamp} - {records[0].total_price} DKK/kWh")
            print(f"Last record: {records[-1].timestamp} - {records[-1].total_price} DKK/kWh")
        
    except Exception as e:
        print(f"API connection failed: {e}")


def test_sequence_fix():
    """Run sequence query fix validation tests."""
    import subprocess
    import sys
    
    script_path = Path(__file__).parent / "test_sequence_fix.py"
    print(f"Running sequence fix test: {script_path}")
    
    try:
        result = subprocess.run([sys.executable, str(script_path)], 
                               capture_output=False, text=True)
        if result.returncode != 0:
            print(f"Test failed with exit code: {result.returncode}")
        else:
            print("Sequence tests completed")
    except Exception as e:
        print(f"Error running tests: {e}")


def main():
    """Main script entry point with command selection."""
    if len(sys.argv) < 2:
        print("Energy Price API Development Scripts")
        print("Usage: python scripts/dev.py <command>")
        print("\nAvailable commands:")
        print("  init-db           - Initialize database")
        print("  fetch-prices      - Manually fetch price data")
        print("  show-prices       - Display recent price data")
        print("  test-optimization - Test price optimization algorithms")
        print("  cleanup-data      - Clean up old price data")
        print("  show-config       - Display current configuration")
        print("  test-api          - Test Andel Energi API connection")
        print("  test-sequences    - Test sequence query fix validation")
        return
    
    command = sys.argv[1]
    
    if command == "init-db":
        asyncio.run(init_db())
    elif command == "fetch-prices":
        asyncio.run(fetch_prices_manual())
    elif command == "show-prices":
        asyncio.run(show_recent_prices())
    elif command == "test-optimization":
        asyncio.run(test_optimization())
    elif command == "cleanup-data":
        asyncio.run(cleanup_old_data())
    elif command == "show-config":
        show_config()
    elif command == "test-api":
        asyncio.run(test_api_connection())
    elif command == "test-sequences":
        test_sequence_fix()
    else:
        print(f"Unknown command: {command}")
        print("Run without arguments to see available commands")


if __name__ == "__main__":
    main()
