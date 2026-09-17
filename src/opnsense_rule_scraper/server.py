from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from .metrics import ScrapeStats

log = logging.getLogger(__name__)


def _read(path: Path) -> tuple[bytes, str] | None:
    if not path.exists():
        return None
    suffix = path.suffix.lower()
    content_type = {
        ".csv": "text/csv; charset=utf-8",
        ".json": "application/json; charset=utf-8",
    }.get(suffix, "application/octet-stream")
    return path.read_bytes(), content_type


def make_handler(
    stats: ScrapeStats,
    files: dict[str, Path],
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            log.debug("http " + format, *args)

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path.rstrip("/") or "/"
            if path == "/health":
                snap = stats.snapshot()
                payload = json.dumps(snap).encode("utf-8")
                self._send(200 if snap["healthy"] else 503, payload, "application/json")
                return
            if path == "/metrics":
                self._send(200, stats.prometheus().encode("utf-8"), "text/plain; version=0.0.4")
                return
            if path in files:
                data = _read(files[path])
                if data is None:
                    self._send(404, b"not ready\n", "text/plain; charset=utf-8")
                    return
                body, content_type = data
                self._send(200, body, content_type)
                return
            self._send(404, b"not found\n", "text/plain; charset=utf-8")

    return Handler


def start_server(
    host: str,
    port: int,
    stats: ScrapeStats,
    files: dict[str, Path],
) -> tuple[ThreadingHTTPServer, Callable[[], None]]:
    server = ThreadingHTTPServer((host, port), make_handler(stats, files))
    thread = threading.Thread(target=server.serve_forever, name="http", daemon=True)
    thread.start()
    log.info("http listening on %s:%s", host, port)

    def stop() -> None:
        server.shutdown()
        thread.join(timeout=5)

    return server, stop
