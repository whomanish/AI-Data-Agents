# Preview installation

## Supported preview path

The documented preview path is a local Codex skill installation on macOS or
Linux with Python 3.11 or newer. This is the only surface claimed by the
preview, and it remains an early-testing claim rather than production support.

Prerequisites:

- Codex with local skills enabled;
- Python 3.11 or newer;
- the downloaded preview ZIP, `preview_smoke.py`, and `SHA256SUMS` from the
  same GitHub prerelease;
- no existing production data copied into the skill directory.

## Verify the download

On macOS:

```sh
shasum -a 256 -c SHA256SUMS
```

On Linux:

```sh
sha256sum -c SHA256SUMS
```

## Install

```sh
mkdir -p ~/.codex/skills
unzip -q product-usage-outreach-preview.zip -d ~/.codex/skills
python3 preview_smoke.py ~/.codex/skills/product-usage-outreach
```

The expected entrypoint is:

```text
~/.codex/skills/product-usage-outreach/SKILL.md
```

Restart Codex, then ask for three general ideas for improving product-usage
outreach. The advisory route should not request organization access or create
an overlay.

## Update

Keep mutable organization state outside the installed skill. Before replacing
an earlier preview, back up any separately stored overlay or campaign workspace.
Remove the old preview directory, extract the new ZIP, and rerun the smoke check.
Never merge an old installed directory into a new version.

## Remove

Delete only the installed preview directory:

```sh
rm -rf ~/.codex/skills/product-usage-outreach
```

This does not remove overlays or campaign workspaces stored elsewhere.

## Troubleshooting

- `SKILL.md not found`: the ZIP was extracted into the wrong directory. The
  path above must exist without an extra wrapper directory.
- Python version failure: install Python 3.11+ and rerun the smoke checker.
- JSON/schema dependency failure during an operational run: install the
  dependency reported by that local script; do not bypass validation.
- Any request to send or upload: stop. Preview testing does not authorize an
  external write.
