"""Single source of truth for the framework release identity and format policy.

The release version, the default project-log format and the transactional store
schema live here so that the CLI, the installer and the release builder cannot
drift apart. Project Log format 2 is the only supported format; format 1 was
retired and its archived files live under ``.project-log/legacy/``.
"""
from __future__ import annotations

VERSION = "0.6.0"
DEFAULT_FORMAT = 2
STORE_SCHEMA = 3
SUPPORTED_FORMATS = (2,)


def version_payload() -> dict:
    """Machine-readable release identity, used by ``vibe version``."""
    return {
        "framework_version": VERSION,
        "default_format": DEFAULT_FORMAT,
        "store_schema": STORE_SCHEMA,
        "supported_formats": list(SUPPORTED_FORMATS),
    }
