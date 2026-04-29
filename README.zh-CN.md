# claude-ds

[English](./README.md) | **中文**

> 用 DeepSeek V4 作为 [Claude Code](https://code.claude.com/docs/en/overview) 的后端 -- 同样的工具，几分之一的价格。

## 这是什么？

[Claude Code](https://code.claude.com/docs/en/overview) 是 Anthropic 推出的 AI 编程助手，运行在终端中 -- 它能读取代码库、编辑文件、执行命令、管理 Git。非常好用，但默认模型（Claude Opus）的输出价格高达 **$25 / 百万 token**。

**claude-ds** 让你用 [DeepSeek V4](https://api-docs.deepseek.com/) 替代默认模型来运行 Claude Code。同样的工具、同样的工作流、同样的内置工具 -- 只是**便宜约 7-89 倍**（取决于模型选择）。

| 模型 | 输出价格（每百万 token） | 相对于 Opus |
|------|:----------------------:|:----------:|
| Claude Opus 4.6 | $25.00 | 1x |
| DeepSeek V4-Pro | $3.48 | **约 7 倍** |
| DeepSeek V4-Flash | $0.28 | **约 89 倍** |

## 前置条件

1. **Claude Code CLI** -- `curl -fsSL https://claude.ai/install.sh | bash` 或 `npm install -g @anthropic-ai/claude-code`（[文档](https://code.claude.com/docs/en/overview)）
2. **DeepSeek API key** -- 在 [platform.deepseek.com](https://platform.deepseek.com/api_keys) 获取
3. **Python 3.10+** -- 仅在需要图像识别功能时安装（可选）

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/danielzhangau/claude-ds.git
cd claude-ds

# 2. 安装（交互式 -- 会提示输入 API key）
./install.sh

# 3. 重启终端
source ~/.zshrc  # 或 ~/.bashrc

# 4. 使用
claude-ds          # V4-Pro 模式 -- 复杂编码、架构设计、重构
claude-ds-flash    # V4-Flash 模式 -- 快速修复、简单任务
```

安装完成。`claude-ds` 和 `claude-ds-flash` 是 `claude` 命令的替代品，用法完全一样。Claude Code 的所有功能（斜杠命令、`/compact`、Agent tool、hooks、MCP servers）都照常工作。已知的差异见[已知限制](#已知限制)。

## 包含内容

| 组件 | 功能 |
|------|------|
| **Shell 函数** | `claude-ds` 和 `claude-ds-flash` 命令，已优化环境变量 |
| **Vision MCP 服务器** | 让纯文本模型具备图像识别能力（可选） |
| **Vision guard hook** | 自动将图像读取请求重定向到 Vision MCP |
| **一键安装器** | 交互式完成所有配置 |

## 工作原理

`claude-ds` 命令本质上是一个薄封装，它通过环境变量让 `claude` 指向 DeepSeek 的 API 而非 Anthropic 的。Claude Code 本身无感知 -- DeepSeek 提供了 [Anthropic 兼容端点](https://api-docs.deepseek.com/guides/anthropic_api)。

<p align="center">
  <img src="assets/architecture.svg" alt="架构图" width="100%"/>
</p>

**两种模式：**
- **`claude-ds`**（Pro 模式）-- 主对话使用 V4-Pro（1M 上下文），内部任务使用 V4-Flash。适合复杂工作。
- **`claude-ds-flash`**（Flash 模式）-- 所有任务都用 V4-Flash。最大程度节省成本。

<p align="center">
  <img src="assets/model-tiers.svg" alt="模型层级路由" width="100%"/>
</p>

<details>
<summary><strong>环境变量（进阶）</strong></summary>

以下变量通过逆向工程 Claude Code v2.1.71 的二进制文件识别得出。大多数第三方配置方案中遗漏的关键变量已标注。

| 变量 | 用途 | 未设置时的风险 |
|------|------|--------------|
| `ANTHROPIC_BASE_URL` | 路由到 DeepSeek 端点 | 使用 Anthropic（无订阅会失败） |
| `ANTHROPIC_AUTH_TOKEN` | DeepSeek API key | 认证失败 |
| `ANTHROPIC_MODEL` | 主对话模型 | 使用 Claude 模型名（API 报错） |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | Opus 层级映射 | 使用 `claude-opus-*` |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | Sonnet 层级映射 | 使用 `claude-sonnet-*` |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | Haiku 层级映射 | 使用 `claude-haiku-*` |
| **`ANTHROPIC_SMALL_FAST_MODEL`** | **内部轻量任务（二进制中大量引用）** | **使用 `claude-haiku-*` -- 静默失败** |
| `CLAUDE_CODE_SUBAGENT_MODEL` | Agent tool 子代理 | 回退到 Sonnet 层级 |
| `CLAUDE_CODE_MAX_RETRIES` | API 503 重试次数 | 0 次重试（立即失败） |
| `CLAUDE_CODE_DISABLE_LEGACY_MODEL_REMAP` | 阻止模型名重映射 | 可能破坏 `deepseek-v4-*` 名称 |
| `CLAUDE_CODE_EFFORT_LEVEL` | 思考深度 | `auto`（DeepSeek 推荐 `max`） |

无需手动设置 -- `install.sh` 会自动处理。此表仅供了解底层机制。

</details>

<details>
<summary><strong>Vision MCP 服务器（可选）</strong></summary>

DeepSeek V4 是纯文本模型，无法识别图像。Vision MCP 服务器通过将图像分析请求路由到任意 OpenAI 兼容的视觉模型来弥补这一差距。

**两个工具：**

| 工具 | 描述 |
|------|------|
| `see_image` | 分析磁盘上的图像文件（绝对路径） |
| `see_clipboard` | 分析当前系统剪贴板中的图像 |

两者都接受可选的 `question` 参数。省略则返回详细描述，提供则针对图像回答具体问题。

**支持的视觉后端：**

任何 OpenAI 兼容的视觉 API 均可使用：

| 提供商 | 模型 | 端点 |
|--------|------|------|
| 阿里云（百炼） | `qwen3-vl-plus` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| OpenAI | `gpt-4o` | `https://api.openai.com/v1` |
| Groq | `meta-llama/llama-4-scout-17b-16e-instruct` | `https://api.groq.com/openai/v1` |
| 本地（Ollama） | `llama3.2-vision` | `http://localhost:11434/v1` |

**Vision guard hook：**

`vision-guard.sh` PreToolUse hook 提供确定性拦截 -- 当模型尝试 `Read` 图像文件时，hook 会阻止并重定向到 `see_image`。这比仅靠 CLAUDE.md 指令更可靠。

<p align="center">
  <img src="assets/vision-flow.svg" alt="Vision guard hook 流程" width="100%"/>
</p>

关键特性：
- 拦截对图像文件的 `Read` 调用（`.png`、`.jpg`、`.jpeg`、`.gif`、`.webp`、`.bmp`）
- 仅在 `ANTHROPIC_BASE_URL` 指向非 Anthropic 端点时激活
- 返回 exit code 2 并指示使用 `see_image`
- **对原生 Claude Opus 无效果**（其内置多模态视觉能力）

</details>

## 已知限制

| 限制 | 解决方案 |
|------|---------|
| Ctrl+V 粘贴图片可能导致纯文本后端 400 错误 | 将图片保存为文件后使用 `see_image`；或使用 `see_clipboard` |
| 图片粘贴错误后会话可能损坏（[#19031](https://github.com/anthropics/claude-code/issues/19031)） | `/rewind` 或按两次 Esc 回退；无法恢复则新建会话 |
| DeepSeek API 高峰期 503 | `MAX_RETRIES=3` 自动处理 |
| 超过 500K token 后连贯性可能下降 | 在长会话中使用 `/compact` |
| V4 思考模式 `reasoning_content` 在多轮对话中可能 400 | 重启会话 |
| `claude-ds` 无法 `/resume` 来自 `claude` 的会话 | 无法解决 -- 不同的 API 端点 |
| 无法自动从 Anthropic 切换到 DeepSeek | 不支持 -- 分开使用 `claude-ds` 或 `claude` |

## 卸载

```bash
./install.sh --uninstall
```

或手动操作：
1. 从 `~/.zshrc`（或 `~/.bashrc`）中移除 `claude-ds` / `claude-ds-flash` 函数
2. 从 `~/.claude/mcp.json` 中移除 `"vision"` 条目
3. 从 `~/.claude/settings.json` 中移除 `"vision-guard"` hook
4. 删除 `~/.claude/mcp-servers/vision/` 目录
5. 从 `~/.claude/CLAUDE.md` 中移除 Vision MCP 相关内容

## 许可证

MIT

## 致谢

- [Claude Code](https://code.claude.com/docs/en/overview) by Anthropic
- [DeepSeek V4](https://api-docs.deepseek.com/) by DeepSeek
- Vision MCP server fork 自 [clipboard-vision-mcp](https://github.com/Capetlevrai/clipboard-vision-mcp) by Capetlevrai
