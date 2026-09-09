#!/usr/bin/env python3
"""Deterministically normalize an approved CSV, JSON, or JSONL export.

Configuration is JSON.  It contains an ``adapter_contract`` object (or the
contract itself), ``field_mappings`` (canonical field -> source name or
``{source,type,values}``), and optional ``filters``.  Filters have ``field``,
``operator`` (equals, not_equals, in, not_in), ``value``/``values``, and are
exclusions.  This intentionally does not implement joins, eligibility, or
channel behaviour.
"""
from __future__ import annotations

import argparse, csv, datetime as dt, hashlib, json, math, os, shutil, sys, tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts" / "control") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "control"))
from runtime_validation import ValidationError, validate_document, strict_json_loads


class NormalizationError(ValueError): pass


def _json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")


def _load_json(path: Path) -> Any:
    try:
        return strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise NormalizationError("invalid-json") from exc


def _source_rows(path: Path, fmt: str) -> list[dict[str, Any]]:
    try:
        if fmt == "csv":
            with path.open("r", encoding="utf-8", newline="") as handle:
                return list(csv.DictReader(handle))
        raw = path.read_text(encoding="utf-8")
        if fmt == "json":
            value = strict_json_loads(raw)
            if not isinstance(value, list) or not all(isinstance(row, dict) for row in value): raise NormalizationError("invalid-input-rows")
            return value
        if fmt == "jsonl":
            rows = []
            for line in raw.splitlines():
                if line.strip():
                    value = strict_json_loads(line)
                    if not isinstance(value, dict): raise NormalizationError("invalid-input-row")
                    rows.append(value)
            return rows
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, NormalizationError): raise
        raise NormalizationError("invalid-input") from exc
    raise NormalizationError("unsupported-input-format")


def _parse(value: Any, kind: str | None) -> Any:
    if kind is None or kind == "string":
        if isinstance(value, (dict, list)) or value is None: raise NormalizationError("parse-failed")
        return str(value)
    if kind == "integer":
        if isinstance(value, bool): raise NormalizationError("parse-failed")
        parsed = int(str(value))
        if str(parsed) != str(value).strip() and not isinstance(value, int): raise NormalizationError("parse-failed")
        return parsed
    if kind == "number":
        if isinstance(value, bool): raise NormalizationError("parse-failed")
        parsed = float(value)
        if not math.isfinite(parsed): raise NormalizationError("parse-failed")
        return parsed
    if kind == "boolean":
        if isinstance(value, bool): return value
        if str(value).lower() in ("true", "1"): return True
        if str(value).lower() in ("false", "0"): return False
        raise NormalizationError("parse-failed")
    if kind == "date-time":
        text = str(value)
        try: parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc: raise NormalizationError("parse-failed") from exc
        if parsed.tzinfo is None: raise NormalizationError("parse-failed")
        return parsed.isoformat().replace("+00:00", "Z")
    raise NormalizationError("unsupported-type")


def _same_target(left: Path, right: Path) -> bool:
    if left.resolve() == right.resolve():
        return True
    try:
        return os.path.samefile(left, right)
    except OSError:
        return False


def _preflight_targets(input_path: Path, targets: list[Path]) -> None:
    if any(path.exists() and path.is_dir() for path in targets):
        raise NormalizationError("invalid-output-target")
    for index, path in enumerate(targets):
        if _same_target(input_path, path):
            raise NormalizationError("source-output-alias")
        if any(_same_target(path, other) for other in targets[:index]):
            raise NormalizationError("duplicate-output-target")
        if not path.parent.exists() or not path.parent.is_dir():
            raise NormalizationError("invalid-output-target")


def _commit_all(items: list[tuple[Path, bytes]]) -> None:
    """Replace a validated artifact set, restoring every prior file on failure."""
    staged: list[tuple[Path, Path]] = []
    backups: list[tuple[Path, Path | None]] = []
    try:
        for path, data in items:
            fd, temporary = tempfile.mkstemp(prefix=".normalize-", dir=str(path.parent))
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            staged.append((path, Path(temporary)))
        for path, _ in items:
            if path.exists():
                fd, backup = tempfile.mkstemp(prefix=".normalize-backup-", dir=str(path.parent))
                os.close(fd)
                shutil.copyfile(path, backup)
                backups.append((path, Path(backup)))
            else:
                backups.append((path, None))
        for path, temporary in staged:
            os.replace(temporary, path)
    except OSError as exc:
        # Backups are deliberately ordinary files so restoration uses the same
        # portable replacement primitive as commit.
        for path, backup in backups:
            try:
                if backup is None:
                    if path.exists():
                        path.unlink()
                else:
                    os.replace(backup, path)
            except OSError:
                pass
        raise NormalizationError("output-commit-failed") from exc
    finally:
        for _, temporary in staged:
            try: temporary.unlink()
            except OSError: pass
        for _, backup in backups:
            if backup is not None:
                try: backup.unlink()
                except OSError: pass


