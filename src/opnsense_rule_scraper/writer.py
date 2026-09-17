from __future__ import annotations

import csv
import io
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .models import Interface, Rule

log = logging.getLogger(__name__)

RULE_FIELDS = ("rid", "descr")
INTERFACE_FIELDS = ("device", "name")


def rules_csv_text(rules: list[Rule]) -> str:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(RULE_FIELDS), lineterminator="\n")
    writer.writeheader()
    for rule in rules:
        writer.writerow({"rid": rule.rid, "descr": rule.descr})
    return buf.getvalue()


def interfaces_csv_text(interfaces: list[Interface]) -> str:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(INTERFACE_FIELDS), lineterminator="\n")
    writer.writeheader()
    for iface in interfaces:
        writer.writerow({"device": iface.device, "name": iface.name})
    return buf.getvalue()


def rules_json_text(
    rules: list[Rule],
    *,
    source: str,
    fetched_at: datetime | None = None,
    interfaces: list[Interface] | None = None,
) -> str:
    stamp = (fetched_at or datetime.now(timezone.utc)).isoformat()
    payload: dict[str, object] = {
        "fetched_at": stamp,
        "source": source,
        "count": len(rules),
        "rules": [{"rid": rule.rid, "descr": rule.descr} for rule in rules],
    }
    if interfaces is not None:
        payload["interfaces"] = [
            {"device": iface.device, "name": iface.name} for iface in interfaces
        ]
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def atomic_write(path: Path, content: str) -> bool:
    """Write `content` to `path` if it changed. Returns True when the file was written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    log.info("wrote %s (%d bytes)", path, len(content.encode("utf-8")))
    return True
