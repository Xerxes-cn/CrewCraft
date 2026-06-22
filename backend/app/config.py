from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///crewcraft.db"
    workspace_root: str = "./workspace"

    # Unified LLM config (new)
    llm_provider: str = "deepseek"  # deepseek | qwen | kimi | openai
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""

    # Legacy deepseek config (fallback when llm_provider=deepseek)
    deepseek_api_key: str = "sk-d34bff3632644228bf509c55e1187a2e"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
