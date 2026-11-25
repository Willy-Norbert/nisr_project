from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_prefix="FARMGAP_", extra="ignore")

    app_name: str = "Analiza API"
    api_prefix: str = "/api/v1"
    raw_data_dir: Path = BACKEND_DIR / "datasets" / "raw"
    processed_data_dir: Path = BACKEND_DIR / "datasets" / "processed"
    geography_dir: Path = BACKEND_DIR / "datasets" / "geography"
    frontend_dist_dir: Path = BACKEND_DIR.parent / "frontend" / "dist"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000", "https://analiza-nisr.vercel.app"]
    log_level: str = "INFO"



@lru_cache
def get_settings() -> Settings:
    return Settings()
