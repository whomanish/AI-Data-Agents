"""Small, dependency-free validation helpers for the portable control runtime."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas"
SYNTHETIC_PROVENANCE = re.compile(
    r"(?i)(?:^|[^a-z0-9])(?:synthetic|fixture|blind|test|testing)(?:$|[^a-z0-9])"
)
# Deliberately bounded durable-data scanner; it does not claim exhaustive PII detection.
SENSITIVE_KEY = re.compile(r"(?i)(?:credential|secret|password|api[_-]?key|access[_-]?token|refresh[_-]?token|recipient|recipient[_-]?row|production[_-]?row)")
DURABLE_SENSITIVE_VALUE = re.compile(r"(?i)(?:\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|\b(?:sk|pk|api)[_-][A-Za-z0-9_-]{12,}\b|\b(?:bearer|password)\s+[A-Za-z0-9._~+/=-]{8,}\b|\b(?:gh[pousr]|github_pat|glpat|xox[baprs]|AKIA)[_-][A-Za-z0-9_-]{12,}\b|\b(?:npm_|pypi-)[A-Za-z0-9_-]{12,}\b|\b\+?[0-9]{1,3}[ .()-][0-9 .()-]{6,}[0-9]\b)")


class ValidationError(ValueError):
    def __init__(self, code: str, location: str = "$") -> None:
        self.code, self.location = code, location
        super().__init__(f"{code} at {location}")


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def strict_json_loads(text: str) -> Any:
    return json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_reject_duplicate_keys)


def read_json(path: Path) -> Any:
    try:
        return strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValidationError("invalid-json", str(path)) from exc


def contains_durable_sensitive_data(value: Any) -> bool:
    if isinstance(value, str): return bool(DURABLE_SENSITIVE_VALUE.search(value))
    if isinstance(value, dict): return any(SENSITIVE_KEY.search(str(key)) or DURABLE_SENSITIVE_VALUE.search(str(key)) or contains_durable_sensitive_data(item) for key, item in value.items())
    if isinstance(value, list): return any(contains_durable_sensitive_data(item) for item in value)
    return False


def ensure_finite_numbers(value: Any, location: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value): raise ValidationError("non-finite-number", location)
    if isinstance(value, dict):
        for key, item in value.items(): ensure_finite_numbers(item, f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value): ensure_finite_numbers(item, f"{location}[{index}]")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def inventory_hash(entries: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for item in sorted(entries, key=lambda entry: entry["path"].encode("utf-8")):
        digest.update(item["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(item["sha256"].encode("ascii"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def identity_collision_scope_definition_hash(definition: dict[str, Any]) -> str:
    """Hash the immutable collision-scope semantics, excluding evidence metadata."""
    digest = hashlib.sha256()
    digest.update(definition["id"].encode("utf-8"))
    digest.update(b"\0")
    digest.update(definition["identity_namespace"].encode("utf-8"))
    digest.update(b"\0")
    for dimension in sorted(definition["collision_dimensions"], key=lambda item: item.encode("utf-8")):
        digest.update(dimension.encode("utf-8"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def _type_matches(value: Any, expected: str) -> bool:
    types = {"object": dict, "array": list, "string": str, "boolean": bool,
             "null": type(None), "number": (int, float), "integer": int}
    kind = types[expected]
    return isinstance(value, kind) and not (expected in {"number", "integer"} and isinstance(value, bool))


def _date_time(value: str) -> bool:
    # JSON Schema's date-time format is RFC 3339: a calendar date alone or a
    # timezone-less local time is not a date-time value.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value) is None:
        return False
    try:
        _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def validate_schema(value: Any, schema: dict[str, Any], location: str = "$") -> None:
    ensure_finite_numbers(value, location)
    if "const" in schema and value != schema["const"]:
        raise ValidationError("schema-const", location)
    if "enum" in schema and value not in schema["enum"]:
        raise ValidationError("schema-enum", location)
    expected = schema.get("type")
    if expected is not None:
        expected_types = expected if isinstance(expected, list) else [expected]
        if not any(_type_matches(value, item) for item in expected_types):
            raise ValidationError("schema-type", location)
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise ValidationError("schema-min-length", location)
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            raise ValidationError("schema-pattern", location)
        if schema.get("format") == "date-time" and not _date_time(value):
            raise ValidationError("schema-date-time", location)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ValidationError("schema-minimum", location)
        if "maximum" in schema and value > schema["maximum"]:
            raise ValidationError("schema-maximum", location)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", len(value)):
            raise ValidationError("schema-item-count", location)
        if schema.get("uniqueItems"):
            enc = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in value]
            if len(enc) != len(set(enc)):
                raise ValidationError("schema-unique-items", location)
        if "items" in schema:
            for index, item in enumerate(value):
                validate_schema(item, schema["items"], f"{location}[{index}]")
        if "contains" in schema:
            count = sum(_matches(item, schema["contains"]) for item in value)
            if count < schema.get("minContains", 1) or count > schema.get("maxContains", len(value)):
                raise ValidationError("schema-contains", location)
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise ValidationError("schema-required", f"{location}.{key}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = set(value) - set(properties)
            if extras:
                raise ValidationError("schema-additional-property", f"{location}.{sorted(extras)[0]}")
        for key, item in value.items():
            if key in properties:
                validate_schema(item, properties[key], f"{location}.{key}")
            elif isinstance(schema.get("additionalProperties"), dict):
                validate_schema(item, schema["additionalProperties"], f"{location}.{key}")
            if "propertyNames" in schema:
                validate_schema(key, schema["propertyNames"], f"{location}.{key}")
    if "oneOf" in schema:
        if sum(_matches(value, candidate) for candidate in schema["oneOf"]) != 1:
            raise ValidationError("schema-one-of", location)
    if "not" in schema and _matches(value, schema["not"]):
        raise ValidationError("schema-not", location)
    for condition in schema.get("allOf", []):
        if "if" in condition and _matches(value, condition["if"]):
            validate_schema(value, condition.get("then", {}), location)
        elif "if" in condition and "else" in condition:
            validate_schema(value, condition["else"], location)
        else:
            validate_schema(value, condition, location)


def _matches(value: Any, schema: dict[str, Any]) -> bool:
    try:
        validate_schema(value, schema)
        return True
    except ValidationError:
        return False


def validate_document(document: Any, schema_name: str) -> None:
    validate_schema(document, read_json(SCHEMAS / schema_name))
    semantic_validate(document, schema_name)


def semantic_validate(document: dict[str, Any], schema_name: str) -> None:
    if schema_name == "identity-collision-scopes.schema.json":
        ids = [item["id"] for item in document["definitions"]]
        if len(ids) != len(set(ids)):
            raise ValidationError("duplicate-identity-collision-scope-id", "$.definitions")
        for index, definition in enumerate(document["definitions"]):
            if definition["definition_hash"] != identity_collision_scope_definition_hash(definition):
                raise ValidationError("identity-collision-scope-hash-mismatch",
                                      f"$.definitions[{index}].definition_hash")
            for field, value in definition["provenance"].items():
                if isinstance(value, str) and SYNTHETIC_PROVENANCE.search(value):
                    raise ValidationError("identity-collision-scope-synthetic-provenance",
                                          f"$.definitions[{index}].provenance.{field}")
    elif schema_name == "profile-index.schema.json":
        ids = [item["profile_id"] for item in document["profiles"]]
        if len(ids) != len(set(ids)): raise ValidationError("duplicate-profile-id", "$.profiles")
    elif schema_name == "runtime-capabilities.schema.json":
        keys = [(item["connector_id"], item["operation"]) for item in document["connector_operations"]]
        if len(keys) != len(set(keys)): raise ValidationError("duplicate-connector-operation", "$.connector_operations")
    elif schema_name == "execution-profile.schema.json":
        if any(item["minimum"] > item["maximum"] for item in document["operating_ranges"].values()):
            raise ValidationError("inverted-operating-range", "$.operating_ranges")
        dependencies = {item["capability_id"] for item in document["capability_dependencies"]}
        checked = {item["capability_id"] for item in document["quick_checks"]}
        if dependencies - checked: raise ValidationError("capability-missing-quick-check", "$.quick_checks")
    elif schema_name == "adapter-result.schema.json":
        fields = ("output_rows", "unresolved_rows", "rejected_rows", "aggregate_excluded_rows")
        if document["input_rows"] != sum(document[field] for field in fields):
            raise ValidationError("adapter-row-count-mismatch")
    elif schema_name == "funnel.schema.json":
        if document["input_count"] != document["unique_trace_count"] + document["duplicate_count"]:
            raise ValidationError("funnel-count-mismatch", "$.input_count")
        if document["unique_trace_count"] != sum(document["dispositions"].values()):
            raise ValidationError("funnel-count-mismatch", "$.dispositions")
    elif schema_name == "channel-output-contract.schema.json":
        row_schema = document["row_schema"]
        fields = row_schema["fields"]
        names = [field["name"] for field in fields]
        declared_names = set(names)
        if len(names) != len(declared_names):
            raise ValidationError("duplicate-channel-output-field-name", "$.row_schema.fields")

        field_order = row_schema["field_order"]
        if len(field_order) != len(set(field_order)):
            raise ValidationError("duplicate-channel-output-field-order", "$.row_schema.field_order")
        for index, name in enumerate(field_order):
            if name not in declared_names:
                raise ValidationError("extra-channel-output-field-order-entry",
                                      f"$.row_schema.field_order[{index}]")
        if set(field_order) != declared_names:
            raise ValidationError("incomplete-channel-output-field-order", "$.row_schema.field_order")

        target_name = document["target_identifier_field"]
        trace_name = document["trace_key_field"]
        if target_name not in declared_names:
            raise ValidationError("missing-target-identifier-field", "$.target_identifier_field")
        if trace_name not in declared_names:
            raise ValidationError("missing-trace-key-field", "$.trace_key_field")

        target_fields = [field for field in fields if field["role"] == "target_identifier"]
        trace_fields = [field for field in fields if field["role"] == "trace_key"]
        if len(target_fields) != 1:
            raise ValidationError("invalid-target-identifier-role-count", "$.row_schema.fields")
        if len(trace_fields) != 1:
            raise ValidationError("invalid-trace-key-role-count", "$.row_schema.fields")
        if target_fields[0]["name"] != target_name:
            raise ValidationError("target-identifier-field-role-mismatch", "$.target_identifier_field")
        if trace_fields[0]["name"] != trace_name:
            raise ValidationError("trace-key-field-role-mismatch", "$.trace_key_field")
        for index, field in enumerate(fields):
            if field["role"] in {"target_identifier", "trace_key"} and not field["required"]:
                raise ValidationError("channel-output-role-field-not-required",
                                      f"$.row_schema.fields[{index}].required")
    elif schema_name == "overlay-export.schema.json":
        entries = document["files"]; paths = [entry["path"] for entry in entries]
        if len(paths) != len(set(paths)) or paths.count("overlay.json") != 1:
            raise ValidationError("duplicate-export-path", "$.files")
        overlay = next(entry for entry in entries if entry["path"] == "overlay.json")
        if document["inventory_hash"] != inventory_hash(entries) or document["overlay_manifest_hash"] != overlay["sha256"]:
            raise ValidationError("export-inventory-hash-mismatch")


def write_json_atomic(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)
