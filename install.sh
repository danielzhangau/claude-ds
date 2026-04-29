#!/usr/bin/env bash
set -euo pipefail

# claude-ds installer
# Sets up DeepSeek V4 as a backend for Claude Code with Vision MCP support.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
MCP_INSTALL_DIR="$CLAUDE_DIR/mcp-servers/vision"
SHELL_RC=""

# Colors (disabled if not a terminal)
if [ -t 1 ]; then
  RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; BLUE=''; NC=''
fi

info()  { echo -e "${BLUE}[info]${NC} $*"; }
ok()    { echo -e "${GREEN}[ok]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
error() { echo -e "${RED}[error]${NC} $*" >&2; }

# --- Uninstall mode ---
if [[ "${1:-}" == "--uninstall" ]]; then
  echo "Uninstalling claude-ds..."

  # Remove shell functions
  for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
    if [ -f "$rc" ] && grep -q "claude-ds.sh" "$rc"; then
      # Remove the source line
      sed -i.bak '/claude-ds\.sh/d' "$rc"
      sed -i.bak '/DEEPSEEK_API_KEY/d' "$rc"
      rm -f "$rc.bak"
      ok "Removed claude-ds from $rc"
    fi
  done

  # Remove MCP server
  if [ -d "$MCP_INSTALL_DIR" ]; then
    rm -rf "$MCP_INSTALL_DIR"
    ok "Removed Vision MCP server"
  fi

  # Note: we don't auto-modify mcp.json, settings.json, or CLAUDE.md
  # because users may have other customizations
  warn "Manual cleanup needed:"
  warn "  1. Remove 'vision' entry from $CLAUDE_DIR/mcp.json"
  warn "  2. Remove vision-guard hook from $CLAUDE_DIR/settings.json"
  warn "  3. Remove Vision MCP section from $CLAUDE_DIR/CLAUDE.md"
  warn "  4. Remove 'mcp__vision' from permissions in $CLAUDE_DIR/settings.json"
  echo "Done."
  exit 0
fi

# --- Pre-flight checks ---
echo ""
echo "claude-ds installer"
echo "==================="
echo ""

# Check claude CLI
if ! command -v claude &>/dev/null; then
  error "Claude Code CLI not found. Install it first:"
  error "  npm install -g @anthropic-ai/claude-code"
  exit 1
fi
ok "Claude Code CLI found: $(which claude)"

# Check Python 3.10+
if ! command -v python3 &>/dev/null; then
  error "Python 3 not found. Install Python 3.10 or later."
  exit 1
fi
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
  error "Python 3.10+ required (found $PY_VERSION)"
  exit 1
fi
ok "Python $PY_VERSION"

# Check jq (needed by vision-guard hook)
if ! command -v jq &>/dev/null; then
  warn "jq not found. Installing..."
  if command -v brew &>/dev/null; then
    brew install jq
  elif command -v apt-get &>/dev/null; then
    sudo apt-get install -y jq
  else
    error "Please install jq manually: https://jqlang.github.io/jq/download/"
    exit 1
  fi
fi
ok "jq found"

# Check pngpaste on macOS (optional but recommended)
if [[ "$(uname)" == "Darwin" ]] && ! command -v pngpaste &>/dev/null; then
  warn "pngpaste not found (recommended for clipboard support on macOS)"
  if command -v brew &>/dev/null; then
    read -rp "Install pngpaste via Homebrew? [Y/n] " yn
    if [[ "${yn:-Y}" =~ ^[Yy]$ ]]; then
      brew install pngpaste
      ok "pngpaste installed"
    fi
  else
    warn "Install manually: brew install pngpaste"
  fi
fi

# Detect shell
if [ -f "$HOME/.zshrc" ]; then
  SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
  SHELL_RC="$HOME/.bashrc"
else
  SHELL_RC="$HOME/.zshrc"
  touch "$SHELL_RC"
fi
ok "Shell config: $SHELL_RC"

echo ""

# --- Collect API keys ---
echo "-----------------------------------------"
echo "  Step 1: DeepSeek API key (required)"
echo "-----------------------------------------"
echo ""
if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "Get your key at: https://platform.deepseek.com/api_keys"
  echo "(input is hidden for security)"
  echo ""
  read -rsp "  DEEPSEEK_API_KEY: " ds_key
  echo ""
  if [ -z "$ds_key" ]; then
    error "DeepSeek API key is required."
    exit 1
  fi
  ok "Key received"
else
  ds_key="$DEEPSEEK_API_KEY"
  ok "Using DEEPSEEK_API_KEY from environment"
fi

echo ""
echo "-----------------------------------------"
echo "  Step 2: Vision API key (optional)"
echo "-----------------------------------------"
echo ""
echo "Enables image analysis for text-only models."
echo "Any OpenAI-compatible vision API works."
echo "Examples: Alibaba Qwen VL, OpenAI GPT-4o, Groq Llama Vision, local Ollama."
echo ""
echo "Press Enter to skip if you don't need vision support."
echo "(input is hidden for security)"
echo ""
read -rsp "  VISION_API_KEY: " vision_key
echo ""

vision_base=""
vision_model=""
if [ -n "$vision_key" ]; then
  ok "Key received"
  echo ""
  read -rp "  VISION_BASE_URL (e.g., https://api.openai.com/v1): " vision_base
  read -rp "  VISION_MODEL (e.g., gpt-4o, qwen3-vl-plus): " vision_model
  : "${vision_model:=gpt-4o}"
fi

echo ""

# --- Install shell functions ---
info "Installing shell functions..."

# Remove old entries if present
if grep -q "claude-ds.sh\|# claude-ds:" "$SHELL_RC" 2>/dev/null; then
  # Remove old block
  sed -i.bak '/# claude-ds: DeepSeek/,/^$/d' "$SHELL_RC"
  sed -i.bak '/claude-ds\.sh/d' "$SHELL_RC"
  sed -i.bak '/DEEPSEEK_API_KEY/d' "$SHELL_RC"
  rm -f "$SHELL_RC.bak"
fi

cat >> "$SHELL_RC" << SHELL_BLOCK

# claude-ds: DeepSeek V4 backend for Claude Code
export DEEPSEEK_API_KEY="$ds_key"
source "$SCRIPT_DIR/scripts/claude-ds.sh"
SHELL_BLOCK

ok "Added claude-ds and claude-ds-flash to $SHELL_RC"

# --- Install Vision MCP server ---
if [ -n "$vision_key" ]; then
  info "Installing Vision MCP server..."

  mkdir -p "$MCP_INSTALL_DIR"

  # Create venv and install
  if [ ! -d "$MCP_INSTALL_DIR/.venv" ]; then
    python3 -m venv "$MCP_INSTALL_DIR/.venv"
  fi

  # Copy source
  cp -r "$SCRIPT_DIR/vision-mcp/clipboard_vision_mcp" "$MCP_INSTALL_DIR/"
  cp "$SCRIPT_DIR/vision-mcp/pyproject.toml" "$MCP_INSTALL_DIR/"

  # Install dependencies
  "$MCP_INSTALL_DIR/.venv/bin/pip" install -q -e "$MCP_INSTALL_DIR"

  ok "Vision MCP server installed at $MCP_INSTALL_DIR"

  # --- Configure MCP in Claude ---
  info "Configuring MCP server..."

  MCP_JSON="$CLAUDE_DIR/mcp.json"
  PYTHON_PATH="$MCP_INSTALL_DIR/.venv/bin/python"

  if [ -f "$MCP_JSON" ]; then
    # Add vision entry to existing mcp.json
    if jq -e '.mcpServers.vision' "$MCP_JSON" &>/dev/null; then
      warn "Vision MCP already configured in $MCP_JSON (skipping)"
    else
      jq --arg py "$PYTHON_PATH" \
         --arg key "$vision_key" \
         --arg base "$vision_base" \
         --arg model "$vision_model" \
         '.mcpServers.vision = {
           "command": $py,
           "args": ["-m", "clipboard_vision_mcp.server"],
           "env": {
             "VISION_API_KEY": $key,
             "VISION_BASE_URL": $base,
             "VISION_MODEL": $model
           },
           "description": "Image analysis via vision model (gives text-only LLMs vision capability)"
         }' "$MCP_JSON" > "$MCP_JSON.tmp" && mv "$MCP_JSON.tmp" "$MCP_JSON"
      ok "Added vision server to $MCP_JSON"
    fi
  else
    # Create new mcp.json
    jq -n --arg py "$PYTHON_PATH" \
       --arg key "$vision_key" \
       --arg base "$vision_base" \
       --arg model "$vision_model" \
       '{mcpServers: {vision: {
          command: $py,
          args: ["-m", "clipboard_vision_mcp.server"],
          env: {VISION_API_KEY: $key, VISION_BASE_URL: $base, VISION_MODEL: $model},
          description: "Image analysis via vision model (gives text-only LLMs vision capability)"
        }}}' > "$MCP_JSON"
    ok "Created $MCP_JSON"
  fi

  # --- Configure settings.json ---
  info "Configuring settings..."

  SETTINGS_JSON="$CLAUDE_DIR/settings.json"
  HOOK_PATH="$SCRIPT_DIR/scripts/vision-guard.sh"
  chmod +x "$HOOK_PATH"

  if [ -f "$SETTINGS_JSON" ]; then
    # Add mcp__vision permission if not present
    if ! jq -e '.permissions.allow | index("mcp__vision")' "$SETTINGS_JSON" &>/dev/null; then
      jq '.permissions.allow += ["mcp__vision"]' "$SETTINGS_JSON" > "$SETTINGS_JSON.tmp" \
        && mv "$SETTINGS_JSON.tmp" "$SETTINGS_JSON"
      ok "Added mcp__vision permission"
    fi

    # Add vision-guard hook if not present
    if ! jq -e '.hooks.PreToolUse[] | select(.matcher == "Read") | .hooks[] | select(.command | contains("vision-guard"))' "$SETTINGS_JSON" &>/dev/null; then
      jq --arg cmd "$HOOK_PATH" \
         '.hooks.PreToolUse = [
           {matcher: "Read", hooks: [{type: "command", command: $cmd, timeout: 5}]}
         ] + .hooks.PreToolUse' "$SETTINGS_JSON" > "$SETTINGS_JSON.tmp" \
        && mv "$SETTINGS_JSON.tmp" "$SETTINGS_JSON"
      ok "Added vision-guard hook"
    fi
  else
    warn "$SETTINGS_JSON not found. Create it manually or copy from examples/."
  fi

  # --- Add CLAUDE.md instructions ---
  CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
  if [ -f "$CLAUDE_MD" ]; then
    if ! grep -q "mcp__vision__see_image" "$CLAUDE_MD"; then
      echo "" >> "$CLAUDE_MD"
      cat "$SCRIPT_DIR/examples/claude-md-additions.md" >> "$CLAUDE_MD"
      ok "Added Vision MCP instructions to $CLAUDE_MD"
    else
      warn "Vision MCP instructions already in $CLAUDE_MD (skipping)"
    fi
  else
    cp "$SCRIPT_DIR/examples/claude-md-additions.md" "$CLAUDE_MD"
    ok "Created $CLAUDE_MD with Vision MCP instructions"
  fi

  ok "Vision support fully configured"
fi

# --- Done ---
echo ""
echo "========================================="
echo ""
ok "Installation complete!"
echo ""
echo "  Restart your shell or run:"
echo "    source $SHELL_RC"
echo ""
echo "  Then use:"
echo "    claude-ds          # V4-Pro mode (complex tasks)"
echo "    claude-ds-flash    # V4-Flash mode (quick tasks)"
echo ""
if [ -n "$vision_key" ]; then
  echo "  Vision support is enabled."
  echo "  The model can use see_image / see_clipboard to analyze images."
  echo ""
fi
