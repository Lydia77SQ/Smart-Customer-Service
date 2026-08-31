"""配置加载单测：默认值、SECRET_KEY 必填、不读进程环境、不碰业务库。"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from pycore.core import ConfigManager
from pycore.core.exceptions import ConfigurationError

from src.core.config import AppSettings, load_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_EXAMPLE_PATH = BACKEND_DIR / ".env.example"

_MINIMAL_ENV = "SECRET_KEY=test-secret-key\nDASHSCOPE_API_KEY=test-dashscope-key\n"


@pytest.fixture(autouse=True)
def reset_config_manager() -> Iterator[None]:
    ConfigManager.reset()
    yield
    ConfigManager.reset()


def _write_env(tmp_path: Path, body: str) -> Path:
    env_file = tmp_path / ".env"
    env_file.write_text(body, encoding="utf-8")
    return env_file


def test_default_database_path(tmp_path: Path) -> None:
    settings = load_settings(_write_env(tmp_path, _MINIMAL_ENV))
    assert settings.database_path == "data/service_robot.db"


def test_default_port_and_host(tmp_path: Path) -> None:
    settings = load_settings(_write_env(tmp_path, _MINIMAL_ENV))
    assert settings.port == 8099
    assert settings.host == "127.0.0.1"
    assert settings.debug is False


def test_default_degraded_messages(tmp_path: Path) -> None:
    settings = load_settings(_write_env(tmp_path, _MINIMAL_ENV))
    assert settings.degraded_qa_message == "很抱歉，您的问题我暂时无法解答，请转人工等待对接人接入"
    assert settings.degraded_suggestion_message == (
        "暂时无法生成建议。请手写回复，不要向员工发送自动消息。"
    )
    assert settings.transfer_success_message == "已提交，等待对接人"


def test_default_cors_origins(tmp_path: Path) -> None:
    settings = load_settings(_write_env(tmp_path, _MINIMAL_ENV))
    assert settings.cors_origins == [
        "http://localhost:5199",
        "http://127.0.0.1:5199",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ]


def test_http_client_trust_env_default_false(tmp_path: Path) -> None:
    settings = load_settings(_write_env(tmp_path, _MINIMAL_ENV))
    assert settings.http_client_trust_env is False


def test_secret_key_missing_raises_clear_error(tmp_path: Path) -> None:
    env_file = _write_env(tmp_path, "DASHSCOPE_API_KEY=test-dashscope-key\n")
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(env_file)
    message = str(exc_info.value)
    assert "SECRET_KEY" in message
    assert "无默认值" in message


def test_secret_key_empty_raises_clear_error(tmp_path: Path) -> None:
    env_file = _write_env(
        tmp_path,
        "SECRET_KEY=\nDASHSCOPE_API_KEY=test-dashscope-key\n",
    )
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(env_file)
    assert "SECRET_KEY" in str(exc_info.value)


def test_process_env_does_not_override_file_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORT", "1111")
    monkeypatch.setenv("PYCORE_PORT", "2222")
    monkeypatch.setenv("DATABASE_PATH", "data/from-process.db")
    settings = load_settings(_write_env(tmp_path, _MINIMAL_ENV))
    assert settings.port == 8099
    assert settings.database_path == "data/service_robot.db"


def test_file_values_override_defaults(tmp_path: Path) -> None:
    body = (
        _MINIMAL_ENV
        + "PORT=8003\n"
        + "DATABASE_PATH=data/custom.db\n"
        + "DEGRADED_QA_MESSAGE=custom-qa\n"
    )
    settings = load_settings(_write_env(tmp_path, body))
    assert settings.port == 8003
    assert settings.database_path == "data/custom.db"
    assert settings.degraded_qa_message == "custom-qa"


def test_cors_origins_json_string(tmp_path: Path) -> None:
    body = (
        _MINIMAL_ENV
        + 'CORS_ORIGINS=["http://localhost:5199","http://localhost:5175"]\n'
    )
    settings = load_settings(_write_env(tmp_path, body))
    assert settings.cors_origins == [
        "http://localhost:5199",
        "http://localhost:5175",
    ]


def test_tech_spec_keys_are_readable(tmp_path: Path) -> None:
    settings = load_settings(_write_env(tmp_path, _MINIMAL_ENV))
    expected = {name.lower() for name in _example_keys()}
    actual = set(type(settings).model_fields)
    assert expected == actual


def test_env_example_exists_and_matches_settings_fields() -> None:
    assert ENV_EXAMPLE_PATH.is_file()
    example_keys = _example_keys()
    field_keys = {name.upper() for name in AppSettings.model_fields}
    assert example_keys == field_keys
    assert "SECRET_KEY" in example_keys
    assert "DASHSCOPE_API_KEY" in example_keys


def test_env_example_has_placeholders_not_real_secrets() -> None:
    text = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    values = _example_values(text)
    assert values["SECRET_KEY"] == "change-me"
    assert values["DASHSCOPE_API_KEY"] == "your-dashscope-api-key"
    for key, value in values.items():
        assert not value.startswith("sk-"), key
        assert "Bearer " not in value, key


def _example_keys() -> set[str]:
    keys: set[str] = set()
    for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        keys.add(stripped.partition("=")[0].strip())
    return keys


def _example_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values
