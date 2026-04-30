"""Tests for image validation functions in server.py.

Covers _validate_image_path (extension, size, existence) and _validate_magic
(magic bytes verification). These are security-critical: they prevent
arbitrary file reads and ensure only real image data is processed.
"""

import os
import tempfile
from pathlib import Path

import pytest

from clipboard_vision_mcp.server import (
    ALLOWED_EXTENSIONS,
    MAX_IMAGE_BYTES,
    _validate_image_path,
    _validate_magic,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def _write_file(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


# ---------------------------------------------------------------------------
# _validate_image_path
# ---------------------------------------------------------------------------

class TestValidateImagePath:
    """Tests for path validation: extension whitelist, size limit, existence."""

    # -- extension checks --

    @pytest.mark.parametrize("ext", sorted(ALLOWED_EXTENSIONS))
    def test_allowed_extensions_accepted(self, tmp_dir, ext):
        p = _write_file(tmp_dir / f"img{ext}", b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        result = _validate_image_path(str(p))
        assert result == p.resolve()

    @pytest.mark.parametrize("ext", [".txt", ".py", ".sh", ".pdf", ".svg", ".exe"])
    def test_disallowed_extensions_rejected(self, tmp_dir, ext):
        p = _write_file(tmp_dir / f"file{ext}", b"not an image")
        with pytest.raises(ValueError, match="only image files are allowed"):
            _validate_image_path(str(p))

    def test_extension_case_insensitive(self, tmp_dir):
        p = _write_file(tmp_dir / "IMG.PNG", b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        result = _validate_image_path(str(p))
        assert result == p.resolve()

    # -- existence checks --

    def test_nonexistent_file_rejected(self, tmp_dir):
        with pytest.raises(ValueError, match="Not a file"):
            _validate_image_path(str(tmp_dir / "nonexistent.png"))

    def test_directory_rejected(self, tmp_dir):
        d = tmp_dir / "subdir.png"
        d.mkdir()
        with pytest.raises(ValueError, match="Not a file"):
            _validate_image_path(str(d))

    # -- size checks --

    def test_file_at_size_limit_accepted(self, tmp_dir):
        p = _write_file(tmp_dir / "big.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * (MAX_IMAGE_BYTES - 8))
        # Should not raise
        _validate_image_path(str(p))

    def test_file_over_size_limit_rejected(self, tmp_dir):
        p = _write_file(tmp_dir / "huge.png", b"\x00" * (MAX_IMAGE_BYTES + 1))
        with pytest.raises(ValueError, match="Image too large"):
            _validate_image_path(str(p))

    def test_empty_file_accepted_by_path_check(self, tmp_dir):
        """An empty file with a valid extension passes path validation.
        (Magic bytes check catches it later.)"""
        p = _write_file(tmp_dir / "empty.png", b"")
        # _validate_image_path only checks extension + size, not content
        result = _validate_image_path(str(p))
        assert result == p.resolve()


# ---------------------------------------------------------------------------
# _validate_magic
# ---------------------------------------------------------------------------

class TestValidateMagic:
    """Tests for magic bytes verification."""

    @pytest.mark.parametrize(
        "header,label",
        [
            (b"\x89PNG\r\n\x1a\n", "PNG"),
            (b"\xff\xd8\xff", "JPEG"),
            (b"GIF87a", "GIF87a"),
            (b"GIF89a", "GIF89a"),
            (b"RIFF\x00\x00\x00\x00WEBP", "WEBP"),
            (b"BM\x00\x00", "BMP"),
        ],
    )
    def test_valid_magic_accepted(self, header, label):
        _validate_magic(header + b"\x00" * 64)

    def test_empty_data_rejected(self):
        with pytest.raises(ValueError, match="does not look like"):
            _validate_magic(b"")

    def test_random_bytes_rejected(self):
        with pytest.raises(ValueError, match="does not look like"):
            _validate_magic(b"\x00\x01\x02\x03\x04\x05\x06\x07")

    def test_text_content_rejected(self):
        with pytest.raises(ValueError, match="does not look like"):
            _validate_magic(b"#!/usr/bin/env python3\nimport os\n")

    def test_pdf_rejected(self):
        with pytest.raises(ValueError, match="does not look like"):
            _validate_magic(b"%PDF-1.4")

    def test_partial_png_header_rejected(self):
        """Only the first few bytes of PNG magic -- should still fail
        if the full 8-byte signature is not present."""
        # b"\x89PN" is only 3 bytes of the 8-byte PNG signature.
        # But our check uses startswith, so b"\x89PNG\r\n\x1a\n" requires
        # the full prefix. Let's verify a truncated one fails.
        with pytest.raises(ValueError, match="does not look like"):
            _validate_magic(b"\x89PN")
