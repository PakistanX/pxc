"""Discover bundled PXC sample activities."""

from pathlib import Path

SAMPLES_DIR = Path(__file__).parent / "samples"


def list_activities() -> list[str]:
    """Return sorted list of available sample activity slugs."""
    if not SAMPLES_DIR.exists():
        return []
    return sorted(
        d.name
        for d in SAMPLES_DIR.iterdir()
        if d.is_dir() and (d / "manifest.json").exists()
    )


def get_activity_dir(slug: str) -> Path:
    """Return the directory for a bundled sample, or raise ValueError."""
    path = SAMPLES_DIR / slug
    if not path.exists() or not (path / "manifest.json").exists():
        raise ValueError(f"Unknown activity: {slug!r}")
    return path
