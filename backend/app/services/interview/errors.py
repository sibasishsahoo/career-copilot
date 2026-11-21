"""Errors for interview preparation (no third-party packages). main.py maps them to HTTP codes."""


class InterviewError(Exception):
    """Base class for interview-preparation errors."""


class NoSavedMatchError(InterviewError):
    """The application has no saved job match, so there is no job description to prepare from (HTTP 409)."""


class InterviewGenerationError(InterviewError):
    """The AI did not produce anything usable (HTTP 502)."""
