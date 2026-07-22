from grovello.asset_scanner import AssetScanner
from grovello.clamav_scanner import ClamAVScanner, ClamAVScannerConfig
from grovello.config import Settings


def build_asset_scanner(settings: Settings) -> AssetScanner | None:
    if not settings.asset_scanner_configured:
        return None
    assert settings.asset_scanner_host is not None
    return ClamAVScanner(
        ClamAVScannerConfig(
            host=settings.asset_scanner_host,
            port=settings.asset_scanner_port,
            connect_timeout_seconds=settings.asset_scanner_connect_timeout_seconds,
            scan_timeout_seconds=settings.asset_scanner_timeout_seconds,
            max_stream_bytes=settings.asset_scanner_max_stream_bytes,
        )
    )
