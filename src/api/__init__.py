"""
API package for the Energy Price API.
Contains FastAPI route handlers and API-related utilities.
"""

from .routes import router

__all__ = [
    "router",
]
