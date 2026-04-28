from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NGO Fraud & Beneficiary Integrity System - Production V1"
    database_url: str = "postgresql+psycopg2://ngo_fraud:ngo_fraud_password@localhost:5432/ngo_fraud"
    supabase_url: str = ""
    supabase_key: str = ""
    jwt_secret: str = ""
    auth_mode: str = "supabase"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