def _contract(config: dict[str, Any]) -> dict[str, Any]:
    candidate = config.get("adapter_contract", config)
    if not isinstance(candidate, dict): raise NormalizationError("invalid-configuration")
    try:
        validate_document(candidate, "adapter-contract.schema.json")
    except ValidationError as exc:
        raise NormalizationError("invalid-adapter-contract") from exc
    if candidate["read_write_behavior"] != "read-only": raise NormalizationError("unsupported-write-behavior")
    output = candidate["output_contract"]
    if output.get("format") not in ("json", "jsonl") or output.get("record_schema") not in {
        "schemas/canonical-behaviour.schema.json", "schemas/canonical-user.schema.json",
        "schemas/canonical-account.schema.json", "schemas/canonical-decision.schema.json",
        "schemas/canonical-audience.schema.json"} or not isinstance(output.get("canonical_path"), str):
        raise NormalizationError("invalid-output-contract")
    return candidate


def _matches(row: dict[str, Any], item: dict[str, Any]) -> bool:
    field, op = item.get("field"), item.get("operator")
    if not isinstance(field, str) or field not in row: raise NormalizationError("invalid-filter")
    values = item.get("values", [item.get("value")])
    if not isinstance(values, list) or op not in ("equals", "not_equals", "in", "not_in"): raise NormalizationError("invalid-filter")
    found = row[field] in values
    return found if op in ("equals", "in") else not found


def _canonical(record: dict[str, Any], schema: str) -> bool:
    try:
        validate_document(record, Path(schema).name)
        return True
    except ValidationError:
        return False


