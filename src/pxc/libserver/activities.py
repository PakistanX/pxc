"""Discover activity bundles under config.ACTIVITIES_DIR."""

from pathlib import Path

from pxc.libserver import config


class ActivityNotFoundError(Exception):
    """Raised when an activity slug has no matching bundle."""


def list_activities() -> list[str]:
    """Return sorted list of available activity slugs."""
    if not config.ACTIVITIES_DIR.exists():
        return []
    return sorted(
        d.name
        for d in config.ACTIVITIES_DIR.iterdir()
        if d.is_dir() and (d / "manifest.json").exists()
    )


def get_activity_dir(slug: str) -> Path:
    """Return the directory for an activity bundle, or raise ActivityNotFoundError."""
    path = config.ACTIVITIES_DIR / slug
    if not path.exists() or not (path / "manifest.json").exists():
        raise ActivityNotFoundError(f"Unknown activity: {slug!r}")
    return path
