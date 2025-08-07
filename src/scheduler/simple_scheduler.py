"""
Simplified scheduler using FastAPI background tasks instead of APScheduler.
Less complex, more predictable for small applications.
"""

import asyncio
from datetime import datetime, time, timedelta
from typing import Optional

from src.config import settings
from src.logging_config import get_logger
from src.services.price_service import price_service

logger = get_logger(__name__)


class SimpleScheduler:
    """Simple background task scheduler for price fetching."""
    
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the scheduler background task."""
        if self._running:
            logger.warning("Scheduler already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Scheduler started", fetch_time=f"{settings.fetch_hour}:{settings.fetch_minute:02d}")
    
    async def stop(self) -> None:
        """Stop the scheduler."""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Scheduler stopped")
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                # Calculate next run time
                next_run = self._calculate_next_run()
                sleep_seconds = (next_run - datetime.now()).total_seconds()
                
                if sleep_seconds > 0:
                    logger.debug("Next price fetch scheduled", next_run=next_run.isoformat(), sleep_seconds=sleep_seconds)
                    await asyncio.sleep(sleep_seconds)
                
                if not self._running:
                    break
                
                # Run the job
                await self._fetch_prices_job()
                
                # Sleep for at least 1 hour to avoid duplicate runs
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Scheduler loop error", error=str(e))
                # Sleep and continue
                await asyncio.sleep(300)  # 5 minutes
    
    def _calculate_next_run(self) -> datetime:
        """Calculate the next scheduled run time."""
        now = datetime.now()
        today_run = now.replace(
            hour=settings.fetch_hour,
            minute=settings.fetch_minute,
            second=0,
            microsecond=0
        )
        
        if now >= today_run:
            # Today's run has passed, schedule for tomorrow
            return today_run + timedelta(days=1)
        else:
            # Today's run is still upcoming
            return today_run
    
    async def _fetch_prices_job(self) -> None:
        """Execute the price fetching job."""
        job_start = datetime.now()
        logger.info("Starting scheduled price fetch")
        
        try:
            # Fetch and store prices
            record_count = await price_service.fetch_and_store_daily_prices()
            
            # Cleanup old records
            deleted_count = await price_service.cleanup_old_data()
            
            duration = (datetime.now() - job_start).total_seconds()
            logger.info(
                "Completed scheduled price fetch",
                records_fetched=record_count,
                records_deleted=deleted_count,
                duration_seconds=duration,
            )
            
        except Exception as e:
            duration = (datetime.now() - job_start).total_seconds()
            logger.error(
                "Scheduled price fetch failed",
                error=str(e),
                duration_seconds=duration,
            )
    
    async def run_manual_fetch(self) -> None:
        """Run a manual price fetch."""
        logger.info("Running manual price fetch")
        await self._fetch_prices_job()
    
    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running


# Global scheduler instance
simple_scheduler = SimpleScheduler()
