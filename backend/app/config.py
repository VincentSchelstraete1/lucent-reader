from dataclasses import dataclass
import os
from urllib.parse import urlsplit


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes"}


def _origins(value: str) -> tuple[str, ...]:
    return tuple(origin.strip().rstrip("/") for origin in value.split(",") if origin.strip())


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    web_origins: tuple[str, ...]
    api_origin: str
    google_client_id: str | None
    google_client_secret: str | None
    google_redirect_uri: str | None
    cookie_secure: bool
    enable_development_auth: bool
    enable_legacy_claim: bool
    extension_ids: tuple[str, ...]
    session_idle_seconds: int = 60 * 60 * 24
    session_absolute_seconds: int = 60 * 60 * 24 * 30

    @property
    def production(self) -> bool:
        return self.environment == "production"

    @property
    def session_cookie_name(self) -> str:
        return "__Host-lucent_session" if self.cookie_secure else "lucent_session"

    def validate(self) -> None:
        if self.environment not in {"development", "test", "production"}:
            raise RuntimeError("APP_ENV must be development, test, or production")
        if self.production:
            required = {
                "GOOGLE_CLIENT_ID": self.google_client_id,
                "GOOGLE_CLIENT_SECRET": self.google_client_secret,
                "GOOGLE_REDIRECT_URI": self.google_redirect_uri,
                "API_ORIGIN": self.api_origin,
            }
            missing = [key for key, value in required.items() if not value]
            if missing:
                raise RuntimeError(f"Missing production security configuration: {', '.join(missing)}")
            if not self.cookie_secure or not self.api_origin.startswith("https://"):
                raise RuntimeError("Production requires HTTPS and secure cookies")
            if self.enable_development_auth or self.enable_legacy_claim:
                raise RuntimeError("Development auth and legacy claim cannot be enabled in production")
        for origin in self.web_origins:
            parsed = urlsplit(origin)
            if parsed.scheme not in {"http", "https", "chrome-extension"} or not parsed.netloc:
                raise RuntimeError(f"Invalid allowed origin: {origin}")


def load_settings() -> Settings:
    environment = os.getenv("APP_ENV", "development")
    settings = Settings(
        environment=environment,
        database_url=os.environ["DATABASE_URL"],
        web_origins=_origins(os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")),
        api_origin=os.getenv("API_ORIGIN", "http://127.0.0.1:8000").rstrip("/"),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID"),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        google_redirect_uri=os.getenv("GOOGLE_REDIRECT_URI"),
        cookie_secure=_bool("COOKIE_SECURE", environment == "production"),
        enable_development_auth=_bool("ENABLE_DEVELOPMENT_AUTH"),
        enable_legacy_claim=_bool("ENABLE_LEGACY_CLAIM"),
        extension_ids=_origins(os.getenv("LUCENT_EXTENSION_IDS", "")),
    )
    settings.validate()
    return settings


settings = load_settings()
