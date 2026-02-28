import os
from functools import lru_cache
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    environment: str = os.getenv("ENVIRONMENT", "local")

    # Releasetrain endpoints
    releasetrain_vendor_api: AnyHttpUrl = "https://releasetrain.io/api/c/names"
    releasetrain_component_api: AnyHttpUrl = "https://releasetrain.io/api/component?q=os"

    # LLM / tools (Gemini for Router; OpenAI kept for optional compatibility)
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    # Data layer (Far's Node service: /facts/latest, /facts/on-date)
    data_layer_service_url: str = os.getenv("DATA_LAKE_SERVICE_URL", "http://localhost:3000")

    # Neo4j (optional)
    neo4j_uri: str = os.getenv("NEO4J_URI", "")
    neo4j_user: str = os.getenv("NEO4J_USER", "")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


SETTINGS = get_settings()

