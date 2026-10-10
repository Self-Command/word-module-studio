from ..runtime import WordError, require_execution, run, digest, write_json


class StudioError(WordError):
    """Compatibility for migrated helpers; keeps their diagnostic codes."""
    pass
