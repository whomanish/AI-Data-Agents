# 0.1.0-preview.1 release notes

**Label:** Preview / early testing

This prerelease makes a maintainer-verified immutable source snapshot available
for controlled, local installation feedback before the formal v1 release gates
are complete.

## Included

- canonical skill instructions and agent metadata;
- blank organization-overlay template;
- deterministic local control and audience-pipeline scripts;
- schemas and implementation references;
- an in-package preview warning;
- deterministic ZIP, content manifest, checksum, and offline smoke checker.

## Tested boundary

The ZIP has been reproducibly built twice and installed into a fresh temporary
directory. Its wrapper layout, required files, JSON parsing, Python syntax,
checksum, absence of symlinks, and exclusion of evaluation/build material were
verified locally.

This evidence supports early installation testing only. It is not independent
surface conformance or production-release sign-off.

## Excluded and unsupported

- production data, credentials, live organization overlays, and campaign
  outputs;
- evaluation suites, blind-evaluation material, build history, and review
  evidence;
- external send, upload, publication, scheduling, or activation;
- support claims for ChatGPT app, Claude app, or Claude Code.

## Feedback

Report the operating system, Codex version, preview version, ZIP checksum,
installation path, testing mode, and non-sensitive reproduction steps. Never
attach secrets, PII, recipient rows, access tokens, or live organization state.
