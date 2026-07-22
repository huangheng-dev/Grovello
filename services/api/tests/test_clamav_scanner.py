import asyncio
import struct

import pytest

from grovello.asset_scanner import AssetScannerError
from grovello.clamav_scanner import ClamAVScanner, ClamAVScannerConfig


async def chunks(content: bytes):
    yield content[:4]
    yield content[4:]


async def scanner_server(response: bytes):
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        command = await reader.readuntil(b"\0")
        if command == b"zINSTREAM\0":
            while True:
                size = struct.unpack(">I", await reader.readexactly(4))[0]
                if size == 0:
                    break
                await reader.readexactly(size)
        writer.write(response + b"\0")
        await writer.drain()
        writer.close()

    return await asyncio.start_server(handle, "127.0.0.1", 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "status", "reference"),
    [
        (b"stream: OK", "clean", None),
        (b"stream: Eicar-Signature FOUND", "infected", "Eicar-Signature"),
    ],
)
async def test_clamav_instream_classifies_clean_and_infected(response, status, reference) -> None:
    server = await scanner_server(response)
    try:
        port = server.sockets[0].getsockname()[1]
        result = await ClamAVScanner(ClamAVScannerConfig("127.0.0.1", port)).scan(
            chunks(b"test content")
        )
    finally:
        server.close()
        await server.wait_closed()
    assert result.status == status
    assert result.reference == reference


@pytest.mark.asyncio
async def test_clamav_health_and_protocol_failure_are_fail_closed() -> None:
    server = await scanner_server(b"PONG")
    try:
        port = server.sockets[0].getsockname()[1]
        scanner = ClamAVScanner(ClamAVScannerConfig("127.0.0.1", port))
        assert (await scanner.health()).available is True
    finally:
        server.close()
        await server.wait_closed()

    server = await scanner_server(b"stream: unknown ERROR")
    try:
        port = server.sockets[0].getsockname()[1]
        with pytest.raises(AssetScannerError) as error:
            await ClamAVScanner(ClamAVScannerConfig("127.0.0.1", port)).scan(chunks(b"x"))
    finally:
        server.close()
        await server.wait_closed()
    assert error.value.retryable is False


@pytest.mark.asyncio
async def test_clamav_stream_limit_is_enforced_before_unbounded_send() -> None:
    server = await scanner_server(b"stream: OK")
    try:
        port = server.sockets[0].getsockname()[1]
        scanner = ClamAVScanner(ClamAVScannerConfig("127.0.0.1", port, max_stream_bytes=3))
        with pytest.raises(AssetScannerError, match="stream_limit_exceeded") as error:
            await scanner.scan(chunks(b"four"))
    finally:
        server.close()
        await server.wait_closed()
    assert error.value.retryable is False
