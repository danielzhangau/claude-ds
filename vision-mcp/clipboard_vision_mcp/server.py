"""MCP server that gives text-only LLMs the ability to see images.

Only two tools:
  - see_image    : analyze an image file on disk.
  - see_clipboard: analyze the image currently in the system clipboard.

Both accept an optional `question` parameter. If omitted, the vision model
returns a thorough, neutral description. If provided, the vision model
answers that specific question about the image. This keeps the MCP layer
thin -- all reasoning and prompt crafting stays with the calling LLM.

Supported backends (via env vars):
  - Any OpenAI-compatible API: VISION_API_KEY + VISION_BASE_URL
  - Groq: GROQ_API_KEY
"""

from __future__ import annotations

import asyncio
import base64
import os
from pathlib import Path
from typing import Any

import aiofiles
import httpx
from openai import AsyncOpenAI
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .clipboard import ClipboardError, save_clipboard_image

SERVER_NAME = "vision-mcp"
SERVER_VERSION = "1.0.0"
VISION_MODEL = os.environ.get("VISION_MODEL", "gpt-4o")

DEFAULT_PROMPT = (
    "Describe this image thoroughly and accurately. "
    "Include all visible text, layout, structure, colors, and any notable details."
)

# Security: only allow image files, bound size to prevent exfiltration.
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20 MB
IMAGE_MAGIC_PREFIXES = (
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"\xff\xd8\xff",        # JPEG
    b"GIF87a",
    b"GIF89a",
    b"RIFF",                # WEBP (RIFF....WEBP)
    b"BM",                  # BMP
)

API_TIMEOUT = int(os.environ.get("VISION_TIMEOUT", "45"))  # seconds


def _validate_image_path(path_str: str) -> Path:
    p = Path(path_str).resolve()
    if not p.is_file():
        raise ValueError(f"Not a file: {path_str}")
    if p.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Refusing to read '{p.suffix}' -- only image files are allowed "
            f"({', '.join(sorted(ALLOWED_EXTENSIONS))})."
        )
    size = p.stat().st_size
    if size > MAX_IMAGE_BYTES:
        raise ValueError(f"Image too large: {size} bytes (max {MAX_IMAGE_BYTES}).")
    return p


def _validate_magic(data: bytes) -> None:
    if not any(data.startswith(m) for m in IMAGE_MAGIC_PREFIXES):
        raise ValueError("File content does not look like a supported image.")


server = Server(SERVER_NAME)


class VisionClient:
    def __init__(self, api_key: str, base_url: str | None = None):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=httpx.Timeout(API_TIMEOUT, connect=10.0),
        )

    async def see(self, image_path: str, question: str | None = None) -> str:
        p = _validate_image_path(image_path)
        async with aiofiles.open(p, "rb") as f:
            data = await f.read()
        _validate_magic(data)

        suffix = p.suffix.lower()
        mime = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
        }.get(suffix, "image/png")
        b64 = base64.b64encode(data).decode("utf-8")

        response = await self.client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question or DEFAULT_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        },
                    ],
                }
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        return response.choices[0].message.content or ""


vision_client: VisionClient | None = None


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="see_image",
            description=(
                "Analyze an image file using a vision model. "
                "Use this when you need to understand the contents of any image "
                "(screenshots, diagrams, photos, charts, documents, etc.). "
                "Pass an optional `question` to ask something specific about the image, "
                "or omit it to get a thorough description."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Absolute path to the image file.",
                    },
                    "question": {
                        "type": "string",
                        "description": "Optional question to ask about the image.",
                    },
                },
                "required": ["image_path"],
            },
        ),
        Tool(
            name="see_clipboard",
            description=(
                "Analyze the image currently in the system clipboard using a vision model. "
                "Use this when the user has copied or screenshotted something and wants "
                "you to look at it. Pass an optional `question` to ask something specific, "
                "or omit it to get a thorough description."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Optional question to ask about the clipboard image.",
                    },
                },
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if vision_client is None:
        return [
            TextContent(
                type="text",
                text="Error: No vision API configured. "
                "Set VISION_API_KEY + VISION_BASE_URL env vars.",
            )
        ]

    try:
        question = arguments.get("question")

        if name == "see_image":
            text = await vision_client.see(arguments["image_path"], question)
        elif name == "see_clipboard":
            try:
                path = save_clipboard_image()
            except ClipboardError as e:
                return [TextContent(type="text", text=f"Clipboard error: {e}")]
            try:
                text = await vision_client.see(path, question)
            finally:
                try:
                    os.unlink(path)
                except OSError:
                    pass
        else:
            text = f"Unknown tool: {name}"

        return [TextContent(type="text", text=text)]
    except httpx.TimeoutException:
        return [TextContent(
            type="text",
            text=f"Error: Vision API timed out after {API_TIMEOUT}s. "
            "The image may be too large or the API is overloaded. Try again.",
        )]
    except httpx.ConnectError:
        return [TextContent(
            type="text",
            text="Error: Cannot connect to vision API. Check network and VISION_BASE_URL.",
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"Vision API error: {type(e).__name__}: {e}")]


async def main() -> None:
    global vision_client
    vision_key = os.environ.get("VISION_API_KEY")
    vision_base = os.environ.get("VISION_BASE_URL")
    groq_key = os.environ.get("GROQ_API_KEY")

    if vision_key:
        vision_client = VisionClient(api_key=vision_key, base_url=vision_base)
    elif groq_key:
        vision_client = VisionClient(
            api_key=groq_key, base_url="https://api.groq.com/openai/v1"
        )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
