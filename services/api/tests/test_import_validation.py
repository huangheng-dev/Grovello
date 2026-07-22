import json
from uuid import UUID

import pytest

from grovello.import_validation import (
    CanonicalObjectSnapshot,
    FieldMapping,
    ImportLimits,
    ImportValidationError,
    parse_source,
    safe_preview,
    validate_mapping_definition,
    validate_rows,
)

LIMITS = ImportLimits(
    max_source_bytes=4096,
    max_rows=3,
    max_columns=10,
    max_scalar_bytes=128,
    max_json_depth=6,
)


def product_mappings() -> tuple[FieldMapping, ...]:
    return (
        FieldMapping("Name", "name", "trim"),
        FieldMapping("Slug", "slug", "lowercase"),
        FieldMapping("SKU", "payload.sku", "trim"),
    )


def test_csv_parser_and_validation_are_bounded_deterministic_and_exact() -> None:
    parsed = parse_source(
        b"Name,Slug,SKU\r\nAlpha,alpha,A-1\r\nAgain,alpha,A-1\r\nFormula,formula,=1+1\r\n",
        source_format="csv",
        delimiter=",",
        limits=LIMITS,
        object_type="product",
        locale="en",
        schema_version=1,
    )
    result = validate_rows(
        parsed,
        source_format="csv",
        declared_source_fields=("Name", "Slug", "SKU"),
        mappings=product_mappings(),
        object_type="product",
        locale="en",
        limits=LIMITS,
    )
    assert [row.status for row in result.rows] == ["valid", "duplicate", "valid"]
    assert result.rows[0].content_hash != result.rows[1].content_hash
    assert result.valid_rows == 2
    assert result.invalid_rows == 1
    assert safe_preview(result.rows[2].normalized_data)["payload"]["sku"] == "'=1+1"


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"Name,Name\na,b\n", "duplicate_header"),
        (b"Name\n\xff\n", "invalid_utf8"),
        (b"Name\na\nb\nc\nd\n", "too_many_rows"),
        (b"Name\n" + b"a" * 129 + b"\n", "scalar_too_large"),
    ],
)
def test_csv_parser_fails_closed_without_echoing_source(content: bytes, code: str) -> None:
    with pytest.raises(ImportValidationError) as caught:
        parse_source(
            content,
            source_format="csv",
            delimiter=",",
            limits=LIMITS,
            object_type="product",
            locale="en",
            schema_version=1,
        )
    assert caught.value.code == code
    assert "a" * 64 not in str(caught.value)


def test_grovello_json_manifest_and_duplicate_keys_are_enforced() -> None:
    package = {
        "manifest": {
            "schemaVersion": 1,
            "locale": "en",
            "objectType": "market",
            "recordCount": 1,
        },
        "records": [{"Name": "Germany", "meta": {"code": "DE"}}],
    }
    parsed = parse_source(
        json.dumps(package).encode(),
        source_format="grovello_json",
        delimiter=None,
        limits=LIMITS,
        object_type="market",
        locale="en",
        schema_version=1,
    )
    assert parsed.source_fields == ("Name", "meta.code")

    duplicate = (
        '{"manifest":{"schemaVersion":1,"locale":"en","objectType":"market",'
        '"recordCount":1},"records":[{"Name":"A","Name":"B"}]}'
    )
    with pytest.raises(ImportValidationError, match="unique") as caught:
        parse_source(
            duplicate.encode(),
            source_format="grovello_json",
            delimiter=None,
            limits=LIMITS,
            object_type="market",
            locale="en",
            schema_version=1,
        )
    assert caught.value.code == "duplicate_json_key"


def test_mapping_rejects_tenant_fields_and_arbitrary_transforms() -> None:
    with pytest.raises(ImportValidationError) as caught:
        validate_mapping_definition(
            ("Workspace",),
            (FieldMapping("Workspace", "workspaceId"),),
            LIMITS,
        )
    assert caught.value.code == "forbidden_target"

    with pytest.raises(ImportValidationError) as caught:
        validate_mapping_definition(
            ("Name",),
            (FieldMapping("Missing", "name"),),
            LIMITS,
        )
    assert caught.value.code == "unknown_mapping_source"


def test_exact_identity_and_stable_identifier_never_fuzzy_merge() -> None:
    canonical = CanonicalObjectSnapshot(
        object_id=UUID("11111111-1111-4111-8111-111111111111"),
        object_type="product",
        slug="existing-product",
        current_version_id=UUID("22222222-2222-4222-8222-222222222222"),
        payload={"sku": "SKU-1"},
    )
    parsed = parse_source(
        b"Name,Slug,SKU\nRenamed,new-slug,sku-1\nNear,existing-products,SKU-2\n",
        source_format="csv",
        delimiter=",",
        limits=LIMITS,
        object_type="product",
        locale="en",
        schema_version=1,
    )
    result = validate_rows(
        parsed,
        source_format="csv",
        declared_source_fields=("Name", "Slug", "SKU"),
        mappings=product_mappings(),
        object_type="product",
        locale="en",
        limits=LIMITS,
        canonical_objects=(canonical,),
    )
    assert result.rows[0].target_identity == {
        "matchKind": "stable_identifier",
        "objectId": str(canonical.object_id),
        "currentVersionId": str(canonical.current_version_id),
    }
    assert result.rows[0].status == "conflict"
    assert result.rows[1].target_identity == {"matchKind": "new"}


def test_issue_samples_are_redacted_and_cross_workspace_ids_fail_closed() -> None:
    mappings = (
        FieldMapping("Name", "name"),
        FieldMapping("Slug", "slug"),
        FieldMapping("Canonical", "canonicalId"),
    )
    parsed = parse_source(
        b"Name,Slug,Canonical\nPrivate,private,aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa\n",
        source_format="csv",
        delimiter=",",
        limits=LIMITS,
        object_type="product",
        locale="en",
        schema_version=1,
    )
    result = validate_rows(
        parsed,
        source_format="csv",
        declared_source_fields=("Name", "Slug", "Canonical"),
        mappings=mappings,
        object_type="product",
        locale="en",
        limits=LIMITS,
    )
    assert result.rows[0].status == "conflict"
    issue = result.rows[0].issues[0]
    assert issue.code == "identity_unavailable_id"
    assert "aaaaaaaa" not in issue.message
    assert issue.redacted_sample is None
    assert safe_preview({"api_token": "do-not-return"}) == {"api_token": "[redacted]"}
