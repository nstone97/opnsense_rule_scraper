from __future__ import annotations

import csv
import io

from opnsense_rule_scraper.models import Interface, Rule
from opnsense_rule_scraper.writer import (
    atomic_write,
    interfaces_csv_text,
    rules_csv_text,
    rules_json_text,
)


def test_rules_csv_quotes_commas_and_quotes() -> None:
    csv_text = rules_csv_text(
        [
            Rule(rid="abc", descr='Allow LAN, "guest" to WAN'),
            Rule(rid="def", descr="plain"),
        ]
    )
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert rows[0] == {"rid": "abc", "descr": 'Allow LAN, "guest" to WAN'}
    assert rows[1] == {"rid": "def", "descr": "plain"}


def test_interfaces_csv() -> None:
    csv_text = interfaces_csv_text([Interface(device="igb0", name="WAN")])
    assert csv_text == "device,name\nigb0,WAN\n"


def test_rules_json_includes_count_and_interfaces() -> None:
    text = rules_json_text(
        [Rule(rid="abc", descr="LAN")],
        source="https://fw/api/diagnostics/firewall/list_rule_ids",
        interfaces=[Interface(device="igb0", name="WAN")],
    )
    assert '"count": 1' in text
    assert '"rid": "abc"' in text
    assert '"device": "igb0"' in text


def test_atomic_write_skips_unchanged(tmp_path) -> None:
    path = tmp_path / "opnsense_rules.csv"
    assert atomic_write(path, "rid,descr\n") is True
    assert atomic_write(path, "rid,descr\n") is False
    assert atomic_write(path, "rid,descr\nabc,LAN\n") is True
    assert path.read_text() == "rid,descr\nabc,LAN\n"
