from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    worker_heartbeat_interval_seconds: float = Field(default=5.0, gt=0, le=10)
    worker_runtime_check_interval_seconds: float = Field(default=30.0, ge=10, le=45)
    worker_job_timeout_seconds: float = Field(default=40.0, ge=5, le=45)
