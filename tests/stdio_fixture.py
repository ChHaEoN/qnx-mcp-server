"""Subprocess fixture. It is not a runtime backend selector."""

import asyncio
import sys
from pathlib import Path

from qnx_mcp.audit import AuditLog
from qnx_mcp.config import TargetProfile
from qnx_mcp.server import create_server, serve_stdio

from .fakes import FakeBackend

if __name__ == "__main__":
    asyncio.run(
        serve_stdio(create_server(TargetProfile(), AuditLog(Path(sys.argv[1])), FakeBackend()))
    )
