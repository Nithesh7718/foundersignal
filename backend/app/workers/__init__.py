"""Background workers for asynchronous operations."""

from typing import Any

__all__ = ["TranscriptionWorker"]


def __getattr__(name: str) -> Any:
    if name == "TranscriptionWorker":
        from app.workers.transcription_worker import TranscriptionWorker

        return TranscriptionWorker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
