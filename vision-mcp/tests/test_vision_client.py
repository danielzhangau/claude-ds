"""Tests for VisionClient.see() with a mocked OpenAI client.

Covers the request shape (image as base64 data URL, prompt selection),
content-type validation that runs end-to-end through .see(), and
graceful handling of empty model responses.
"""

import base64
from unittest.mock import AsyncMock, MagicMock

import pytest

from clipboard_vision_mcp.server import DEFAULT_PROMPT, VisionClient

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def png_file(tmp_path):
    p = tmp_path / "img.png"
    p.write_bytes(PNG_MAGIC + b"\x00" * 64)
    return p


def _mock_completion(text):
    """Build a minimal mock matching openai's ChatCompletion shape."""
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    completion = MagicMock()
    completion.choices = [choice]
    return completion


def _patch_openai(client, response_text):
    """Replace the AsyncOpenAI .chat.completions.create with an AsyncMock."""
    create_mock = AsyncMock(return_value=_mock_completion(response_text))
    client.client = MagicMock()
    client.client.chat = MagicMock()
    client.client.chat.completions = MagicMock()
    client.client.chat.completions.create = create_mock
    return create_mock


# ---------------------------------------------------------------------------
# Request shape
# ---------------------------------------------------------------------------


class TestSeeRequestShape:
    async def test_image_sent_as_base64_data_url(self, png_file):
        client = VisionClient(api_key="fake", base_url="https://fake.example")
        create_mock = _patch_openai(client, "a tiny red square")

        result = await client.see(str(png_file))

        assert result == "a tiny red square"
        create_mock.assert_awaited_once()
        messages = create_mock.await_args.kwargs["messages"]
        image_content = messages[0]["content"][1]
        assert image_content["type"] == "image_url"
        url = image_content["image_url"]["url"]
        assert url.startswith("data:image/png;base64,")
        # round-trip: the base64 payload must decode back to the original file.
        b64 = url.split(",", 1)[1]
        assert base64.b64decode(b64) == png_file.read_bytes()

    async def test_default_prompt_when_no_question(self, png_file):
        client = VisionClient(api_key="fake")
        create_mock = _patch_openai(client, "desc")

        await client.see(str(png_file))

        messages = create_mock.await_args.kwargs["messages"]
        assert messages[0]["content"][0]["text"] == DEFAULT_PROMPT

    async def test_user_question_overrides_default_prompt(self, png_file):
        client = VisionClient(api_key="fake")
        create_mock = _patch_openai(client, "answer")

        await client.see(str(png_file), question="how many cats?")

        messages = create_mock.await_args.kwargs["messages"]
        assert messages[0]["content"][0]["text"] == "how many cats?"


# ---------------------------------------------------------------------------
# Validation runs before API call
# ---------------------------------------------------------------------------


class TestSeeValidation:
    async def test_rejects_non_image_extension(self, tmp_path):
        txt = tmp_path / "notes.txt"
        txt.write_text("hello")
        client = VisionClient(api_key="fake")
        create_mock = _patch_openai(client, "should not be called")

        with pytest.raises(ValueError, match="only image files are allowed"):
            await client.see(str(txt))
        create_mock.assert_not_awaited()

    async def test_rejects_bad_magic_bytes(self, tmp_path):
        """File has .png extension but content is plain text."""
        fake = tmp_path / "fake.png"
        fake.write_bytes(b"this is not a png at all")
        client = VisionClient(api_key="fake")
        create_mock = _patch_openai(client, "should not be called")

        with pytest.raises(ValueError, match="does not look like"):
            await client.see(str(fake))
        create_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# Response handling
# ---------------------------------------------------------------------------


class TestSeeResponseHandling:
    async def test_none_content_returns_empty_string(self, png_file):
        """When the vision API returns content=None, see() must not crash."""
        client = VisionClient(api_key="fake")
        _patch_openai(client, None)

        result = await client.see(str(png_file))
        assert result == ""
