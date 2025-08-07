"""
Domain exceptions for the Energy Price API.
Provides clear, typed exceptions for business logic errors.
"""


class PriceAPIException(Exception):
    """Base exception for all Energy Price API errors."""
    pass


class NoPriceDataError(PriceAPIException):
    """Raised when no price data is available for the requested timeframe."""
    pass


class NoSequenceFoundError(PriceAPIException):
    """Raised when no suitable price sequence is found."""
    pass


class DataFetchError(PriceAPIException):
    """Raised when external data fetching fails."""
    pass


class DatabaseError(PriceAPIException):
    """Raised when database operations fail."""
    pass
