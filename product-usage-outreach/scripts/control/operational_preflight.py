#!/usr/bin/env python3
"""Bind resolved runtime, overlay, profile matching, and quick checks read-only.

This is the operational router's machine boundary.  It intentionally does not
initialize, migrate, mutate, execute a runner, or authorize an external write.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from check_freshness import check_freshness
from match_profile import match_profile
from runtime_validation import ValidationError, read_json, validate_document
from validate_state import validate_overlay_state


def _result(status: str, **values: Any) -> dict[str, Any]:
    return {"status": status, **values}


def _runtime(path: Path) -> dict[str, Any] | None:
    try:
        document = read_json(path)
        validate_document(document, "runtime-capabilities.schema.json")
    except ValidationError:
        return None
    return document


def _same_path(left: str | None, right: Path) -> bool:
    if not isinstance(left, str) or not left:
        return False
    try:
        return Path(left).resolve(strict=True) == right.resolve(strict=True)
    except OSError:
        return False


def operational_preflight(runtime_path: Path, overlay: Path, request: Any,
                          observed: Any) -> dict[str, Any]:
    """Choose only a safe next state using already-observed evidence.

    A failure never makes a profile executable; callers must use targeted
    adaptation.  The returned profile identifier is safe only after a `ready`
    result and is not an external-write authorization.
    """
    runtime = _runtime(runtime_path)
    if runtime is None:
        return _result("adapt-required", affected_capabilities=[],
                       diagnostic="invalid-runtime-record", stop_fast_path=True)
    storage = runtime["storage"]
    execution = runtime["execution"]
    if not storage["readable"] or not _same_path(storage.get("overlay_path"), overlay):
        return _result("adapt-required", affected_capabilities=["environment-and-access"],
                       diagnostic="runtime-overlay-unavailable", stop_fast_path=True)
    if not execution["available"]:
        return _result("adapt-required", affected_capabilities=["environment-and-access"],
                       diagnostic="deterministic-execution-unavailable", stop_fast_path=True)
    try:
        validate_overlay_state(overlay)
    except ValidationError as exc:
        return _result("adapt-required", affected_capabilities=[], diagnostic=exc.code,
                       stop_fast_path=True)
    matched = match_profile(overlay, request)
    if matched["status"] != "matched":
        return _result("adapt-required", affected_capabilities=[],
                       diagnostic=matched.get("diagnostic", matched["status"]),
                       stop_fast_path=True)
    quick = check_freshness(overlay, matched["profile_id"], observed)
    if quick["status"] == "ready":
        return _result("ready", profile_id=matched["profile_id"],
                       profile_version=matched["version"], stop_fast_path=False,
                       external_write_authorized=False)
    if quick["status"] == "adapt-required":
        return _result("adapt-required", affected_capabilities=quick["affected_capabilities"],
                       diagnostic="quick-check-failed", failures=quick["failures"],
                       stop_fast_path=True)
    return _result("adapt-required", affected_capabilities=[],
                   diagnostic=quick.get("diagnostic", "quick-check-rejected"),
                   stop_fast_path=True)


def _strict_json(path: Path) -> Any:
    try:
        return read_json(path)
    except ValidationError:
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--observed", required=True, type=Path)
    args = parser.parse_args()
    try:
        request, observed = _strict_json(args.request), _strict_json(args.observed)
    except ValidationError:
        output = _result("adapt-required", affected_capabilities=[],
                         diagnostic="invalid-preflight-input", stop_fast_path=True)
    else:
        output = operational_preflight(args.runtime, args.overlay, request, observed)
    print(json.dumps(output, sort_keys=True))
    return 0 if output["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
