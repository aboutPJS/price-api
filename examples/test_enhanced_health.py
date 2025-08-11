#!/usr/bin/env python3
"""
Demo script to showcase the enhanced health endpoint with data freshness monitoring.
"""

import asyncio
import httpx
from datetime import datetime
import pytz


async def demo_health_endpoint():
    """Demonstrate the enhanced health endpoint features."""
    print("🏥 Enhanced Health Endpoint Demo")
    print("=" * 50)
    
    # Test the health endpoint
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:8000/api/v1/health")
            response.raise_for_status()
            
            health_data = response.json()
            
            # Display the basic response
            print("📊 Health Response:")
            print(f"  Status: {health_data['status']}")
            print(f"  Timestamp: {health_data['timestamp']}")
            print()
            
            # Parse the enhanced details
            details = health_data.get('details', {})
            
            print("🔍 Enhanced Details:")
            print(f"  Service: {details.get('service')}")
            print()
            
            # Data freshness analysis
            last_fetch = details.get('last_fetch')
            last_fetch_utc = details.get('last_fetch_utc')
            data_age_hours = details.get('data_age_hours')
            data_status = details.get('data_status')
            
            if last_fetch:
                print("📅 Data Freshness Analysis:")
                print(f"  Last Fetch (Copenhagen): {last_fetch}")
                print(f"  Last Fetch (UTC): {last_fetch_utc}")
                print(f"  Data Age: {data_age_hours} hours")
                
                # Visual status indicator
                status_indicators = {
                    'fresh': '✅ FRESH - Data is very recent',
                    'acceptable': '⚠️  ACCEPTABLE - Within daily update cycle', 
                    'stale': '❌ STALE - Data is old, check fetching process',
                    'unknown': '❓ UNKNOWN - No data status available'
                }
                
                print(f"  Data Status: {status_indicators.get(data_status, data_status)}")
                print()
                
                # Recommendations based on data status
                if data_status == 'fresh':
                    print("💡 Recommendation: System is working optimally!")
                elif data_status == 'acceptable':
                    print("💡 Recommendation: System is functioning normally.")
                elif data_status == 'stale':
                    print("💡 Recommendation: Check the daily fetching process and logs.")
                    print("   - Verify Andel Energi API connectivity")
                    print("   - Check scheduler configuration")
                    print("   - Review application logs for errors")
                else:
                    print("💡 Recommendation: Check if any data has been fetched.")
            else:
                print("❌ No data fetch information available")
                print("💡 Recommendation: Initialize the system with data fetch")
            
            print()
            print("🔧 Timezone Handling:")
            print("  • last_fetch: Converted to Copenhagen time for readability")
            print("  • last_fetch_utc: Raw database timestamp (UTC)")
            print("  • Helps monitor if daily 14:10 CET fetch is working")
            
            return health_data
            
        except httpx.ConnectError:
            print("❌ Connection Error: API server is not running")
            print("💡 Start the server with: python -m src.main")
            return None
        except httpx.RequestError as e:
            print(f"❌ Request Error: {e}")
            return None


async def compare_with_basic_health():
    """Compare enhanced health endpoint with basic health check."""
    print("\n🔄 Comparison with Basic Health Check")
    print("=" * 50)
    
    # Test basic database connectivity
    from src.database.service import db_service
    from src.api.routes import health_check
    
    try:
        # Test database connection
        db_healthy = await db_service.health_check()
        print(f"Database Health: {'✅ Connected' if db_healthy else '❌ Failed'}")
        
        # Get enhanced health data
        enhanced_response = await health_check()
        enhanced_data = enhanced_response.model_dump()
        
        print("\n📈 Enhanced Features Added:")
        details = enhanced_data.get('details', {})
        
        if details.get('last_fetch'):
            print("  ✅ Last fetch timestamp (Copenhagen time)")
            print("  ✅ Last fetch timestamp (UTC)")
            print("  ✅ Data age calculation")
            print("  ✅ Data freshness status")
            print("  ✅ Timezone conversion")
        else:
            print("  ⚠️  No data available yet")
            
        print("\n📊 Use Cases:")
        print("  • Monitor daily price fetching")
        print("  • Detect stale data issues")
        print("  • Alert on data freshness problems")
        print("  • Troubleshoot fetching failures")
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    async def main():
        await demo_health_endpoint()
        await compare_with_basic_health()
        
        print("\n✨ Demo completed!")
        print("\nNext Steps:")
        print("  1. Integrate with monitoring systems")
        print("  2. Set up alerts for stale data")
        print("  3. Use in load balancer health checks")
    
    asyncio.run(main())
