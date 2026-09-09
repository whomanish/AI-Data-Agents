#!/usr/bin/env python3
"""Create an operation-scoped runtime record without probing production writes."""
from __future__ import annotations

import argparse
import datetime as dt
import platform
import shutil
import sys
import tempfile
from pathlib import Path

from runtime_validation import ValidationError, validate_document, write_json_atomic

OPERATIONS = ("search", "schema", "query", "export", "write")


def _path_access(path: Path | None, label: str, evidence: list[str]) -> tuple[bool, bool]:
    if path is None:
        return False, False
    exists = path.exists()
    readable = exists and (path.is_dir() or path.is_file())
    evidence.append(f"{label} path metadata inspected")
    # Metadata alone cannot establish that a write operation is available.
    return readable, False


def _scratch_probe(probe_dir: Path) -> bool:
    """Perform a confined, disposable same-session read-back probe."""
    if not probe_dir.is_dir() or probe_dir.is_symlink():
        raise ValueError("scratch-probe-dir-invalid")
    scratch = Path(tempfile.mkdtemp(prefix="outreach-runtime-", dir=probe_dir))
    try:
        probe = scratch / "read-back"
        probe.write_text("outreach-runtime-probe", encoding="utf-8")
        return probe.read_text(encoding="utf-8") == "outreach-runtime-probe"
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _operation(value: str, parser: argparse.ArgumentParser) -> dict[str, object]:
    parts = value.split(":")
    if len(parts) != 3 or not all(parts):
        parser.error("--operation must be connector:search|schema|query|export|write:available|blocked")
    connector, operation, status = parts
    if operation not in OPERATIONS or status not in ("available", "blocked"):
        parser.error("--operation must be connector:search|schema|query|export|write:available|blocked")
    return {"connector_id": connector, "operation": operation,
            "available": status == "available", "evidence": "declared safe operation observation"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--overlay", type=Path)
    parser.add_argument("--campaign-workspace", type=Path)
    parser.add_argument("--probe-dir", type=Path,
                        help="approved existing scratch parent; never a production workspace")
    parser.add_argument("--allow-scratch-probe", action="store_true",
                        help="confirm the optional confined scratch probe")
    parser.add_argument("--persistence", default="unknown",
                        choices=("persistent", "session-only", "none", "unknown"))
    parser.add_argument("--persistence-evidence", action="append", default=[])
    parser.add_argument("--operation", action="append", default=[])
    parser.add_argument("--network", default="unknown",
                        choices=("allowed", "restricted", "unavailable", "unknown"))
    parser.add_argument("--network-constraint", action="append", default=[])
    parser.add_argument("--blocker", action="append", default=[])
    args = parser.parse_args()
    if args.probe_dir and not args.allow_scratch_probe:
        parser.error("--probe-dir requires --allow-scratch-probe")
    if args.allow_scratch_probe and not args.probe_dir:
        parser.error("--allow-scratch-probe requires --probe-dir")
    if args.persistence == "persistent" and not args.persistence_evidence:
        parser.error("persistent storage requires --persistence-evidence; a scratch probe is same-session only")

    evidence: list[str] = []
    overlay_readable, overlay_writable = _path_access(args.overlay, "overlay", evidence)
    campaign_readable, campaign_writable = _path_access(args.campaign_workspace, "campaign workspace", evidence)
    readable = overlay_readable or campaign_readable
    writable = overlay_writable or campaign_writable
    if args.probe_dir:
        try:
            passed = _scratch_probe(args.probe_dir)
        except (OSError, ValueError) as exc:
            print(f"scratch-probe-failed: {exc}", file=sys.stderr)
            return 2
        evidence.append("approved confined scratch write/read-back probe passed" if passed else "approved confined scratch write/read-back probe failed")
        writable = writable or passed
        readable = readable or passed
    if args.persistence_evidence:
        evidence.extend(args.persistence_evidence)
    if not evidence:
        evidence.append("no storage path supplied")
    operations = [_operation(item, parser) for item in args.operation]
    blockers = []
    for item in args.blocker:
        try:
            ident, capability, consequence, detail = item.split(":", 3)
        except ValueError:
            parser.error("--blocker must be id:capability:safety|execution:detail")
        if consequence not in ("safety", "execution") or not all((ident, capability, detail)):
            parser.error("--blocker must be id:capability:safety|execution:detail")
        blockers.append({"id": ident, "capability": capability, "consequence": consequence, "detail": detail})
    record = {"schema_version": "1.0", "observed_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"), "environment_label": platform.system().lower(), "storage": {"readable": readable, "writable": writable, "persistence_class": args.persistence, "overlay_path": str(args.overlay) if args.overlay else None, "evidence": evidence}, "execution": {"available": sys.version_info >= (3, 11), "python_version": platform.python_version(), "evidence": ["python interpreter inspected; Python 3.11+ required"]}, "connector_operations": operations, "network": {"status": args.network, "constraints": args.network_constraint}, "external_write": {"supported": any(item["operation"] == "write" and item["available"] for item in operations), "requires_confirmation": True, "evidence": "write operations are never probed; confirmation remains required"}, "blockers": blockers}
    try:
        validate_document(record, "runtime-capabilities.schema.json")
    except ValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    write_json_atomic(args.output, record)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
