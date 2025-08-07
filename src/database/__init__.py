"""
Database package for the Energy Price API.
Contains unified database service.
"""

from .service import db_service, DatabaseService

__all__ = [
    "db_service",
    "DatabaseService", 
]
