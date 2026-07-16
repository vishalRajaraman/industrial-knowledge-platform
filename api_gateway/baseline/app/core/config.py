from dataclasses import dataclass, field
import os


def _parse_csv_env(name: str, default: list[str]) -> list[str]:
    raw_value = os.getenv(name, "")
    if not raw_value.strip():
        return default

    values = [item.strip() for item in raw_value.split(",")]
    return [item for item in values if item]


@dataclass(frozen=True, slots=True)
class GatewaySettings:
    app_name: str = "Industrial Knowledge API Gateway"
    version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    jwt_secret_key: str = os.getenv("API_GATEWAY_JWT_SECRET_KEY", "dev-only-change-me-please-rotate-this-key")
    jwt_algorithm: str = os.getenv("API_GATEWAY_JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("API_GATEWAY_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    cors_allow_origins: list[str] = field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    gzip_minimum_size: int = 1024
    request_timeout_seconds: int = 30
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"


settings = GatewaySettings(
    cors_allow_origins=_parse_csv_env(
        "API_GATEWAY_CORS_ORIGINS",
        ["http://localhost:3000", "http://127.0.0.1:3000"],
    )
)
