#!/usr/bin/env python3
"""
Database inspection script for the Energy Price API.
Provides utilities for monitoring, debugging, and maintaining the price database.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiosqlite

from src.config import settings
from src.database.service import db_service
from src.logging_config import setup_logging
from src.models.price import PriceCategory


async def show_schema():
    """Display database schema information."""
    print("Database Schema Information")
    print("=" * 60)
    
    try:
        async with aiosqlite.connect(settings.database_path) as db:
            # Schema version
            try:
                cursor = await db.execute(
                    "SELECT version, applied_at FROM schema_version ORDER BY version DESC LIMIT 1"
                )
                version_info = await cursor.fetchone()
                if version_info:
                    print(f"Schema Version: {version_info[0]} (applied: {version_info[1]})")
                else:
                    print("Schema Version: Not found")
            except:
                print("Schema Version: Table not found")
            
            print()
            
            # Table information
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = await cursor.fetchall()
            
            print("Tables:")
            for table in tables:
                table_name = table[0]
                print(f"  - {table_name}")
                
                # Show table schema
                cursor = await db.execute(f"PRAGMA table_info({table_name})")
                columns = await cursor.fetchall()
                
                for col in columns:
                    print(f"    {col[1]} {col[2]} {'NOT NULL' if col[3] else ''} {'PK' if col[5] else ''}".strip())
                print()
            
            # Index information
            cursor = await db.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
            indexes = await cursor.fetchall()
            
            if indexes:
                print("Indexes:")
                for idx in indexes:
                    print(f"  - {idx[0]}")
                    if idx[1]:
                        print(f"    {idx[1]}")
                print()
            
    except Exception as e:
        print(f"Error reading schema: {e}")


async def show_stats():
    """Display database statistics."""
    print("Database Statistics")
    print("=" * 60)
    
    try:
        async with aiosqlite.connect(settings.database_path) as db:
            # Total records
            cursor = await db.execute("SELECT COUNT(*) FROM price_records")
            total_records = await cursor.fetchone()
            print(f"Total Price Records: {total_records[0]}")
            
            # Date range
            cursor = await db.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM price_records"
            )
            date_range = await cursor.fetchone()
            if date_range[0]:
                print(f"Date Range: {date_range[0]} to {date_range[1]}")
            
            # Records by category
            cursor = await db.execute(
                "SELECT category, COUNT(*) FROM price_records GROUP BY category ORDER BY category"
            )
            categories = await cursor.fetchall()
            
            if categories:
                print("\nRecords by Category:")
                for cat, count in categories:
                    print(f"  {cat}: {count}")
            
            # Price statistics
            cursor = await db.execute(
                "SELECT MIN(total_price), MAX(total_price), AVG(total_price) FROM price_records"
            )
            price_stats = await cursor.fetchone()
            
            if price_stats[0] is not None:
                print(f"\nPrice Statistics (DKK/kWh):")
                print(f"  Min: {price_stats[0]:.4f}")
                print(f"  Max: {price_stats[1]:.4f}")
                print(f"  Avg: {price_stats[2]:.4f}")
            
            # Recent data count
            last_24h = datetime.now() - timedelta(hours=24)
            cursor = await db.execute(
                "SELECT COUNT(*) FROM price_records WHERE timestamp >= ?",
                (last_24h.isoformat(),)
            )
            recent_count = await cursor.fetchone()
            print(f"\nRecords in last 24 hours: {recent_count[0]}")
            
    except Exception as e:
        print(f"Error reading statistics: {e}")


async def show_recent_data(hours: int = 12):
    """Show recent price data."""
    print(f"Recent Price Data (last {hours} hours)")
    print("=" * 80)
    
    try:
        start_time = datetime.now() - timedelta(hours=hours)
        
        async with aiosqlite.connect(settings.database_path) as db:
            cursor = await db.execute("""
                SELECT timestamp, spot_price, transport_taxes, total_price, category
                FROM price_records 
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 50
            """, (start_time.isoformat(),))
            
            records = await cursor.fetchall()
            
            if not records:
                print("No recent data found")
                return
            
            print(f"{'Timestamp':<20} {'Spot':<8} {'Tax':<8} {'Total':<8} {'Category':<12}")
            print("-" * 80)
            
            for record in records:
                timestamp = datetime.fromisoformat(record[0])
                print(f"{timestamp.strftime('%Y-%m-%d %H:%M'):<20} "
                      f"{record[1]:<8.3f} "
                      f"{record[2]:<8.3f} "
                      f"{record[3]:<8.3f} "
                      f"{record[4]:<12}")
            
    except Exception as e:
        print(f"Error reading recent data: {e}")


async def check_gaps():
    """Check for missing hourly data."""
    print("Data Gap Analysis")
    print("=" * 60)
    
    try:
        async with aiosqlite.connect(settings.database_path) as db:
            # Get date range
            cursor = await db.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM price_records"
            )
            date_range = await cursor.fetchone()
            
            if not date_range[0]:
                print("No data found in database")
                return
            
            start_time = datetime.fromisoformat(date_range[0])
            end_time = datetime.fromisoformat(date_range[1])
            
            print(f"Checking for gaps between {start_time} and {end_time}")
            print()
            
            # Find gaps
            current_time = start_time
            gaps_found = 0
            
            while current_time < end_time:
                next_time = current_time + timedelta(hours=1)
                
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM price_records WHERE timestamp = ?",
                    (current_time.isoformat(),)
                )
                count = await cursor.fetchone()
                
                if count[0] == 0:
                    print(f"Missing data for: {current_time}")
                    gaps_found += 1
                
                current_time = next_time
            
            if gaps_found == 0:
                print("No gaps found in hourly data!")
            else:
                print(f"\nTotal gaps found: {gaps_found}")
            
    except Exception as e:
        print(f"Error checking gaps: {e}")


async def vacuum_database():
    """Vacuum the database to reclaim space."""
    print("Database Vacuum")
    print("=" * 60)
    
    try:
        # Get database size before
        db_path = Path(settings.database_path)
        if not db_path.exists():
            print("Database file not found")
            return
        
        size_before = db_path.stat().st_size
        print(f"Database size before: {size_before / 1024:.2f} KB")
        
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute("VACUUM")
            await db.commit()
        
        size_after = db_path.stat().st_size
        saved = size_before - size_after
        
        print(f"Database size after: {size_after / 1024:.2f} KB")
        print(f"Space reclaimed: {saved / 1024:.2f} KB")
        
    except Exception as e:
        print(f"Error during vacuum: {e}")


async def run_all_checks():
    """Run all inspection checks."""
    await show_schema()
    print("\n" + "=" * 80 + "\n")
    
    await show_stats()
    print("\n" + "=" * 80 + "\n")
    
    await show_recent_data(12)
    print("\n" + "=" * 80 + "\n")
    
    await check_gaps()
    print("\n" + "=" * 80 + "\n")


def main():
    """Main script entry point."""
    if len(sys.argv) < 2:
        print("Database Inspection Tool for Energy Price API")
        print("Usage: python scripts/db_inspect.py <command> [options]")
        print("\nAvailable commands:")
        print("  schema     - Show database schema and structure")
        print("  stats      - Show database statistics")
        print("  recent [H] - Show recent data (default: 12 hours)")
        print("  gaps       - Check for missing hourly data")
        print("  vacuum     - Vacuum database to reclaim space")
        print("  all        - Run all checks")
        return
    
    command = sys.argv[1].lower()
    setup_logging()
    
    if command == "schema":
        asyncio.run(show_schema())
    elif command == "stats":
        asyncio.run(show_stats())
    elif command == "recent":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 12
        asyncio.run(show_recent_data(hours))
    elif command == "gaps":
        asyncio.run(check_gaps())
    elif command == "vacuum":
        asyncio.run(vacuum_database())
    elif command == "all":
        asyncio.run(run_all_checks())
    else:
        print(f"Unknown command: {command}")
        print("Run without arguments to see available commands")


if __name__ == "__main__":
    main()
