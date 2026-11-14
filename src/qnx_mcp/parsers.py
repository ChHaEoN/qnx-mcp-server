"""Interpret the deliberately fixed QNX command formats; never infer missing IDs."""

import re
from collections import Counter
from decimal import Decimal

from .errors import ToolFailure
from .policy import safe_text
from .schemas import BlockedOn, LogEntry, Memory, Process, Thread

THREAD_HEADER = ["pid", "tid", "prio", "STATE", "Blocked", "name"]
_PEER = re.compile(r".+\((\d{1,10})\)\s+(\d{1,10})s?-(\d{1,10})-(\d{1,10})s?")
_NUMBER = re.compile(r"\d{1,10}")
_PRIORITY = re.compile(r"(\d{1,3})([a-zA-Z]?)")
# The verified QEMU guest prints some states with a trailing "?" (for example "MUTEX?").
_STATE = re.compile(r"[A-Z][A-Z0-9_-]{0,31}\??")
_LOG = re.compile(
    r"^(\d{1,12}(?:\.\d{1,9})?)\s+(\S+)\s+(\S+)\s+(\d{1,10})\s+"
    r"(\d{1,10})\s+([0-7])(?:[ \t]+(.*))?$"
)
_LOG_HEADER_LIKE = re.compile(r"^\s*\d+\.\d+\s")
LOG_MESSAGE_LIMIT = 2048


def parse_uname(text: str) -> tuple[str, str, str]:
    fields = text.strip().split()
    if len(fields) != 3:
        raise ToolFailure("parse_error", "Unexpected uname -srm layout")
    os_name, release, machine = fields
    arch = {
        "x86pc": "x86_64",
        "x86_64": "x86_64",
        "aarch64": "aarch64",
        "arm64": "aarch64",
    }.get(machine.lower())
    if os_name != "QNX" or not re.fullmatch(r"8\.0(?:\.\d+)?", release) or arch is None:
        raise ToolFailure("unsupported_target", "Expected a recognized QNX 8.0 target")
    return release, machine, arch


def parse_info(text: str) -> tuple[int | None, str | None, Memory]:
    cpu = dict(re.findall(r"(?m)^\s*Processor(\d+):\s*(.*?)\s*$", text))
    models = set()
    for description in cpu.values():
        model = re.split(r"\s+\d+(?:\.\d+)?[KMGT]Hz\b", description, maxsplit=1)[0]
        model = re.sub(r"^\d+\s+", "", model).strip()
        if model:
            models.add(safe_text(model[:128]))
    sizes = re.search(r"\bFreeMem:\s*(\d{1,16})([KMGTP]?B)\s*/\s*(\d{1,16})([KMGTP]?B)\b", text)
    memory = Memory()
    if sizes:
        scale = {name: 1024**i for i, name in enumerate(("B", "KB", "MB", "GB", "TB", "PB"))}
        free = int(sizes[1]) * scale[sizes[2]]
        total = int(sizes[3]) * scale[sizes[4]]
        if 0 <= free <= total <= 2**53 - 1:
            memory = Memory(
                free_bytes=free,
                total_bytes=total,
                approximate=sizes[2] != "B" or sizes[4] != "B",
            )
    return len(cpu) or None, next(iter(models)) if len(models) == 1 else None, memory


def base_state(state: str) -> str:
    """The state name without pidin's trailing qualifier; the reported text is kept elsewhere."""
    return state.removesuffix("?")


def parse_blocked(state: str, raw: str) -> BlockedOn:
    display = safe_text(raw)
    state = base_state(state)
    if state == "JOIN":
        if _NUMBER.fullmatch(raw):
            return BlockedOn(kind="thread", availability="observed", peer_tid=int(raw), raw=display)
        return BlockedOn(kind="thread", availability="unknown", raw=display)
    if state in {"SEND", "REPLY"}:
        if m := _PEER.fullmatch(raw):
            peer, coid, channel, scoid = map(int, m.groups())
            return BlockedOn(
                kind="peer",
                availability="observed",
                peer_pid=peer,
                coid=coid,
                channel_id=channel,
                scoid=scoid,
                raw=display,
            )
        if _NUMBER.fullmatch(raw):
            return BlockedOn(kind="peer", availability="observed", peer_pid=int(raw), raw=display)
        return BlockedOn(kind="peer", availability="unknown", raw=display)
    if state == "RECEIVE":
        if _NUMBER.fullmatch(raw):
            return BlockedOn(
                kind="channel", availability="observed", channel_id=int(raw), raw=display
            )
        return BlockedOn(kind="channel", availability="unknown", raw=display)
    if raw:
        return BlockedOn(kind="other", availability="observed", raw=display)
    return BlockedOn(kind="none", availability="not_applicable")


