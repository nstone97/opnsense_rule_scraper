from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Union

TlsVerify = Union[bool, str]


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _env_bool(name: str, default: bool) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    if value is None:
        return default
    return int(value)


def parse_tls_verify(raw: str | None) -> TlsVerify:
    if raw is None or raw.lower() in {"1", "true", "yes", "on"}:
        return True
    if raw.lower() in {"0", "false", "no", "off"}:
        return False
    return raw


@dataclass(frozen=True)
class Config:
    url: str
    api_key: str
    api_secret: str
    tls_verify: TlsVerify
    timeout: float
    scrape_interval: float
    output_dir: Path
    http_host: str
    http_port: int
    include_interfaces: bool
    run_once: bool

    @property
    def rules_csv(self) -> Path:
        return self.output_dir / "opnsense_rules.csv"

    @property
    def rules_json(self) -> Path:
        return self.output_dir / "opnsense_rules.json"

    @property
    def interfaces_csv(self) -> Path:
        return self.output_dir / "opnsense_interfaces.csv"

    @classmethod
    def from_env(cls, *, run_once: bool = False) -> Config:
        url = _env("OPNSENSE_URL")
        api_key = _env("OPNSENSE_API_KEY")
        api_secret = _env("OPNSENSE_API_SECRET")
        if not url or not api_key or not api_secret:
            raise SystemExit(
                "OPNSENSE_URL, OPNSENSE_API_KEY, and OPNSENSE_API_SECRET are required"
            )
        return cls(
            url=url.rstrip("/"),
            api_key=api_key,
            api_secret=api_secret,
            tls_verify=parse_tls_verify(_env("OPNSENSE_TLS_VERIFY")),
            timeout=float(_env("OPNSENSE_TIMEOUT", "30")),
            scrape_interval=float(_env("SCRAPE_INTERVAL", "60")),
            output_dir=Path(_env("OUTPUT_DIR", "/data")),
            http_host=_env("HTTP_HOST", "0.0.0.0") or "0.0.0.0",
            http_port=_env_int("HTTP_PORT", 8080),
            include_interfaces=_env_bool("INCLUDE_INTERFACES", True),
            run_once=run_once or _env_bool("RUN_ONCE", False),
        )
