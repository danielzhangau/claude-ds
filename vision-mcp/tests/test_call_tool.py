"""Tests for the MCP `call_tool` dispatcher in server.py.

Covers the dispatch paths around the module-level `vision_client` singleton:
  - No client configured -> friendly error response
  - see_image -> delegates to VisionClient.see
  - see_clipboard -> save_clipboard_image -> see -> temp cleanup
  - ClipboardError -> formatted message, no API call
  - httpx.TimeoutException / ConnectError -> user-friendly translations
  - Generic exceptions surfaced with type name
  - Unknown tool name handled gracefully
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from clipboard_vision_mcp import server
from clipboard_vision_mcp.clipboard import ClipboardError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_vision_client():
    """Each test starts with vision_client = None; restore after."""
    original = server.vision_client
    server.vision_client = None
    yield
    server.vision_client = original


def _text(result):
    """Extract the text from a list[TextContent] response."""
    assert len(result) == 1
    return result[0].text


# ---------------------------------------------------------------------------
# No client configured
# ---------------------------------------------------------------------------


class TestNoClientConfigured:
    async def test_returns_error_message_without_crashing(self):
        result = await server.call_tool("see_image", {"image_path": "/tmp/x.png"})
        assert "No vision API configured" in _text(result)
        assert "VISION_API_KEY" in _text(result)


# ---------------------------------------------------------------------------
# see_image
# ---------------------------------------------------------------------------


class TestSeeImageDispatch:
    async def test_calls_vision_client_with_path_and_question(self):
        mock_client = MagicMock()
        mock_client.see = AsyncMock(return_value="described")
        server.vision_client = mock_client

        result = await server.call_tool(
            "see_image", {"image_path": "/tmp/x.png", "question": "what color?"}
        )

        assert _text(result) == "described"
        mock_client.see.assert_awaited_once_with("/tmp/x.png", "what color?")

    async def test_question_optional(self):
        mock_client = MagicMock()
        mock_client.see = AsyncMock(return_value="generic description")
        server.vision_client = mock_client

        result = await server.call_tool("see_image", {"image_path": "/tmp/x.png"})

        assert _text(result) == "generic description"
        # question should be None when not provided
        mock_client.see.assert_awaited_once_with("/tmp/x.png", None)


# ---------------------------------------------------------------------------
# see_clipboard
# ---------------------------------------------------------------------------


class TestSeeClipboardDispatch:
    async def test_happy_path_saves_calls_see_and_cleans_up(self, tmp_path):
        clip_file = tmp_path / "clip.png"
        clip_file.write_bytes(b"fake")
        mock_client = MagicMock()
        mock_client.see = AsyncMock(return_value="clipboard analyzed")
        server.vision_client = mock_client

        with patch.object(server, "save_clipboard_image", return_value=str(clip_file)):
            result = await server.call_tool("see_clipboard", {"question": "what?"})

        assert _text(result) == "clipboard analyzed"
        mock_client.see.assert_awaited_once_with(str(clip_file), "what?")
        # Temp file must be removed even on success
        assert not clip_file.exists()

    async def test_temp_file_removed_even_when_see_raises(self, tmp_path):
        clip_file = tmp_path / "clip.png"
        clip_file.write_bytes(b"fake")
        mock_client = MagicMock()
        mock_client.see = AsyncMock(side_effect=RuntimeError("api blew up"))
        server.vision_client = mock_client

        with patch.object(server, "save_clipboard_image", return_value=str(clip_file)):
            result = await server.call_tool("see_clipboard", {})

        # Exception is caught and formatted, but the temp file must still be gone.
        assert "RuntimeError" in _text(result)
        assert not clip_file.exists()

    async def test_clipboard_error_returns_message_without_calling_see(self):
        mock_client = MagicMock()
        mock_client.see = AsyncMock()
        server.vision_client = mock_client

        with patch.object(
            server, "save_clipboard_image", side_effect=ClipboardError("empty clipboard")
        ):
            result = await server.call_tool("see_clipboard", {})

        assert "Clipboard error" in _text(result)
        assert "empty clipboard" in _text(result)
        mock_client.see.assert_not_awaited()


# ---------------------------------------------------------------------------
# Error translation
# ---------------------------------------------------------------------------


class TestErrorTranslation:
    async def test_timeout_translated_to_friendly_message(self):
        mock_client = MagicMock()
        mock_client.see = AsyncMock(side_effect=httpx.TimeoutException("slow"))
        server.vision_client = mock_client

        result = await server.call_tool("see_image", {"image_path": "/tmp/x.png"})
        text = _text(result)

        assert "timed out" in text
        assert str(server.API_TIMEOUT) in text

    async def test_connect_error_translated_to_friendly_message(self):
        mock_client = MagicMock()
        mock_client.see = AsyncMock(side_effect=httpx.ConnectError("dns fail"))
        server.vision_client = mock_client

        result = await server.call_tool("see_image", {"image_path": "/tmp/x.png"})
        text = _text(result)

        assert "Cannot connect" in text
        assert "VISION_BASE_URL" in text

    async def test_generic_exception_surfaces_type_name(self):
        mock_client = MagicMock()
        mock_client.see = AsyncMock(side_effect=ValueError("bad path"))
        server.vision_client = mock_client

        result = await server.call_tool("see_image", {"image_path": "/tmp/x.png"})
        text = _text(result)

        assert "ValueError" in text
        assert "bad path" in text


# ---------------------------------------------------------------------------
# Unknown tool
# ---------------------------------------------------------------------------


class TestUnknownTool:
    async def test_unknown_tool_name_returns_message(self):
        server.vision_client = MagicMock()

        result = await server.call_tool("not_a_real_tool", {})
        assert "Unknown tool" in _text(result)
        assert "not_a_real_tool" in _text(result)
