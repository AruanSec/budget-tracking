from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    environment: Literal["development", "production"] = "development"
    database_url: str = (
        "postgresql+psycopg://budget:dev-secret@localhost:5432/budget"
    )
    jwt_secret: str = "dev-secret"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60 * 24 * 7  # 7 days

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.environment == "production":
            password = make_url(self.database_url).password
            if not password or password == "dev-secret":
                raise ValueError("Production requires a non-placeholder database password")
            if self.jwt_secret == "dev-secret" or len(self.jwt_secret.encode()) < 32:
                raise ValueError("Production requires a JWT secret of at least 32 bytes")
        return self

    model_config = {"env_prefix": "BUDGET_", "env_file": ".env", "extra": "ignore", "hide_input_in_errors": True}


settings = Settings()
