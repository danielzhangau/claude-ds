# claude-ds

> Use DeepSeek V4 as a drop-in backend for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) -- same harness, fraction of the cost.

Claude Code's harness (multi-layer context compression, Agent Teams, 24 tools, Git integration) is what makes it powerful -- the model is swappable. This project packages a production-ready DeepSeek V4 configuration with:

- **Optimized environment variables** audited against Claude Code's binary (50+ vars checked, critical ones identified)
- **Vision MCP server** that gives text-only models the ability to see images via any OpenAI-compatible vision API
- **PreToolUse hook** that automatically redirects image file reads to the Vision MCP when running on text-only backends
- **One-line installer** that sets everything up

## Cost comparison

| Model | Output cost (per 1M tokens) | Relative to Opus |
|-------|:---------------------------:|:----------------:|
| Claude Opus 4.6 | $25.00 | 1x |
| DeepSeek V4-Pro | $0.87* | **~29x cheaper** |
| DeepSeek V4-Flash | $0.28 | **~89x cheaper** |

\* V4-Pro 75% launch discount effective through May 5, 2026 15:59 UTC. Regular price: $3.48/M.

## Quick start

```bash
# 1. Clone
git clone https://github.com/danielzhangau/claude-ds.git
cd claude-ds

# 2. Install (interactive -- prompts for API keys)
./install.sh

# 3. Restart your shell
source ~/.zshrc  # or ~/.bashrc

# 4. Use it
claude-ds          # V4-Pro -- complex coding, architecture, refactoring
claude-ds-flash    # V4-Flash -- quick fixes, simple tasks
```

## Architecture

<p align="center">
  <img src="assets/architecture.svg" alt="Architecture diagram" width="100%"/>
</p>

## Environment variables (audited)

These variables were identified by reverse-engineering Claude Code v2.1.71's binary. The critical ones missing from most third-party setups are marked.

| Variable | Purpose | Default risk if unset |
|----------|---------|----------------------|
| `ANTHROPIC_BASE_URL` | Route to DeepSeek endpoint | Uses Anthropic (fails without subscription) |
| `ANTHROPIC_AUTH_TOKEN` | DeepSeek API key | Auth failure |
| `ANTHROPIC_MODEL` | Primary conversation model | Uses Claude model name (API error) |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | Opus tier mapping | Uses `claude-opus-*` |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | Sonnet tier mapping | Uses `claude-sonnet-*` |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | Haiku tier mapping | Uses `claude-haiku-*` |
| **`ANTHROPIC_SMALL_FAST_MODEL`** | **Internal lightweight tasks (many refs in binary)** | **Uses `claude-haiku-*` -- silent failures** |
| `CLAUDE_CODE_SUBAGENT_MODEL` | Agent tool subagents | Falls back to Sonnet tier |
| `CLAUDE_CODE_MAX_RETRIES` | API retry on 503 | 0 retries (immediate failure) |
| `CLAUDE_CODE_DISABLE_LEGACY_MODEL_REMAP` | Prevent model name remapping | May corrupt `deepseek-v4-*` names |
| `CLAUDE_CODE_EFFORT_LEVEL` | Thinking depth | `auto` (DeepSeek recommends `max`) |

## Model tier strategy

<p align="center">
  <img src="assets/model-tiers.svg" alt="Model tier routing" width="100%"/>
</p>

## Vision MCP server

The Vision MCP server bridges text-only LLMs to any OpenAI-compatible vision model. It provides two tools:

| Tool | Description |
|------|-------------|
| `see_image` | Analyze an image file on disk (absolute path) |
| `see_clipboard` | Analyze the image currently in the system clipboard |

Both accept an optional `question` parameter. If omitted, returns a thorough description. If provided, answers that specific question about the image.

### Supported vision backends

Any OpenAI-compatible vision API works. Examples:

| Provider | Model | Endpoint |
|----------|-------|----------|
| Alibaba Cloud (Bailian) | `qwen-vl-plus` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| OpenAI | `gpt-4o` | `https://api.openai.com/v1` |
| Groq | `meta-llama/llama-4-scout-17b-16e-instruct` | `https://api.groq.com/openai/v1` |
| Local (Ollama) | `llava` | `http://localhost:11434/v1` |

### Vision guard hook

The `vision-guard.sh` PreToolUse hook provides **deterministic enforcement** (vs probabilistic CLAUDE.md compliance):

<p align="center">
  <img src="assets/vision-flow.svg" alt="Vision guard hook flow" width="100%"/>
</p>

Key properties:
- Intercepts `Read` tool calls for image files (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp`)
- Only activates when `ANTHROPIC_BASE_URL` points to a non-Anthropic endpoint
- Returns exit code 2 with instructions to use `see_image` instead
- **No-op for native Claude Opus** (which has built-in multimodal vision)

## Known limitations

| Limitation | Workaround |
|------------|------------|
| Ctrl+V image paste may cause 400 error on text-only backends | Save image to file, use `see_image`; or use `see_clipboard` |
| Session may be corrupted after image paste error ([#19031](https://github.com/anthropics/claude-code/issues/19031)) | `/rewind` or Esc twice to step back; if unrecoverable, start a new session |
| DeepSeek API 503 during peak hours | `MAX_RETRIES=3` handles this automatically |
| Coherence may degrade past 500K tokens | Use `/compact` in long sessions |
| V4 thinking mode `reasoning_content` may 400 in multi-turn | Restart session if this occurs |
| `claude-ds` cannot `/resume` sessions from `claude` (different backends) | Not fixable -- different API endpoints |
| No native auto-fallback from Anthropic to DeepSeek | Not supported -- use `claude-ds` or `claude` separately |

## Uninstall

```bash
./install.sh --uninstall
```

Or manually:
1. Remove the `claude-ds` / `claude-ds-flash` functions from `~/.zshrc` (or `~/.bashrc`)
2. Remove `"vision"` entry from `~/.claude/mcp.json`
3. Remove `"vision-guard"` hook from `~/.claude/settings.json`
4. Remove `~/.claude/mcp-servers/vision/` directory
5. Remove Vision MCP lines from `~/.claude/CLAUDE.md`

## License

MIT

## Credits

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) by Anthropic
- [DeepSeek V4](https://api-docs.deepseek.com/) by DeepSeek
- Vision MCP server forked from [clipboard-vision-mcp](https://github.com/Capetlevrai/clipboard-vision-mcp) by Capetlevrai
