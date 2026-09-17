from __future__ import annotations

import logging
import signal
import time
from datetime import datetime, timezone

from .client import OpnSenseClient, OpnSenseError
from .config import Config
from .metrics import ScrapeStats
from .models import Interface, Rule
from .server import start_server
from .writer import (
    atomic_write,
    interfaces_csv_text,
    rules_csv_text,
    rules_json_text,
)

log = logging.getLogger(__name__)


def scrape_once(config: Config, client: OpnSenseClient, stats: ScrapeStats) -> None:
    started = time.monotonic()
    try:
        rules = client.list_rules()
        interfaces: list[Interface] = []
        if config.include_interfaces:
            try:
                interfaces = client.list_interfaces()
            except OpnSenseError as exc:
                log.warning("interface scrape skipped: %s", exc)
        wrote_csv = write_outputs(config, rules, interfaces)
        stats.record_success(
            rules=len(rules),
            interfaces=len(interfaces),
            duration=time.monotonic() - started,
            wrote_csv=wrote_csv,
        )
        log.info(
            "scrape ok rules=%d interfaces=%d csv_changed=%s",
            len(rules),
            len(interfaces),
            wrote_csv,
        )
    except Exception as exc:
        stats.record_failure(str(exc), time.monotonic() - started)
        log.exception("scrape failed: %s", exc)
        raise


def write_outputs(
    config: Config,
    rules: list[Rule],
    interfaces: list[Interface],
) -> bool:
    csv_changed = atomic_write(config.rules_csv, rules_csv_text(rules))
    atomic_write(
        config.rules_json,
        rules_json_text(
            rules,
            source=f"{config.url}/api/diagnostics/firewall/list_rule_ids",
            fetched_at=datetime.now(timezone.utc),
            interfaces=interfaces or None,
        ),
    )
    if config.include_interfaces:
        atomic_write(config.interfaces_csv, interfaces_csv_text(interfaces))
    return csv_changed


def run(config: Config) -> int:
    stats = ScrapeStats()
    files = {
        "/rules.csv": config.rules_csv,
        "/rules.json": config.rules_json,
        "/interfaces.csv": config.interfaces_csv,
    }
    stop_http = None
    if not config.run_once:
        _, stop_http = start_server(config.http_host, config.http_port, stats, files)

    stop = False

    def _handle_stop(signum: int, _frame: object) -> None:
        nonlocal stop
        log.info("received signal %s, shutting down", signum)
        stop = True

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    with OpnSenseClient.from_config(config) as client:
        while not stop:
            try:
                scrape_once(config, client, stats)
            except Exception:
                if config.run_once:
                    return 1
            if config.run_once:
                return 0 if stats.snapshot()["healthy"] else 1
            deadline = time.monotonic() + config.scrape_interval
            while not stop and time.monotonic() < deadline:
                time.sleep(0.25)

    if stop_http is not None:
        stop_http()
    return 0
