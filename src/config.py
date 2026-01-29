"""
Configuration module for the Movie Enrichment Bot.

Handles loading and validation of environment variables using Pydantic Settings.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Attributes:
        telegram_bot_token: The Telegram Bot API token.
        telegram_channel_id: The target channel ID for posting enriched movies.
        tmdb_api_key: The TMDB API key for fetching movie metadata.
        tmdb_base_url: Base URL for TMDB API.
        tmdb_image_base_url: Base URL for TMDB images.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        poster_cache_ttl: TTL for poster cache in seconds.
        poster_cache_max_size: Maximum number of posters to cache.
        request_timeout: HTTP request timeout in seconds.
        max_retries: Maximum number of retry attempts for API calls.
        allowed_user_ids: List of user IDs allowed to use the bot.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Telegram Configuration
    telegram_bot_token: str = Field(
        ...,
        description="Telegram Bot API Token"
    )
    telegram_channel_id: int = Field(
        ...,
        description="Target channel ID for posting movies"
    )
    
    # TMDB Configuration
    tmdb_api_key: str = Field(
        ...,
        description="TMDB API Key"
    )
    tmdb_base_url: str = Field(
        default="https://api.themoviedb.org/3",
        description="TMDB API Base URL"
    )
    tmdb_image_base_url: str = Field(
        default="https://image.tmdb.org/t/p",
        description="TMDB Image Base URL"
    )
    
    # Bot Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    poster_cache_ttl: int = Field(
        default=3600,
        description="Poster cache TTL in seconds"
    )
    poster_cache_max_size: int = Field(
        default=100,
        description="Maximum posters to cache"
    )
    request_timeout: int = Field(
        default=30,
        description="HTTP request timeout in seconds"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts"
    )
    
    # Access Control
    allowed_user_ids: Optional[str] = Field(
        default=None,
        description="Comma-separated list of allowed user IDs"
    )
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is a valid Python logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper
    
    @property
    def allowed_users(self) -> set[int]:
        """Parse allowed user IDs into a set of integers."""
        if not self.allowed_user_ids:
            return set()
        try:
            return {
                int(uid.strip()) 
                for uid in self.allowed_user_ids.split(",") 
                if uid.strip()
            }
        except ValueError:
            return set()
    
    @property
    def poster_base_url(self) -> str:
        """Get the full poster base URL with w500 resolution."""
        return f"{self.tmdb_image_base_url}/w500"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.
    
    Returns:
        Settings: The application settings instance.
    """
    return Settings()