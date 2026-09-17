from __future__ import annotations

import json
import urllib.error
import urllib.request

from opnsense_rule_scraper.metrics import ScrapeStats
from opnsense_rule_scraper.server import start_server


def test_health_and_metrics(tmp_path) -> None:
    stats = ScrapeStats()
    csv_path = tmp_path / "opnsense_rules.csv"
    csv_path.write_text("rid,descr\nabc,LAN\n", encoding="utf-8")
    server, stop = start_server(
        "127.0.0.1",
        0,
        stats,
        {"/rules.csv": csv_path},
    )
    port = server.server_address[1]
    try:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health")
            raise AssertionError("expected 503 before the first successful scrape")
        except urllib.error.HTTPError as exc:
            assert exc.code == 503
            body = json.loads(exc.read().decode())
            assert body["healthy"] is False

        stats.record_success(rules=1, interfaces=0, duration=0.01, wrote_csv=True)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as response:
            payload = json.loads(response.read().decode())
            assert payload["healthy"] is True
            assert payload["rules"] == 1

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics") as response:
            assert b"opnsense_rule_scraper_up 1" in response.read()

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/rules.csv") as response:
            assert b"abc,LAN" in response.read()
    finally:
        stop()
