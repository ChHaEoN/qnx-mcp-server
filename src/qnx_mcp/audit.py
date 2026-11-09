"""Private append-only metadata. A failed audit disables subsequent reads."""

import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

from .errors import ToolFailure


class AuditLog:
    def __init__(self, path: Path):
        self.path = path.expanduser()
        self.failed = False

    def record(self, event: str, **details: object) -> None:
        if self.failed:
            raise ToolFailure("audit_failure", "Local audit is unavailable; reads are disabled")
        fd = None
        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            parent = self.path.parent.lstat()
            if (
                not stat.S_ISDIR(parent.st_mode)
                or parent.st_uid != os.getuid()
                or parent.st_mode & 0o022
            ):
                raise OSError("Unsafe audit directory")
            fd = os.open(
                self.path,
                os.O_APPEND
                | os.O_CREAT
                | os.O_WRONLY
                | os.O_CLOEXEC
                | os.O_NOFOLLOW
                | os.O_NONBLOCK,
                0o600,
            )
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_mode & 0o077
                or info.st_nlink != 1
            ):
                raise OSError("Unsafe audit file")
            payload = (
                json.dumps(
                    {"timestamp": datetime.now(UTC).isoformat(), "event": event, **details},
                    ensure_ascii=True,
                    separators=(",", ":"),
                ).encode()
                + b"\n"
            )
            if os.write(fd, payload) != len(payload):
                raise OSError("Incomplete audit write")
            os.fsync(fd)
        except OSError:
            self.failed = True
            raise ToolFailure(
                "audit_failure", "Local audit is unavailable; reads are disabled"
            ) from None
        finally:
            if fd is not None:
                os.close(fd)


def default_audit_path() -> Path:
    state = os.environ.get("XDG_STATE_HOME")
    return (Path(state) if state else Path.home() / ".local/state") / "qnx-mcp/audit.jsonl"
