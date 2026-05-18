"""Tests for cross-platform clipboard image extraction.

We can't actually populate the clipboard inside CI, so these tests
mock subprocess.run / ImageGrab to drive each code path:
  - Linux: wl-paste, xclip success and failure
  - macOS: pngpaste missing, pngpaste returning non-zero
  - Common: empty output produces ClipboardError
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clipboard_vision_mcp import clipboard
from clipboard_vision_mcp.clipboard import (
    ClipboardError,
    _grab_linux,
    _grab_macos_pngpaste,
    _temp_path,
    save_clipboard_image,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _completed(returncode: int, stdout: bytes = b""):
    """Mimic subprocess.CompletedProcess."""
    cp = MagicMock(spec=subprocess.CompletedProcess)
    cp.returncode = returncode
    cp.stdout = stdout
    return cp


# ---------------------------------------------------------------------------
# _temp_path
# ---------------------------------------------------------------------------


class TestTempPath:
    def test_returns_unique_paths(self):
        p1 = _temp_path()
        p2 = _temp_path()
        assert p1 != p2
        assert p1.suffix == ".png"
        assert p1.parent.exists()


# ---------------------------------------------------------------------------
# _grab_linux
# ---------------------------------------------------------------------------


class TestGrabLinux:
    def test_wl_paste_success_short_circuits(self, tmp_path):
        out = tmp_path / "out.png"

        def fake_run(cmd, **_kw):
            if cmd[0] == "wl-paste":
                return _completed(0, PNG_BYTES)
            raise AssertionError("xclip should not run when wl-paste succeeds")

        with patch.object(subprocess, "run", side_effect=fake_run):
            _grab_linux(out)

        assert out.read_bytes() == PNG_BYTES

    def test_falls_back_to_xclip_when_wl_paste_missing(self, tmp_path):
        out = tmp_path / "out.png"

        def fake_run(cmd, **_kw):
            if cmd[0] == "wl-paste":
                raise FileNotFoundError
            if cmd[0] == "xclip":
                return _completed(0, PNG_BYTES)
            raise AssertionError(f"unexpected cmd: {cmd}")

        with patch.object(subprocess, "run", side_effect=fake_run):
            _grab_linux(out)

        assert out.read_bytes() == PNG_BYTES

    def test_both_tools_missing_raises_with_helpful_message(self, tmp_path):
        out = tmp_path / "out.png"

        with (
            patch.object(subprocess, "run", side_effect=FileNotFoundError),
            pytest.raises(ClipboardError, match="wl-clipboard|xclip"),
        ):
            _grab_linux(out)

    def test_both_tools_return_empty_raises(self, tmp_path):
        out = tmp_path / "out.png"

        with (
            patch.object(subprocess, "run", return_value=_completed(0, b"")),
            pytest.raises(ClipboardError, match="returned no image"),
        ):
            _grab_linux(out)


# ---------------------------------------------------------------------------
# _grab_macos_pngpaste
# ---------------------------------------------------------------------------


class TestGrabMacosPngpaste:
    def test_pngpaste_missing_raises(self, tmp_path):
        out = tmp_path / "out.png"
        with (
            patch.object(subprocess, "run", side_effect=FileNotFoundError),
            pytest.raises(ClipboardError, match="brew install pngpaste"),
        ):
            _grab_macos_pngpaste(out)

    def test_pngpaste_non_zero_returncode_raises(self, tmp_path):
        out = tmp_path / "out.png"
        with (
            patch.object(subprocess, "run", return_value=_completed(1)),
            pytest.raises(ClipboardError, match="pngpaste failed"),
        ):
            _grab_macos_pngpaste(out)

    def test_pngpaste_success_does_not_raise(self, tmp_path):
        out = tmp_path / "out.png"
        # pngpaste writes the file itself; the function only checks returncode.
        with patch.object(subprocess, "run", return_value=_completed(0)):
            _grab_macos_pngpaste(out)


# ---------------------------------------------------------------------------
# save_clipboard_image
# ---------------------------------------------------------------------------


class TestSaveClipboardImage:
    def test_empty_output_file_raises(self, tmp_path):
        """Even if the grabber returns successfully, an empty file means no image."""

        def fake_linux(out: Path):
            out.write_bytes(b"")

        with (
            patch.object(clipboard, "sys") as fake_sys,
            patch.object(clipboard, "_grab_linux", side_effect=fake_linux),
        ):
            fake_sys.platform = "linux"
            with pytest.raises(ClipboardError, match="does not contain an image"):
                save_clipboard_image()

    def test_linux_dispatch(self):
        with (
            patch.object(clipboard, "sys") as fake_sys,
            patch.object(clipboard, "_grab_linux") as fake_grab,
        ):
            fake_sys.platform = "linux"

            # Make the grabber actually write a file so the empty-check passes
            def writer(out: Path):
                out.write_bytes(PNG_BYTES)

            fake_grab.side_effect = writer
            path = save_clipboard_image()

        fake_grab.assert_called_once()
        assert Path(path).read_bytes() == PNG_BYTES

    def test_macos_falls_back_to_pngpaste_when_pil_fails(self):
        with (
            patch.object(clipboard, "sys") as fake_sys,
            patch.object(
                clipboard, "_grab_with_pil", side_effect=ClipboardError("no PIL data")
            ) as pil_mock,
            patch.object(clipboard, "_grab_macos_pngpaste") as pngpaste_mock,
        ):
            fake_sys.platform = "darwin"

            def writer(out: Path):
                out.write_bytes(PNG_BYTES)

            pngpaste_mock.side_effect = writer

            path = save_clipboard_image()

        pil_mock.assert_called_once()
        pngpaste_mock.assert_called_once()
        assert Path(path).read_bytes() == PNG_BYTES
