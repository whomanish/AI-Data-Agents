#!/usr/bin/env python3
"""Initialize, export, and restore portable organization overlays."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from runtime_validation import (ValidationError, inventory_hash, read_json, sha256_bytes,
                                validate_document)
from validate_state import validate_overlay_state

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "assets/organization-overlay"
STATE_SCHEMAS = {"registry.json": "registry.schema.json", "profile-index.json": "profile-index.schema.json", "health.json": "health.schema.json"}
COLLISION_SCOPE_CATALOG = "identity-collision-scopes.json"
EXCLUSIONS = ["campaign-workspaces", "credentials", "production-row-data", "blind-materials"]
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")
FORBIDDEN_PARTS = ("campaign", "credential", "secret", "token", "recipient", "blind", "production-row", "activation-response")


class OverlayError(ValueError):
    pass


def emit(status: str, **values: object) -> int:
    print(json.dumps({"status": status, **values}, sort_keys=True))
    return 0 if status in {"initialized", "exported", "restored"} else 2


def under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def portable(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and "\\" not in value and all(part not in {"", ".", ".."} for part in path.parts)


def regular_files(root: Path) -> list[Path]:
    try:
        items = list(root.rglob("*"))
    except OSError as exc:
        raise OverlayError("overlay-unreadable") from exc
    if root.is_symlink() or any(item.is_symlink() for item in items):
        raise OverlayError("symlinked-overlay")
    if any(not item.is_dir() and not item.is_file() for item in items):
        raise OverlayError("non-regular-overlay-entry")
    return [item for item in items if item.is_file()]


def confined(root: Path, relative: str) -> Path:
    if not portable(relative):
        raise OverlayError("unsafe-overlay-path")
    path = root / relative
    if not under(path.resolve(strict=False), root.resolve()):
        raise OverlayError("unsafe-overlay-path")
    return path


def outside_core(path: Path, core: Path) -> None:
    if path.is_symlink() or under(path.resolve(strict=False), core.resolve()):
        raise OverlayError("installed-core-location")


def validate_overlay(root: Path, core: Path = ROOT) -> tuple[dict[str, object], list[Path]]:
    outside_core(root, core)
    if not root.is_dir():
        raise OverlayError("overlay-root-not-directory")
    files = regular_files(root)
    manifest_path = root / "overlay.json"
    if not manifest_path.is_file():
        raise OverlayError("missing-overlay-manifest")
    try:
        manifest = read_json(manifest_path)
    except ValidationError as exc:
        raise OverlayError("malformed-overlay-manifest") from exc
    if not isinstance(manifest, dict) or manifest.get("overlay_schema_version") != "1.0":
        raise OverlayError("unsupported-overlay-version")
    try:
        validate_document(manifest, "overlay-manifest.schema.json")
    except ValidationError as exc:
        raise OverlayError(f"invalid-overlay-manifest:{exc.code}") from exc
    for name in ("state", "organization", "generated"):
        component = confined(root, str(manifest["paths"][name]))
        if not component.is_dir():
            raise OverlayError("missing-overlay-component")
    catalog_path = confined(root, f"{manifest['paths']['organization']}/{COLLISION_SCOPE_CATALOG}")
    if not catalog_path.is_file():
        raise OverlayError("missing-identity-collision-scope-catalog")
    try:
        catalog = read_json(catalog_path)
        validate_document(catalog, "identity-collision-scopes.schema.json")
    except ValidationError as exc:
        raise OverlayError(f"invalid-identity-collision-scope-catalog:{exc.code}") from exc
    if catalog.get("organization_id") != manifest["organization_id"]:
        raise OverlayError("organization-identity-mismatch")
    state = confined(root, str(manifest["paths"]["state"]))
    for filename, schema in STATE_SCHEMAS.items():
        document_path = state / filename
        if not document_path.is_file():
            raise OverlayError("missing-compact-state")
        try:
            document = read_json(document_path)
            validate_document(document, schema)
        except ValidationError as exc:
            raise OverlayError(f"invalid-compact-state:{filename}:{exc.code}") from exc
        if filename == "registry.json" and document.get("organization_id") != manifest["organization_id"]:
            raise OverlayError("organization-identity-mismatch")
    for resource in manifest["generated_resources"]:
        resource_path = confined(root, str(resource["path"]))
        if not resource_path.is_file():
            raise OverlayError("missing-generated-resource")
    try:
        validate_overlay_state(root, core)
    except ValidationError as exc:
        raise OverlayError(f"invalid-overlay-state:{exc.code}") from exc
    return manifest, files


def category(path: str, manifest: dict[str, object]) -> str:
    if path == "overlay.json":
        return "manifest"
    paths = manifest["paths"]
    if path == paths["state"] or path.startswith(str(paths["state"]) + "/"):
        return "state"
    if path == paths["organization"] or path.startswith(str(paths["organization"]) + "/"):
        return "organization"
    return "generated"


def export_files(source: Path, manifest: dict[str, object], files: list[Path]) -> list[Path]:
    selected = []
    organization = str(manifest["paths"]["organization"])
    collision_scope_catalog = f"{organization}/{COLLISION_SCOPE_CATALOG}"
    for file_path in files:
        relative = file_path.relative_to(source).as_posix()
        if relative == "overlay-export.json":
            raise OverlayError("unexpected-export-manifest")
        if any(part in relative.lower() for part in FORBIDDEN_PARTS):
            raise OverlayError("excluded-material-path")
        if (relative.startswith(organization + "/") and file_path.suffix != ".md" and
                relative != collision_scope_catalog):
            raise OverlayError("non-markdown-organization-file")
        selected.append(file_path)
    if not any(item.relative_to(source).as_posix() == "overlay.json" for item in selected):
        raise OverlayError("missing-overlay-manifest")
    return selected


def stage(parent: Path, prefix: str) -> Path:
    if not parent.is_dir() or parent.is_symlink():
        raise OverlayError("target-parent-unwritable")
    return Path(tempfile.mkdtemp(prefix=prefix, dir=parent))


def copy_files(source: Path, destination: Path, files: list[Path]) -> None:
    for source_file in files:
        relative = source_file.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_file, target)


def atomic_publish(staged: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise OverlayError("target-exists")
    staged.replace(destination)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def initialize(args: argparse.Namespace) -> int:
    target, core = args.target, args.installed_core
    try:
        outside_core(target, core)
        if target.exists() or target.is_symlink():
            raise OverlayError("target-exists")
        if not ID_PATTERN.fullmatch(args.organization_id):
            raise OverlayError("invalid-organization-id")
        template_manifest, files = validate_overlay(TEMPLATE, core=Path("/__template-core__"))
        if template_manifest["organization_id"] != "unconfigured-org" or args.organization_id == "unconfigured-org":
            raise OverlayError("neutral-organization-required")
        staged = stage(target.parent, ".outreach-init-")
        try:
            copy_files(TEMPLATE, staged, files)
            stamp = now()
            manifest_path = staged / "overlay.json"
            manifest = read_json(manifest_path)
            manifest.update({"organization_id": args.organization_id, "persistence_class": args.persistence,
                             "created_at": stamp, "updated_at": stamp, "exported_at": None})
            registry_path = staged / str(manifest["paths"]["state"]) / "registry.json"
            registry = read_json(registry_path); registry.update({"organization_id": args.organization_id, "updated_at": stamp})
            catalog_path = staged / str(manifest["paths"]["organization"]) / COLLISION_SCOPE_CATALOG
            catalog = read_json(catalog_path); catalog["organization_id"] = args.organization_id
            for name in ("profile-index.json", "health.json"):
                path = staged / str(manifest["paths"]["state"]) / name
                document = read_json(path); document["updated_at"] = stamp
                path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            catalog_path.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            validate_overlay(staged, core=core)
            atomic_publish(staged, target)
        except Exception:
            shutil.rmtree(staged, ignore_errors=True)
            raise
    except (OverlayError, ValidationError, OSError) as exc:
        return emit("rejected", diagnostic=str(exc), target=str(target))
    return emit("initialized", overlay_path=str(target), organization_id=args.organization_id,
                persistence_class=args.persistence, durable_continuation=args.persistence == "persistent")


def export(args: argparse.Namespace) -> int:
    source, destination, core = args.source, args.destination, args.installed_core
    try:
        outside_core(destination, core)
        if destination.exists() or destination.is_symlink():
            raise OverlayError("target-exists")
        manifest, files = validate_overlay(source, core)
        files = export_files(source, manifest, files)
        staged = stage(destination.parent, ".outreach-export-")
        try:
            copy_files(source, staged, files)
            entries = []
            for source_file in files:
                relative = source_file.relative_to(source).as_posix()
                data = source_file.read_bytes()
                entries.append({"path": relative, "sha256": sha256_bytes(data), "bytes": len(data),
                                "category": category(relative, manifest)})
            overlay_entry = next(entry for entry in entries if entry["path"] == "overlay.json")
            document = {"export_format_version": "1.0", "overlay_schema_version": "1.0",
                        "organization_id": manifest["organization_id"], "created_at": now(),
                        "overlay_manifest_hash": overlay_entry["sha256"],
                        "inventory_hash_algorithm": "sha256-path-null-sha256-newline-v1",
                        "inventory_hash": inventory_hash(entries), "files": entries,
                        "excluded_content": EXCLUSIONS,
                        "restore_policy": {"on_incompatible_version": "leave-unchanged",
                                           "on_hash_mismatch": "abort-without-write", "overwrite_existing": False}}
            validate_document(document, "overlay-export.schema.json")
            (staged / "overlay-export.json").write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            atomic_publish(staged, destination)
        except Exception:
            shutil.rmtree(staged, ignore_errors=True)
            raise
    except (OverlayError, ValidationError, OSError) as exc:
        return emit("rejected", diagnostic=str(exc), source=str(source), destination=str(destination))
    return emit("exported", export_path=str(destination), organization_id=manifest["organization_id"], files=len(entries))


def restore_export(source: Path, target: Path, core: Path) -> dict[str, object]:
    outside_core(target, core)
    if target.exists() or target.is_symlink():
        raise OverlayError("target-exists")
    all_files = regular_files(source)
    export_path = source / "overlay-export.json"
    if not export_path.is_file():
        raise OverlayError("missing-export-manifest")
    try:
        document = read_json(export_path)
        validate_document(document, "overlay-export.schema.json")
    except ValidationError as exc:
        raise OverlayError(f"invalid-export-manifest:{exc.code}") from exc
    entries = document["files"]
    expected = {"overlay-export.json"} | {str(entry["path"]) for entry in entries}
    actual = {path.relative_to(source).as_posix() for path in all_files}
    if actual != expected:
        raise OverlayError("export-file-set-mismatch")
    for entry in entries:
        relative = str(entry["path"])
        if not portable(relative):
            raise OverlayError("unsafe-export-path")
        path = source / relative
        data = path.read_bytes()
        if len(data) != entry["bytes"] or sha256_bytes(data) != entry["sha256"]:
            raise OverlayError("export-file-hash-mismatch")
    if document["inventory_hash"] != inventory_hash(entries):
        raise OverlayError("export-inventory-hash-mismatch")
    manifest_path = source / "overlay.json"
    if sha256_bytes(manifest_path.read_bytes()) != document["overlay_manifest_hash"]:
        raise OverlayError("export-overlay-binding-mismatch")
    staged = stage(target.parent, ".outreach-restore-")
    try:
        copy_files(source, staged, [source / str(entry["path"]) for entry in entries])
        manifest, _ = validate_overlay(staged, core)
        if manifest["organization_id"] != document["organization_id"]:
            raise OverlayError("export-organization-mismatch")
        atomic_publish(staged, target)
    except Exception:
        shutil.rmtree(staged, ignore_errors=True)
        raise
    return manifest


def restore(args: argparse.Namespace) -> int:
    try:
        manifest = restore_export(args.source, args.target, args.installed_core)
    except (OverlayError, ValidationError, OSError) as exc:
        return emit("rejected", diagnostic=str(exc), source=str(args.source), target=str(args.target))
    session_only = manifest["persistence_class"] == "session-only"
    return emit("restored", overlay_path=str(args.target), organization_id=manifest["organization_id"],
                persistence_class=manifest["persistence_class"], durable_continuation=not session_only,
                limitation="continuation restored but durable persistence is not established; export/restore remains required" if session_only else None)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed-core", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init"); init.add_argument("--target", required=True, type=Path); init.add_argument("--organization-id", required=True); init.add_argument("--persistence", required=True, choices=("persistent", "session-only")); init.set_defaults(handler=initialize)
    export_parser = commands.add_parser("export"); export_parser.add_argument("--source", required=True, type=Path); export_parser.add_argument("--destination", required=True, type=Path); export_parser.set_defaults(handler=export)
    restore_parser = commands.add_parser("restore"); restore_parser.add_argument("--source", required=True, type=Path); restore_parser.add_argument("--target", required=True, type=Path); restore_parser.set_defaults(handler=restore)
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
