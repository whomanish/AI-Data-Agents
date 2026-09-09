#!/usr/bin/env python3
"""Assign canonical records to a deterministic percentage holdout.

Only the configured canonical identity, salt, percentage, and SHA-256
algorithm affect assignment.  This helper deliberately does not implement
eligibility, channels, funnels, or campaign policy.
"""
from __future__ import annotations

import argparse, hashlib, json, math, os, tempfile
from pathlib import Path
from typing import Any
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "control"))
from runtime_validation import strict_json_loads


class HoldoutError(ValueError):
    pass


def _json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _load(path: Path) -> Any:
    try:
        return strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HoldoutError("invalid-json") from exc


def _rows(path: Path, fmt: str) -> list[dict[str, Any]]:
    try:
        if fmt == "json":
            value = _load(path)
            if not isinstance(value, list) or not all(isinstance(x, dict) for x in value):
                raise HoldoutError("invalid-input-rows")
            return value
        if fmt == "jsonl":
            result = []
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    value = strict_json_loads(line)
                    if not isinstance(value, dict): raise HoldoutError("invalid-input-row")
                    result.append(value)
            return result
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, HoldoutError): raise
        raise HoldoutError("invalid-input") from exc
    raise HoldoutError("invalid-input-format")


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".holdout-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle: handle.write(data)
        os.replace(temporary, path)
    except OSError:
        try: os.unlink(temporary)
        except OSError: pass
        raise


def _aliases(left: Path, right: Path) -> bool:
    if left.resolve() == right.resolve():
        return True
    try:
        return os.path.samefile(left, right)
    except OSError:
        return False


def assign(input_path: Path, config: dict[str, Any], output_path: Path) -> dict[str, Any]:
    if not isinstance(config, dict): raise HoldoutError("invalid-configuration")
    required = {"input_format", "identity_field", "salt", "holdout_percentage", "algorithm", "output_format"}
    if set(config) != required: raise HoldoutError("invalid-configuration")
    if _aliases(input_path, output_path): raise HoldoutError("source-output-alias")
    if output_path.exists() and output_path.is_dir(): raise HoldoutError("invalid-output-target")
    if not output_path.parent.exists() or not output_path.parent.is_dir(): raise HoldoutError("invalid-output-target")
    fmt = config["input_format"]
    if fmt not in ("json", "jsonl"): raise HoldoutError("invalid-input-format")
    field = config["identity_field"]
    salt = config["salt"]
    percentage = config["holdout_percentage"]
    algorithm = config["algorithm"]
    output_format = config["output_format"]
    if not isinstance(field, str) or not field or not isinstance(salt, str) or not salt:
        raise HoldoutError("invalid-configuration")
    if algorithm != "sha256" or output_format not in ("json", "jsonl") or isinstance(percentage, bool) or not isinstance(percentage, (int, float)):
        raise HoldoutError("invalid-configuration")
    if not math.isfinite(float(percentage)) or percentage < 0 or percentage > 100: raise HoldoutError("invalid-percentage")
    rows = _rows(input_path, fmt)
    identities = []
    for row in rows:
        identity = row.get(field)
        if not isinstance(identity, str) or not identity: raise HoldoutError("invalid-identity")
        identities.append(identity)
    if len(set(identities)) != len(identities): raise HoldoutError("duplicate-identity")
    # Integer basis points avoid floating point and interpreter differences.
    threshold = int(round(float(percentage) * 100))
    result = []
    for row, identity in zip(rows, identities):
        digest = hashlib.sha256((salt + "\x00" + identity).encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:8], "big") % 10000
        assigned = bucket < threshold
        copy = dict(row)
        copy["holdout_assignment"] = {
            "assigned": assigned, "bucket": bucket, "percentage": percentage,
            "algorithm": algorithm,
        }
        result.append(copy)
    result.sort(key=lambda row: (row[field], _json(row)))
    data = _json(result) if output_format == "json" else b"".join(_json(row) for row in result)
    _atomic(output_path, data)
    return {"status": "assigned", "input_rows": len(rows), "holdout_rows": sum(x["holdout_assignment"]["assigned"] for x in result)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path); parser.add_argument("--config", required=True, type=Path); parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try: outcome = assign(args.input, _load(args.config), args.output)
    except (HoldoutError, OSError) as exc: outcome = {"status": "rejected", "diagnostic": str(exc)}
    print(json.dumps(outcome, sort_keys=True)); return 0 if outcome["status"] == "assigned" else 2


if __name__ == "__main__": raise SystemExit(main())
