"""Explicit input and output schemas for the four read tools."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SystemArgs(Input):
    pass


class ProcessArgs(Input):
    pid: int | None = Field(default=None, ge=1, le=2**31 - 1)
    name: str | None = Field(default=None, min_length=1, max_length=256)
    limit: int = Field(default=200, ge=1, le=1000, description="Maximum number of thread rows")


EpochMillis = Annotated[int, Field(ge=0, le=253_402_300_799_999)]


class LogArgs(Input):
    buffer_set: str | None = Field(default=None, min_length=1, max_length=128)
    pid: int | None = Field(default=None, ge=1, le=2**31 - 1)
    severity_max: int | None = Field(default=None, ge=0, le=7)
    since_epoch_ms: EpochMillis | None = None
    until_epoch_ms: EpochMillis | None = None
    limit: int = Field(default=100, ge=1, le=500)

    @model_validator(mode="after")
    def valid_window(self) -> "LogArgs":
        if (
            self.since_epoch_ms is not None
            and self.until_epoch_ms is not None
            and self.since_epoch_ms > self.until_epoch_ms
        ):
            raise ValueError("since_epoch_ms must not exceed until_epoch_ms")
        return self


class FileArgs(Input):
    path: str = Field(min_length=1, max_length=1024)
    offset: int = Field(default=0, ge=0, le=2**53 - 1)
    max_bytes: int = Field(default=16_384, ge=4, le=65_536)


class Memory(BaseModel):
    free_bytes: int | None = None
    total_bytes: int | None = None
    approximate: bool = True


class Capabilities(BaseModel):
    pidin: bool | None
    slog2info: bool | None
    sftp: bool


class SystemData(BaseModel):
    os: Literal["QNX"] = "QNX"
    release: str
    machine: str
    arch: Literal["x86_64", "aarch64"]
    cpu_count: int | None = None
    cpu_model: str | None = None
    memory: Memory
    capabilities: Capabilities


class BlockedOn(BaseModel):
    kind: Literal["peer", "channel", "other", "none"]
    availability: Literal["observed", "unknown", "not_applicable"]
    peer_pid: int | None = None
    peer_tid: int | None = None
    channel_id: int | None = None
    coid: int | None = None
    scoid: int | None = None
    raw: str = ""


class Thread(BaseModel):
    tid: int
    state: str
    priority: int | None
    policy: str | None
    blocked_on: BlockedOn


class Process(BaseModel):
    pid: int
    executable: str
    threads: list[Thread]


class ProcessData(BaseModel):
    processes: list[Process]
    returned_threads: int
    visibility: Literal["account_limited"] = "account_limited"
    permission_denied: int = 0


class LogEntry(BaseModel):
    timestamp: str
    epoch_ms: int
    pid: int | None
    tid: int
    buffer_set: str
    buffer: str
    oldest: bool = False
    severity: int
    code: int
    message: str


class LogData(BaseModel):
    clock_basis: Literal["unix_epoch"] = "unix_epoch"
    visibility: Literal["account_limited"] = "account_limited"
    entries: list[LogEntry]


class FileData(BaseModel):
    path: str
    content: str
    encoding: Literal["utf-8"] = "utf-8"
    bytes_read: int
    next_offset: int | None
    eof: bool


class Envelope[T: BaseModel](BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    target_id: str
    observed_at: datetime
    status: Literal["ok", "partial"]
    data: T
    warnings: list[str] = Field(default_factory=list)
    truncated: bool = False


class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool
