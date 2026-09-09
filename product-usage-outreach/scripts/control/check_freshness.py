#!/usr/bin/env python3
"""Run bounded, profile-defined fast-path checks against caller-observed evidence.

Evidence is deliberately a compact JSON object.  Its six maps are keyed by
quick-check id (except ``ranges``, which is keyed by an operating-range id):
``access``, ``freshness``, ``fingerprints``, ``events``, ``ranges``, and
``blockers``.  No observation is discovered or written by this utility.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

from runtime_validation import ValidationError, read_json
from validate_state import validate_overlay_state


def _result(status: str, **values: Any) -> dict[str, Any]:
    return {"status": status, **values}


def _time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def _finite_number(value: Any) -> bool:
    """Accept JSON numbers only when they are finite (and never booleans)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _read_strict_json(path: Path) -> Any:
    """Read an input document without accepting Python's non-standard constants."""
    try:
        return read_json(path)
    except ValidationError:
        raise


def _evidence(value: Any) -> dict[str, Any] | None:
    keys = {"observed_at", "access", "freshness", "fingerprints", "events", "ranges", "blockers"}
    if not isinstance(value, dict) or set(value) != keys or _time(value["observed_at"]) is None:
        return None
    if not all(isinstance(value[name], dict) for name in keys - {"observed_at"}):
        return None
    return value


def _profile(overlay: Path, snapshot: dict[str, Any], profile_id: str) -> dict[str, Any] | None:
    if not isinstance(profile_id, str):
        return None
    entry = next((item for item in snapshot["profile_index"]["profiles"] if item["profile_id"] == profile_id), None)
    return read_json(overlay / entry["path"]) if entry else None


def _valid_operating_ranges(profile: dict[str, Any]) -> bool:
    ranges = profile.get("operating_ranges")
    if not isinstance(ranges, dict):
        return False
    return all(
        isinstance(bounds, dict) and _finite_number(bounds.get("minimum")) and
        _finite_number(bounds.get("maximum")) and bounds["minimum"] <= bounds["maximum"]
        for bounds in ranges.values()
    )


def check_freshness(overlay: Path, profile_id: str, observed: Any) -> dict[str, Any]:
    """Return readiness or affected capabilities; never mutate overlay state."""
    try:
        snapshot = validate_overlay_state(overlay)
        profile = _profile(overlay, snapshot, profile_id)
    except ValidationError as exc:
        return _result("rejected", diagnostic=exc.code)
    if profile is None:
        return _result("rejected", diagnostic="unknown-profile")
    if not _valid_operating_ranges(profile):
        return _result("rejected", diagnostic="invalid-quick-check-configuration")
    evidence = _evidence(observed)
    if evidence is None:
        return _result("rejected", diagnostic="invalid-quick-check-evidence")
    if profile["status"] not in {"ready", "verified"}:
        return _result("adapt-required", affected_capabilities=[], diagnostic="profile-not-ready", stop_fast_path=True)

    failures: list[dict[str, str]] = []
    now = _time(evidence["observed_at"])
    assert now is not None
    for check in profile["quick_checks"]:
        kind, check_id, capability = check["type"], check["id"], check["capability_id"]
        config = check.get("configuration", {})
        if not isinstance(config, dict):
            return _result("rejected", diagnostic="invalid-quick-check-configuration")
        reason: str | None = None
        if kind == "access":
            if evidence["access"].get(check_id) is not True: reason = "access-unavailable"
        elif kind == "event-availability":
            if evidence["events"].get(check_id) is not True: reason = "event-unavailable"
        elif kind == "blocker":
            if evidence["blockers"].get(check_id) is not False: reason = "known-blocker"
        elif kind == "freshness":
            age = config.get("max_age_days")
            seen = _time(evidence["freshness"].get(check_id))
            if not _finite_number(age) or age < 0:
                return _result("rejected", diagnostic="invalid-quick-check-configuration")
            if seen is None or seen > now or now - seen > dt.timedelta(days=age): reason = "stale-source"
        elif kind == "fingerprint":
            expected = config.get("expected_fingerprint")
            if not isinstance(expected, str) or not expected:
                return _result("rejected", diagnostic="invalid-quick-check-configuration")
            if evidence["fingerprints"].get(check_id) != expected: reason = "fingerprint-changed"
        elif kind == "operating-range":
            range_id = config.get("range_id")
            bounds = profile["operating_ranges"].get(range_id) if isinstance(range_id, str) else None
            value = evidence["ranges"].get(range_id) if isinstance(range_id, str) else None
            if not isinstance(bounds, dict) or not _finite_number(value):
                return _result("rejected", diagnostic="invalid-quick-check-configuration")
            if value < bounds["minimum"] or value > bounds["maximum"]: reason = "outside-operating-range"
        else:
            return _result("rejected", diagnostic="invalid-quick-check-configuration")
        if reason:
            failures.append({"id": check_id, "capability_id": capability, "diagnostic": reason})
    affected = sorted({item["capability_id"] for item in failures})
    if affected:
        return _result("adapt-required", affected_capabilities=affected, failures=failures, stop_fast_path=True)
    return _result("ready", affected_capabilities=[], failures=[], stop_fast_path=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--observed", required=True, type=Path)
    args = parser.parse_args()
    try:
        observed = _read_strict_json(args.observed)
    except ValidationError as exc:
        output = _result("rejected", diagnostic=exc.code)
    else:
        output = check_freshness(args.overlay, args.profile_id, observed)
    print(json.dumps(output, sort_keys=True))
    return 0 if output["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
