"""The four audited, read-only operations."""

import codecs
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import PurePosixPath

import asyncssh
from pydantic import BaseModel

from .config import TargetProfile
from .errors import ToolFailure
from .parsers import parse_info, parse_logs, parse_processes, parse_uname
from .policy import remote_path, require_read_path, safe_text
from .schemas import (
    Capabilities,
    Envelope,
    FileArgs,
    FileData,
    LogArgs,
    LogData,
    Memory,
    ProcessArgs,
    ProcessData,
    SystemArgs,
    SystemData,
)
from .transport import Command, CommandResult, Session

Record = Callable[..., None]
_PERMISSION = re.compile("operation not permitted|permission denied|access denied", re.I)


def command_warnings(result: CommandResult) -> list[str]:
    warnings = []
    count = len(_PERMISSION.findall(result.stderr))
    if count:
        warnings.append(f"{count} target permission diagnostic(s); visibility is incomplete")
    elif result.stderr.strip():
        warnings.append(
            "Target returned diagnostic stderr; inspect the account and utility configuration"
        )
    if result.truncated:
        warnings.append("Target output reached its byte limit; the snapshot is incomplete")
    return warnings


async def query(session: Session, command: Command, record: Record) -> CommandResult:
    record("command", command=command.value)
    result = await session.run(command)
    if result.truncated:
        return result
    if result.exit_code != 0:
        if result.exit_code == 127 or re.search(r"\bnot found\b", result.stderr, re.I):
            raise ToolFailure(
                "utility_unavailable", f"Configured {command.value} utility is unavailable"
            )
        if result.exit_code == 126 or _PERMISSION.search(result.stderr):
            raise ToolFailure("permission_denied", f"Target refused {command.value}")
        raise ToolFailure(
            "target_error", f"Target {command.value} command did not complete successfully"
        )
    return result


def result_for[T: BaseModel](
    profile: TargetProfile,
    data: T,
    warnings: list[str] | None = None,
    truncated: bool = False,
) -> Envelope[T]:
    return Envelope[type(data)](
        target_id=profile.target_id,
        observed_at=datetime.now(UTC),
        status="partial" if warnings or truncated else "ok",
        data=data,
        warnings=warnings or [],
        truncated=truncated,
    )


async def system_info(
    profile: TargetProfile, session: Session, _: SystemArgs, record: Record
) -> Envelope[SystemData]:
    uname = await query(session, Command.UNAME, record)
    release, machine, arch = parse_uname(uname.stdout)
    if arch != profile.arch:
        raise ToolFailure(
            "unsupported_target", "QNX machine architecture does not match its profile"
        )
    warnings = command_warnings(uname)
    cpu_count = cpu_model = None
    memory = Memory()
    pidin = None
    truncated = uname.truncated
    try:
        info = await query(session, Command.INFO, record)
        pidin = True
        cpu_count, cpu_model, memory = parse_info(info.stdout)
        warnings.extend(command_warnings(info))
        truncated |= info.truncated
        if cpu_count is None or memory.total_bytes is None:
            warnings.append("Some CPU or memory fields were unavailable in pidin info")
    except ToolFailure as exc:
        pidin = False if exc.code == "utility_unavailable" else None
        warnings.append(exc.message)
    record("sftp_probe")
    sftp = True
    try:
        async with session.files():
            pass
    except (asyncssh.Error, OSError):
        sftp = False
        warnings.append("Target SFTP subsystem is unavailable to this account")
    return result_for(
        profile,
        SystemData(
            release=release,
            machine=machine,
            arch=arch,
            cpu_count=cpu_count,
            cpu_model=cpu_model,
            memory=memory,
            capabilities=Capabilities(pidin=pidin, slog2info=None, sftp=sftp),
        ),
        warnings,
        truncated,
    )


