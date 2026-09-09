#!/usr/bin/env python3
"""Offline structural smoke check for an extracted preview skill."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


REQUIRED = {
    "PREVIEW.md",
    "SKILL.md",
    "agents/openai.yaml",
    "assets/organization-overlay/overlay.json",
    "compatibility.json",
    "references/core/campaign-workflow.md",
    "schemas/execution-profile.schema.json",
    "scripts/control/operational_preflight.py",
    "scripts/pipeline/run_local_profile.py",
}
FORBIDDEN_TOP_LEVEL = {"build", "evals", "openspec", ".git", ".codex"}


def strict_json(path: Path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"non-finite JSON value in {path}: {value}")

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                       parse_constant=constant)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite JSON value in {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_dir", type=Path)
    args = parser.parse_args()
    root = args.skill_dir.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("skill path is not a directory")
    missing = sorted(path for path in REQUIRED if not (root / path).is_file())
    if missing:
        raise ValueError("missing required files: " + ", ".join(missing))
    forbidden = sorted(path.name for path in root.iterdir()
                       if path.name in FORBIDDEN_TOP_LEVEL)
    if forbidden:
        raise ValueError("forbidden preview content: " + ", ".join(forbidden))
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"symlink not allowed: {path.relative_to(root)}")
        if path.is_file() and path.suffix == ".json":
            strict_json(path)
        if path.is_file() and path.suffix == ".py":
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
    entrypoint = (root / "SKILL.md").read_text(encoding="utf-8")
    if not entrypoint.startswith("---\nname: product-usage-outreach\n"):
        raise ValueError("unexpected SKILL.md frontmatter")
    print(json.dumps({"status": "pass", "skill_dir": str(root)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, sort_keys=True),
              file=sys.stderr)
        raise SystemExit(2)
