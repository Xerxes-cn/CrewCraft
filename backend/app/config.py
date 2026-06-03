from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///crewcraft.db"
    deepseek_api_key: str = "sk-d34bff3632644228bf509c55e1187a2e"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-pro"
    workspace_root: str = "./workspace"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