async def list_processes(
    profile: TargetProfile, session: Session, args: ProcessArgs, record: Record
) -> Envelope[ProcessData]:
    raw = await query(session, Command.PROCESSES, record)
    processes, notes = parse_processes(raw.stdout)
    warnings = command_warnings(raw) + [f"{n} {note}" for note, n in sorted(notes.items())]
    if not processes and _PERMISSION.search(raw.stderr):
        raise ToolFailure("permission_denied", "No pidin thread rows were visible to this account")
    warnings.append(
        "Only threads visible to the SSH account are included; this is not a system-wide snapshot"
    )
    filtered = []
    remaining = args.limit
    capped = False
    for proc in processes:
        if args.pid is not None and args.pid != proc.pid:
            continue
        if args.name is not None and args.name not in proc.executable:
            continue
        included = proc.threads[:remaining]
        if included:
            filtered.append(proc.model_copy(update={"threads": included}))
            remaining -= len(included)
        if len(included) < len(proc.threads):
            capped = True
            break
    if capped:
        warnings.append("Thread limit reached; refine the filters for more detail")
    return result_for(
        profile,
        ProcessData(
            processes=filtered,
            returned_threads=args.limit - remaining,
            permission_denied=len(_PERMISSION.findall(raw.stderr)),
        ),
        warnings,
        raw.truncated or capped,
    )


async def read_system_log(
    profile: TargetProfile, session: Session, args: LogArgs, record: Record
) -> Envelope[LogData]:
    raw = await query(session, Command.LOG, record)
    entries, notes = parse_logs(raw.stdout)
    warnings = command_warnings(raw) + [f"{n} {note}" for note, n in sorted(notes.items())]
    if not entries and _PERMISSION.search(raw.stderr):
        raise ToolFailure("permission_denied", "No slog2 buffers were readable to this account")
    if not entries:
        warnings.append("No slog2 records were visible to this account")
    filtered = [
        e
        for e in entries
        if (args.buffer_set is None or args.buffer_set == e.buffer_set)
        and (args.pid is None or args.pid == e.pid)
        and (args.severity_max is None or e.severity <= args.severity_max)
        and (args.since_epoch_ms is None or e.epoch_ms >= args.since_epoch_ms)
        and (args.until_epoch_ms is None or e.epoch_ms <= args.until_epoch_ms)
    ]
    capped = len(filtered) > args.limit
    if capped:
        warnings.append(
            "Entry limit reached; returning the latest matching entries in snapshot order"
        )
    return result_for(
        profile,
        LogData(entries=filtered[-args.limit :]),
        warnings,
        raw.truncated or capped or bool(notes.get("log message segments clipped")),
    )


async def read_file(
    profile: TargetProfile, session: Session, args: FileArgs, record: Record
) -> Envelope[FileData]:
    path = require_read_path(args.path, profile.read_roots)
    record("sftp_read", offset=args.offset, max_bytes=args.max_bytes)
    async with session.files() as files:
        for directory in reversed(path.parents):
            if directory == PurePosixPath("/"):
                continue
            if (await files.lstat(str(directory))).kind != "directory":
                raise ToolFailure("path_denied", "Every path component must be a real directory")
        entry = await files.lstat(str(path))
        if entry.kind != "file" or entry.size is None or entry.size < 0:
            raise ToolFailure("path_denied", "Only regular files with a known size may be read")
        try:
            canonical = remote_path(await files.realpath(str(path)))
        except ValueError:
            raise ToolFailure("path_denied", "Invalid SFTP canonical path") from None
        if canonical != path:
            raise ToolFailure("path_denied", "SFTP canonical path differs from the requested path")
        require_read_path(str(canonical), profile.read_roots)
        if args.offset >= entry.size:
            return result_for(
                profile,
                FileData(path=str(path), content="", bytes_read=0, next_offset=None, eof=True),
            )
        size = min(entry.size - args.offset, args.max_bytes)
        blob = await files.read(str(canonical), args.offset, size)
        if len(blob) != size:
            raise ToolFailure(
                "target_error", "File changed or returned an incomplete read", retryable=True
            )
    eof = args.offset + len(blob) >= entry.size
    if b"\x00" in blob:
        raise ToolFailure("invalid_text", "File contains NUL bytes")
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        text = decoder.decode(blob, final=eof)
    except UnicodeDecodeError:
        raise ToolFailure(
            "invalid_text", "Expected UTF-8 text at the requested byte offset"
        ) from None
    read = len(blob) - len(decoder.getstate()[0])
    return result_for(
        profile,
        FileData(
            path=str(path),
            content=safe_text(text),
            bytes_read=read,
            next_offset=None if eof else args.offset + read,
            eof=eof,
        ),
        truncated=not eof,
    )
