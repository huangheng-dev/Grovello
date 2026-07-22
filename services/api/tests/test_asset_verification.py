import pytest

from grovello.asset_uploads import AssetVerificationInput
from grovello.asset_verification_activity import verification_failure

SHA256 = "a" * 64
PAYLOAD = AssetVerificationInput(
    workspace_id="00000000-0000-4000-8000-000000000001",
    upload_session_id="11111111-1111-4111-8111-111111111111",
    object_key="workspaces/one/staging/session/object",
    expected_content_type="application/pdf",
    expected_content_length=128,
    expected_sha256=SHA256,
)


@pytest.mark.parametrize(
    ("size", "content_type", "metadata_hash", "content_hash", "expected"),
    [
        (127, "application/pdf", SHA256, SHA256, "content_length_mismatch"),
        (128, "image/png", SHA256, SHA256, "content_type_mismatch"),
        (128, "application/pdf", "b" * 64, SHA256, "declared_checksum_metadata_mismatch"),
        (128, "application/pdf", SHA256, "b" * 64, "content_checksum_mismatch"),
        (128, "application/pdf", SHA256, SHA256, None),
    ],
)
def test_verification_fails_closed_for_every_declared_constraint(
    size: int,
    content_type: str,
    metadata_hash: str,
    content_hash: str,
    expected: str | None,
) -> None:
    assert verification_failure(PAYLOAD, size, content_type, metadata_hash, content_hash) == expected
