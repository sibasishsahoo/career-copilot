"""Errors for resume handling. main.py maps each one to an HTTP status code."""


class ResumeError(Exception):
    """Base class for all resume-related errors."""


class UnsupportedFileTypeError(ResumeError):
    """Not a .pdf or .docx file."""


class FileTooLargeError(ResumeError):
    """Upload exceeds the size limit."""


class InvalidFileError(ResumeError):
    """Empty, corrupt, password-protected, or not really the type its name claims."""


class NoTextFoundError(ResumeError):
    """The file is valid but contains no extractable text (e.g. a scanned PDF)."""
