"""Configuration for Document Service."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# Get the directory where this config.py file is located
CONFIG_DIR = Path(__file__).parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres@localhost:5433/dociq"
    )

    # Database pool settings
    db_pool_size: int = int(os.getenv("DB_POOL_SIZE", "5"))
    db_max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    db_pool_timeout: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))

    # Worker settings
    worker_poll_interval: int = int(os.getenv("WORKER_POLL_INTERVAL", "30"))  # seconds
    worker_batch_size: int = int(os.getenv("WORKER_BATCH_SIZE", "10"))

    # Security settings
    max_file_size: int = int(os.getenv("MAX_FILE_SIZE", str(50 * 1024 * 1024)))  # 50MB
    max_processing_size: int = int(os.getenv("MAX_PROCESSING_SIZE", str(50 * 1024 * 1024)))

    # ClamAV
    clamav_host: str = os.getenv("CLAMAV_HOST", "127.0.0.1")
    clamav_port: int = int(os.getenv("CLAMAV_PORT", "3310"))
    clamav_timeout: int = int(os.getenv("CLAMAV_TIMEOUT", "120"))
    # Directory where scanned files are staged. MUST be the host path of the
    # Docker volume also mounted into the ClamAV container (/shared), because
    # ClamAV's SCAN command operates on paths visible to the daemon.
    # If ClamAV runs natively (not in Docker), set this equal to the system
    # temp dir and CLAMAV_SHARED_MOUNT_CONTAINER to "" (no translation).
    security_scan_dir: str = os.getenv("SECURITY_SCAN_DIR", r"D:\Projects\DocIQ\clamav")
    # Path of that same volume inside the container ("" disables translation).
    clamav_shared_mount_container: str = os.getenv("CLAMAV_SHARED_MOUNT_CONTAINER", "/shared")

    # R2/Object Storage
    r2_account_id: str = os.getenv("R2_ACCOUNT_ID", "")
    r2_access_key_id: str = os.getenv("R2_ACCESS_KEY_ID", "")
    r2_secret_access_key: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
    r2_bucket_name: str = os.getenv("R2_BUCKET_NAME", "")
    r2_endpoint: str = os.getenv("R2_ENDPOINT", "")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = CONFIG_DIR / ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()