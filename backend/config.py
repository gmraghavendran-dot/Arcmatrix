from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ArcMatrix"
    app_version: str = "1.0.0"

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "arcmatrix"
    db_user: str = "postgres"
    db_password: str

    app_host: str = "127.0.0.1"
    app_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def database_url(self) -> str:
        from sqlalchemy.engine import URL

        return URL.create(
            drivername="postgresql+psycopg2",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        ).render_as_string(hide_password=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
