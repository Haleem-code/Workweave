from pathlib import Path
import re
from urllib.parse import quote, urlsplit
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_OLLAMA_CLOUD_MODEL = "gemma4:31b"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WORKWEAVE_", env_file=".env", env_ignore_empty=True, extra="ignore")
    graph_url: str = "redis://localhost:16379"
    graph_host: str = ""
    graph_port: int = Field(default=6379, ge=1, le=65535)
    graph_username: str = ""
    graph_password: SecretStr = SecretStr("") 
    graph_password_file: Path | None = None
    graph_tls: bool = True
    secure_cookies: bool = False
    ollama_url: str = "http://localhost:11434"
    groq_key: str = ""
    gemini_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    gemini_model: str = "gemini-3.5-flash-lite"
    ollama_model: str = "qwen3:8b"
    ollama_cloud_key: SecretStr = SecretStr("")
    ollama_cloud_model: str = DEFAULT_OLLAMA_CLOUD_MODEL
    embedding_model: str = "embeddinggemma:300m"
    admin_username: str = "admin"
    admin_password: str = ""
    data_dir: Path = Path(".workweave")
    google_client_id: str = ""
    google_client_secret: str = ""
    google_picker_key: str = ""
    google_project_id: str = ""
    google_redirect_uri: str = "http://localhost:8080/api/v1/google/callback"
    allow_private_drive: bool = False
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "api"]
    frontend_dir: Path = Path(__file__).resolve().parents[2] / "workweave-web" / "dist"

    @property
    def ollama_cloud_model_valid(self) -> bool:
        # The Cloud API accepts model identifiers, not URLs or credentials.
        return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*(?::[A-Za-z0-9][A-Za-z0-9._-]*)?", self.ollama_cloud_model.strip())) and len(self.ollama_cloud_model.strip()) <= 128

    @property
    def effective_ollama_cloud_model(self) -> str:
        return self.ollama_cloud_model.strip() if self.ollama_cloud_model_valid else DEFAULT_OLLAMA_CLOUD_MODEL

    @property
    def graph_connection_url(self) -> str:
        if not self.graph_host:
            return self.graph_url
        host = self.graph_host.strip()
        if any(part in host for part in ("/", "@", "?", "#")):
            raise ValueError("Graph host must be a hostname, without a URL scheme or credentials")
        password = self.graph_password.get_secret_value()
        if self.graph_password_file:
            try:
                password = self.graph_password_file.read_text(encoding="utf-8").rstrip("\r\n")
            except OSError as exc:
                raise ValueError("Configured database password file is missing or unreadable") from exc
        credentials = (quote(self.graph_username, safe="") + ":" + quote(password, safe="") + "@") if password or self.graph_username else ""
        return f"{'rediss' if self.graph_tls else 'redis'}://{credentials}{host}:{self.graph_port}"

    @property
    def graph_connection_info(self) -> dict:
        parsed = urlsplit(self.graph_connection_url)
        return {"mode": "local" if parsed.hostname in ("localhost", "127.0.0.1", "falkordb", "host.docker.internal") else "remote",
                "tls": parsed.scheme == "rediss"}


settings = Settings()
