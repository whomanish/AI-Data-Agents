# Preview / early testing

This is `product-usage-outreach` version `0.1.0-preview.1`. It is an
installable preview, not a production release.

## What you installed

Product Usage Outreach helps turn a product-usage question into a defined
cohort, reviewable audience decisions, and a campaign and measurement handoff.
It is designed to keep behavioural fit, identity, eligibility, suppression,
holdout, and authorization decisions explicit instead of silently filling in
missing facts.

For example, you can ask it to identify synthetic active customers who tried a
feature but have not adopted it, explain every inclusion and exclusion, and
prepare an email or in-app campaign plan without contacting anyone.

## First safe test

Restart Codex, then ask:

> Use $product-usage-outreach to give me three low-risk ideas for improving
> adoption of a fictional product feature. Do not inspect organization data,
> create files, connect to external systems, or contact anyone.

For a more concrete test, follow `docs/EXAMPLE_WORKFLOW.md` in the GitHub
repository.

## Preview boundary

Use only synthetic or explicitly approved local data. Do not use production
PII, recipient data, credentials, or live organization state. This preview is
not authorized to send, upload, publish, schedule, or activate a campaign.

The tested path is a local Codex installation with Python 3.11 or newer. Other
surfaces and production workflows remain untested and unsupported.

Before testing, read the installation, testing, and limitations documents in
the GitHub repository. Report only non-sensitive information in public issues.
