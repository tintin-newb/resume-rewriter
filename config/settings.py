import os
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_HOME_DIR: Path = Path.home() / ".resume-rewriter"
APP_UPLOADS_DIR: Path = APP_HOME_DIR / "uploads"
APP_OUTPUT_DIR: Path = APP_HOME_DIR / "output"
APP_HOME_ENV: Path = APP_HOME_DIR / "config.env"
LEGACY_HOME_ENV: Path = Path.home() / ".resume-rewriter.env"


def _ensure_dir(p: Path) -> bool:
    try:
        p.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False


def get_active_env_file() -> Path:
    """Returns the primary home configuration env path, initializing if needed."""
    global APP_HOME_DIR, APP_UPLOADS_DIR, APP_OUTPUT_DIR, APP_HOME_ENV

    if not _ensure_dir(APP_HOME_DIR):
        local_fallback = Path(".resume-rewriter")
        if _ensure_dir(local_fallback):
            APP_HOME_DIR = local_fallback.resolve()
        else:
            tmp_fallback = Path("/tmp/.resume-rewriter")
            _ensure_dir(tmp_fallback)
            APP_HOME_DIR = tmp_fallback

        APP_UPLOADS_DIR = APP_HOME_DIR / "uploads"
        APP_OUTPUT_DIR = APP_HOME_DIR / "output"
        APP_HOME_ENV = APP_HOME_DIR / "config.env"

    _ensure_dir(APP_UPLOADS_DIR)
    _ensure_dir(APP_OUTPUT_DIR)

    if "CRAWL4_AI_BASE_DIRECTORY" not in os.environ:
        os.environ["CRAWL4_AI_BASE_DIRECTORY"] = str(APP_HOME_DIR)

    if LEGACY_HOME_ENV.exists() and not APP_HOME_ENV.exists():
        return LEGACY_HOME_ENV

    if not APP_HOME_ENV.exists():
        # Seed from project .env or .env.example if available
        local_env = Path(".env")
        example_env = Path(".env.example")
        if local_env.exists():
            APP_HOME_ENV.write_text(local_env.read_text(encoding="utf-8"), encoding="utf-8")
        elif example_env.exists():
            APP_HOME_ENV.write_text(example_env.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            try:
                APP_HOME_ENV.touch()
            except OSError:
                pass

    return APP_HOME_ENV


active_env_path = get_active_env_file()


class Settings(BaseSettings):
    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    OLLAMA_REASONING: bool = False
    REASONING: Optional[bool] = None
    REWRITER_TEMP: float = 0.2
    REFERRAL_TEMP: float = 0.2
    RECRUITER_TEMP: float = 0.0

    # PostgreSQL
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "resume_rewriter_db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""

    # Pipeline & Content Settings
    WORD_LIMIT: int = 20
    OUTPUT_DIR: Path = APP_OUTPUT_DIR

    model_config = SettingsConfigDict(
        env_file=(str(active_env_path), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def reasoning(self) -> bool:
        if self.REASONING is not None:
            return self.REASONING
        return self.OLLAMA_REASONING

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()


def reload_settings() -> Settings:
    global settings
    env_file = get_active_env_file()
    new_settings = Settings(_env_file=(str(env_file), ".env"))
    valid_fields = set(type(settings).model_fields.keys())
    for k, v in new_settings.model_dump().items():
        if k in valid_fields:
            setattr(settings, k, v)
    return settings


def save_home_env_config(updates: Dict[str, Any]) -> Path:
    env_file = get_active_env_file()
    lines = []
    existing_keys = set()

    if env_file.exists():
        content = env_file.read_text(encoding="utf-8").splitlines()
        for line in content:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _ = stripped.split("=", 1)
                k = k.strip()
                if k in updates:
                    lines.append(f"{k}={updates[k]}")
                    existing_keys.add(k)
                    continue
            lines.append(line)

    for k, v in updates.items():
        if k not in existing_keys:
            lines.append(f"{k}={v}")

    env_file.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    
    # Also update os.environ so any code directly reading os.environ or downstream libraries pick it up
    for k, v in updates.items():
        os.environ[k] = str(v)

    reload_settings()
    return env_file