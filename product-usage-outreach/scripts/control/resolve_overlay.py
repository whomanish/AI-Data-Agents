#!/usr/bin/env python3
"""Resolve an existing organization overlay without initializing or modifying it."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from runtime_validation import ValidationError, validate_document, read_json
from validate_state import validate_overlay_state

STATE_SCHEMAS = {"registry.json": "registry.schema.json", "profile-index.json": "profile-index.schema.json", "health.json": "health.schema.json"}


def _emit(status: str, **values: object) -> int:
    print(json.dumps({"status": status, **values}, sort_keys=True))
    return 0 if status in ("resolved", "needs-initialization") else 2


def _under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _regular(path: Path) -> bool:
    return path.exists() and path.is_file() and not path.is_symlink()


def _component(root: Path, relative: str) -> Path | None:
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            return None
    try:
        resolved = current.resolve(strict=False)
    except OSError:
        return None
    return current if _under(resolved, root.resolve()) else None


def _reject(code: str, source: str, candidate: Path) -> int:
    return _emit("rejected", diagnostic=code, source=source, overlay_path=str(candidate))


def _validate(candidate: Path, source: str, installed_core: Path) -> int:
    if candidate.is_symlink():
        return _reject("symlinked-overlay-root", source, candidate)
    try:
        root = candidate.resolve(strict=True)
        core = installed_core.resolve(strict=True)
    except OSError:
        return _reject("overlay-root-unreadable", source, candidate)
    if not root.is_dir():
        return _reject("overlay-root-not-directory", source, candidate)
    if _under(root, core):
        return _reject("installed-core-location", source, candidate)
    try:
        if any(path.is_symlink() for path in candidate.rglob("*")):
            return _reject("symlinked-overlay-component", source, candidate)
    except OSError:
        return _reject("overlay-root-unreadable", source, candidate)
    manifest_path = candidate / "overlay.json"
    if manifest_path.is_symlink():
        return _reject("symlinked-overlay-component", source, candidate)
    if not _regular(manifest_path):
        return _reject("missing-overlay-manifest", source, candidate)
    try:
        manifest = read_json(manifest_path)
    except ValidationError:
        return _reject("malformed-overlay-manifest", source, candidate)
    version = manifest.get("overlay_schema_version") if isinstance(manifest, dict) else None
    if version != "1.0":
        return _reject("unsupported-overlay-version", source, candidate)
    try:
        validate_document(manifest, "overlay-manifest.schema.json")
    except ValidationError as exc:
        return _reject(f"invalid-overlay-manifest:{exc.code}", source, candidate)
    if source == "session-only" and manifest["persistence_class"] != "session-only":
        return _reject("session-source-persistence-mismatch", source, candidate)
    for name in ("state", "organization", "generated"):
        component = _component(candidate, manifest["paths"][name])
        if component is None:
            return _reject("symlinked-or-unconfined-overlay-component", source, candidate)
        if not component.is_dir():
            return _reject("missing-overlay-component", source, candidate)
    for resource in manifest["generated_resources"]:
        resource_path = _component(candidate, resource["path"])
        if resource_path is None:
            return _reject("symlinked-or-unconfined-overlay-component", source, candidate)
        if not _regular(resource_path):
            return _reject("missing-generated-resource", source, candidate)
    state_dir = candidate / manifest["paths"]["state"]
    documents: dict[str, object] = {}
    for filename, schema in STATE_SCHEMAS.items():
        path = state_dir / filename
        if path.is_symlink():
            return _reject("symlinked-compact-state", source, candidate)
        if not _regular(path):
            return _reject("missing-compact-state", source, candidate)
        try:
            document = read_json(path)
            validate_document(document, schema)
        except ValidationError as exc:
            return _reject(f"invalid-compact-state:{filename}:{exc.code}", source, candidate)
        documents[filename] = document
    if documents["registry.json"].get("organization_id") != manifest["organization_id"]:
        return _reject("organization-identity-mismatch", source, candidate)
    try:
        validate_overlay_state(candidate, installed_core)
    except ValidationError as exc:
        return _reject(exc.code, source, candidate)
    durable = source != "session-only" and manifest["persistence_class"] == "persistent"
    return _emit("resolved", source=source, overlay_path=str(candidate), organization_id=manifest["organization_id"], persistence_class=manifest["persistence_class"], durable_continuation=durable, limitation=None if durable else "durable continuation and resumability unavailable until export/restore exists")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--explicit", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--host-persistent", type=Path)
    parser.add_argument("--session-only", type=Path)
    parser.add_argument("--installed-core", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    project = args.project_root / ".product-usage-outreach"
    candidates = []
    if args.explicit is not None:
        candidates.append(("explicit", args.explicit, True))
    candidates.append(("project-local", project, False))
    if args.host_persistent is not None:
        candidates.append(("host-persistent", args.host_persistent, False))
    if args.session_only is not None:
        candidates.append(("session-only", args.session_only, False))
    for source, candidate, selected in candidates:
        if candidate.exists() or candidate.is_symlink() or selected:
            if not candidate.exists() and not candidate.is_symlink():
                return _emit("needs-initialization", source=source, overlay_path=str(candidate), diagnostic="selected-overlay-missing", mutation="none")
            return _validate(candidate, source, args.installed_core)
    return _emit("needs-initialization", source="project-local", overlay_path=str(project), diagnostic="no-overlay-candidate", mutation="none")


if __name__ == "__main__":
    raise SystemExit(main())
