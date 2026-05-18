#!/usr/bin/env bash
# claude-ds: DeepSeek V4 backend for Claude Code
#
# Source this file in your shell profile (~/.zshrc or ~/.bashrc):
#   source /path/to/claude-ds/scripts/claude-ds.sh
#
# Prerequisites:
#   - Claude Code CLI installed (`claude` command available)
#   - DEEPSEEK_API_KEY environment variable set
#
# Environment variables (all optional, with sensible defaults):
#   DEEPSEEK_API_KEY          - Your DeepSeek API key (required)
#   CLAUDE_DS_PRO_MODEL       - Pro model name (default: deepseek-v4-pro[1m])
#   CLAUDE_DS_FLASH_MODEL     - Flash model name (default: deepseek-v4-flash)
#   CLAUDE_DS_ENDPOINT        - API endpoint (default: https://api.deepseek.com/anthropic)
#   CLAUDE_DS_MAX_RETRIES     - API retry count (default: 3)
#   CLAUDE_DS_EFFORT          - Thinking effort level (default: max)
#   CLAUDE_DS_STRICT_MCP      - If "1", pass --strict-mcp-config to isolate from user MCP servers

# Defaults
: "${CLAUDE_DS_PRO_MODEL:=deepseek-v4-pro[1m]}"
: "${CLAUDE_DS_FLASH_MODEL:=deepseek-v4-flash}"
: "${CLAUDE_DS_ENDPOINT:=https://api.deepseek.com/anthropic}"
: "${CLAUDE_DS_MAX_RETRIES:=3}"
: "${CLAUDE_DS_EFFORT:=max}"
: "${CLAUDE_DS_STRICT_MCP:=0}"

# Vision MCP config (only loaded if file exists)
CLAUDE_DS_VISION_MCP="$HOME/.claude/claude-ds-vision-mcp.json"

# Internal: launch claude with DeepSeek env mapping.
#   $1 = main model (drives ANTHROPIC_MODEL and Opus tier)
#   $2 = small/fast model (drives Sonnet, Haiku, subagent, small-fast tiers)
#   $3+ = passthrough args forwarded to claude
_claude_ds_run() {
  if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "Error: DEEPSEEK_API_KEY is not set." >&2
    echo "Get your API key at https://platform.deepseek.com/api_keys" >&2
    return 1
  fi

  local main_model="$1"
  local small_model="$2"
  shift 2

  local mcp_args=()
  if [ -f "$CLAUDE_DS_VISION_MCP" ]; then
    mcp_args=(--mcp-config "$CLAUDE_DS_VISION_MCP")
    if [ "$CLAUDE_DS_STRICT_MCP" = "1" ]; then
      mcp_args+=(--strict-mcp-config)
    fi
  fi

  ANTHROPIC_BASE_URL="$CLAUDE_DS_ENDPOINT" \
  ANTHROPIC_AUTH_TOKEN="$DEEPSEEK_API_KEY" \
  ANTHROPIC_MODEL="$main_model" \
  ANTHROPIC_DEFAULT_OPUS_MODEL="$main_model" \
  ANTHROPIC_DEFAULT_SONNET_MODEL="$small_model" \
  ANTHROPIC_DEFAULT_HAIKU_MODEL="$small_model" \
  ANTHROPIC_SMALL_FAST_MODEL="$small_model" \
  CLAUDE_CODE_SUBAGENT_MODEL="$small_model" \
  CLAUDE_CODE_EFFORT_LEVEL="$CLAUDE_DS_EFFORT" \
  CLAUDE_CODE_MAX_RETRIES="$CLAUDE_DS_MAX_RETRIES" \
  CLAUDE_CODE_DISABLE_LEGACY_MODEL_REMAP=1 \
  claude "${mcp_args[@]}" "$@"
}

# claude-ds: Pro mode -- complex coding, architecture, refactoring
# Main conversation uses V4-Pro (1M context), all internal tasks use V4-Flash
claude-ds() {
  _claude_ds_run "$CLAUDE_DS_PRO_MODEL" "$CLAUDE_DS_FLASH_MODEL" "$@"
}

# claude-ds-flash: Flash mode -- quick fixes, simple tasks, maximum savings
# All tiers use V4-Flash (1M context)
claude-ds-flash() {
  _claude_ds_run "$CLAUDE_DS_FLASH_MODEL" "$CLAUDE_DS_FLASH_MODEL" "$@"
}
