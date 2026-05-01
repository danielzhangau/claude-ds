# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in claude-ds, please report it responsibly:

1. **Do NOT open a public issue.**
2. Email the maintainer directly or use [GitHub's private vulnerability reporting](https://github.com/danielzhangau/claude-ds/security/advisories/new).
3. Include a clear description of the vulnerability, steps to reproduce, and potential impact.

You should receive an acknowledgment within 72 hours.

## Scope

Security-relevant areas in this project include:

- **API key handling** -- keys are stored in `~/.zshrc` (or `~/.bashrc`) and `~/.claude/claude-ds-vision-mcp.json`
- **Image path validation** -- `_validate_image_path` and `_validate_magic` in `vision-mcp/clipboard_vision_mcp/server.py`
- **Clipboard access** -- `vision-mcp/clipboard_vision_mcp/clipboard.py`
- **Shell script injection** -- `install.sh` and `scripts/claude-ds.sh`

## Supported Versions

Only the latest version on the `main` branch is supported with security updates.
