"""Bundled NotoSans font resolution.

All PDF rendering code should use this module to resolve fonts instead of
relying on system fonts (C:\\Windows\\Fonts, /usr/share/fonts).  The project
ships NotoSans-{Regular,Bold,Italic,BoldItalic}.ttf inside ``backend/fonts/``
so that Docker deployments work without installing extra OS packages.

Priority order:
  1. ``FONT_DIR`` environment variable (if set and exists)
  2. Bundled ``backend/fonts/`` directory
  3. System font directories (Windows / Linux) — dev convenience only
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Bundled font directory (relative to the *backend* root, not this file)
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.abspath(os.path.join(_THIS_DIR, os.pardir, os.pardir, os.pardir))
_BUNDLED_FONT_DIR = os.path.join(_BACKEND_ROOT, "fonts")

# NotoSans variant map: (is_bold, is_italic) → filename
_NOTO_VARIANTS: Dict[Tuple[bool, bool], str] = {
    (False, False): "NotoSans-Regular.ttf",
    (True,  False): "NotoSans-Bold.ttf",
    (False, True):  "NotoSans-Italic.ttf",
    (True,  True):  "NotoSans-BoldItalic.ttf",
}


@lru_cache(maxsize=1)
def get_font_dir() -> str:
    """Return the best available font directory.

    Checks in order: FONT_DIR env → bundled fonts/ → system dirs.
    """
    env = os.environ.get("FONT_DIR", "").strip()
    if env and os.path.isdir(env):
        return env
    if os.path.isdir(_BUNDLED_FONT_DIR):
        return _BUNDLED_FONT_DIR
    for candidate in (r"C:\Windows\Fonts", "/usr/share/fonts/truetype", "/usr/share/fonts"):
        if os.path.isdir(candidate):
            return candidate
    return ""


@lru_cache(maxsize=8)
def get_noto_sans(is_bold: bool = False, is_italic: bool = False) -> Optional[str]:
    """Return the absolute path to a bundled NotoSans TTF variant, or *None*."""
    fname = _NOTO_VARIANTS.get((is_bold, is_italic), _NOTO_VARIANTS[(False, False)])
    # 1. Check bundled dir
    path = os.path.join(_BUNDLED_FONT_DIR, fname)
    if os.path.isfile(path):
        return path
    # 2. Check FONT_DIR env
    font_dir = get_font_dir()
    if font_dir:
        path = os.path.join(font_dir, fname)
        if os.path.isfile(path):
            return path
    return None


def get_noto_sans_or_fallback(is_bold: bool = False, is_italic: bool = False) -> Optional[str]:
    """Like *get_noto_sans* but falls back to any available NotoSans variant."""
    path = get_noto_sans(is_bold, is_italic)
    if path:
        return path
    # Try regular as last resort
    return get_noto_sans(False, False)
