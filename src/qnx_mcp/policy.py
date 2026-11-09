"""Bounded input and path rules shared by configuration and tools."""

import unicodedata
from pathlib import PurePosixPath

from .errors import ToolFailure

DENIED_ROOTS = (PurePosixPath("/dev"), PurePosixPath("/proc"))


def remote_path(value: str) -> PurePosixPath:
    if (
        not value.startswith("/")
        or value.startswith("//")
        or ".." in value.split("/")
        or any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in value)
    ):
        raise ValueError("Expected an absolute POSIX path without traversal or control characters")
    return PurePosixPath(value)


def require_read_path(value: str, roots: tuple[str, ...]) -> PurePosixPath:
    try:
        path = remote_path(value)
    except ValueError as exc:
        raise ToolFailure("path_denied", str(exc)) from None
    if any(path.is_relative_to(root) for root in DENIED_ROOTS) or not any(
        path.is_relative_to(root) and path != PurePosixPath(root) for root in roots
    ):
        raise ToolFailure("path_denied", "File must be inside an approved read directory")
    return path


def safe_text(value: str) -> str:
    """Keep data readable without emitting terminal controls or bidi overrides."""
    return "".join(
        c
        if c in "\n\t" or unicodedata.category(c) not in {"Cc", "Cf", "Cs"}
        else f"\\u{ord(c):04x}"
        for c in value
    )
