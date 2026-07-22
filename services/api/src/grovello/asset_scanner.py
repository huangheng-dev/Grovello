from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class AssetScanResult:
    status: Literal["clean", "infected"]
    provider: str
    reference: str | None = None


@dataclass(frozen=True, slots=True)
class AssetScannerHealth:
    available: bool
    provider: str
    detail: str | None = None


class AssetScannerError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(f"Asset scan failed ({code})")
        self.code = code
        self.retryable = retryable


@runtime_checkable
class AssetScanner(Protocol):
    """Provider-neutral streaming malware scanner boundary."""

    async def health(self) -> AssetScannerHealth: ...

    async def scan(self, chunks: AsyncIterator[bytes]) -> AssetScanResult: ...
