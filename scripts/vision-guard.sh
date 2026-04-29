#!/bin/bash
# Claude Code PreToolUse hook: redirect image Read calls to Vision MCP
#
# Only activates when ANTHROPIC_BASE_URL points to a non-Anthropic endpoint.
# When a text-only model tries to Read an image file, this hook blocks the
# call and instructs the model to use mcp__vision__see_image instead.
#
# Behavior by mode:
#   claude (native Opus)  -> no-op (Opus has built-in vision)
#   claude-ds / claude-ds-flash -> blocks image Read, guides to Vision MCP

# Skip if using native Anthropic API
if [ -z "$ANTHROPIC_BASE_URL" ] || [[ "$ANTHROPIC_BASE_URL" == *"anthropic.com"* ]]; then
  exit 0
fi

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')

if [ "$TOOL" = "Read" ]; then
  FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
  EXT="${FILE_PATH##*.}"
  EXT_LOWER=$(echo "$EXT" | tr '[:upper:]' '[:lower:]')

  case "$EXT_LOWER" in
    png|jpg|jpeg|gif|webp|bmp)
      cat <<'EOF'
BLOCKED. You MUST call mcp__vision__see_image now with the same path. Do NOT say "cannot view".
EOF
      exit 2
      ;;
  esac
fi

exit 0
