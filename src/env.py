from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings

CWD = Path(__file__).parent.parent


class AppSettings(BaseSettings):
    SRC_ROY_ORG_ID: int | None = None
    SRC_ROY_SECTIONS: str | None = None
    SRC_ROY_LOGIN: SecretStr | None = None
    SRC_ROY_PASSWORD: SecretStr | None = None

    SRC_NOTION_WIKI_ID: str | None = None
    SRC_NOTION_API_KEY: SecretStr | None = None

    BOT_API_KEY: SecretStr | None = None

    LANG: str = "English"

    LLM_OPENAI_API_KEY: SecretStr | None = None
    LLM_OPENAI_MODEL_NAME: str = "gpt-3.5-turbo-0125"

    # OPTIONAL
    DEBUG: bool = False

    @property
    def roy_sections(self) -> set[int] | None:
        return {int(sect.strip()) for sect in app_settings.SRC_ROY_SECTIONS.split(",")} if app_settings.SRC_ROY_SECTIONS else None

    class Config:
        env_file = CWD / ".env"
        extra = "ignore"


app_settings = AppSettings()
