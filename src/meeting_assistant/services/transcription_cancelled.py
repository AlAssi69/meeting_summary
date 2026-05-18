"""Cooperative cancellation during local transcription."""


class TranscriptionCancelled(Exception):
    """Raised when the user stops processing while transcription is in progress."""
