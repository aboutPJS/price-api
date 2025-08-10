#!/usr/bin/env python3
"""
Test script to validate the sequence query fix.
Tests various edge cases to ensure no past timestamps are returned.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.database.service import db_service
from src.logging_config import setup_logging, get_logger
from src.models.price import PriceCategory, PriceRecord

logger = get_logger(__name__)


async def create_test_data():
    """Create test data spanning past and future hours."""
    setup_logging()
    await db_service.init_database()
    
    print("Creating test data...")
    
    # Create 48 hours of test data: 24 hours in past, 24 hours in future
    now = datetime.now()
    start_time = now - timedelta(hours=24)
    
    records = []
    for i in range(48):
        timestamp = start_time + timedelta(hours=i)
        
        # Create varied prices with some patterns
        base_price = 2.0
        if i < 12:  # Past morning (expensive)
            price = base_price + 0.8
        elif i < 24:  # Past afternoon/evening (cheaper)
            price = base_price + 0.2
        elif i < 30:  # Future early hours (very cheap)
            price = base_price - 0.5
        elif i < 36:  # Future morning (expensive)
            price = base_price + 1.0
        else:  # Future afternoon/evening (moderate)
            price = base_price + 0.3
        
        record = PriceRecord(
            timestamp=timestamp,
            spot_price=price * 0.8,
            transport_taxes=price * 0.2,
            total_price=price,
            median_price=base_price,  # Fixed median for simplicity
            category=PriceCategory.OKAY  # Will be updated by tertiles
        )
        records.append(record)
    
    await db_service.save_price_records(records)
    print(f"Created {len(records)} test records")
    
    # Show the data around current time
    print(f"\nCurrent time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("Test data around current time:")
    print("-" * 60)
    
    for i, record in enumerate(records):
        if abs((record.timestamp - now).total_seconds()) < 6 * 3600:  # Within 6 hours
            status = "PAST" if record.timestamp < now else "FUTURE"
            print(f"{status:6} | {record.timestamp.strftime('%Y-%m-%d %H:%M')} | {record.total_price:.2f} DKK/kWh")


async def test_sequence_queries():
    """Test various sequence queries to validate the fix."""
    print("\n" + "="*60)
    print("TESTING SEQUENCE QUERIES")
    print("="*60)
    
    now = datetime.now()
    
    test_cases = [
        {"duration": 1, "within_hours": 12, "description": "1-hour sequence within 12 hours"},
        {"duration": 3, "within_hours": 12, "description": "3-hour sequence within 12 hours"},
        {"duration": 6, "within_hours": 24, "description": "6-hour sequence within 24 hours"},
        {"duration": 3, "within_hours": None, "description": "3-hour sequence, no time limit"},
        {"duration": 8, "within_hours": 12, "description": "8-hour sequence within 12 hours (should fail)"},
    ]
    
    for test_case in test_cases:
        print(f"\nTest: {test_case['description']}")
        print("-" * 40)
        
        try:
            result = await db_service.get_cheapest_sequence_start(
                duration=test_case['duration'],
                within_hours=test_case['within_hours']
            )
            
            sequence_end = result.timestamp + timedelta(hours=test_case['duration']-1)
            is_future = result.timestamp >= now
            is_end_in_bounds = True
            
            if test_case['within_hours']:
                search_limit = now + timedelta(hours=test_case['within_hours'])
                is_end_in_bounds = sequence_end <= search_limit
            
            status_emoji = "✅" if is_future and is_end_in_bounds else "❌"
            
            print(f"{status_emoji} Start:  {result.timestamp.strftime('%Y-%m-%d %H:%M')} (Price: {result.total_price:.2f})")
            print(f"   End:    {sequence_end.strftime('%Y-%m-%d %H:%M')}")
            print(f"   Future: {is_future}")
            print(f"   In bounds: {is_end_in_bounds}")
            
            if not is_future:
                print(f"   ❌ ERROR: Start time is in the past!")
            if not is_end_in_bounds:
                print(f"   ❌ ERROR: Sequence end exceeds time window!")
                
        except Exception as e:
            print(f"❌ Failed: {e}")


async def test_edge_cases():
    """Test edge cases that previously caused issues."""
    print("\n" + "="*60)
    print("TESTING EDGE CASES")
    print("="*60)
    
    now = datetime.now()
    
    # Test 1: Very short time window
    print("\nEdge Case 1: Short time window (2 hours, need 3-hour sequence)")
    try:
        result = await db_service.get_cheapest_sequence_start(duration=3, within_hours=2)
        print(f"❌ Should have failed but got: {result.timestamp}")
    except Exception as e:
        print(f"✅ Correctly failed: {e}")
    
    # Test 2: Exact boundary case
    print("\nEdge Case 2: Exact boundary (3 hours window, need 3-hour sequence)")
    try:
        result = await db_service.get_cheapest_sequence_start(duration=3, within_hours=3)
        sequence_end = result.timestamp + timedelta(hours=2)
        search_limit = now + timedelta(hours=3)
        
        print(f"Start: {result.timestamp.strftime('%Y-%m-%d %H:%M')}")
        print(f"End:   {sequence_end.strftime('%Y-%m-%d %H:%M')}")
        print(f"Limit: {search_limit.strftime('%Y-%m-%d %H:%M')}")
        
        if result.timestamp >= now and sequence_end <= search_limit:
            print("✅ Boundary case handled correctly")
        else:
            print("❌ Boundary case failed")
            
    except Exception as e:
        print(f"Result: {e}")


async def main():
    """Main test runner."""
    print("Sequence Query Fix Validation")
    print("="*60)
    
    try:
        await create_test_data()
        await test_sequence_queries()
        await test_edge_cases()
        
        print("\n" + "="*60)
        print("VALIDATION COMPLETE")
        print("="*60)
        print("Check the results above:")
        print("✅ = Working correctly")
        print("❌ = Issue found")
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
