import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal
from uuid import UUID

from grovello.business_truth import (
    STRUCTURED_PAYLOAD_RULES,
    InvalidBusinessTruthPayloadError,
    validate_business_truth_payload,
)

PARSER_VERSION = "grovello-import-parser-v1"
FORMULA_PREFIXES = ("=", "+", "-", "@")
SENSITIVE_PARTS = ("password", "secret", "token", "credential", "api_key", "private_key")
TARGET_PATTERN = re.compile(
    r"^(?:canonicalId|slug|name|status|locale|citations|payload\.[A-Za-z0-9][A-Za-z0-9_-]*(?:\.[A-Za-z0-9][A-Za-z0-9_-]*)*)$"
)
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REFERENCE_TYPES = {
    "marketId": "market",
    "productId": "product",
    "offerId": "offer",
    "icpId": "icp",
}


class ImportValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ImportLimits:
    max_source_bytes: int
    max_rows: int
    max_columns: int
    max_scalar_bytes: int
    max_json_depth: int


@dataclass(frozen=True, slots=True)
class ParsedSource:
    source_fields: tuple[str, ...]
    records: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class FieldMapping:
    source: str | None
    target: str
    transform: Literal[
        "identity", "trim", "lowercase", "uppercase", "integer", "decimal", "boolean", "json", "split"
    ] = "identity"
    default_value: Any = None
    has_default: bool = False
    separator: str = ","


@dataclass(frozen=True, slots=True)
class CanonicalObjectSnapshot:
    object_id: UUID
    object_type: str
    slug: str
    current_version_id: UUID
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ImportIssueDraft:
    source_row_number: int | None
    code: str
    severity: Literal["warning", "error", "blocking"]
    field_locator: dict[str, str]
    message: str
    redacted_sample: str | None = None


@dataclass(frozen=True, slots=True)
class StagedImportRow:
    source_row_number: int
    content_hash: str
    normalized_data: dict[str, Any]
    target_identity: dict[str, Any]
    status: Literal["valid", "invalid", "duplicate", "conflict"]
    issues: tuple[ImportIssueDraft, ...]


@dataclass(frozen=True, slots=True)
class ValidationResult:
    rows: tuple[StagedImportRow, ...]
    schema_fingerprint: str

    @property
    def valid_rows(self) -> int:
        return sum(row.status == "valid" for row in self.rows)

    @property
    def invalid_rows(self) -> int:
        return len(self.rows) - self.valid_rows


def parse_source(
    content: bytes,
    *,
    source_format: str,
    delimiter: str | None,
    limits: ImportLimits,
    object_type: str,
    locale: str,
    schema_version: int,
) -> ParsedSource:
    if len(content) > limits.max_source_bytes:
        raise ImportValidationError("source_too_large", "Import source exceeds the configured byte limit")
    if b"\x00" in content:
        raise ImportValidationError("invalid_control_character", "Import source contains a NUL byte")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ImportValidationError("invalid_utf8", "Import source must be valid UTF-8") from error
    if source_format == "csv":
        return _parse_csv(text, delimiter, limits)
    if source_format == "grovello_json":
        return _parse_json(text, limits, object_type, locale, schema_version)
    raise ImportValidationError("unsupported_source_format", "Import source format is unsupported")


