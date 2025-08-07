"""
Health check module for Docker health checks and monitoring.
Verifies database connectivity and basic service functionality.
"""

import asyncio
import sys

from src.database.service import db_service
from src.logging_config import get_logger

logger = get_logger(__name__)


async def health_check() -> bool:
    """
    Perform comprehensive health check of the service.
    """
    try:
        # Check database
        db_healthy = await db_service.health_check()
        
        # Add additional health checks here as needed
        # - External API connectivity
        # - Disk space
        # - Memory usage
        
        return db_healthy
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return False


async def main():
    """
    Main health check entry point for command line usage.
    """
    is_healthy = await health_check()
    
    if is_healthy:
        logger.info("Health check passed")
        sys.exit(0)
    else:
        logger.error("Health check failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
