#!/usr/bin/env python3
"""Replace an overlay's bounded, non-PII health summary after validation."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from runtime_validation import (ValidationError, read_json, validate_document,
                                contains_durable_sensitive_data, ensure_finite_numbers)
from validate_state import _no_durable_sensitive_data, validate_overlay_state

_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")


def _result(status: str, **values: Any) -> dict[str, Any]: return {"status": status, **values}


def _time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str): return None
    try: value = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError: return None
    return value if value.tzinfo else None


def _contains_non_finite_number(value: Any) -> bool:
    try: ensure_finite_numbers(value)
    except ValidationError: return True
    return False


def _contains_sensitive_health_text(value: Any) -> bool:
    """Scan every user-supplied health value and map label before persistence."""
    return contains_durable_sensitive_data(value)


def _read_strict_json(path: Path) -> Any:
    try:
        return read_json(path)
    except ValidationError:
        raise


def _safe_health(health: Any) -> str | None:
    if _contains_non_finite_number(health): return "health-non-finite-number"
    try: validate_document(health, "health.schema.json")
    except ValidationError as exc: return exc.code
    if _contains_sensitive_health_text(health): return "health-sensitive-value"
    try: _no_durable_sensitive_data(health, "$.health")
    except ValidationError as exc: return exc.code
    # Schema permits arbitrary operation names.  Health writers intentionally
    # accept only identifier-like operation labels, never free-form row text.
    for item in health["connector_operations"]:
        if not _IDENTIFIER.fullmatch(item["operation"]): return "health-sensitive-value"
    return None


def record_run_health(overlay: Path, health: Any) -> dict[str, Any]:
    """Atomically replace health only after source and staged state validate."""
    try: snapshot = validate_overlay_state(overlay)
    except ValidationError as exc: return _result("rejected", diagnostic=exc.code)
    if _contains_non_finite_number(snapshot["health"]):
        return _result("rejected", diagnostic="health-non-finite-number")
    problem = _safe_health(health)
    if problem: return _result("rejected", diagnostic=problem)
    old, latest = snapshot["health"], _time(health["latest_successful_run_at"])
    old_latest = _time(old["latest_successful_run_at"])
    updated, old_updated = _time(health["updated_at"]), _time(old["updated_at"])
    if updated is None or old_updated is None or updated < old_updated: return _result("rejected", diagnostic="health-updated-at-regression")
    if old_latest is not None and (latest is None or latest < old_latest): return _result("rejected", diagnostic="health-latest-success-regression")
    state = Path(snapshot["manifest"]["paths"]["state"]); target = overlay / state / "health.json"
    stage = Path(tempfile.mkdtemp(prefix="health-stage-", dir=overlay.parent))
    try:
        staged = stage / "overlay"; shutil.copytree(overlay, staged)
        candidate = staged / state / "health.json"
        candidate.write_text(json.dumps(health, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        validate_overlay_state(staged)
        temporary = target.with_name(target.name + ".new")
        temporary.write_bytes(candidate.read_bytes())
        os.replace(temporary, target)
        return _result("recorded", updated_at=health["updated_at"], latest_successful_run_at=health["latest_successful_run_at"])
    except (OSError, ValidationError) as exc:
        return _result("rejected", diagnostic=getattr(exc, "code", "atomic-replace-failed"))
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        (target.with_name(target.name + ".new")).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument("--health", required=True, type=Path)
    args = parser.parse_args()
    try: health = _read_strict_json(args.health)
    except ValidationError as exc: output = _result("rejected", diagnostic=exc.code)
    else: output = record_run_health(args.overlay, health)
    print(json.dumps(output, sort_keys=True))
    return 0 if output["status"] == "recorded" else 2


if __name__ == "__main__": raise SystemExit(main())
