# Packaging and compatibility contract

Build every target artifact from one frozen canonical skill directory. Surface-specific metadata and installation instructions may wrap that source but cannot fork campaign logic, safety rules, schemas, scripts, or universal references.

## Reproducible package boundary

The canonical package contains `SKILL.md`, `agents/`, `assets/organization-overlay/`, `references/`, `schemas/`, `scripts/`, `evals/`, and `compatibility.json` according to the frozen manifest. Exclude repository-only `build/`, `.codex/`, `.git/`, OpenSpec planning artifacts, review reports, live overlays, campaign workspaces, credentials, production data, and blind inputs or oracles.

For every directory and ZIP build:

1. start from the exact frozen canonical content hash;
2. sort relative paths deterministically;
3. normalize permitted archive metadata and timestamps;
4. hash every file and the ordered manifest;
5. ensure the archive opens directly at the skill root without an unintended wrapper directory;
6. compare canonical relative paths and content hashes across package forms;
7. fail if a thin surface addition changes or shadows canonical logic.

Structural equivalence establishes package consistency only. It does not establish runtime support.

## Compatibility status

Maintain [`compatibility.json`](../../compatibility.json) against [`compatibility.schema.json`](../../schemas/compatibility.schema.json). Use only:

- `tested`: the documented package and all cases for the claimed operating modes passed on the recorded product version or date;
- `supported-with-limitations`: applicable cases passed and every unsupported outcome is stated;
- `untested`: structural validation may exist, but the package has not completed the required runtime conformance;
- `unsupported`: required operations are unavailable or unsafe for the stated outcome.

Every `tested` or `supported-with-limitations` record names the package form, tested product version and time, operating modes, persistence strategy, limitations, and immutable evidence references. The evidence records path, SHA-256 hash, and observation time. A package install or upload without the representative runtime workflow remains `untested`.

Mark an affected claim stale by returning it to `untested` when a material host version, package, schema, runtime contract, persistence behavior, or installation path changes. Preserve prior evidence as history outside the released skill; do not present it as current support.

## Target intent

- Codex local and Claude Code local target full execution, subject to actual operation and persistence checks.
- ChatGPT and Claude app packages are capability-gated; claim only modes exercised in the evaluated environment.

Release-time installation instructions identify the artifact, prerequisites, overlay behavior, smoke workflow, update path, backup/export behavior, and removal path for each target. Current platform documentation is rechecked during that release task because installation contracts can change.

The seed record keeps all four targets `untested` until their own conformance evidence exists.
