from __future__ import annotations

import httpx
import pytest

from opnsense_rule_scraper.client import (
    OpnSenseClient,
    OpnSenseError,
    normalize_interfaces,
    normalize_rules,
)


def test_normalize_rules_wrapped_items() -> None:
    rules = normalize_rules(
        {
            "items": [
                {"id": "aaa111bbb222ccc333ddd444eee555ff", "descr": "Allow LAN to WAN"},
                {"id": "bbb111bbb222ccc333ddd444eee555ff", "descr": "Block bogons"},
            ]
        }
    )
    assert [rule.rid for rule in rules] == [
        "aaa111bbb222ccc333ddd444eee555ff",
        "bbb111bbb222ccc333ddd444eee555ff",
    ]
    assert rules[0].descr == "Allow LAN to WAN"


def test_normalize_rules_bare_list_and_aliases() -> None:
    rules = normalize_rules(
        [
            {"rid": "abc", "description": "First"},
            {"uuid": "abc", "descr": "duplicate rid ignored"},
            {"id": "def", "descr": "Second"},
        ]
    )
    assert [(rule.rid, rule.descr) for rule in rules] == [
        ("abc", "First"),
        ("def", "Second"),
    ]


def test_normalize_rules_rejects_unknown_payload() -> None:
    with pytest.raises(OpnSenseError):
        normalize_rules("nope")


def test_normalize_interfaces() -> None:
    interfaces = normalize_interfaces({"igb0": "WAN", "igb1": "LAN", "_meta": {}})
    assert [(iface.device, iface.name) for iface in interfaces] == [
        ("igb1", "LAN"),
        ("igb0", "WAN"),
    ]


def test_list_rules_uses_snake_case_then_falls_back() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("list_rule_ids"):
            return httpx.Response(404, json={"errorMessage": "Endpoint not found"})
        if request.url.path.endswith("listRuleIds"):
            return httpx.Response(
                200,
                json={"items": [{"id": "deadbeefdeadbeefdeadbeefdeadbeef", "descr": "LAN"}]},
            )
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    client = OpnSenseClient(
        "https://opnsense.example",
        "key",
        "secret",
        transport=transport,
    )
    rules = client.list_rules()
    assert rules[0].descr == "LAN"


def test_list_rules_403_explains_acl() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Forbidden")

    client = OpnSenseClient(
        "https://opnsense.example",
        "key",
        "secret",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(OpnSenseError, match="403"):
        client.list_rules()
