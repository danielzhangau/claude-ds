"""Cross-platform clipboard image extraction.

Windows: uses PIL.ImageGrab (native).
macOS:   uses PIL.ImageGrab, falls back to `pngpaste`.
Linux:   uses `wl-paste` (Wayland) or `xclip` (X11).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


class ClipboardError(RuntimeError):
    """Raised when no image can be read from the clipboard."""


def _temp_path() -> Path:
    d = Path(tempfile.gettempdir()) / "clipboard_vision_mcp"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"clip_{uuid.uuid4().hex}.png"


def save_clipboard_image() -> str:
    """Save the current clipboard image to a temp PNG and return its path.

    Raises ClipboardError if the clipboard does not contain an image.
    """
    out = _temp_path()
    platform = sys.platform

    if platform == "win32":
        _grab_with_pil(out)
    elif platform == "darwin":
        try:
            _grab_with_pil(out)
        except ClipboardError:
            _grab_macos_pngpaste(out)
    else:
        _grab_linux(out)

    if not out.exists() or out.stat().st_size == 0:
        raise ClipboardError("Clipboard does not contain an image.")
    return str(out)


def _grab_with_pil(out: Path) -> None:
    try:
        from PIL import Image, ImageGrab  # type: ignore
    except ImportError as e:
        raise ClipboardError(
            "Pillow is required for clipboard image support. Run: pip install Pillow"
        ) from e

    img = ImageGrab.grabclipboard()
    if img is None:
        raise ClipboardError("No image found in clipboard.")

    # On Windows, if the user copied a file from Explorer, PIL returns a list of paths.
    if isinstance(img, list):
        if not img:
            raise ClipboardError("No image found in clipboard.")
        src = img[0]
        Image.open(src).save(out, "PNG")
        return

    img.save(out, "PNG")


def _grab_macos_pngpaste(out: Path) -> None:
    try:
        result = subprocess.run(["pngpaste", str(out)], capture_output=True, timeout=10)
    except FileNotFoundError as e:
        raise ClipboardError(
            "No image in clipboard. Install `pngpaste` for better support: brew install pngpaste"
        ) from e
    if result.returncode != 0:
        raise ClipboardError("No image in clipboard (pngpaste failed).")


def _grab_linux(out: Path) -> None:
    attempts = [
        (["wl-paste", "--type", "image/png"], "wl-clipboard"),
        (["xclip", "-selection", "clipboard", "-t", "image/png", "-o"], "xclip"),
    ]
    errors: list[str] = []
    for cmd, pkg in attempts:
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=10)
        except FileNotFoundError:
            errors.append(f"{pkg} not installed")
            continue
        if result.returncode == 0 and result.stdout:
            out.write_bytes(result.stdout)
            return
        errors.append(f"{pkg} returned no image")
    raise ClipboardError(
        "No image in clipboard. Install one of: wl-clipboard (Wayland) or xclip (X11). "
        f"Attempts: {', '.join(errors)}"
    )
