"""Errors for job analysis and matching. main.py maps each one to an HTTP status code."""


class JobError(Exception):
    """Base class for all job-related errors."""


class EmptyJobDescriptionError(JobError):
    """The job description text is empty after cleaning."""


class NoSkillsToCompareError(JobError):
    """The job posting lists no skills, so there is nothing to compare the resume against."""
