"""Database-specific exceptions."""

from __future__ import annotations


class DatabaseError(Exception):
    """Base class for database-related errors."""


class ValidationError(DatabaseError):
    """Raised when input validation for database operations fails."""


class RaceConditionError(DatabaseError):
    """Raised when a unique ID could not be generated after retries."""
