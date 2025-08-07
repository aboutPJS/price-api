"""
Simplified database service using pure aiosqlite.
Handles all database operations and migrations in one place.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import aiosqlite

from src.config import settings
from src.exceptions import DatabaseError, NoPriceDataError, NoSequenceFoundError
from src.logging_config import get_logger
from src.models.price import PriceCategory, PriceRecord

logger = get_logger(__name__)

CURRENT_SCHEMA_VERSION = 2


class DatabaseService:
    """Unified database service for all price data operations."""
    
    def __init__(self, database_path: str = None):
        self.database_path = database_path or settings.database_path
    
    async def init_database(self) -> None:
        """Initialize database with tables, indexes, and migrations."""
        try:
            # Ensure directory exists
            database_path = Path(self.database_path)
            database_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiosqlite.connect(self.database_path) as db:
                # Check current schema version
                current_version = await self._get_schema_version(db)
                
                if current_version == 0:
                    # Initial setup
                    await self._create_initial_schema(db)
                    await self._set_schema_version(db, CURRENT_SCHEMA_VERSION)
                    logger.info("Database initialized with schema version", version=CURRENT_SCHEMA_VERSION)
                elif current_version < CURRENT_SCHEMA_VERSION:
                    # Run migrations
                    await self._run_migrations(db, current_version)
                    logger.info("Database migrated", from_version=current_version, to_version=CURRENT_SCHEMA_VERSION)
                    
        except Exception as e:
            logger.error("Failed to initialize database", error=str(e))
            raise DatabaseError(f"Database initialization failed: {e}")
    
    async def _get_schema_version(self, db: aiosqlite.Connection) -> int:
        """Get current database schema version."""
        try:
            cursor = await db.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            )
            result = await cursor.fetchone()
            return result[0] if result else 0
        except aiosqlite.OperationalError:
            # Table doesn't exist, this is a new database
            return 0
    
    async def _set_schema_version(self, db: aiosqlite.Connection, version: int) -> None:
        """Set database schema version."""
        await db.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (version, datetime.now().isoformat())
        )
        await db.commit()
    
    async def _create_initial_schema(self, db: aiosqlite.Connection) -> None:
        """Create initial database schema."""
        # Schema version tracking
        await db.execute("""
            CREATE TABLE schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
        """)
        
        # Price records table with median_price column
        await db.execute("""
            CREATE TABLE price_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                spot_price REAL NOT NULL,
                transport_taxes REAL NOT NULL,
                total_price REAL NOT NULL,
                median_price REAL NOT NULL,
                category TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(timestamp)
            )
        """)
        
        # Indexes for performance
        await db.execute(
            "CREATE INDEX idx_timestamp ON price_records(timestamp)"
        )
        await db.execute(
            "CREATE INDEX idx_total_price ON price_records(total_price)"
        )
        await db.execute(
            "CREATE INDEX idx_category ON price_records(category)"
        )
        
        await db.commit()
    
    async def _run_migrations(self, db: aiosqlite.Connection, from_version: int) -> None:
        """Run database migrations from current version to latest."""
        if from_version < 2:
            await self._migrate_to_v2(db)
            await self._set_schema_version(db, 2)
    
    async def _migrate_to_v2(self, db: aiosqlite.Connection) -> None:
        """Migrate to schema version 2: Add median_price column."""
        logger.info("Running migration to schema version 2")
        
        # Add median_price column with default value
        await db.execute("""
            ALTER TABLE price_records 
            ADD COLUMN median_price REAL DEFAULT 0.0
        """)
        
        # Update existing records with a default median (could be improved later)
        await db.execute("""
            UPDATE price_records 
            SET median_price = total_price 
            WHERE median_price = 0.0
        """)
        
        await db.commit()
        logger.info("Migration to schema version 2 completed")
    
    async def save_price_records(self, records: List[PriceRecord]) -> None:
        """Save price records to database with duplicate detection and price change logging."""
        if not records:
            return
            
        try:
            async with aiosqlite.connect(self.database_path) as db:
                price_changes = []
                
                # Check for existing records and detect price changes
                for record in records:
                    cursor = await db.execute(
                        "SELECT total_price FROM price_records WHERE timestamp = ?",
                        (record.timestamp.isoformat(),)
                    )
                    existing = await cursor.fetchone()
                    
                    if existing and existing[0] != record.total_price:
                        price_changes.append({
                            'timestamp': record.timestamp,
                            'old_price': existing[0],
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
                
                # Save all records
                records_data = [
                    (
                        record.timestamp.isoformat(),
                        record.spot_price,
                        record.transport_taxes,
                        record.total_price,
                        record.median_price,
                        record.category.value,
                    )
                    for record in records
                ]
                
                await db.executemany("""
                    INSERT OR REPLACE INTO price_records 
                    (timestamp, spot_price, transport_taxes, total_price, median_price, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, records_data)
                
                await db.commit()
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
            async with aiosqlite.connect(self.database_path) as db:
                now = datetime.now()
                
                if within_hours is not None:
                    end_time = now + timedelta(hours=within_hours)
                    query = """
                        SELECT timestamp, spot_price, transport_taxes, total_price, median_price, category
                        FROM price_records 
                        WHERE timestamp >= ? AND timestamp <= ?
                        ORDER BY total_price ASC, timestamp ASC
                        LIMIT 1
                    """
                    params = (now.isoformat(), end_time.isoformat())
                else:
                    query = """
                        SELECT timestamp, spot_price, transport_taxes, total_price, median_price, category
                        FROM price_records 
                        WHERE timestamp >= ?
                        ORDER BY total_price ASC, timestamp ASC
                        LIMIT 1
                    """
                    params = (now.isoformat(),)
                
                cursor = await db.execute(query, params)
                row = await cursor.fetchone()
                
                if not row:
                    raise NoPriceDataError("No price data available for the specified timeframe")
                
                return PriceRecord(
                    timestamp=datetime.fromisoformat(row[0]),
                    spot_price=row[1],
                    transport_taxes=row[2],
                    total_price=row[3],
                    median_price=row[4],
                    category=PriceCategory(row[5]),
                )
                
        except NoPriceDataError:
            raise
        except Exception as e:
            logger.error("Failed to get cheapest hour", error=str(e))
            raise DatabaseError(f"Database query failed: {e}")
    
    async def get_cheapest_sequence_start(self, duration: int, within_hours: Optional[int] = None) -> PriceRecord:
        """Find the start of cheapest consecutive sequence."""
        try:
            async with aiosqlite.connect(self.database_path) as db:
                now = datetime.now()
                
                # Initialize params list
                params = [now.isoformat()]
                
                # Base condition for time filtering
                base_condition = "timestamp >= ?"
                if within_hours is not None:
                    end_time = now + timedelta(hours=within_hours)
                    base_condition += " AND timestamp <= ?"
                    params.append(end_time.isoformat())
                
                # Fixed query: use julianday for proper datetime arithmetic
                query = f"""
                    WITH hourly_prices AS (
                        SELECT timestamp, spot_price, transport_taxes, total_price, median_price, category,
                               julianday(timestamp) as jd
                        FROM price_records 
                        WHERE {base_condition}
                        ORDER BY timestamp
                    ),
                    sequence_sums AS (
                        SELECT h1.timestamp, h1.spot_price, h1.transport_taxes, h1.total_price, h1.median_price, h1.category,
                               (
                                   SELECT SUM(h2.total_price)
                                   FROM hourly_prices h2
                                   WHERE h2.jd >= h1.jd
                                     AND h2.jd < (h1.jd + {duration}/24.0)
                               ) as sequence_sum,
                               (
                                   SELECT COUNT(*)
                                   FROM hourly_prices h3
                                   WHERE h3.jd >= h1.jd
                                     AND h3.jd < (h1.jd + {duration}/24.0)
                               ) as sequence_count
                        FROM hourly_prices h1
                    )
                    SELECT timestamp, spot_price, transport_taxes, total_price, median_price, category
                    FROM sequence_sums
                    WHERE sequence_count = {duration}
                      AND sequence_sum IS NOT NULL
                    ORDER BY sequence_sum ASC, timestamp ASC
                    LIMIT 1
                """
                
                cursor = await db.execute(query, params)
                row = await cursor.fetchone()
                
                if not row:
                    raise NoSequenceFoundError(f"No suitable {duration}-hour sequence found")
                
                return PriceRecord(
                    timestamp=datetime.fromisoformat(row[0]),
                    spot_price=row[1],
                    transport_taxes=row[2],
                    total_price=row[3],
                    median_price=row[4] if row[4] is not None else row[3],
                    category=PriceCategory(row[5]),
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
            
            async with aiosqlite.connect(self.database_path) as db:
                cursor = await db.execute(
                    "DELETE FROM price_records WHERE timestamp < ?",
                    (cutoff_date.isoformat(),)
                )
                await db.commit()
                
                deleted_count = cursor.rowcount
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
            
            async with aiosqlite.connect(self.database_path) as db:
                cursor = await db.execute("""
                    SELECT timestamp, spot_price, transport_taxes, total_price, 
                           COALESCE(median_price, total_price) as median_price, category
                    FROM price_records 
                    WHERE timestamp >= ?
                    ORDER BY timestamp ASC
                """, (start_time.isoformat(),))
                
                rows = await cursor.fetchall()
                
                return [
                    PriceRecord(
                        timestamp=datetime.fromisoformat(row[0]),
                        spot_price=row[1],
                        transport_taxes=row[2],
                        total_price=row[3],
                        median_price=row[4],
                        category=PriceCategory(row[5]),
                    )
                    for row in rows
                ]
                
        except Exception as e:
            logger.error("Failed to get recent records", error=str(e))
            raise DatabaseError(f"Query failed: {e}")
    
    async def health_check(self) -> bool:
        """Check database health."""
        try:
            database_path = Path(self.database_path)
            if not database_path.exists():
                logger.error("Database file does not exist")
                return False
            
            async with aiosqlite.connect(self.database_path) as db:
                cursor = await db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='price_records'"
                )
                result = await cursor.fetchone()
                
                if not result:
                    logger.error("Price records table not found")
                    return False
                
            return True
            
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False


# Global database service instance
db_service = DatabaseService()
