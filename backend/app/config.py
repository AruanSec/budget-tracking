from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://budget:***@localhost:5432/budget"
    )
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60 * 24 * 7  # 7 days

    model_config = {"env_prefix": "BUDGET_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
