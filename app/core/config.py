import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        # App
        self.APP_NAME = self._get_str("APP_NAME", "ai-job-agent-api")
        self.APP_ENV = self._get_str("APP_ENV", "development").lower()
        self.PORT = self._get_int("PORT", default=8000)
        self.DEBUG = self._resolve_debug()

        # Security
        self.API_KEY = self._get_str("API_KEY")

        # Database
        self.DB_HOST = self._get_str("DB_HOST")
        self.DB_PORT = self._get_int("DB_PORT", default=5432)
        self.DB_NAME = self._get_str("DB_NAME")
        self.DB_USER = self._get_str("DB_USER")
        self.DB_PASSWORD = self._get_str("DB_PASSWORD")

        # LLM
        self.OLLAMA_BASE_URL = self._get_str("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.MODEL_NAME = self._get_str("MODEL_NAME", "qwen2.5-coder")

        # Optional
        self.LOG_LEVEL = self._resolve_log_level()

        # Existing app behavior
        self.RESUME_VERSION = self._get_str("RESUME_VERSION", "base_v2")
        self.LLM_TIMEOUT = self._get_int("LLM_TIMEOUT", default=30)
        self.RATE_LIMIT_MAX_REQUESTS = self._get_int("RATE_LIMIT_MAX_REQUESTS", default=10)
        self.RATE_LIMIT_WINDOW_SECONDS = self._get_int("RATE_LIMIT_WINDOW_SECONDS", default=60)

        # Mode-aware CORS policy
        self.CORS_ORIGINS = self._resolve_cors_origins()

        self._validate()

    @staticmethod
    def _to_bool(value: str | None) -> bool:
        if value is None:
            return False
        return value.strip().lower() in {"true", "1", "yes"}

    def _get_str(self, name: str, default: str | None = None) -> str | None:
        value = os.getenv(name, default)
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed if trimmed else None

    def _get_int(self, name: str, default: int) -> int:
        raw_value = os.getenv(name)
        if raw_value is None or not raw_value.strip():
            return default
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid integer value for {name}: {raw_value}")

    def _get_list(self, name: str, default: str | None = None) -> list[str]:
        raw_value = os.getenv(name, default)
        if raw_value is None:
            return []
        return [item.strip() for item in raw_value.split(",") if item.strip()]

    def _resolve_debug(self) -> bool:
        raw_debug = os.getenv("DEBUG")
        if raw_debug is None:
            return self.APP_ENV == "development"
        return self._to_bool(raw_debug)

    def _resolve_log_level(self) -> str:
        raw_level = self._get_str("LOG_LEVEL")
        if raw_level:
            return raw_level.upper()
        return "DEBUG" if self.DEBUG else "INFO"

    def _resolve_cors_origins(self) -> list[str]:
        if self.APP_ENV == "development":
            default_origins = "http://localhost:8501,http://127.0.0.1:8501"
            return self._get_list("CORS_ORIGINS", default=default_origins)
        return self._get_list("CORS_ORIGINS")

    def _validate(self) -> None:
        if self.APP_ENV not in {"development", "production"}:
            raise ValueError("APP_ENV must be one of: development, production")

        missing = []
        for name in ("API_KEY", "DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"):
            if not getattr(self, name):
                missing.append(name)

        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        if self.PORT <= 0:
            raise ValueError("PORT must be greater than 0")
        if self.DB_PORT <= 0:
            raise ValueError("DB_PORT must be greater than 0")
        if self.LLM_TIMEOUT <= 0:
            raise ValueError("LLM_TIMEOUT must be greater than 0")
        if self.RATE_LIMIT_MAX_REQUESTS <= 0:
            raise ValueError("RATE_LIMIT_MAX_REQUESTS must be greater than 0")
        if self.RATE_LIMIT_WINDOW_SECONDS <= 0:
            raise ValueError("RATE_LIMIT_WINDOW_SECONDS must be greater than 0")
        if self.APP_ENV == "production" and not self.CORS_ORIGINS:
            raise ValueError("CORS_ORIGINS is required when APP_ENV=production")

    def validate(self) -> None:
        self._validate()


settings = Settings()