def schema_fingerprint(source_format: str, fields: tuple[str, ...]) -> str:
    canonical_fields = tuple(sorted(fields)) if source_format == "grovello_json" else fields
    canonical = json.dumps(
        {"sourceFormat": source_format, "fields": list(canonical_fields)},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_rows(
    parsed: ParsedSource,
    *,
    source_format: str,
    declared_source_fields: tuple[str, ...],
    mappings: tuple[FieldMapping, ...],
    object_type: str,
    locale: str,
    limits: ImportLimits,
    canonical_objects: tuple[CanonicalObjectSnapshot, ...] = (),
    evidence_version_ids: frozenset[UUID] = frozenset(),
) -> ValidationResult:
    _validate_mapping(declared_source_fields, mappings, limits)
    expected = declared_source_fields if source_format == "csv" else tuple(sorted(declared_source_fields))
    actual = parsed.source_fields if source_format == "csv" else tuple(sorted(parsed.source_fields))
    if actual != expected:
        raise ImportValidationError(
            "source_schema_mismatch",
            "Verified source fields do not match the immutable mapping schema",
        )

    by_id = {str(item.object_id): item for item in canonical_objects}
    by_slug = {(item.object_type, item.slug): item for item in canonical_objects}
    stable = _stable_index(canonical_objects)
    seen: set[tuple[str, str]] = set()
    rows: list[StagedImportRow] = []
    for number, source_record in enumerate(parsed.records, start=1):
        issues: list[ImportIssueDraft] = []
        normalized: dict[str, Any] = {
            "status": "draft",
            "locale": locale,
            "payload": {},
            "citations": [],
        }
        if shape_error := source_record.get("__grovello_shape_error__"):
            issues.append(_issue(number, shape_error, "record", "Source record shape is invalid"))
        for mapping in mappings:
            raw = _select(source_record, mapping.source) if mapping.source else None
            if _is_empty(raw) and mapping.has_default:
                raw = mapping.default_value
            try:
                value = _transform(raw, mapping, limits)
                _assign(normalized, mapping.target, value)
            except ImportValidationError as error:
                issues.append(
                    _issue(
                        number,
                        error.code,
                        mapping.target,
                        str(error),
                        _redacted_sample(raw),
                    )
                )

        issues.extend(
            _validate_normalized(
                number,
                normalized,
                object_type,
                by_id,
                evidence_version_ids,
            )
        )
        identity, identity_issues = _resolve_identity(number, normalized, object_type, by_id, by_slug, stable)
        issues.extend(identity_issues)
        has_error = any(issue.severity in {"error", "blocking"} for issue in issues)
        status: Literal["valid", "invalid", "duplicate", "conflict"]
        if any(issue.code.startswith("identity_") for issue in issues):
            status = "conflict"
        elif has_error:
            status = "invalid"
        else:
            identity_key = (
                ("object", identity["objectId"])
                if identity.get("objectId")
                else ("slug", f"{object_type}:{normalized.get('slug', '')}")
            )
            if identity_key in seen:
                status = "duplicate"
                issues.append(
                    _issue(
                        number,
                        "duplicate_source_identity",
                        "slug",
                        "Another source row already resolved to the same exact identity",
                        severity="warning",
                    )
                )
            else:
                seen.add(identity_key)
                status = "valid"
        canonical = _canonical_json(normalized)
        rows.append(
            StagedImportRow(
                source_row_number=number,
                content_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                normalized_data=normalized,
                target_identity=identity,
                status=status,
                issues=tuple(issues),
            )
        )
    return ValidationResult(
        rows=tuple(rows),
        schema_fingerprint=schema_fingerprint(source_format, parsed.source_fields),
    )


def validate_mapping_definition(
    source_fields: tuple[str, ...], mappings: tuple[FieldMapping, ...], limits: ImportLimits
) -> None:
    _validate_mapping(source_fields, mappings, limits)


def safe_preview(value: Any, *, max_string: int = 200) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "[redacted]"
                if any(part in key.casefold() for part in SENSITIVE_PARTS)
                else safe_preview(item, max_string=max_string)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [safe_preview(item, max_string=max_string) for item in value[:50]]
    if isinstance(value, str):
        bounded = value[:max_string]
        return f"'{bounded}" if bounded.startswith(FORMULA_PREFIXES) else bounded
    return value


def _parse_csv(text: str, delimiter: str | None, limits: ImportLimits) -> ParsedSource:
    if delimiter not in {",", ";", "\t", "|"}:
        raise ImportValidationError(
            "invalid_delimiter", "CSV delimiter must be comma, semicolon, tab, or pipe"
        )
    try:
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
        headers = next(reader)
    except StopIteration as error:
        raise ImportValidationError("missing_header", "CSV source must contain a header row") from error
    except csv.Error as error:
        raise ImportValidationError("invalid_csv", "CSV source is malformed") from error
    if not headers or any(not header.strip() for header in headers):
        raise ImportValidationError("invalid_header", "CSV headers must be non-empty")
    if len(headers) > limits.max_columns:
        raise ImportValidationError("too_many_columns", "CSV source exceeds the configured column limit")
    headers = [header.strip() for header in headers]
    if any(any(ord(character) < 32 for character in header) for header in headers):
        raise ImportValidationError("invalid_header", "CSV headers cannot contain control characters")
    if len(set(headers)) != len(headers):
        raise ImportValidationError("duplicate_header", "CSV headers must be unique")
    _check_fields(headers, limits)

    records: list[dict[str, Any]] = []
    try:
        for row in reader:
            if not row or (len(row) == 1 and not row[0]):
                continue
            if len(records) >= limits.max_rows:
                raise ImportValidationError("too_many_rows", "Import source exceeds the configured row limit")
            _check_fields(row, limits)
            record = {
                header: row[index] if index < len(row) else None for index, header in enumerate(headers)
            }
            if len(row) != len(headers):
                record["__grovello_shape_error__"] = "row_column_count_mismatch"
            records.append(record)
    except csv.Error as error:
        raise ImportValidationError("invalid_csv", "CSV source is malformed") from error
    return ParsedSource(tuple(headers), tuple(records))


def _parse_json(
    text: str,
    limits: ImportLimits,
    object_type: str,
    locale: str,
    schema_version: int,
) -> ParsedSource:
    try:
        package = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except ImportValidationError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        raise ImportValidationError("invalid_json", "Grovello JSON source is malformed") from error
    _check_json_value(package, limits, depth=1)
    if not isinstance(package, dict) or set(package) != {"manifest", "records"}:
        raise ImportValidationError(
            "invalid_json_package", "Grovello JSON requires only manifest and records at the root"
        )
    manifest = package["manifest"]
    records = package["records"]
    if not isinstance(manifest, dict) or not isinstance(records, list):
        raise ImportValidationError("invalid_json_package", "Grovello JSON manifest or records is invalid")
    expected_manifest = {
        "schemaVersion": schema_version,
        "locale": locale,
        "objectType": object_type,
        "recordCount": len(records),
    }
    if any(manifest.get(key) != value for key, value in expected_manifest.items()):
        raise ImportValidationError(
            "manifest_mismatch", "Grovello JSON manifest does not match the authorized import job"
        )
    if len(records) > limits.max_rows:
        raise ImportValidationError("too_many_rows", "Import source exceeds the configured row limit")
    if not all(isinstance(record, dict) for record in records):
        raise ImportValidationError("invalid_record", "Every Grovello JSON record must be an object")
    fields: set[str] = set()
    for record in records:
        fields.update(_leaf_paths(record))
    if len(fields) > limits.max_columns:
        raise ImportValidationError("too_many_columns", "JSON source exceeds the configured field limit")
    return ParsedSource(tuple(sorted(fields)), tuple(records))


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if any(ord(character) < 32 for character in key):
            raise ImportValidationError(
                "invalid_json_key", "Grovello JSON keys cannot contain control characters"
            )
        if key in result:
            raise ImportValidationError("duplicate_json_key", "Grovello JSON keys must be unique")
        if key.startswith("__grovello"):
            raise ImportValidationError("reserved_json_key", "Grovello JSON contains a reserved key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ImportValidationError("invalid_json_number", "JSON source contains a non-finite number")


def _check_json_value(value: Any, limits: ImportLimits, *, depth: int) -> None:
    if depth > limits.max_json_depth:
        raise ImportValidationError("json_too_deep", "JSON source exceeds the configured nesting limit")
    if isinstance(value, dict):
        if len(value) > limits.max_columns:
            raise ImportValidationError("too_many_columns", "JSON object exceeds the field limit")
        for key, item in value.items():
            _check_scalar(key, limits)
            _check_json_value(item, limits, depth=depth + 1)
    elif isinstance(value, list):
        if len(value) > limits.max_rows:
            raise ImportValidationError("json_array_too_large", "JSON array exceeds the item limit")
        for item in value:
            _check_json_value(item, limits, depth=depth + 1)
    elif isinstance(value, str):
        _check_scalar(value, limits)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        _check_scalar(str(value), limits)


def _leaf_paths(value: dict[str, Any], prefix: str = "") -> set[str]:
    result: set[str] = set()
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            result.update(_leaf_paths(item, path))
        else:
            result.add(path)
    return result


def _validate_mapping(
    source_fields: tuple[str, ...], mappings: tuple[FieldMapping, ...], limits: ImportLimits
) -> None:
    if not source_fields or len(source_fields) > limits.max_columns:
        raise ImportValidationError("invalid_mapping_schema", "Mapping source field count is invalid")
    if len(set(source_fields)) != len(source_fields):
        raise ImportValidationError("duplicate_mapping_field", "Mapping source fields must be unique")
    for source_field in source_fields:
        _check_scalar(source_field, limits)
        if any(ord(character) < 32 for character in source_field):
            raise ImportValidationError(
                "invalid_mapping_field", "Mapping source fields cannot contain control characters"
            )
    if not mappings or len(mappings) > limits.max_columns:
        raise ImportValidationError("invalid_mapping", "Mapping field count is invalid")
    targets: set[str] = set()
    for mapping in mappings:
        if not TARGET_PATTERN.fullmatch(mapping.target):
            raise ImportValidationError("forbidden_target", "Mapping target is not importable")
        if mapping.target in targets:
            raise ImportValidationError("duplicate_target", "Mapping targets must be unique")
        if mapping.source is None and not mapping.has_default:
            raise ImportValidationError("missing_mapping_source", "A mapping needs a source or default")
        if mapping.source is not None and mapping.source not in source_fields:
            raise ImportValidationError("unknown_mapping_source", "Mapping source is not declared")
        if mapping.transform == "split" and not mapping.separator:
            raise ImportValidationError("invalid_separator", "Split separator cannot be empty")
        if mapping.has_default:
            _check_json_value(mapping.default_value, limits, depth=1)
        targets.add(mapping.target)


def _select(record: dict[str, Any], selector: str | None) -> Any:
    if selector is None:
        return None
    current: Any = record
    for part in selector.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _transform(value: Any, mapping: FieldMapping, limits: ImportLimits) -> Any:
    if value is None:
        return None
    transform = mapping.transform
    if transform == "identity":
        result = value
    elif transform in {"trim", "lowercase", "uppercase"}:
        if not isinstance(value, str):
            raise ImportValidationError("invalid_text", "Text transform requires a string value")
        result = value.strip()
        if transform == "lowercase":
            result = result.casefold()
        elif transform == "uppercase":
            result = result.upper()
    elif transform == "integer":
        try:
            result = int(str(value).strip())
        except ValueError as error:
            raise ImportValidationError("invalid_integer", "Value is not a valid integer") from error
    elif transform == "decimal":
        try:
            result = format(Decimal(str(value).strip()), "f")
        except InvalidOperation as error:
            raise ImportValidationError("invalid_decimal", "Value is not a valid decimal") from error
    elif transform == "boolean":
        normalized = str(value).strip().casefold()
        if normalized not in {"true", "false", "1", "0", "yes", "no"}:
            raise ImportValidationError("invalid_boolean", "Value is not a valid boolean")
        result = normalized in {"true", "1", "yes"}
    elif transform == "json":
        if not isinstance(value, str):
            result = value
        else:
            try:
                result = json.loads(
                    value,
                    object_pairs_hook=_unique_object,
                    parse_constant=_reject_json_constant,
                )
            except (json.JSONDecodeError, ImportValidationError, ValueError) as error:
                raise ImportValidationError("invalid_embedded_json", "Value is not valid JSON") from error
        _check_json_value(result, limits, depth=1)
    elif transform == "split":
        if not isinstance(value, str):
            raise ImportValidationError("invalid_list", "Split transform requires a string value")
        result = [part.strip() for part in value.split(mapping.separator) if part.strip()]
    else:
        raise ImportValidationError("unsupported_transform", "Mapping transform is unsupported")
    _check_json_value(result, limits, depth=1)
    return result


def _assign(target: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = target
    for part in parts[:-1]:
        child = current.setdefault(part, {})
        if not isinstance(child, dict):
            raise ImportValidationError("target_path_conflict", "Mapping target paths conflict")
        current = child
    current[parts[-1]] = value


def _validate_normalized(
    number: int,
    normalized: dict[str, Any],
    object_type: str,
    by_id: dict[str, CanonicalObjectSnapshot],
    evidence_version_ids: frozenset[UUID],
) -> list[ImportIssueDraft]:
    issues: list[ImportIssueDraft] = []
    name = normalized.get("name")
    slug = normalized.get("slug")
    status = normalized.get("status")
    locale = normalized.get("locale")
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        issues.append(_issue(number, "invalid_name", "name", "Name must contain 1 to 200 characters"))
    if not isinstance(slug, str) or not 2 <= len(slug) <= 120 or not SLUG_PATTERN.fullmatch(slug):
        issues.append(_issue(number, "invalid_slug", "slug", "Slug must use lowercase kebab-case"))
    if status not in {"draft", "active", "archived"}:
        issues.append(_issue(number, "invalid_status", "status", "Status is invalid"))
    if locale not in {"en", "zh-CN"}:
        issues.append(_issue(number, "invalid_locale", "locale", "Locale is invalid"))
    payload = normalized.get("payload")
    citations = normalized.get("citations")
    if not isinstance(payload, dict):
        issues.append(_issue(number, "invalid_payload", "payload", "Payload must be an object"))
        payload = {}
    if not isinstance(citations, list):
        issues.append(_issue(number, "invalid_citations", "citations", "Citations must be a list"))
        citations = []
    else:
        for index, citation in enumerate(citations):
            locator = f"citations.{index}"
            if not isinstance(citation, dict):
                issues.append(_issue(number, "invalid_citation", locator, "Citation must be an object"))
                continue
            try:
                evidence_id = UUID(str(citation.get("evidenceVersionId")))
            except (TypeError, ValueError, AttributeError):
                issues.append(
                    _issue(
                        number,
                        "invalid_evidence_version",
                        locator,
                        "Citation requires an evidence version UUID",
                    )
                )
                continue
            if evidence_id not in evidence_version_ids:
                issues.append(
                    _issue(
                        number,
                        "missing_evidence_version",
                        locator,
                        "Evidence version is unavailable in this workspace",
                    )
                )
            if not isinstance(citation.get("claimText"), str) or not citation["claimText"].strip():
                issues.append(_issue(number, "invalid_claim", locator, "Citation claim text is required"))

    for field in STRUCTURED_PAYLOAD_RULES.get(object_type, {}).get("references", ()):
        value = payload.get(field)
        if value is None:
            continue
        snapshot = by_id.get(str(value))
        if snapshot is None or snapshot.object_type != REFERENCE_TYPES.get(field):
            issues.append(
                _issue(
                    number,
                    "invalid_reference",
                    f"payload.{field}",
                    "Canonical reference is unavailable or has the wrong type",
                )
            )
    if not issues:
        try:
            validate_business_truth_payload(
                object_type,
                payload,
                status=status,
                citation_count=len(citations),
            )
        except InvalidBusinessTruthPayloadError as error:
            issues.append(_issue(number, "invalid_business_payload", "payload", str(error)))
    return issues


def _resolve_identity(
    number: int,
    normalized: dict[str, Any],
    object_type: str,
    by_id: dict[str, CanonicalObjectSnapshot],
    by_slug: dict[tuple[str, str], CanonicalObjectSnapshot],
    stable: dict[tuple[str, str], list[CanonicalObjectSnapshot]],
) -> tuple[dict[str, Any], list[ImportIssueDraft]]:
    canonical_id = normalized.get("canonicalId")
    if canonical_id:
        try:
            canonical_uuid = UUID(str(canonical_id))
        except (ValueError, TypeError, AttributeError):
            return {}, [_issue(number, "identity_invalid_id", "canonicalId", "Canonical ID is invalid")]
        item = by_id.get(str(canonical_uuid))
        if item is None or item.object_type != object_type:
            return {}, [
                _issue(
                    number,
                    "identity_unavailable_id",
                    "canonicalId",
                    "Canonical ID is unavailable in this workspace or has the wrong type",
                )
            ]
        if normalized.get("slug") != item.slug:
            return _identity(item, "canonical_id"), [
                _issue(
                    number,
                    "identity_disagreement",
                    "slug",
                    "Canonical ID and slug do not resolve to the same exact identity",
                )
            ]
        return _identity(item, "canonical_id"), []

    slug = normalized.get("slug")
    if isinstance(slug, str) and (item := by_slug.get((object_type, slug))):
        stable_value = _row_stable_identity(object_type, normalized.get("payload", {}))
        stable_matches = stable.get((object_type, stable_value), []) if stable_value else []
        if stable_matches and any(match.object_id != item.object_id for match in stable_matches):
            return _identity(item, "slug"), [
                _issue(
                    number,
                    "identity_disagreement",
                    "payload",
                    "Slug and stable identifier do not resolve to the same exact identity",
                )
            ]
        return _identity(item, "slug"), []

    stable_value = _row_stable_identity(object_type, normalized.get("payload", {}))
    if stable_value:
        matches = stable.get((object_type, stable_value), [])
        if len(matches) == 1:
            if slug != matches[0].slug:
                return _identity(matches[0], "stable_identifier"), [
                    _issue(
                        number,
                        "identity_disagreement",
                        "slug",
                        "Stable identifier matches an object with a different canonical slug",
                    )
                ]
            return _identity(matches[0], "stable_identifier"), []
        if len(matches) > 1:
            return {}, [
                _issue(
                    number,
                    "identity_ambiguous",
                    "payload",
                    "Stable identifier matches multiple canonical objects",
                )
            ]
    return {"matchKind": "new"}, []


def _identity(item: CanonicalObjectSnapshot, kind: str) -> dict[str, Any]:
    return {
        "matchKind": kind,
        "objectId": str(item.object_id),
        "currentVersionId": str(item.current_version_id),
    }


def _stable_index(
    items: tuple[CanonicalObjectSnapshot, ...],
) -> dict[tuple[str, str], list[CanonicalObjectSnapshot]]:
    result: dict[tuple[str, str], list[CanonicalObjectSnapshot]] = {}
    for item in items:
        value = _row_stable_identity(item.object_type, item.payload)
        if value:
            result.setdefault((item.object_type, value), []).append(item)
    return result


def _row_stable_identity(object_type: str, payload: dict[str, Any]) -> str | None:
    field = {"product": "sku", "market": "countryCode"}.get(object_type)
    value = payload.get(field) if field and isinstance(payload, dict) else None
    return str(value).strip().casefold() if value is not None and str(value).strip() else None


def _issue(
    row: int | None,
    code: str,
    field: str,
    message: str,
    sample: str | None = None,
    *,
    severity: Literal["warning", "error", "blocking"] = "error",
) -> ImportIssueDraft:
    return ImportIssueDraft(row, code, severity, {"field": field}, message[:500], sample)


def _redacted_sample(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return f"[redacted text: {len(value)} characters]"
    return f"[redacted {type(value).__name__}]"


def _check_fields(values: list[str], limits: ImportLimits) -> None:
    for value in values:
        _check_scalar(value, limits)


def _check_scalar(value: str, limits: ImportLimits) -> None:
    if len(value.encode("utf-8")) > limits.max_scalar_bytes:
        raise ImportValidationError("scalar_too_large", "A scalar value exceeds the configured byte limit")


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
