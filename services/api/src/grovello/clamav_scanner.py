import asyncio
import re
import struct
from collections.abc import AsyncIterator
from dataclasses import dataclass

from grovello.asset_scanner import (
    AssetScannerError,
    AssetScannerHealth,
    AssetScanResult,
)


@dataclass(frozen=True, slots=True)
class ClamAVScannerConfig:
    host: str
    port: int = 3310
    connect_timeout_seconds: float = 5.0
    scan_timeout_seconds: float = 120.0
    max_stream_bytes: int = 104_857_600

    def __post_init__(self) -> None:
        if not self.host:
            raise ValueError("ClamAV host is required")
        if not 1 <= self.port <= 65535:
            raise ValueError("ClamAV port is invalid")
        if self.connect_timeout_seconds <= 0 or self.scan_timeout_seconds <= 0:
            raise ValueError("ClamAV timeouts must be positive")
        if self.max_stream_bytes <= 0:
            raise ValueError("ClamAV stream limit must be positive")


class ClamAVScanner:
    def __init__(self, config: ClamAVScannerConfig) -> None:
        self._config = config

    async def health(self) -> AssetScannerHealth:
        try:
            response = await self._exchange(b"zPING\0", send_stream=None)
        except AssetScannerError as error:
            return AssetScannerHealth(
                available=False,
                provider="clamav",
                detail=f"{error.code};retryable={str(error.retryable).lower()}",
            )
        return AssetScannerHealth(
            available=response.rstrip(b"\0\n") == b"PONG",
            provider="clamav",
            detail=None if response.rstrip(b"\0\n") == b"PONG" else "unexpected_response",
        )

    async def scan(self, chunks: AsyncIterator[bytes]) -> AssetScanResult:
        response = await self._exchange(b"zINSTREAM\0", send_stream=chunks)
        text = response.rstrip(b"\0\n").decode("utf-8", errors="replace")
        if text.endswith(": OK"):
            return AssetScanResult(status="clean", provider="clamav")
        if text.endswith(" FOUND") and ": " in text:
            signature = text.rsplit(": ", 1)[1][:-6]
            reference = re.sub(r"[^A-Za-z0-9._:+ -]", "_", signature)[:500]
            return AssetScanResult(status="infected", provider="clamav", reference=reference)
        if text.endswith(" size limit exceeded. ERROR"):
            raise AssetScannerError("stream_limit_exceeded", retryable=False)
        raise AssetScannerError("protocol_error", retryable=False)

    async def _exchange(
        self,
        command: bytes,
        *,
        send_stream: AsyncIterator[bytes] | None,
    ) -> bytes:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._config.host, self._config.port),
                timeout=self._config.connect_timeout_seconds,
            )
            try:
                writer.write(command)
                sent = 0
                if send_stream is not None:
                    async for chunk in send_stream:
                        sent += len(chunk)
                        if sent > self._config.max_stream_bytes:
                            raise AssetScannerError("stream_limit_exceeded", retryable=False)
                        writer.write(struct.pack(">I", len(chunk)))
                        writer.write(chunk)
                        await asyncio.wait_for(
                            writer.drain(), timeout=self._config.scan_timeout_seconds
                        )
                    writer.write(struct.pack(">I", 0))
                await asyncio.wait_for(writer.drain(), timeout=self._config.scan_timeout_seconds)
                return await asyncio.wait_for(
                    reader.readuntil(b"\0"), timeout=self._config.scan_timeout_seconds
                )
            finally:
                writer.close()
                await writer.wait_closed()
        except AssetScannerError:
            raise
        except TimeoutError as error:
            raise AssetScannerError("timeout", retryable=True) from error
        except (ConnectionError, OSError, asyncio.IncompleteReadError) as error:
            raise AssetScannerError("unavailable", retryable=True) from error
        except asyncio.LimitOverrunError as error:
            raise AssetScannerError("protocol_error", retryable=False) from error
