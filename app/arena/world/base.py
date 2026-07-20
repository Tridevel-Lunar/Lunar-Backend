"""MissionWorld protocol and shared run helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class WorldError(Exception):
    """Hard stop during a domain op (maps to RunResult error)."""

    def __init__(self, code: str, message_th: str, block_id: str | None = None) -> None:
        super().__init__(message_th)
        self.code = code
        self.message_th = message_th
        self.block_id = block_id


class MissionWorld(ABC):
    @abstractmethod
    def apply(self, op: str, args: dict[str, Any] | None, block_id: str | None) -> Any:
        """Apply a domain op; may return a value for expression ops."""

    @abstractmethod
    def tick(self) -> None:
        """Advance discrete simulation one tick (power drain, etc.)."""

    @abstractmethod
    def snapshot(self) -> dict[str, Any]:
        """Public world state for finalWorld / frames."""

    @abstractmethod
    def grade(self, success_rules: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
        """Return (passedChecks, failedChecks)."""

    @abstractmethod
    def metrics(self) -> dict[str, Any]:
        """Summary metrics for the feedback window."""