def parse_processes(text: str) -> tuple[list[Process], Counter[str]]:
    lines = [line for line in text.split("\n") if line.strip()]
    if not lines or [cell.strip() for cell in lines[0].split("|")] != THREAD_HEADER:
        raise ToolFailure("parse_error", "Unexpected pidin thread header")
    rows: dict[int, Process] = {}
    notes: Counter[str] = Counter()
    seen: set[tuple[int, int]] = set()
    for line in lines[1:]:
        fields = [field.strip() for field in line.split("|")]
        if len(fields) != 6:
            notes["malformed thread rows"] += 1
            continue
        pid, tid, prio, state, blocked, executable = fields
        if not (_NUMBER.fullmatch(pid) and _NUMBER.fullmatch(tid) and _STATE.fullmatch(state)):
            notes["malformed thread rows"] += 1
            continue
        pid_num, tid_num = int(pid), int(tid)
        if (pid_num, tid_num) in seen:
            notes["duplicate thread rows"] += 1
            continue
        seen.add((pid_num, tid_num))
        priority = _PRIORITY.fullmatch(prio)
        if priority is None:
            notes["unknown thread priorities"] += 1
        wait = parse_blocked(state, blocked)
        if wait.availability == "unknown":
            notes["unknown IPC endpoints"] += 1
        proc = rows.setdefault(
            pid_num, Process(pid=pid_num, executable=safe_text(executable), threads=[])
        )
        if proc.executable != safe_text(executable):
            notes["process identity changed during snapshot"] += 1
            continue
        proc.threads.append(
            Thread(
                tid=tid_num,
                state=state,
                priority=int(priority[1]) if priority else None,
                policy=(priority[2] or None) if priority else None,
                blocked_on=wait,
            )
        )
    if not rows and notes:
        raise ToolFailure("parse_error", "No valid pidin thread rows")
    return list(rows.values()), notes


def parse_logs(text: str) -> tuple[list[LogEntry], Counter[str]]:
    entries: list[LogEntry] = []
    notes: Counter[str] = Counter()
    previous: LogEntry | None = None
    for raw in text.removesuffix("\n").split("\n"):
        line = raw.removesuffix("\r")
        if m := _LOG.fullmatch(line.lstrip()):
            timestamp, name, buffer, tid, code, severity, message = m.groups()
            epoch_ms = int(Decimal(timestamp) * 1000)
            if epoch_ms > 253_402_300_799_999:
                previous = None
                notes["invalid log timestamps"] += 1
                continue
            suffix = re.fullmatch(r"(.+)\.(\d{1,10})", name)
            previous = LogEntry(
                timestamp=timestamp,
                epoch_ms=epoch_ms,
                pid=int(suffix[2]) if suffix else None,
                tid=int(tid),
                buffer_set=safe_text(suffix[1] if suffix else name),
                buffer=safe_text(buffer.removesuffix("*")),
                oldest=buffer.endswith("*"),
                severity=int(severity),
                code=int(code),
                message="",
            )
            entries.append(previous)
            piece = safe_text(message or "")
        elif previous is not None and not _LOG_HEADER_LIKE.match(line):
            piece = "\n" + safe_text(line)
        else:
            previous = None
            if line.strip():
                notes["unrecognized log lines"] += 1
            continue
        remaining = LOG_MESSAGE_LIMIT - len(previous.message)
        if len(piece) > remaining:
            notes["log message segments clipped"] += 1
        previous.message += piece[:remaining]
    if not entries and notes:
        raise ToolFailure("parse_error", "No recognized slog2info epoch records")
    return entries, notes
