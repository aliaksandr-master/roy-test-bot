from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings

CWD = Path(__file__).parent.parent


class AppSettings(BaseSettings):
    NOTION_API_KEY: SecretStr | None = None
    TELEGRAM_API_KEY: SecretStr | None = None
    PINECONE_API_KEY: SecretStr | None = None
    OPENAI_API_KEY: SecretStr | None = None
    REDIS_DSN: SecretStr | None = None
    DEBUG: bool = False

    class Config:
        env_file = CWD / ".env"


app_settings = AppSettings()
