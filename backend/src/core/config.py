"""应用配置：基于 pycore.core.ConfigManager 加载 tech-spec §4 全部键。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pycore.core import BaseSettings, ConfigLoader, ConfigManager
from pycore.core.exceptions import ConfigurationError
from pydantic import Field, field_validator

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = BACKEND_ROOT / ".env"

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:5199",
    "http://127.0.0.1:5199",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
]

_SECRET_KEY_MISSING_MESSAGE = (
    "SECRET_KEY 未配置或为空：该配置无默认值，请在 backend/.env 中设置 SECRET_KEY 后启动。"
)


class DotEnvFileLoader(ConfigLoader):
    """从 .env 文件加载配置，不写入、不读取进程环境变量。"""

    def supports(self, path: Path) -> bool:
        name = path.name
        return name == ".env" or name.startswith(".env.") or path.suffix.lower() == ".env"

    def load(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise ConfigurationError(
                f"Configuration file not found: {path}",
                config_path=str(path),
            )
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigurationError(
                f"Failed to read configuration file: {exc}",
                config_path=str(path),
            ) from exc
        return _parse_dotenv(text)


def _parse_dotenv(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        result[key.lower()] = _unquote(value.strip())
    return result


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


class AppSettings(BaseSettings):
    """tech-spec §4 后端 config 键。字段名对应 .env 键的小写形式。"""

    database_path: str = "data/service_robot.db"
    upload_dir: str = "data/uploads"
    host: str = "127.0.0.1"
    port: int = 8099
    debug: bool = False
    secret_key: str = Field(min_length=1)
    cors_origins: list[str] = Field(default_factory=lambda: list(_DEFAULT_CORS_ORIGINS))
    session_expire_hours: int = 72
    account_min_length: int = 3
    account_max_length: int = 64
    password_min_length: int = 6
    password_max_length: int = 128
    ticket_title_max_length: int = 80
    employee_message_max_length: int = 4000
    agent_message_max_length: int = 4000
    ticket_list_page_default: int = 1
    ticket_list_page_size: int = 20
    ticket_list_page_size_max: int = 100
    knowledge_list_page_default: int = 1
    knowledge_list_page_size: int = 50
    knowledge_max_size_bytes: int = 20971520
    qa_similarity_threshold: float = 0.8
    short_term_memory_rounds: int = 3
    search_top_k: int = 10
    rrf_k: int = 60
    rerank_top_n: int = 5
    chunk_size: int = 800
    chunk_overlap: int = 100
    dashscope_api_key: str
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen-max"
    llm_timeout_seconds: int = 60
    llm_temperature_intent: float = 0.1
    llm_temperature_generation: float = 0.3
    embedding_base_url: str = (
        "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
    )
    embedding_model: str = "text-embedding-v3"
    embedding_timeout_seconds: int = 30
    embedding_dimensions: int = 1024
    rerank_base_url: str = (
        "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
    )
    rerank_model: str = "gte-rerank"
    rerank_timeout_seconds: int = 30
    http_client_trust_env: bool = False
    degraded_qa_message: str = "暂时无法自动答疑，请稍后再试，或转人工等待对接人。"
    degraded_suggestion_message: str = (
        "暂时无法生成建议。请手写回复，不要向员工发送自动消息。"
    )
    transfer_success_message: str = "已提交，等待对接人"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return list(_DEFAULT_CORS_ORIGINS)
            if text.startswith("["):
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return parsed
            return [part.strip() for part in text.split(",") if part.strip()]
        return value


def load_settings(config_path: str | Path | None = None) -> AppSettings:
    """从 .env 文件加载配置；禁止用进程环境覆盖文件值。"""
    path = Path(config_path) if config_path is not None else DEFAULT_ENV_PATH
    manager: ConfigManager[AppSettings] = ConfigManager()
    manager.register_loader(DotEnvFileLoader())
    try:
        manager.load(AppSettings, path, use_env=False)
    except ConfigurationError as exc:
        if "secret_key" in str(exc).lower():
            raise ConfigurationError(
                _SECRET_KEY_MISSING_MESSAGE,
                config_path=str(path),
                field="SECRET_KEY",
            ) from exc
        raise
    return manager.settings


def get_settings() -> AppSettings:
    """返回已加载的配置；尚未加载时从默认 backend/.env 读取。"""
    manager: ConfigManager[AppSettings] = ConfigManager()
    try:
        loaded = manager.settings
    except ConfigurationError:
        return load_settings()
    if isinstance(loaded, AppSettings):
        return loaded
    return load_settings()
