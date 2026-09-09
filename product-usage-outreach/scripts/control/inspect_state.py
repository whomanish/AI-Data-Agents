#!/usr/bin/env python3
"""Print a compact, non-PII inspection of validated overlay state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from runtime_validation import ROOT, ValidationError
from validate_state import validate_overlay_state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument("--installed-core", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        snapshot = validate_overlay_state(args.overlay, args.installed_core)
    except ValidationError as exc:
        print(json.dumps({"status": "rejected", "diagnostic": exc.code, "location": exc.location}, sort_keys=True))
        return 2
    manifest, registry, index = snapshot["manifest"], snapshot["registry"], snapshot["profile_index"]
    capabilities = [{"id": item["capability_id"], "maturity": item["maturity"],
                     "blocked": bool(item["blockers"])} for item in registry["capabilities"]]
    profiles = [{"id": item["profile_id"], "status": item["status"], "channel": item["channel"],
                 "deliverable": item["deliverable"]} for item in index["profiles"]]
    # This reports stored state only; it deliberately makes no runtime-readiness claim.
    print(json.dumps({"status": "valid", "organization_id": manifest["organization_id"],
                      "persistence_class": manifest["persistence_class"], "profile_status": registry["profile_status"],
                      "capabilities": capabilities, "profiles": profiles}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
