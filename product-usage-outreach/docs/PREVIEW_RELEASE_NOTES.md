# 0.1.0-preview.1 release notes

**Label:** Preview / early testing

Product Usage Outreach helps product, growth, and lifecycle teams turn product
behaviour into a defined campaign cohort, reviewable audience decisions, and a
campaign and measurement handoff.

For example, it can help identify active customers who tried a feature but have
not adopted it, explain who qualifies and who does not, apply eligibility and
suppression rules, and prepare an email or in-app outreach plan. It does not
contact users automatically.

This pre-release is available for controlled local installation and synthetic
testing in Codex.

## What you can do

- Ask for product-usage campaign strategy without connecting organization data.
- Turn an ambiguous adoption idea into a precise cohort definition.
- Run a local synthetic cohort and audience workflow.
- Review inclusion, exclusion, suppression, holdout, and unresolved decisions.
- Prepare campaign messaging, timing, measurement, and activation handoffs.
- Verify that external actions remain disabled without separate authorization.

See the repository's synthetic example for a five-workspace walkthrough that
shows how behavioural fit is kept separate from email eligibility.

## Included in the package

- Skill instructions and agent metadata.
- A blank organization-overlay template with no company or customer data.
- Deterministic local control and audience-pipeline scripts.
- Schemas, examples, campaign references, and handoff templates.
- A content manifest, checksum, offline smoke checker, and preview notice.

## Safety boundary

Use synthetic or explicitly approved local test data only. Production customer
or recipient data is not approved for this preview. Sending, uploading,
publishing, scheduling, and activation are disabled and unsupported.

## Tested boundary

The ZIP has been reproducibly built twice and installed into a fresh temporary
directory. Its wrapper layout, required files, JSON parsing, Python syntax,
checksum, absence of symlinks, and exclusion of evaluation/build material were
verified locally.

This evidence supports early installation and usability testing. It is not a
production-readiness or multi-surface compatibility claim.

## Excluded and unsupported

- production data, credentials, live organization overlays, and campaign
  outputs.
- internal evaluation suites, build history, and review evidence.
- external send, upload, publication, scheduling, or activation.
- support claims for ChatGPT app, Claude app, or Claude Code.

## Feedback

Report the operating system, Codex version, preview version, ZIP checksum,
installation path, testing mode, and non-sensitive reproduction steps. Never
attach secrets, PII, recipient rows, access tokens, or live organization state.
