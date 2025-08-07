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

CURRENT_SCHEMA_VERSION = 1


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
        
        # Price records table
        await db.execute("""
            CREATE TABLE price_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                spot_price REAL NOT NULL,
                transport_taxes REAL NOT NULL,
                total_price REAL NOT NULL,
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
        # Future migrations would go here
        # if from_version < 2:
        #     await self._migrate_to_v2(db)
        #     await self._set_schema_version(db, 2)
        pass
    
    async def save_price_records(self, records: List[PriceRecord]) -> None:
        """Save price records to database."""
        if not records:
            return
            
        try:
            async with aiosqlite.connect(self.database_path) as db:
                records_data = [
                    (
                        record.timestamp.isoformat(),
                        record.spot_price,
                        record.transport_taxes,
                        record.total_price,
                        record.category.value,
                    )
                    for record in records
                ]
                
                await db.executemany("""
                    INSERT OR REPLACE INTO price_records 
                    (timestamp, spot_price, transport_taxes, total_price, category)
                    VALUES (?, ?, ?, ?, ?)
                """, records_data)
                
                await db.commit()
                logger.debug("Saved price records", count=len(records))
                
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
                        SELECT timestamp, spot_price, transport_taxes, total_price, category
                        FROM price_records 
                        WHERE timestamp >= ? AND timestamp <= ?
                        ORDER BY total_price ASC, timestamp ASC
                        LIMIT 1
                    """
                    params = (now.isoformat(), end_time.isoformat())
                else:
                    query = """
                        SELECT timestamp, spot_price, transport_taxes, total_price, category
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
                    category=PriceCategory(row[4]),
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
                
                # Build time constraint
                time_constraint = "WHERE p1.timestamp >= ?"
                params = [now.isoformat()]
                
                if within_hours is not None:
                    end_time = now + timedelta(hours=within_hours)
                    time_constraint += " AND p1.timestamp <= ?"
                    params.append(end_time.isoformat())
                
                # Find cheapest consecutive sequence
                query = f"""
                    WITH sequence_sums AS (
                        SELECT 
                            p1.timestamp,
                            p1.spot_price,
                            p1.transport_taxes,
                            p1.total_price,
                            p1.category,
                            (
                                SELECT SUM(p2.total_price)
                                FROM price_records p2
                                WHERE p2.timestamp >= p1.timestamp 
                                AND p2.timestamp < datetime(p1.timestamp, '+{duration} hours')
                                GROUP BY p1.timestamp
                                HAVING COUNT(p2.timestamp) = {duration}
                            ) as sequence_total
                        FROM price_records p1
                        {time_constraint}
                        ORDER BY p1.timestamp
                    )
                    SELECT timestamp, spot_price, transport_taxes, total_price, category
                    FROM sequence_sums 
                    WHERE sequence_total IS NOT NULL
                    ORDER BY sequence_total ASC, timestamp ASC
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
                    category=PriceCategory(row[4]),
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
                    SELECT timestamp, spot_price, transport_taxes, total_price, category
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
                        category=PriceCategory(row[4]),
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
