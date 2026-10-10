"""AIS navigation field normalization (not-available speed/course)."""

from __future__ import annotations

from typing import Any, Optional, Tuple

# ITU-R M.1371 "not available" encodings commonly surfaced by AIS-catcher.
AIS_SPEED_NOT_AVAILABLE_KN = 102.3
AIS_COURSE_NOT_AVAILABLE_DEG = 360.0


def _near(a: float, b: float, eps: float = 0.05) -> bool:
    return abs(a - b) <= eps


def normalize_ais_speed(speed: Any) -> Tuple[Optional[float], bool]:
    """Return (knots or None, known_bool)."""
    if speed is None:
        return None, False
    try:
        v = float(speed)
    except (TypeError, ValueError):
        return None, False
    if _near(v, AIS_SPEED_NOT_AVAILABLE_KN):
        return None, False
    return v, True


def normalize_ais_course(cog: Any) -> Tuple[Optional[float], bool]:
    if cog is None:
        return None, False
    try:
        v = float(cog)
    except (TypeError, ValueError):
        return None, False
    if _near(v, AIS_COURSE_NOT_AVAILABLE_DEG):
        return None, False
    return v % 360.0, True


def normalize_ais_heading(heading: Any) -> Tuple[Optional[float], bool]:
    if heading is None:
        return None, False
    try:
        v = float(heading)
    except (TypeError, ValueError):
        return None, False
    if v >= 360 or v < 0:
        return None, False
    return v, True
