"""Small read-only SSH/SFTP boundary, replaceable by a synthetic backend in tests."""

import asyncio
import shlex
import stat
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol

import asyncssh

from .config import TargetProfile
from .errors import ToolFailure

PIDIN_FORMAT = "%a|%b|%p|%J|%80B|%n"
STREAM_LIMIT = 256 * 1024
LOG_LIMIT = 1024 * 1024


class Command(StrEnum):
    UNAME = "uname"
    INFO = "pidin_info"
    PROCESSES = "pidin_threads"
    LOG = "slog2_snapshot"


def command_line(profile: TargetProfile, command: Command) -> str:
    utilities = profile.utilities
    argv = {
        Command.UNAME: (utilities.uname, "-srm"),
        Command.INFO: (utilities.pidin, "info"),
        Command.PROCESSES: (utilities.pidin, "-v", "-F", PIDIN_FORMAT),
        Command.LOG: (utilities.slog2info, "-f", "-s", "-t"),
    }[command]
    return "LC_ALL=C " + shlex.join(argv)


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str = ""
    exit_code: int | None = 0
    truncated: bool = False


@dataclass(frozen=True)
class Entry:
    kind: Literal["file", "directory", "symlink", "other"]
    size: int | None = None


class Files(Protocol):
    async def lstat(self, path: str) -> Entry: ...
    async def realpath(self, path: str) -> str: ...
    async def read(self, path: str, offset: int, size: int) -> bytes: ...


class Session(Protocol):
    @property
    def fingerprint(self) -> str: ...
    async def run(self, command: Command) -> CommandResult: ...
    def files(self) -> AbstractAsyncContextManager[Files]: ...


class Backend(Protocol):
    def connect(self) -> AbstractAsyncContextManager[Session]: ...


class SFTPFiles:
    def __init__(self, client: asyncssh.SFTPClient):
        self.client = client

    async def lstat(self, path: str) -> Entry:
        attrs = await self.client.lstat(path)
        mode = attrs.permissions
        if attrs.type == asyncssh.FILEXFER_TYPE_SYMLINK or (
            mode is not None and stat.S_ISLNK(mode)
        ):
            return Entry("symlink")
        if attrs.type == asyncssh.FILEXFER_TYPE_DIRECTORY or (
            mode is not None and stat.S_ISDIR(mode)
        ):
            return Entry("directory")
        if attrs.type == asyncssh.FILEXFER_TYPE_REGULAR or (
            mode is not None and stat.S_ISREG(mode)
        ):
            return Entry("file", attrs.size)
        return Entry("other")

    async def realpath(self, path: str) -> str:
        resolved = await self.client.realpath(path)
        if not isinstance(resolved, str):
            raise ToolFailure("path_denied", "Target did not return a canonical text path")
        return resolved

    async def read(self, path: str, offset: int, size: int) -> bytes:
        async with self.client.open(path, "rb", block_size=32 * 1024, max_requests=1) as file:
            return await file.read(size, offset)


class AsyncSession:
    def __init__(self, connection: asyncssh.SSHClientConnection, profile: TargetProfile):
        self.connection = connection
        self.profile = profile

    @property
    def fingerprint(self) -> str:
        key = self.connection.get_server_host_key()
        if key is None:
            raise ToolFailure("host_key_mismatch", "No SSH server host key was verified")
        return key.get_fingerprint("sha256")

    async def run(self, command: Command) -> CommandResult:
        limit = LOG_LIMIT if command is Command.LOG else STREAM_LIMIT
        async with self.connection.create_process(
            command_line(self.profile, command), encoding=None, request_pty=False
        ) as proc:
            proc.stdin.write_eof()

            async def collect(reader: asyncssh.SSHReader, cap: int) -> tuple[bytes, bool]:
                data = bytearray()
                while chunk := await reader.read(min(32 * 1024, cap + 1 - len(data))):
                    data.extend(chunk)
                    if len(data) > cap:
                        proc.close()
                        # A truncated final record is never treated as a complete observation.
                        prefix = bytes(data[:cap])
                        return prefix[: prefix.rfind(b"\n") + 1], True
                return bytes(data), False

            readers = [
                asyncio.create_task(collect(proc.stdout, limit)),
                asyncio.create_task(collect(proc.stderr, STREAM_LIMIT)),
            ]
            try:
                (out, out_cut), (err, err_cut) = await asyncio.gather(*readers)
                await proc.wait_closed()
            finally:
                for reader in readers:
                    if not reader.done():
                        reader.cancel()
                await asyncio.gather(*readers, return_exceptions=True)
            return CommandResult(
                out.decode("utf-8", "replace"),
                err.decode("utf-8", "replace"),
                proc.exit_status,
                out_cut or err_cut,
            )

    @asynccontextmanager
    async def files(self) -> AsyncIterator[Files]:
        async with self.connection.start_sftp_client() as sftp:
            yield SFTPFiles(sftp)


class SSHBackend:
    def __init__(self, profile: TargetProfile):
        self.profile = profile

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[Session]:
        p = self.profile
        if not Path(p.key_path).is_file() or not Path(p.known_hosts).is_file():
            raise ToolFailure(
                "configuration_error", "Configure an existing SSH key and trusted known_hosts file"
            )
        async with asyncssh.connect(
            p.host,
            port=p.port,
            username=p.user,
            client_keys=[p.key_path],
            known_hosts=p.known_hosts,
            config=None,
            agent_path=None,
            agent_forwarding=False,
            preferred_auth=["publickey"],
            password_auth=False,
            kbdint_auth=False,
            login_timeout=8,
        ) as connection:
            yield AsyncSession(connection, p)
