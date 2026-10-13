"""Single source of truth for the framework release identity and format policy.

The release version, the default project-log format and the transactional store
schema live here so that the CLI and the installer cannot drift apart.
``STORE_SCHEMA`` must equal ``state_store.STORE_SCHEMA``; the two lived in
separate files and silently disagreed (this module said 3 while the projection
wrote 4), so ``vibe version`` reported a schema the database had outgrown.
Project Log format 2 is the only supported format.
"""
from __future__ import annotations

VERSION = "0.6.0"
DEFAULT_FORMAT = 2
# Keep in lockstep with state_store.STORE_SCHEMA and the CHECK constraint on its
# metadata table. tests/test_release_surface.py pins the agreement.
STORE_SCHEMA = 4
SUPPORTED_FORMATS = (2,)


def version_payload() -> dict:
    """Machine-readable release identity, used by ``vibe version``."""
    return {
        "framework_version": VERSION,
        "default_format": DEFAULT_FORMAT,
        "store_schema": STORE_SCHEMA,
        "supported_formats": list(SUPPORTED_FORMATS),
    }