def normalize(input_path: Path, config: dict[str, Any], output_path: Path, manifest_path: Path,
              report_path: Path, unresolved_path: Path, rejected_path: Path) -> dict[str, Any]:
    targets = [output_path, manifest_path, report_path, unresolved_path, rejected_path]
    _preflight_targets(input_path, targets)
    contract = _contract(config); fmt = config.get("input_format")
    if fmt not in contract["input_contract"].get("formats", []): raise NormalizationError("invalid-input-format")
    mappings = config.get("field_mappings")
    if not isinstance(mappings, dict) or not mappings: raise NormalizationError("invalid-configuration")
    rows = _source_rows(input_path, fmt)
    fields = set().union(*(row.keys() for row in rows)) if rows else set()
    missing = sorted(set(contract["input_contract"].get("required_fields", [])) - fields)
    if missing: raise NormalizationError("missing-required-source-field:" + ",".join(missing))
    filters = config.get("filters", [])
    if not isinstance(filters, list) or not all(isinstance(item, dict) for item in filters): raise NormalizationError("invalid-filter")
    result, unresolved, rejected, excluded = [], [], [], 0
    dispositions = contract["failure_dispositions"]
    for index, row in enumerate(rows, 1):
        try:
            if any(_matches(row, item) for item in filters): excluded += 1; continue
            record: dict[str, Any] = {}
            for target, rule in mappings.items():
                rule = {"source": rule} if isinstance(rule, str) else rule
                if not isinstance(target, str) or not isinstance(rule, dict): raise NormalizationError("invalid-mapping")
                if "constant" in rule:
                    value = rule["constant"]
                elif "fields" in rule:
                    if not isinstance(rule["fields"], dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in rule["fields"].items()): raise NormalizationError("invalid-mapping")
                    if any(row.get(source) in (None, "") for source in rule["fields"].values()): raise NormalizationError("missing-value")
                    value = {name: row[source] for name, source in rule["fields"].items()}
                else:
                    source = rule.get("source")
                    if not isinstance(source, str): raise NormalizationError("invalid-mapping")
                    value = row.get(source)
                    if value is None or value == "": raise NormalizationError("missing-value:" + source)
                    value = _parse(value, rule.get("type"))
                if "values" in rule:
                    if not isinstance(rule["values"], dict) or str(value) not in rule["values"]: raise NormalizationError("unmapped-enum:" + str(value))
                    value = rule["values"][str(value)]
                record[target] = value
            # Canonical records must not gain arbitrary source fields; source_trace
            # is declarative just like every other mapped field.
            if not _canonical(record, contract["output_contract"]["record_schema"]): raise NormalizationError("canonical-validation-failed")
            result.append(record)
        except NormalizationError as exc:
            code = str(exc).split(":", 1)[0]
            if code == "canonical-validation-failed":
                # A declaration/mapping that cannot emit its declared schema is
                # invalid configuration, not a row-level permissive outcome.
                raise NormalizationError("invalid-canonical-record") from exc
            disposition_key = "unmapped_enum" if code == "unmapped-enum" else ("missing" if code == "missing-value" else "malformed")
            disposition = dispositions.get(disposition_key)
            if disposition == "fail":
                raise NormalizationError("declared-failure-disposition:" + disposition_key) from exc
            target = unresolved if disposition == "unresolved" else rejected
            detail = str(exc).split(":", 1)[1] if ":" in str(exc) else None
            target.append({"input_row": index, "reason_code": code, "trace_evidence": {"input_row": index}, "observed_value": detail if code == "unmapped-enum" else None})
    # Sort by canonical JSON so output is independent of input permutation.
    result.sort(key=lambda row: _json(row))
    unresolved.sort(key=lambda row: row["input_row"]); rejected.sort(key=lambda row: row["input_row"])
    if len(result) + len(unresolved) + len(rejected) + excluded != len(rows): raise NormalizationError("row-reconciliation-failed")
    output = b"".join(_json(row) for row in result) if contract["output_contract"]["format"] == "jsonl" else _json(result)
    unresolved_data, rejected_data = b"".join(_json(row) for row in unresolved), b"".join(_json(row) for row in rejected)
    input_bytes = input_path.read_bytes()
    report = {"schema_version":"1.0", "status":"completed", "input_rows":len(rows), "output_rows":len(result), "unresolved_rows":len(unresolved), "rejected_rows":len(rejected), "aggregate_excluded_rows":excluded, "unmapped_enum_counts":{}}
    for record in unresolved + rejected:
        if record["reason_code"] == "unmapped-enum":
            value = record["observed_value"]
            report["unmapped_enum_counts"][value] = report["unmapped_enum_counts"].get(value, 0) + 1
    report_data = _json(report)
    manifest = {"schema_version":"1.0", "adapter_id":contract["adapter_id"], "adapter_version":contract["adapter_version"], "input_path":input_path.name, "input_hash":"sha256:"+hashlib.sha256(input_bytes).hexdigest(), "input_rows":len(rows), "output_path":output_path.name, "output_hash":"sha256:"+hashlib.sha256(output).hexdigest(), "output_rows":len(result), "validation_report_path":report_path.name, "unresolved_path":unresolved_path.name if unresolved else None, "unresolved_rows":len(unresolved), "read_write_behavior":"read-only", "rejected_path":rejected_path.name if rejected else None, "rejected_rows":len(rejected), "aggregate_excluded_rows":excluded, "aggregate_exclusion_reason":"configured-filter" if excluded else None, "activation_receipt":None}
    try:
        validate_document(manifest, "adapter-result.schema.json")
    except ValidationError as exc:
        raise NormalizationError("invalid-result-manifest") from exc
    # All validation and bytes are prepared before any target replacement.
    _commit_all([(output_path, output), (manifest_path, _json(manifest)), (report_path, report_data), (unresolved_path, unresolved_data), (rejected_path, rejected_data)])
    return {"status":"completed", "output_rows":len(result), "unresolved_rows":len(unresolved), "rejected_rows":len(rejected), "excluded_rows":excluded}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path); parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path); parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path); parser.add_argument("--unresolved", required=True, type=Path); parser.add_argument("--rejected", required=True, type=Path)
    args = parser.parse_args()
    try: outcome = normalize(args.input, _load_json(args.config), args.output, args.manifest, args.report, args.unresolved, args.rejected)
    except (NormalizationError, OSError) as exc: outcome = {"status":"rejected", "diagnostic":str(exc)}
    print(json.dumps(outcome, sort_keys=True)); return 0 if outcome["status"] == "completed" else 2


if __name__ == "__main__": raise SystemExit(main())
