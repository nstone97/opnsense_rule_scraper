from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import Config, TlsVerify
from .models import Interface, Rule

log = logging.getLogger(__name__)

RULE_IDS_PATHS = (
    "/api/diagnostics/firewall/list_rule_ids",
    "/api/diagnostics/firewall/listRuleIds",
)
INTERFACE_PATHS = (
    "/api/diagnostics/interface/get_interface_names",
    "/api/diagnostics/interface/getInterfaceNames",
)


class OpnSenseError(RuntimeError):
    pass


def _as_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "rows", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise OpnSenseError(f"unexpected list_rule_ids payload: {type(payload).__name__}")


def normalize_rules(payload: Any) -> list[Rule]:
    rules: list[Rule] = []
    seen: set[str] = set()
    for item in _as_items(payload):
        rid = item.get("id") or item.get("rid") or item.get("uuid")
        if rid is None:
            continue
        rid = str(rid).strip()
        if not rid or rid in seen:
            continue
        descr = item.get("descr") or item.get("description") or ""
        rules.append(Rule(rid=rid, descr=str(descr)))
        seen.add(rid)
    rules.sort(key=lambda rule: (rule.descr.lower(), rule.rid))
    return rules


def normalize_interfaces(payload: Any) -> list[Interface]:
    if not isinstance(payload, dict):
        raise OpnSenseError(
            f"unexpected get_interface_names payload: {type(payload).__name__}"
        )
    mapping = payload
    if "rows" in payload and isinstance(payload["rows"], dict):
        mapping = payload["rows"]
    interfaces = [
        Interface(device=str(device), name=str(name))
        for device, name in mapping.items()
        if not str(device).startswith("_") and not isinstance(name, (dict, list))
    ]
    interfaces.sort(key=lambda item: (item.name.lower(), item.device))
    return interfaces


class OpnSenseClient:
    def __init__(
        self,
        url: str,
        api_key: str,
        api_secret: str,
        *,
        tls_verify: TlsVerify = True,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._url,
            auth=(api_key, api_secret),
            verify=tls_verify,
            timeout=timeout,
            headers={"Accept": "application/json"},
            transport=transport,
        )

    @classmethod
    def from_config(cls, config: Config) -> OpnSenseClient:
        return cls(
            config.url,
            config.api_key,
            config.api_secret,
            tls_verify=config.tls_verify,
            timeout=config.timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OpnSenseClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _get_json(self, paths: tuple[str, ...]) -> Any:
        last_error: Exception | None = None
        for path in paths:
            try:
                response = self._client.get(path)
            except httpx.HTTPError as exc:
                last_error = exc
                log.warning("request failed %s: %s", path, exc)
                continue
            if response.status_code == 404 and path != paths[-1]:
                log.debug("endpoint %s not found, trying alias", path)
                continue
            if response.status_code == 403:
                raise OpnSenseError(
                    f"{path} returned 403; grant the API user Diagnostics: Firewall "
                    "(and Diagnostics: Interfaces if INCLUDE_INTERFACES=true). "
                    "Some OPNsense versions only expose list_rule_ids with All Pages."
                )
            if response.status_code >= 400:
                raise OpnSenseError(
                    f"{path} returned {response.status_code}: {response.text[:300]}"
                )
            try:
                return response.json()
            except ValueError as exc:
                raise OpnSenseError(f"{path} returned non-JSON") from exc
        raise OpnSenseError(f"request failed for {paths[0]}: {last_error}")

    def list_rules(self) -> list[Rule]:
        return normalize_rules(self._get_json(RULE_IDS_PATHS))

    def list_interfaces(self) -> list[Interface]:
        return normalize_interfaces(self._get_json(INTERFACE_PATHS))
