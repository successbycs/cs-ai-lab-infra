"""Pure migration-ledger rules shared by local validation and the adapter contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


class ChecksumDriftError(ValueError):
    """Raised when an applied filename no longer has its recorded content."""


@dataclass(frozen=True)
class LedgerDecision:
    filename: str
    sha256: str
    action: str


def decide(existing: Mapping[str, str], *, filename: str, sha256: str) -> LedgerDecision:
    """Return apply/already-applied, or refuse mutation of historic content."""
    recorded = existing.get(filename)
    if recorded is None:
        return LedgerDecision(filename=filename, sha256=sha256, action="apply")
    if recorded == sha256:
        return LedgerDecision(filename=filename, sha256=sha256, action="already-applied")
    raise ChecksumDriftError(
        f"Refusing migration {filename}: recorded checksum differs from reviewed content."
    )
