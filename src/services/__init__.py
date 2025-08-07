"""
Services package for the Energy Price API.
Contains unified price service for data fetching and optimization.
"""

from .price_service import price_service, PriceService

__all__ = [
    "price_service",
    "PriceService",
]
