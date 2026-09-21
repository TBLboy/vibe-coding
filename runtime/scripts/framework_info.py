"""Single source of truth for the framework release identity and format policy.

The release version, the default project-log format, the transactional store
schema and the legacy retirement stages live here so that the CLI, the
installer and the release builder cannot drift apart.
"""
from __future__ import annotations

VERSION = "0.5.0"
DEFAULT_FORMAT = 2
STORE_SCHEMA = 3
SUPPORTED_FORMATS = (1, 2)

# Contract wording frozen by DEC-009 and the framework-landing production contract
# (the source document moved to .project-log/legacy/specs/ once this project
# migrated itself to format 2).
LEGACY_GUIDANCE = "legacy format: migrate with vibe migrate"
LEGACY_WRITE_WARNING = (
    "deprecated: format 1 writes are accepted only during the migration window; "
    "run 'vibe migrate preview' to move this project to format 2"
)

# Retiring format 1 is staged: every stage is a separate user gate. No stage may
# be executed by an agent on its own authority (see DEC-009).
RETIREMENT_STAGES = (
    {
        "id": "stop-writing",
        "title": "Stop writing format 1",
        "scope": "loopctl/vibe reject format 1 writes; read-only queries and migration stay available",
        "gate": "user-approval",
        "status": "pending",
    },
    {
        "id": "stop-reading",
        "title": "Stop reading format 1",
        "scope": "status/validate/restore no longer parse format 1; the migration tool still runs offline",
        "gate": "user-approval",
        "status": "pending",
    },
    {
        "id": "stop-support",
        "title": "Stop supporting format 1",
        "scope": "remove the migration tool, the legacy templates and the compatibility code",
        "gate": "user-approval",
        "status": "pending",
    },
)


def version_payload() -> dict:
    """Machine-readable release identity, used by ``vibe version``."""
    return {
        "framework_version": VERSION,
        "default_format": DEFAULT_FORMAT,
        "store_schema": STORE_SCHEMA,
        "supported_formats": list(SUPPORTED_FORMATS),
        "legacy_guidance": LEGACY_GUIDANCE,
        "retirement_stages": [dict(stage) for stage in RETIREMENT_STAGES],
    }
