#!/usr/bin/env python3
"""Validate a portable organization overlay without changing it."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from runtime_validation import (ROOT, ValidationError, read_json, validate_document,
                                identity_collision_scope_definition_hash,
                                SYNTHETIC_PROVENANCE, contains_durable_sensitive_data,
                                DURABLE_SENSITIVE_VALUE)

STATE_SCHEMAS = {
    "registry.json": "registry.schema.json",
    "profile-index.json": "profile-index.schema.json",
    "health.json": "health.schema.json",
}
RESOURCE_SCHEMAS = {"adapter": "adapter-contract.schema.json", "runner": "execution-profile.schema.json"}
COLLISION_SCOPE_CATALOG = "identity-collision-scopes.json"
NEUTRAL_EVIDENCE_STATUS = re.compile(r"(?im)^\s*status:\s*(?:unconfigured|unknown|partial)\b")


def _fail(code: str, location: str) -> None:
    raise ValidationError(code, location)


def _under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _portable(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and "\\" not in value and all(part not in {"", ".", ".."} for part in path.parts)


def _confined_regular(root: Path, relative: str, location: str) -> Path:
    if not _portable(relative):
        _fail("unsafe-state-path", location)
    path = root / relative
    try:
        if path.is_symlink() or not path.is_file() or not _under(path.resolve(strict=True), root.resolve(strict=True)):
            _fail("unsafe-state-path", location)
    except OSError as exc:
        raise ValidationError("missing-state-reference", location) from exc
    return path


def _confined_directory(root: Path, relative: str, location: str) -> Path:
    if not _portable(relative):
        _fail("unsafe-state-path", location)
    path = root / relative
    try:
        if path.is_symlink() or not path.is_dir() or not _under(path.resolve(strict=True), root.resolve(strict=True)):
            _fail("unsafe-state-path", location)
    except OSError as exc:
        raise ValidationError("missing-overlay-component", location) from exc
    return path


def _inside(path: Path, directory: Path, code: str, location: str) -> None:
    try:
        if not _under(path.resolve(strict=True), directory.resolve(strict=True)):
            _fail(code, location)
    except OSError as exc:
        raise ValidationError(code, location) from exc


def _no_durable_sensitive_data(value: Any, location: str = "$") -> None:
    if contains_durable_sensitive_data(value):
        _fail("durable-sensitive-state", location)


def _scan_confined_content(root: Path, target: Path, location: str) -> None:
    """Reject concrete sensitive values in a confined durable-state file or tree."""
    try:
        files = [target] if target.is_file() else (path for path in target.rglob("*") if path.is_file())
        for path in files:
            try:
                if path.is_symlink() or not _under(path.resolve(strict=True), root.resolve(strict=True)):
                    _fail("unsafe-state-path", location)
                # Concrete secret and email patterns are ASCII.  Lossy decoding
                # lets us detect them in otherwise non-text artifacts without
                # pretending to infer identities from arbitrary binary content.
                text = path.read_bytes().decode("utf-8", errors="ignore")
            except OSError as exc:
                raise ValidationError("unreadable-durable-content", location) from exc
            if DURABLE_SENSITIVE_VALUE.search(text):
                _fail("durable-sensitive-state", location)
    except OSError as exc:
        raise ValidationError("unreadable-durable-content", location) from exc


def _validate_promotion(capability: dict[str, Any], location: str) -> None:
    maturity = capability["maturity"]
    if maturity not in {"ready", "verified"}:
        return
    # The compact registry can prove only references, scope, and implementation.
    # Detailed semantic/policy confirmation remains in its referenced evidence.
    required = ("supported_scopes", "implementation_refs", "evidence_refs")
    if any(not capability[name] for name in required):
        _fail("illegal-readiness-promotion", location)
    if maturity == "verified":
        # Synthetic-only evidence must not be promoted.  This conservative check
        # rejects explicit fixture/test references, while requiring a concrete ref.
        if any(re.search(r"(?i)(?:synthetic|fixture|blind|test)", ref) for ref in capability["evidence_refs"]):
            _fail("illegal-verification-promotion", f"{location}.evidence_refs")


def _validate_execution_profile_document(profile: Any, location: str) -> dict[str, Any]:
    if not isinstance(profile, dict):
        _fail("schema-type", location)
    criteria = profile.get("match_criteria")
    if (profile.get("schema_version") == "1.0" or not isinstance(criteria, dict) or
            "identity_collision_scope" not in criteria or
            "identity_collision_scope_definition_hash" not in criteria):
        _fail("profile-collision-scope-migration-required", location)
    if (criteria.get("deliverable") in {"audience-ready", "activation-ready"} and
            not any(item.get("capability_id") == "identity-resolution"
                    for item in profile.get("capability_dependencies", []) if isinstance(item, dict))):
        _fail("identity-resolution-dependency-required", location)
    validate_document(profile, "execution-profile.schema.json")
    return profile


def _validate_collision_binding(profile: dict[str, Any], collision_scopes: dict[str, dict[str, Any]],
                                identity_capability: dict[str, Any], location: str) -> None:
    criteria = profile["match_criteria"]
    collision_scope = criteria["identity_collision_scope"]
    collision_scope_hash = criteria["identity_collision_scope_definition_hash"]
    dependency = next((item for item in profile["capability_dependencies"]
                       if item["capability_id"] == "identity-resolution"), None)
    if dependency is None:
        _fail("identity-resolution-dependency-required", location)
    if (dependency["implementation_id"] not in identity_capability["implementation_refs"] or
            identity_capability["maturity"] not in {"ready", "verified"} or
            collision_scope not in identity_capability["supported_scopes"] or
            collision_scope not in collision_scopes):
        _fail("identity-collision-scope-unresolved", f"{location}.match_criteria.identity_collision_scope")
    definition = collision_scopes[collision_scope]
    if (definition["definition_hash"] != collision_scope_hash or
            identity_collision_scope_definition_hash(definition) != collision_scope_hash):
        _fail("identity-collision-scope-definition-changed",
              f"{location}.match_criteria.identity_collision_scope_definition_hash")


def _validate_profile(root: Path, state: Path, entry: dict[str, Any], location: str) -> dict[str, Any]:
    path = _confined_regular(root, entry["path"], f"{location}.path")
    _inside(path, state, "invalid-profile-path", f"{location}.path")
    try:
        profile = read_json(path)
        _validate_execution_profile_document(profile, f"{location}.profile")
    except ValidationError as exc:
        raise ValidationError(exc.code, f"{location}.path") from exc
    _no_durable_sensitive_data(profile, f"{location}.profile")
    for field in ("profile_id", "version", "status"):
        if profile[field] != entry[field]:
            _fail("profile-index-profile-mismatch", f"{location}.{field}")
    for field in ("channel", "deliverable"):
        if profile["match_criteria"][field] != entry[field]:
            _fail("profile-index-profile-mismatch", f"{location}.{field}")
    versions = {item["capability_id"]: item["version"] for item in profile["capability_dependencies"]}
    if versions != entry["capability_versions"]:
        _fail("profile-capability-version-mismatch", f"{location}.capability_versions")
    if profile["status"] == "verified":
        if not profile["evidence_refs"] or any(re.search(r"(?i)(?:synthetic|fixture|blind|test)", ref) for ref in profile["evidence_refs"]):
            _fail("illegal-verification-promotion", f"{location}.profile.evidence_refs")
    return profile


def validate_overlay_state(overlay: Path, installed_core: Path = ROOT) -> dict[str, Any]:
    """Return a validated, read-only compact state snapshot or raise ValidationError."""
    try:
        root = overlay.resolve(strict=True)
        core = installed_core.resolve(strict=False)
    except OSError as exc:
        raise ValidationError("overlay-root-unreadable", str(overlay)) from exc
    if overlay.is_symlink() or not root.is_dir() or _under(root, core):
        _fail("unsafe-overlay-root", str(overlay))
    try:
        if any(path.is_symlink() for path in root.rglob("*")):
            _fail("symlinked-overlay-component", str(overlay))
    except OSError as exc:
        raise ValidationError("overlay-root-unreadable", str(overlay)) from exc
    manifest_path = _confined_regular(root, "overlay.json", "$.overlay")
    manifest = read_json(manifest_path)
    validate_document(manifest, "overlay-manifest.schema.json")
    _no_durable_sensitive_data(manifest, "$.overlay")
    components = {name: _confined_directory(root, relative, f"$.overlay.paths.{name}")
                  for name, relative in manifest["paths"].items()}
    _scan_confined_content(root, components["organization"], "$.overlay.paths.organization")
    catalog_relative = f"{manifest['paths']['organization']}/{COLLISION_SCOPE_CATALOG}"
    try:
        catalog_path = _confined_regular(root, catalog_relative, "$.identity_collision_scopes")
    except ValidationError as exc:
        raise ValidationError("identity-collision-scope-catalog-missing", "$.identity_collision_scopes") from exc
    catalog = read_json(catalog_path)
    validate_document(catalog, "identity-collision-scopes.schema.json")
    _no_durable_sensitive_data(catalog, "$.identity_collision_scopes")
    if catalog["organization_id"] != manifest["organization_id"]:
        _fail("identity-collision-scope-organization-mismatch", "$.identity_collision_scopes.organization_id")
    if manifest["organization_id"] == "unconfigured-org" and catalog["definitions"]:
        _fail("unconfigured-organization-state", "$.identity_collision_scopes.definitions")
    collision_scopes = {item["id"]: item for item in catalog["definitions"]}
    for definition_index, definition in enumerate(catalog["definitions"]):
        for evidence_index, evidence_ref in enumerate(definition["evidence_refs"]):
            location = f"$.identity_collision_scopes.definitions[{definition_index}].evidence_refs[{evidence_index}]"
            try:
                evidence_path = _confined_regular(root, evidence_ref, location)
            except ValidationError as exc:
                raise ValidationError("identity-collision-scope-evidence-unresolved", location) from exc
            _inside(evidence_path, components["organization"], "identity-collision-scope-evidence-unresolved", location)
            try:
                evidence_text = evidence_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise ValidationError("identity-collision-scope-evidence-unreadable", location) from exc
            if NEUTRAL_EVIDENCE_STATUS.search(evidence_text):
                _fail("identity-collision-scope-evidence-neutral", location)
            if SYNTHETIC_PROVENANCE.search(evidence_text):
                _fail("identity-collision-scope-evidence-synthetic", location)
    state = _confined_directory(root, manifest["paths"]["state"], "$.overlay.paths.state")
    _scan_confined_content(root, state, "$.overlay.paths.state")
    documents: dict[str, Any] = {}
    for filename, schema in STATE_SCHEMAS.items():
        path = _confined_regular(root, f"{manifest['paths']['state']}/{filename}", f"$.state.{filename}")
        document = read_json(path)
        validate_document(document, schema)
        _no_durable_sensitive_data(document, f"$.state.{filename}")
        documents[filename] = document
    registry = documents["registry.json"]
    index = documents["profile-index.json"]
    if registry["organization_id"] != manifest["organization_id"]:
        _fail("organization-identity-mismatch", "$.state.registry.json.organization_id")
    profiles_by_id = {entry["profile_id"]: entry for entry in index["profiles"]}
    for capability_index, capability in enumerate(registry["capabilities"]):
        location = f"$.state.registry.json.capabilities[{capability_index}]"
        detail = _confined_regular(root, capability["detail_reference"], f"{location}.detail_reference")
        _inside(detail, components["organization"], "invalid-detail-reference", f"{location}.detail_reference")
        if not detail.suffix == ".md":
            _fail("invalid-detail-reference", f"{location}.detail_reference")
        _validate_promotion(capability, location)
        for profile_id in capability["dependent_profile_ids"]:
            if profile_id not in profiles_by_id:
                _fail("missing-profile-reference", f"{location}.dependent_profile_ids")
    parsed_profiles = [_validate_profile(root, state, entry, f"$.state.profile-index.json.profiles[{index_number}]")
                       for index_number, entry in enumerate(index["profiles"])]
    identity_capability = next(item for item in registry["capabilities"] if item["capability_id"] == "identity-resolution")
    capability_ids = {item["capability_id"] for item in registry["capabilities"]}
    for entry, profile in zip(index["profiles"], parsed_profiles):
        _validate_collision_binding(profile, collision_scopes, identity_capability,
                                    f"$.profiles.{entry['profile_id']}")
        for dependency in profile["capability_dependencies"]:
            if dependency["capability_id"] not in capability_ids:
                _fail("missing-capability-reference", f"$.profiles.{entry['profile_id']}")
    for resource_index, resource in enumerate(manifest["generated_resources"]):
        location = f"$.overlay.generated_resources[{resource_index}]"
        resource_path = _confined_regular(root, resource["path"], f"{location}.path")
        _inside(resource_path, components["generated"], "invalid-generated-resource-path", f"{location}.path")
        _scan_confined_content(root, resource_path, f"{location}.path")
        schema = RESOURCE_SCHEMAS.get(resource["kind"])
        if schema:
            document = read_json(resource_path)
            if resource["kind"] == "runner":
                _validate_execution_profile_document(document, f"{location}.resource")
                _validate_collision_binding(document, collision_scopes, identity_capability,
                                            f"{location}.resource")
            else:
                validate_document(document, schema)
            _no_durable_sensitive_data(document, f"{location}.resource")
            if resource["kind"] == "runner" and (document["profile_id"] != resource["id"] or document["version"] != resource["version"]):
                _fail("generated-resource-version-mismatch", location)
    return {"manifest": manifest, "registry": registry, "profile_index": index,
            "health": documents["health.json"], "identity_collision_scopes": catalog}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument("--installed-core", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        snapshot = validate_overlay_state(args.overlay, args.installed_core)
    except (ValidationError, OSError) as exc:
        print(json.dumps({"status": "rejected", "diagnostic": getattr(exc, "code", "state-validation-error"),
                          "location": getattr(exc, "location", str(args.overlay))}, sort_keys=True))
        return 2
    print(json.dumps({"status": "valid", "organization_id": snapshot["manifest"]["organization_id"],
                      "profile_status": snapshot["registry"]["profile_status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
