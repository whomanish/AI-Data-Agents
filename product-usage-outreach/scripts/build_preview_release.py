#!/usr/bin/env python3
"""Build the deterministic installable preview from a verified source snapshot."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_CONTEXT = ROOT / "build/preview-release-context.json"
DIST = ROOT / "dist/preview"
PACKAGE_NAME = "product-usage-outreach"
VERSION = "0.1.0-preview.1"
ALLOWED = ("SKILL.md", "agents", "assets", "compatibility.json", "references", "schemas", "scripts")
PREVIEW_METADATA = ("PREVIEW.md",)
FORBIDDEN_PARTS = {"evals", "build", "openspec", ".git", ".codex", "__pycache__"}
ZIP_TIME = (2026, 1, 1, 0, 0, 0)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root: Path):
    return sorted(path for path in root.rglob("*") if path.is_file())


def inventory(root: Path):
    values = []
    digest = hashlib.sha256()
    for path in files(root):
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        item_hash = hashlib.sha256(data).hexdigest()
        values.append({"path": relative, "bytes": len(data), "sha256": "sha256:" + item_hash})
        digest.update(relative.encode("utf-8") + b"\0" + item_hash.encode("ascii") + b"\n")
    return values, "sha256:" + digest.hexdigest()


def content_hash(values):
    digest = hashlib.sha256()
    for item in values:
        digest.update(item["path"].encode("utf-8") + b"\0")
        digest.update(item["sha256"].encode("ascii") + b"\n")
    return "sha256:" + digest.hexdigest()


def load_build_context():
    if not BUILD_CONTEXT.is_file():
        raise SystemExit("maintainer preview build context is missing")
    context = json.loads(BUILD_CONTEXT.read_text(encoding="utf-8"))
    if context.get("version") != VERSION:
        raise ValueError("preview version differs from maintainer build context")
    required = ("source_directory", "source_manifest", "source_content_sha256")
    if any(not isinstance(context.get(key), str) or not context[key] for key in required):
        raise ValueError("maintainer preview build context is incomplete")
    source = ROOT / context["source_directory"]
    source_manifest = ROOT / context["source_manifest"]
    return context, source, source_manifest


def validate_frozen_source(source, source_manifest, source_hash):
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    expected = manifest["files"]
    actual = []
    for path in sorted(
        (path for path in source.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(source).as_posix().encode("utf-8"),
    ):
        relative = path.relative_to(source)
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            raise ValueError(f"generated cache in frozen source: {relative}")
        data = path.read_bytes()
        actual.append({
            "path": relative.as_posix(),
            "bytes": len(data),
            "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
        })
    if actual != expected:
        raise ValueError("source snapshot differs from its immutable manifest")
    if content_hash(actual) != source_hash:
        raise ValueError("source snapshot content hash mismatch")


def copy_source(destination: Path, source_root: Path):
    for name in ALLOWED:
        source = source_root / name
        target = destination / name
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    for name in PREVIEW_METADATA:
        shutil.copy2(ROOT / name, destination / name)
    for path in destination.rglob("*"):
        if path.is_symlink() or any(part in FORBIDDEN_PARTS for part in path.relative_to(destination).parts):
            raise ValueError(f"forbidden package entry: {path.relative_to(destination)}")


def write_zip(source: Path, output: Path):
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files(source):
            relative = Path(PACKAGE_NAME) / path.relative_to(source)
            info = zipfile.ZipInfo(relative.as_posix(), ZIP_TIME)
            executable = path.suffix == ".py"
            info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def main():
    context, source, source_manifest = load_build_context()
    if not source.is_dir():
        raise SystemExit("maintainer source snapshot directory is missing")
    if not source_manifest.is_file():
        raise SystemExit("maintainer source snapshot manifest is missing")
    validate_frozen_source(source, source_manifest, context["source_content_sha256"])
    DIST.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="preview-build-", dir=str(DIST)) as temporary:
        stage = Path(temporary) / PACKAGE_NAME
        stage.mkdir()
        copy_source(stage, source)
        package_inventory, content_hash = inventory(stage)
        zip_stage = Path(temporary) / "product-usage-outreach-preview.zip"
        write_zip(stage, zip_stage)
        final_dir = DIST / PACKAGE_NAME
        final_zip = DIST / zip_stage.name
        if final_dir.exists():
            shutil.rmtree(final_dir)
        if final_zip.exists():
            final_zip.unlink()
        shutil.copytree(stage, final_dir)
        shutil.copy2(zip_stage, final_zip)
    manifest = {
        "schema_version": "preview-release-1",
        "version": VERSION,
        "label": "PREVIEW / EARLY TESTING",
        "source": "maintainer-verified immutable preview snapshot",
        "package_content_sha256": content_hash,
        "zip": {"path": final_zip.name, "bytes": final_zip.stat().st_size,
                "sha256": "sha256:" + sha256(final_zip)},
        "directory": {"path": PACKAGE_NAME, "files": len(package_inventory),
                      "bytes": sum(item["bytes"] for item in package_inventory)},
        "excluded": ["evals", "build", "openspec", ".git", ".codex", "__pycache__"],
        "limitations": ["early testing only", "no production data", "no external actions",
                        "non-Codex surfaces untested"],
        "files": package_inventory,
    }
    manifest_path = DIST / "preview-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksum = f"{sha256(final_zip)}  {final_zip.name}\n"
    (DIST / "SHA256SUMS").write_text(checksum, encoding="utf-8")
    print(json.dumps({"status": "built", "version": VERSION,
                      "zip_sha256": "sha256:" + sha256(final_zip),
                      "files": len(package_inventory)}, sort_keys=True))


if __name__ == "__main__":
    main()
