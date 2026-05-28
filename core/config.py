from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    discord_token: str = ""
    twitter_bearer_token: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "IdentiFix/1.0"
    saucenao_api_key: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    h8mail_haveibeenpwned_key: str = ""
    h8mail_snusbase_key: str = ""
    h8mail_leaklookup_key: str = ""

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    data_dir: str = "./data"

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
