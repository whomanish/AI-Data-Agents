# Preview verification

## What this evidence means

The preview can be downloaded, checked, installed in the documented local
environment, and exercised with controlled synthetic scenarios. Its package is
reproducible and its deterministic validation tests pass.

This evidence does not approve production data, guarantee compatibility with
unlisted environments, or authorize a real campaign action. It supports early
testing of the skill's reasoning, local workflow, outputs, and safety
boundaries.

## Artifact identity

- Version: `0.1.0-preview.1`
- Source: maintainer-verified immutable preview snapshot
- Preview ZIP SHA-256:
  `6aec8714f34e5273abf50aa55e3765520a7d412e798d110d3740b8e1a9ffde8f`
- Preview package content SHA-256:
  `41fc024b24b86eec40631ec579a047fbf99bb2cdf8571a24c715e89b4756e244`
- Archive size: 131,449 bytes
- Installed files: 132

## Local verification environment

- Date: 2026-09-09
- Operating system: macOS 26.5.2, arm64
- Codex CLI: 0.153.4
- Python: 3.12.3

## Checks completed

- The source directory and its immutable manifest matched before packaging.
- Two consecutive preview builds produced byte-identical ZIP files.
- The release checksum verified successfully.
- The ZIP extracted with exactly one `product-usage-outreach/` wrapper.
- A fresh temporary installation passed the offline smoke checker.
- All packaged JSON files parsed strictly and all packaged Python files
  compiled in memory.
- No symlink, evaluator, build history, internal specification source,
  repository metadata, Codex workspace metadata, or Python cache was present
  in the package.
- The normal evaluation harness passed 123/123 cases with zero failures or
  errors.
- The repository deterministic unit suite passed 141/141 tests.
- Git diff hygiene passed.

## Interpretation

These are maintainer-run preview checks. They establish reproducibility,
structural integrity, and a controlled local installation path. They are not
production-data approval, production support, or a multi-surface compatibility
claim.
