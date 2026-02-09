"""Application configuration settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Field(default=Path("data"))
    projects_dir: Path = Field(default=Path("data/projects"))
    session_store: Path = Field(default=Path("data/sessions"))
    config_json: Path = Field(default=Path("config.json"))
    step_config_path: Path = Field(default=Path("config/step_config.json"))
    frontend_dist: Path = Field(default=Path("app/dist"))
    max_audio_mb: int = Field(default=500)
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])

    @property
    def max_audio_bytes(self) -> int:
        return self.max_audio_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    settings = AppSettings()
    settings.projects_dir.mkdir(parents=True, exist_ok=True)
    settings.session_store.mkdir(parents=True, exist_ok=True)
    return settings
