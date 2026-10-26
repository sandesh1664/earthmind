from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", hide_input_in_errors=True, populate_by_name=True
    )

    database_url: str = "postgresql://localhost:5434/earthmind"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["http://localhost:3000"]
    health_timeout_seconds: float = Field(default=2.0, gt=0, le=10)
    dev_write_token: SecretStr | None = Field(
        default=None, validation_alias="EARTHMIND_DEV_WRITE_TOKEN"
    )
    geo_max_request_bytes: int = Field(default=262144, ge=1024, le=1048576)
    geo_max_coordinates: int = Field(default=5000, ge=4, le=5000)
    geo_max_bbox_degrees: float = Field(default=1.0, gt=0, le=5)
    geo_max_page_size: int = Field(default=100, ge=1, le=100)
    geo_max_radius_m: float = Field(default=5000, gt=0, le=5000)
    geo_max_validation_features: int = Field(default=10000, ge=10, le=100000)
    geo_max_validation_coordinates: int = Field(default=100000, ge=10, le=100000)
    geo_boundary_tolerance_m: float = Field(default=5.0, ge=0, le=100)

    @field_validator("dev_write_token")
    @classmethod
    def strong_development_token(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value():
            return None
        if value is not None and len(value.get_secret_value()) < 32:
            raise ValueError("Development write token must contain at least 32 characters")
        return value

    @field_validator("database_url")
    @classmethod
    def valid_database_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "postgresql"
            or not parsed.hostname
            or not parsed.path.strip("/")
            or value.strip() != value
            or any(character in value for character in "\r\n")
            or (parsed.port is not None and not 0 < parsed.port < 65536)
        ):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL with a host and database")
        return value

    @field_validator("redis_url")
    @classmethod
    def valid_redis_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"redis", "rediss"}
            or not parsed.hostname
            or value.strip() != value
            or any(character in value for character in "\r\n")
            or (parsed.port is not None and not 0 < parsed.port < 65536)
        ):
            raise ValueError("REDIS_URL must use redis:// or rediss:// with a host")
        return value

    @field_validator("cors_origins")
    @classmethod
    def explicit_cors_origins(cls, values: list[str]) -> list[str]:
        for value in values:
            parsed = urlsplit(value)
            if (
                "*" in value
                or parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                or (parsed.port is not None and not 0 < parsed.port < 65536)
            ):
                raise ValueError("CORS origins must be explicit HTTP(S) origins without wildcards")
        return [value.rstrip("/") for value in values]
