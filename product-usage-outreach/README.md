# Product Usage Outreach — Preview

> **PREVIEW / EARLY TESTING:** This repository is not a production release.
> Use it with synthetic or approved local data only. External sending,
> uploading, scheduling, publication, and activation remain out of scope.

Product Usage Outreach is a portable agent skill for turning product-usage
signals into validated cohorts, local audience artifacts, campaign plans, and
reviewable activation handoffs while preserving identity, eligibility,
suppression, privacy, and authorization boundaries.

## Preview status

The current preview is built from a maintainer-verified immutable source
snapshot. Its deterministic local pipeline and selected routing/safety
scenarios have passed controlled synthetic tests. Formal independent QA
consolidation, blind evaluation, multi-surface conformance, and
production-release sign-off are still open.

| Capability | Preview status |
| --- | --- |
| General campaign advice | Available |
| Local deterministic synthetic cohort/audience run | Available |
| Failed quick-check handling | Available |
| Local overlay template | Available |
| External send/upload/activation | Disabled and unsupported |
| Production data | Not approved for preview testing |
| Claude, ChatGPT app, or other surfaces | Untested |

## Install

Download `product-usage-outreach-preview.zip` from the GitHub pre-release and
verify its checksum from `SHA256SUMS`.

```sh
mkdir -p ~/.codex/skills
unzip -q product-usage-outreach-preview.zip -d ~/.codex/skills
python3 preview_smoke.py ~/.codex/skills/product-usage-outreach
```

Read the installed `PREVIEW.md`, then restart Codex. See
[Preview installation](docs/PREVIEW_INSTALLATION.md) for prerequisites,
updates, removal, and troubleshooting.

## Try the preview safely

Start with an advisory request that uses no organization data, or follow the
controlled synthetic walkthrough in [Preview testing](docs/PREVIEW_TESTING.md).
Review [Preview limitations](docs/PREVIEW_LIMITATIONS.md) before testing.
Exact package checks and the local test environment are recorded in
[Preview verification](docs/PREVIEW_VERIFICATION.md).

## Release track

This preview exists to collect early installation and usability feedback. It
does not mark the v1 OpenSpec work complete. Later releases will retain the
same repository and upgrade the preview after the remaining QA, blind tests,
surface conformance, and release gates pass.
