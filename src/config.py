"""
Application configuration management using Pydantic Settings.
Handles environment variables and default values for the service.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    
    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host address")
    api_port: int = Field(default=8000, description="API port")
    api_debug: bool = Field(default=False, description="Enable debug mode")
    api_reload: bool = Field(default=False, description="Enable auto-reload")
    
    # Database Configuration
    database_url: str = Field(
        default="postgresql://priceapi:secure_password_123@localhost:5432/energy_prices",
        description="PostgreSQL database connection URL"
    )
    
    # Andel Energi API Configuration
    andel_energi_base_url: str = Field(
        default="https://andelenergi.dk/",
        description="Base URL for Andel Energi API"
    )
    andel_energi_region: str = Field(
        default="east",
        description="Energy region (must be 'east' as per PRD)"
    )
    andel_energi_tax: int = Field(default=0, description="Tax parameter for API")
    andel_energi_product_id: str = Field(
        default="1#1#TIMEENERGI",
        description="Product ID for time-based energy pricing"
    )
    
    # Scheduler Configuration
    fetch_hour: int = Field(default=14, description="Hour to fetch daily prices (24h format)")
    fetch_minute: int = Field(default=10, description="Minute to fetch daily prices")
    fetch_timezone: str = Field(default="Europe/Copenhagen", description="Timezone for scheduling")
    
    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json/text)")
    
    # Data Retention Configuration
    data_retention_days: int = Field(default=30, description="Days to retain old price data")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
