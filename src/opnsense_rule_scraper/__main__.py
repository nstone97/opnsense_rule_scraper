from __future__ import annotations

import argparse
import logging

from .app import run
from .config import Config


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape OPNsense firewall rule labels into Vector enrichment files"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="scrape once and exit (default is to poll forever)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="logging level (default: INFO)",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = Config.from_env(run_once=args.once)
    return run(config)


if __name__ == "__main__":
    raise SystemExit(main())
