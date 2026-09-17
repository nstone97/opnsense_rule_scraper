from __future__ import annotations

from pathlib import Path

import httpx

from opnsense_rule_scraper.app import scrape_once
from opnsense_rule_scraper.client import OpnSenseClient
from opnsense_rule_scraper.config import Config
from opnsense_rule_scraper.metrics import ScrapeStats


def _config(tmp_path: Path) -> Config:
    return Config(
        url="https://opnsense.example",
        api_key="key",
        api_secret="secret",
        tls_verify=False,
        timeout=5,
        scrape_interval=60,
        output_dir=tmp_path,
        http_host="127.0.0.1",
        http_port=0,
        include_interfaces=True,
        run_once=True,
    )


def test_scrape_once_writes_vector_csv(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "list_rule_ids" in request.url.path or "listRuleIds" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "fae559338f65e11c53669fc3642c93c2",
                            "descr": "Allow LAN to WAN",
                        }
                    ]
                },
            )
        if "interface" in request.url.path:
            return httpx.Response(200, json={"igb0": "WAN", "igb1": "LAN"})
        return httpx.Response(404)

    config = _config(tmp_path)
    client = OpnSenseClient(
        config.url,
        config.api_key,
        config.api_secret,
        tls_verify=False,
        transport=httpx.MockTransport(handler),
    )
    stats = ScrapeStats()
    scrape_once(config, client, stats)

    csv_text = (tmp_path / "opnsense_rules.csv").read_text()
    assert csv_text.startswith("rid,descr\n")
    assert "fae559338f65e11c53669fc3642c93c2,Allow LAN to WAN" in csv_text
    assert "igb1,LAN" in (tmp_path / "opnsense_interfaces.csv").read_text()
    snap = stats.snapshot()
    assert snap["healthy"] is True
    assert snap["rules"] == 1
    assert "opnsense_rule_scraper_up 1" in stats.prometheus()
