from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Korean Study"
    environment: str = "development"
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db_name: str = "korean_study"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60 * 24 * 7
    internal_auth_secret: str = "change-me-too"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    assignment_pdf_max_bytes: int = 50 * 1024 * 1024
    ocr_languages: Annotated[list[str], NoDecode] = ["kor", "eng"]

    @field_validator("cors_origins", "ocr_languages", mode="before")
    @classmethod
    def split_csv_values(cls, value: object) -> object:
        if isinstance(value, str):
            items = [item.strip() for item in value.split(",")]
            return [item for item in items if item]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
