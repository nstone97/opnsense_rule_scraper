from __future__ import annotations

import pytest

from opnsense_rule_scraper.config import Config, parse_tls_verify


def test_parse_tls_verify() -> None:
    assert parse_tls_verify(None) is True
    assert parse_tls_verify("false") is False
    assert parse_tls_verify("/etc/ssl/opnsense.crt") == "/etc/ssl/opnsense.crt"


def test_from_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPNSENSE_URL", "https://192.168.1.1/")
    monkeypatch.setenv("OPNSENSE_API_KEY", "k")
    monkeypatch.setenv("OPNSENSE_API_SECRET", "s")
    monkeypatch.setenv("OPNSENSE_TLS_VERIFY", "false")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    config = Config.from_env()
    assert config.url == "https://192.168.1.1"
    assert config.tls_verify is False
    assert config.rules_csv == tmp_path / "opnsense_rules.csv"


def test_from_env_requires_credentials(monkeypatch) -> None:
    monkeypatch.delenv("OPNSENSE_URL", raising=False)
    monkeypatch.delenv("OPNSENSE_API_KEY", raising=False)
    monkeypatch.delenv("OPNSENSE_API_SECRET", raising=False)
    with pytest.raises(SystemExit):
        Config.from_env()
