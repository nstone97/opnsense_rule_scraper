from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class ScrapeStats:
    lock: threading.Lock = field(default_factory=threading.Lock)
    rules: int = 0
    interfaces: int = 0
    last_success: float = 0.0
    last_error: str = ""
    last_duration: float = 0.0
    scrapes_ok: int = 0
    scrapes_failed: int = 0
    csv_writes: int = 0
    healthy: bool = False

    def record_success(
        self,
        *,
        rules: int,
        interfaces: int,
        duration: float,
        wrote_csv: bool,
    ) -> None:
        with self.lock:
            self.rules = rules
            self.interfaces = interfaces
            self.last_success = time.time()
            self.last_error = ""
            self.last_duration = duration
            self.scrapes_ok += 1
            if wrote_csv:
                self.csv_writes += 1
            self.healthy = True

    def record_failure(self, error: str, duration: float) -> None:
        with self.lock:
            self.last_error = error
            self.last_duration = duration
            self.scrapes_failed += 1
            self.healthy = False

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            return {
                "healthy": self.healthy,
                "rules": self.rules,
                "interfaces": self.interfaces,
                "last_success": self.last_success,
                "last_error": self.last_error,
                "last_duration": self.last_duration,
                "scrapes_ok": self.scrapes_ok,
                "scrapes_failed": self.scrapes_failed,
                "csv_writes": self.csv_writes,
            }

    def prometheus(self) -> str:
        snap = self.snapshot()
        last_error = str(snap["last_error"]).replace("\\", "\\\\").replace("\n", " ").replace('"', '\\"')
        lines = [
            "# HELP opnsense_rule_scraper_up 1 if the last scrape succeeded",
            "# TYPE opnsense_rule_scraper_up gauge",
            f"opnsense_rule_scraper_up {1 if snap['healthy'] else 0}",
            "# HELP opnsense_rule_scraper_rules Firewall rules in the last successful scrape",
            "# TYPE opnsense_rule_scraper_rules gauge",
            f"opnsense_rule_scraper_rules {snap['rules']}",
            "# HELP opnsense_rule_scraper_interfaces Interfaces in the last successful scrape",
            "# TYPE opnsense_rule_scraper_interfaces gauge",
            f"opnsense_rule_scraper_interfaces {snap['interfaces']}",
            "# HELP opnsense_rule_scraper_last_success_timestamp_seconds Unix time of last successful scrape",
            "# TYPE opnsense_rule_scraper_last_success_timestamp_seconds gauge",
            f"opnsense_rule_scraper_last_success_timestamp_seconds {snap['last_success']:.3f}",
            "# HELP opnsense_rule_scraper_scrape_duration_seconds Duration of the last scrape",
            "# TYPE opnsense_rule_scraper_scrape_duration_seconds gauge",
            f"opnsense_rule_scraper_scrape_duration_seconds {snap['last_duration']:.6f}",
            "# HELP opnsense_rule_scraper_scrapes_total Completed scrapes by result",
            "# TYPE opnsense_rule_scraper_scrapes_total counter",
            f'opnsense_rule_scraper_scrapes_total{{result="ok"}} {snap["scrapes_ok"]}',
            f'opnsense_rule_scraper_scrapes_total{{result="error"}} {snap["scrapes_failed"]}',
            "# HELP opnsense_rule_scraper_csv_writes_total Times the Vector CSV actually changed",
            "# TYPE opnsense_rule_scraper_csv_writes_total counter",
            f"opnsense_rule_scraper_csv_writes_total {snap['csv_writes']}",
            "# HELP opnsense_rule_scraper_last_error Last scrape error, empty when healthy",
            "# TYPE opnsense_rule_scraper_last_error gauge",
            f'opnsense_rule_scraper_last_error{{error="{last_error}"}} {0 if snap["healthy"] else 1}',
            "",
        ]
        return "\n".join(lines)
