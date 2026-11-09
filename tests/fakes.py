from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from qnx_mcp.transport import Command, CommandResult, Entry

FIXTURES = Path(__file__).parent / "fixtures/synthetic"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeFiles:
    def __init__(self):
        self.entries = {
            "/data": Entry("directory"),
            "/data/demo": Entry("directory"),
            "/data/demo/link": Entry("symlink"),
            "/data/demo/fifo": Entry("other"),
        }
        self.contents: dict[str, bytes] = {}
        self.canonical: dict[str, str] = {}
        self.reads: list[tuple[str, int, int]] = []
        self.add("/data/demo/probe.txt", b"original synthetic marker\n")

    def add(self, path: str, content: bytes) -> None:
        self.entries[path] = Entry("file", len(content))
        self.contents[path] = content

    async def lstat(self, path: str) -> Entry:
        return self.entries[path]

    async def realpath(self, path: str) -> str:
        return self.canonical.get(path, path)

    async def read(self, path: str, offset: int, size: int) -> bytes:
        self.reads.append((path, offset, size))
        return self.contents[path][offset : offset + size]


class FakeBackend:
    fingerprint = "SHA256:synthetic-test"

    def __init__(self):
        self.results = {
            Command.UNAME: CommandResult("QNX 8.0.0 x86pc\n"),
            Command.INFO: CommandResult(
                "CPU:X86_64 Release:8.0.0 FreeMem:128MB/512MB\n"
                "Processor1: 45 Fictional Model 100MHz FPU\n"
                "Processor2: 45 Fictional Model 100MHz FPU\n"
            ),
            Command.PROCESSES: CommandResult(
                fixture("pidin.txt"), "fixture: Operation not permitted"
            ),
            Command.LOG: CommandResult(fixture("slog2.txt")),
        }
        self.filesystem = FakeFiles()
        self.commands: list[Command] = []
        self.connections = 0
        self.connect_error: Exception | None = None

    @asynccontextmanager
    async def connect(self) -> AsyncIterator["FakeBackend"]:
        self.connections += 1
        if self.connect_error:
            raise self.connect_error
        yield self

    async def run(self, command: Command) -> CommandResult:
        self.commands.append(command)
        return self.results[command]

    @asynccontextmanager
    async def files(self) -> AsyncIterator[FakeFiles]:
        yield self.filesystem
