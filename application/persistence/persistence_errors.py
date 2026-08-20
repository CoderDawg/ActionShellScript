from __future__ import annotations


class PersistenceError(RuntimeError):
    """Base error for shared persistence operations."""


class PersistenceLoadError(PersistenceError):
    """Raised when a persisted artifact cannot be loaded."""


class PersistenceSaveError(PersistenceError):
    """Raised when a persisted artifact cannot be saved."""
