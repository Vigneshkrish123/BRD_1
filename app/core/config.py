from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Azure AI Foundry
    azure_foundry_endpoint: str = Field(..., description="Azure AI Foundry endpoint URL")
    azure_foundry_api_key: str = Field(..., description="Azure AI Foundry API key")
    azure_foundry_model: str = Field(default="gpt-4o-mini", description="Model deployment name")

    # API Security
    api_secret_key: str = Field(..., description="Shared secret for Power Automate → API auth")

    # App
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    max_file_size_mb: int = Field(default=20)
    allowed_extensions: list[str] = Field(default=[".docx", ".vtt"])

    # BRD Template
    brd_template_path: str = Field(
        default="./templates/brd_template.docx",
        description="Absolute or relative path to company BRD .docx template",
    )

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


# Single shared instance — import this everywhere
settings = Settings()  # type: ignore[call-arg]
