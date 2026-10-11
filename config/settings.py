from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"

    # PostgreSQL
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "resume_rewriter_db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""

    # Pipeline Settings
    MIN_MATCH_SCORE: float = 8.0
    MAX_LOOPS: int = 3
    DEFAULT_ACTION_VERBS_PATH: Path = Path("data/action_verbs.pdf")
    OUTPUT_DIR: Path = Path("output")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()