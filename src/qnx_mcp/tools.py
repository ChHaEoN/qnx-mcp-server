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
    DirectoryEntry,
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
from .transport import Command, CommandResult, Files, Session
from .waits import analyze_waits

Record = Callable[..., None]
_PERMISSION = re.compile("operation not permitted|permission denied|access denied", re.I)

# Directory listings: entries per page, and how many names one call reads before it stops.
DIRECTORY_PAGE = 200
DIRECTORY_SCAN_LIMIT = 2000
# first_line counts newlines before the offset, reading at most this many bytes in chunks.
LINE_SCAN_LIMIT = 1024 * 1024
LINE_SCAN_CHUNK = 256 * 1024


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
    returned = {(proc.pid, thread.tid) for proc in filtered for thread in proc.threads}
    analysis = analyze_waits(processes, returned)
    if analysis.truncated:
        warnings.append("Wait analysis reached its size limit; refine the filters")
    return result_for(
        profile,
        ProcessData(
            processes=filtered,
            returned_threads=args.limit - remaining,
            permission_denied=len(_PERMISSION.findall(raw.stderr)),
            wait_analysis=analysis,
        ),
        warnings,
        raw.truncated or capped or analysis.truncated,
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


async def require_canonical(
    files: Files, path: PurePosixPath, roots: tuple[str, ...], *, allow_root: bool
) -> PurePosixPath:
    try:
        canonical = remote_path(await files.realpath(str(path)))
    except ValueError:
        raise ToolFailure("path_denied", "Invalid SFTP canonical path") from None
    if canonical != path:
        raise ToolFailure("path_denied", "SFTP canonical path differs from the requested path")
    return require_read_path(str(canonical), roots, allow_root=allow_root)


async def complete_read(files: Files, path: str, offset: int, size: int) -> bytes:
    blob = await files.read(path, offset, size)
    if len(blob) != size:
        raise ToolFailure(
            "target_error", "File changed or returned an incomplete read", retryable=True
        )
    return blob


async def line_at(files: Files, path: str, offset: int, record: Record) -> int | None:
    """1-based line of the byte at `offset`, or None when the prefix exceeds the scan cap."""
    if offset > LINE_SCAN_LIMIT:
        return None
    if offset:
        record("sftp_line_scan", bytes=offset)
    newlines = position = 0
    while position < offset:
        size = min(LINE_SCAN_CHUNK, offset - position)
        newlines += (await complete_read(files, path, position, size)).count(b"\n")
        position += size
    return newlines + 1


def number_lines(text: str, first: int) -> str:
    """cat -n style numbering; a final partial line is numbered, a final newline is kept."""
    lines = text.split("\n")
    ended = lines[-1] == ""
    if ended:
        lines.pop()
    body = "\n".join(f"{first + i:>6}\t{line}" for i, line in enumerate(lines))
    return body + ("\n" if ended and lines else "")


async def list_directory(
    profile: TargetProfile, files: Files, path: PurePosixPath, args: FileArgs, record: Record
) -> Envelope[FileData]:
    record("sftp_list", offset=args.offset)
    raw, more = await files.listdir(str(path), DIRECTORY_SCAN_LIMIT)
    ordered = sorted(raw, key=lambda item: item[0])
    page = ordered[args.offset : args.offset + DIRECTORY_PAGE]
    end = args.offset + len(page)
    last_page = end >= len(ordered)
    warnings = []
    if more:
        warnings.append(
            f"Directory has more than {DIRECTORY_SCAN_LIMIT} entries; only the first "
            f"{DIRECTORY_SCAN_LIMIT} read were sorted and listed"
        )
    eof = last_page and not more
    return result_for(
        profile,
        FileData(
            path=str(path),
            kind="directory",
            content="",
            bytes_read=0,
            next_offset=None if last_page else end,
            eof=eof,
            entries=[
                DirectoryEntry(
                    name=safe_text(name),
                    type=entry.kind,
                    size=entry.size if entry.kind == "file" else None,
                )
                for name, entry in page
            ],
            total_entries=None if more else len(ordered),
        ),
        warnings,
        truncated=not eof,
    )


async def read_file(
    profile: TargetProfile, session: Session, args: FileArgs, record: Record
) -> Envelope[FileData]:
    path = require_read_path(args.path, profile.read_roots, allow_root=True)
    record("sftp_read", offset=args.offset, max_bytes=args.max_bytes)
    async with session.files() as files:
        for directory in reversed(path.parents):
            if directory == PurePosixPath("/"):
                continue
            if (await files.lstat(str(directory))).kind != "directory":
                raise ToolFailure("path_denied", "Every path component must be a real directory")
        entry = await files.lstat(str(path))
        if entry.kind == "directory":
            await require_canonical(files, path, profile.read_roots, allow_root=True)
            return await list_directory(profile, files, path, args, record)
        if entry.kind != "file" or entry.size is None or entry.size < 0:
            raise ToolFailure(
                "path_denied", "Only regular files with a known size and directories may be read"
            )
        canonical = await require_canonical(files, path, profile.read_roots, allow_root=False)
        if args.offset >= entry.size:
            return result_for(
                profile,
                FileData(path=str(path), content="", bytes_read=0, next_offset=None, eof=True),
            )
        size = min(entry.size - args.offset, args.max_bytes)
        blob = await complete_read(files, str(canonical), args.offset, size)
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
        first_line = await line_at(files, str(canonical), args.offset, record)
    read = len(blob) - len(decoder.getstate()[0])
    content = safe_text(text)
    warnings = []
    if first_line is None:
        warnings.append(
            f"Line number unknown beyond the first {LINE_SCAN_LIMIT} bytes; cite byte offsets"
        )
        if args.line_numbers:
            warnings.append("line_numbers was ignored because the line number is unknown")
    numbered = args.line_numbers and first_line is not None
    return result_for(
        profile,
        FileData(
            path=str(path),
            content=number_lines(content, first_line) if numbered else content,
            bytes_read=read,
            first_line=first_line,
            numbered=numbered,
            next_offset=None if eof else args.offset + read,
            eof=eof,
        ),
        warnings,
        truncated=not eof,
    )
