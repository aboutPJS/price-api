"""
Database service using PostgreSQL with asyncpg.
Handles all database operations and migrations in one place.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urlparse

import asyncpg

from src.config import settings
from src.exceptions import DatabaseError, NoPriceDataError, NoSequenceFoundError
from src.logging_config import get_logger
from src.models.price import PriceCategory, PriceRecord

logger = get_logger(__name__)

CURRENT_SCHEMA_VERSION = 2


class DatabaseService:
    """Unified database service for all price data operations."""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or settings.database_url
        self._pool = None
    
    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create connection pool."""
        if self._pool is None or self._pool.is_closing():
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
        return self._pool
    
    async def close(self):
        """Close database connection pool."""
        if self._pool and not self._pool.is_closing():
            await self._pool.close()
    
    async def init_database(self) -> None:
        """Initialize database with tables, indexes, and migrations."""
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                # Check current schema version
                current_version = await self._get_schema_version(conn)
                
                if current_version == 0:
                    # Initial setup
                    await self._create_initial_schema(conn)
                    await self._set_schema_version(conn, CURRENT_SCHEMA_VERSION)
                    logger.info("Database initialized with schema version", version=CURRENT_SCHEMA_VERSION)
                elif current_version < CURRENT_SCHEMA_VERSION:
                    # Run migrations
                    await self._run_migrations(conn, current_version)
                    logger.info("Database migrated", from_version=current_version, to_version=CURRENT_SCHEMA_VERSION)
                    
        except Exception as e:
            logger.error("Failed to initialize database", error=str(e))
            raise DatabaseError(f"Database initialization failed: {e}")
    
    async def _get_schema_version(self, conn: asyncpg.Connection) -> int:
        """Get current database schema version."""
        try:
            result = await conn.fetchval(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            )
            return result if result else 0
        except asyncpg.UndefinedTableError:
            # Table doesn't exist, this is a new database
            return 0
    
    async def _set_schema_version(self, conn: asyncpg.Connection, version: int) -> None:
        """Set database schema version."""
        await conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES ($1, $2)",
            version, datetime.now()
        )
    
    async def _create_initial_schema(self, conn: asyncpg.Connection) -> None:
        """Create initial database schema."""
        # Schema version tracking
        await conn.execute("""
            CREATE TABLE schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Price records table with median_price column
        await conn.execute("""
            CREATE TABLE price_records (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                spot_price DECIMAL(10,6) NOT NULL CHECK (spot_price >= 0),
                transport_taxes DECIMAL(10,6) NOT NULL CHECK (transport_taxes >= 0),
                total_price DECIMAL(10,6) NOT NULL CHECK (total_price >= 0),
                median_price DECIMAL(10,6) NOT NULL CHECK (median_price >= 0),
                category VARCHAR(10) NOT NULL CHECK (category IN ('AVOID', 'OKAY', 'PREFER')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(timestamp)
            )
        """)
        
        # Indexes for performance
        await conn.execute(
            "CREATE INDEX idx_timestamp ON price_records(timestamp)"
        )
        await conn.execute(
            "CREATE INDEX idx_total_price ON price_records(total_price)"
        )
        await conn.execute(
            "CREATE INDEX idx_category ON price_records(category)"
        )
        
        logger.info("Initial database schema created")
    
    async def _run_migrations(self, conn: asyncpg.Connection, from_version: int) -> None:
        """Run database migrations from current version to latest."""
        if from_version < 2:
            await self._migrate_to_v2(conn)
            await self._set_schema_version(conn, 2)
    
    async def _migrate_to_v2(self, conn: asyncpg.Connection) -> None:
        """Migrate to schema version 2: Add median_price column."""
        logger.info("Running migration to schema version 2")
        
        # Check if column exists
        column_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='price_records' AND column_name='median_price'
            )
        """)
        
        if not column_exists:
            # Add median_price column with default value
            await conn.execute("""
                ALTER TABLE price_records 
                ADD COLUMN median_price DECIMAL(10,6) DEFAULT 0.0 NOT NULL
            """)
            
            # Update existing records with a default median
            await conn.execute("""
                UPDATE price_records 
                SET median_price = total_price 
                WHERE median_price = 0.0
            """)
        
        logger.info("Migration to schema version 2 completed")
    
    async def save_price_records(self, records: List[PriceRecord]) -> None:
        """Save price records to database with duplicate detection and price change logging."""
        if not records:
            return
            
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                price_changes = []
                
                # Check for existing records and detect price changes
                for record in records:
                    existing = await conn.fetchval(
                        "SELECT total_price FROM price_records WHERE timestamp = $1",
                        record.timestamp
                    )
                    
                    if existing and float(existing) != record.total_price:
                        price_changes.append({
                            'timestamp': record.timestamp,
                            'old_price': float(existing),
                            'new_price': record.total_price
                        })
                
                # Log price changes
                for change in price_changes:
                    logger.info(
                        "Price updated for timestamp",
                        timestamp=change['timestamp'].strftime('%d.%m.%Y %H:%M'),
                        old_price=f"{change['old_price']:.4f} DKK/kWh",
                        new_price=f"{change['new_price']:.4f} DKK/kWh"
                    )
                
                # Prepare data for batch insert
                records_data = [
                    (
                        record.timestamp,
                        record.spot_price,
                        record.transport_taxes,
                        record.total_price,
                        record.median_price,
                        record.category.value,
                    )
                    for record in records
                ]
                
                # Use ON CONFLICT to handle duplicates (PostgreSQL UPSERT)
                await conn.executemany("""
                    INSERT INTO price_records 
                    (timestamp, spot_price, transport_taxes, total_price, median_price, category)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (timestamp) DO UPDATE SET
                        spot_price = EXCLUDED.spot_price,
                        transport_taxes = EXCLUDED.transport_taxes,
                        total_price = EXCLUDED.total_price,
                        median_price = EXCLUDED.median_price,
                        category = EXCLUDED.category
                """, records_data)
                
                logger.info(
                    "Saved price records", 
                    count=len(records),
                    price_changes=len(price_changes)
                )
                
        except Exception as e:
            logger.error("Failed to save price records", error=str(e))
            raise DatabaseError(f"Failed to save records: {e}")
    
    async def get_cheapest_hour(self, within_hours: Optional[int] = None) -> PriceRecord:
        """Find the cheapest hour within timeframe."""
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                now = datetime.now()
                
                if within_hours is not None:
                    end_time = now + timedelta(hours=within_hours)
                    query = """
                        SELECT timestamp, spot_price, transport_taxes, total_price, median_price, category
                        FROM price_records 
                        WHERE timestamp >= $1 AND timestamp <= $2
                        ORDER BY total_price ASC, timestamp ASC
                        LIMIT 1
                    """
                    row = await conn.fetchrow(query, now, end_time)
                else:
                    query = """
                        SELECT timestamp, spot_price, transport_taxes, total_price, median_price, category
                        FROM price_records 
                        WHERE timestamp >= $1
                        ORDER BY total_price ASC, timestamp ASC
                        LIMIT 1
                    """
                    row = await conn.fetchrow(query, now)
                
                if not row:
                    raise NoPriceDataError("No price data available for the specified timeframe")
                
                return PriceRecord(
                    timestamp=row['timestamp'],
                    spot_price=float(row['spot_price']),
                    transport_taxes=float(row['transport_taxes']),
                    total_price=float(row['total_price']),
                    median_price=float(row['median_price']),
                    category=PriceCategory(row['category']),
                )
                
        except NoPriceDataError:
            raise
        except Exception as e:
            logger.error("Failed to get cheapest hour", error=str(e))
            raise DatabaseError(f"Database query failed: {e}")
    
    async def get_cheapest_sequence_start(self, duration: int, within_hours: Optional[int] = None) -> PriceRecord:
        """Find the start of cheapest consecutive sequence."""
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                now = datetime.now()
                
                # Calculate the end time for the search window
                if within_hours is not None:
                    search_end_time = now + timedelta(hours=within_hours)
                else:
                    # Default to a reasonable future window (48 hours)
                    search_end_time = now + timedelta(hours=48)
                
                # For sequence to be valid, we need to ensure:
                # 1. Start time is in the future (>= now)
                # 2. End time of sequence is within our search window
                # 3. We have complete hourly data for the entire sequence
                sequence_end_cutoff = search_end_time - timedelta(hours=duration-1)
                
                # PostgreSQL query using window functions for sequence analysis
                query = f"""
                    WITH hourly_prices AS (
                        SELECT timestamp, spot_price, transport_taxes, total_price, median_price, category
                        FROM price_records 
                        WHERE timestamp >= $1 AND timestamp <= $2
                        ORDER BY timestamp
                    ),
                    sequence_sums AS (
                        SELECT h1.timestamp, h1.spot_price, h1.transport_taxes, h1.total_price, h1.median_price, h1.category,
                               (
                                   SELECT SUM(h2.total_price)
                                   FROM hourly_prices h2
                                   WHERE h2.timestamp >= h1.timestamp
                                     AND h2.timestamp <= (h1.timestamp + INTERVAL '{duration-1} hours')
                               ) as sequence_sum,
                               (
                                   SELECT COUNT(*)
                                   FROM hourly_prices h3
                                   WHERE h3.timestamp >= h1.timestamp
                                     AND h3.timestamp <= (h1.timestamp + INTERVAL '{duration-1} hours')
                               ) as sequence_count
                        FROM hourly_prices h1
                    )
                    SELECT timestamp, spot_price, transport_taxes, total_price, median_price, category
                    FROM sequence_sums
                    WHERE sequence_count = $3
                      AND sequence_sum IS NOT NULL
                    ORDER BY sequence_sum ASC, timestamp ASC
                    LIMIT 1
                """
                
                row = await conn.fetchrow(query, now, sequence_end_cutoff, duration)
                
                if not row:
                    raise NoSequenceFoundError(f"No suitable {duration}-hour sequence found")
                
                return PriceRecord(
                    timestamp=row['timestamp'],
                    spot_price=float(row['spot_price']),
                    transport_taxes=float(row['transport_taxes']),
                    total_price=float(row['total_price']),
                    median_price=float(row['median_price']),
                    category=PriceCategory(row['category']),
                )
                
        except NoSequenceFoundError:
            raise
        except Exception as e:
            logger.error("Failed to get cheapest sequence", error=str(e), duration=duration)
            raise DatabaseError(f"Database query failed: {e}")
    
    async def cleanup_old_records(self, retention_days: int) -> int:
        """Remove old price records."""
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM price_records WHERE timestamp < $1",
                    cutoff_date
                )
                
                # Extract number from result string like "DELETE 42"
                deleted_count = int(result.split()[-1]) if result.split()[-1].isdigit() else 0
                
                if deleted_count > 0:
                    logger.info("Cleaned up old records", deleted_count=deleted_count)
                
                return deleted_count
                
        except Exception as e:
            logger.error("Failed to cleanup old records", error=str(e))
            raise DatabaseError(f"Cleanup failed: {e}")
    
    async def get_recent_records(self, hours: int = 48) -> List[PriceRecord]:
        """Get recent price records for monitoring."""
        try:
            start_time = datetime.now() - timedelta(hours=hours)
            
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT timestamp, spot_price, transport_taxes, total_price, 
                           COALESCE(median_price, total_price) as median_price, category
                    FROM price_records 
                    WHERE timestamp >= $1
                    ORDER BY timestamp ASC
                """, start_time)
                
                return [
                    PriceRecord(
                        timestamp=row['timestamp'],
                        spot_price=float(row['spot_price']),
                        transport_taxes=float(row['transport_taxes']),
                        total_price=float(row['total_price']),
                        median_price=float(row['median_price']),
                        category=PriceCategory(row['category']),
                    )
                    for row in rows
                ]
                
        except Exception as e:
            logger.error("Failed to get recent records", error=str(e))
            raise DatabaseError(f"Query failed: {e}")
    
    async def health_check(self) -> bool:
        """Check database health."""
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                # Simple connectivity and table existence check
                result = await conn.fetchval(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'price_records'"
                )
                
                if result != 1:
                    logger.error("Price records table not found")
                    return False
                
            return True
            
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False


# Global database service instance
db_service = DatabaseService()
