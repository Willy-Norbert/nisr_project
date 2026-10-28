from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_prefix="FARMGAP_", extra="ignore")

    app_name: str = "FarmGap Rwanda API"
    api_prefix: str = "/api/v1"
    raw_data_dir: Path = BACKEND_DIR / "datasets" / "raw"
    processed_data_dir: Path = BACKEND_DIR / "datasets" / "processed"
    geography_dir: Path = BACKEND_DIR / "datasets" / "geography"
    frontend_dist_dir: Path = BACKEND_DIR.parent / "frontend" / "dist"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000", "https://analiza-nisr.vercel.app"]
    log_level: str = "INFO"

    # Any OpenAI-compatible chat API (Gemini, Groq, OpenAI, OpenRouter...). Empty key = rule-based answers only.
    llm_enabled: bool = False
    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("FARMGAP_LLM_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    llm_model: str = "gemini-3.8-flash"
    llm_timeout_s: float = 40.0


@lru_cache
def get_settings() -> Settings:
    return Settings()

