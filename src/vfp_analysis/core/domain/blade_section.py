from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BladeSection:
    """Radial section of the fan blade (root, mid-span, tip)."""

    name: str
    reynolds: float


