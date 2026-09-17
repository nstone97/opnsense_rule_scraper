from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    """One live pf rule label from OPNsense.

    `rid` is the hex label in filterlog field 4 (0-indexed field 3).
    It is the stable join key for logs. The pf `@N` rule number in
    filterlog field 1 changes whenever the ruleset is rebuilt.
    """

    rid: str
    descr: str


@dataclass(frozen=True)
class Interface:
    """Physical device name as it appears in filterlog, plus GUI name."""

    device: str
    name: str
