import asyncio
import json
import sys
from pathlib import Path

import asyncssh
import pytest
from mcp import Client, StdioServerParameters

from qnx_mcp.audit import AuditLog
from qnx_mcp.config import TargetProfile
from qnx_mcp.server import create_server
from qnx_mcp.transport import Command, CommandResult, Entry

from .fakes import FakeBackend, fixture


@pytest.fixture
def setup(tmp_path):
    backend = FakeBackend()
    profile = TargetProfile(read_roots=("/data/demo",))
    audit = AuditLog(tmp_path / "audit" / "test.jsonl")
    return backend, profile, audit


def error_code(result):
    assert result.is_error
    return result.structured_content["code"]


async def test_contract_partial_process_data_and_local_filter(setup):
    backend, profile, audit = setup
    async with Client(create_server(profile, audit, backend)) as client:
        listed = (await client.list_tools()).tools
        assert {t.name for t in listed} == {
            "system_info",
            "list_processes",
            "read_system_log",
            "read_file",
        }
        assert all(t.annotations.read_only_hint and t.output_schema for t in listed)
        result = await client.call_tool("list_processes", {"pid": 701, "limit": 1})
    data = result.structured_content
    assert not result.is_error
    assert data["status"] == "partial" and data["truncated"]
    assert data["data"]["permission_denied"] == 1
    assert data["data"]["returned_threads"] == 1
    assert data["data"]["processes"][0]["threads"][0]["blocked_on"]["peer_pid"] == 804
    assert data["schema_version"] == "1.1"
    waits = data["data"]["wait_analysis"]
    assert waits["blocked_threads"] == 1
    assert [(e["source"]["pid"], e["candidate_basis"]) for e in waits["edges"]] == [
        (701, "inferred"),
        (804, "possible"),
    ]
    assert waits["cycles"][0]["basis"] == "possible"
    assert backend.commands == [Command.PROCESSES]


async def test_wait_analysis_follows_a_filtered_display_into_other_processes(setup):
    backend, profile, audit = setup
    backend.results[Command.PROCESSES] = CommandResult(fixture("pidin_cluster.txt"))
    async with Client(create_server(profile, audit, backend)) as client:
        result = await client.call_tool("list_processes", {"name": "display"})
    data = result.structured_content["data"]
    assert {p["pid"] for p in data["processes"]} == {340}
    ends = data["wait_analysis"]["ends"]
    assert [(e["thread"]["pid"], e["kind"]) for e in ends] == [
        (310, "untimed_wait"),
        (310, "untimed_wait"),
        (320, "self_resolving"),
    ]
    assert ends[0]["executable"] == "/data/demo/sensor"


async def test_validation_and_denials_audited_before_network(setup):
    backend, profile, audit = setup
    async with Client(create_server(profile, audit, backend)) as client:
        invalid = await client.call_tool("list_processes", {"pid": "42; DO_NOT_LOG_ME"})
        assert error_code(invalid) == "invalid_arguments"
        assert error_code(await client.call_tool("run_program", {})) == "unknown_tool"
        denied = await client.call_tool("read_file", {"path": "/data/demo-else/DO_NOT_LOG_ME"})
        assert error_code(denied) == "path_denied"
    assert not backend.connections
    text = audit.path.read_text()
    assert "DO_NOT_LOG_ME" not in text
    assert [
        json.loads(line)["code"] for line in text.splitlines() if '"event":"result"' in line
    ] == ["invalid_arguments", "unknown_tool", "path_denied"]


async def test_sftp_metadata_checks_and_utf8_boundary(setup):
    backend, profile, audit = setup
    files = backend.filesystem
    files.add("/data/demo/pages.txt", "abc€d".encode())
    files.entries["/data/demo/linkdir"] = Entry("symlink")
    files.add("/data/demo/alias.txt", b"data")
    files.canonical["/data/demo/alias.txt"] = "/data/else/secret.txt"
    files.add("/data/demo/binary", b"\x00\xff")
    async with Client(create_server(profile, audit, backend)) as client:
        for path in ("link", "fifo", "linkdir/a", "alias.txt"):
            denied = await client.call_tool("read_file", {"path": f"/data/demo/{path}"})
            assert error_code(denied) == "path_denied"
        assert not files.reads
        first = await client.call_tool(
            "read_file", {"path": "/data/demo/pages.txt", "max_bytes": 4}
        )
        page = first.structured_content["data"]
        assert (page["content"], page["next_offset"], page["eof"]) == ("abc", 3, False)
        second = await client.call_tool("read_file", {"path": "/data/demo/pages.txt", "offset": 3})
        assert second.structured_content["data"]["content"] == "€d"
        assert second.structured_content["data"]["eof"]
        binary = await client.call_tool("read_file", {"path": "/data/demo/binary"})
        assert error_code(binary) == "invalid_text"
    assert files.reads[:2] == [("/data/demo/pages.txt", 0, 4), ("/data/demo/pages.txt", 3, 4)]
    audit_text = audit.path.read_text()
    assert "/data/demo/pages.txt" not in audit_text
    assert all("content" not in json.loads(line) for line in audit_text.splitlines())


async def test_log_filters_use_epoch_and_severity_boundaries(setup):
    backend, profile, audit = setup
    async with Client(create_server(profile, audit, backend)) as client:
        result = await client.call_tool(
            "read_system_log",
            {
                "buffer_set": "fixture_a",
                "pid": 701,
                "severity_max": 3,
                "since_epoch_ms": 1_700_000_800_021,
                "until_epoch_ms": 1_700_000_800_021,
            },
        )
        assert [e["code"] for e in result.structured_content["data"]["entries"]] == [111]
        assert (
            error_code(
                await client.call_tool(
                    "read_system_log", {"since_epoch_ms": 10, "until_epoch_ms": 9}
                )
            )
            == "invalid_arguments"
        )
    assert backend.commands == [Command.LOG]


async def test_audit_failure_fails_closed(setup, tmp_path):
    backend, profile, audit = setup
    audit.path.parent.mkdir()
    other = tmp_path / "unchanged"
    other.write_text("original")
    audit.path.symlink_to(other)
    async with Client(create_server(profile, audit, backend)) as client:
        assert error_code(await client.call_tool("system_info")) == "audit_failure"
    assert not backend.connections
    assert other.read_text() == "original"


async def test_host_key_and_utility_failure_are_distinct(setup):
    backend, profile, audit = setup
    backend.connect_error = asyncssh.HostKeyNotVerifiable("not a client-facing value")
    async with Client(create_server(profile, audit, backend)) as client:
        bad = await client.call_tool("system_info")
        assert error_code(bad) == "host_key_mismatch"
        assert "client-facing" not in str(bad.structured_content)
        backend.connect_error = None
        backend.results[Command.UNAME] = CommandResult("", "not found", 127)
        assert error_code(await client.call_tool("system_info")) == "utility_unavailable"


async def test_deadline_and_cap_are_reported(setup):
    backend, profile, audit = setup
    original = backend.run

    async def blocked(command):
        await asyncio.sleep(2)
        return await original(command)

    backend.run = blocked
    async with Client(create_server(profile, audit, backend, timeout_s=0.05)) as client:
        assert error_code(await client.call_tool("system_info")) == "timeout"
    backend.run = original
    backend.results[Command.PROCESSES] = CommandResult(
        backend.results[Command.PROCESSES].stdout, exit_code=None, truncated=True
    )
    async with Client(create_server(profile, audit, backend)) as client:
        result = await client.call_tool("list_processes")
        assert not result.is_error and result.structured_content["truncated"]


async def test_fake_stdio_subprocess(tmp_path: Path):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "tests.stdio_fixture", str(tmp_path / "audit" / "stdio.jsonl")],
        cwd=str(Path(__file__).parent.parent),
    )
    async with Client(params, read_timeout_seconds=15) as client:
        listed = (await client.list_tools()).tools
        assert len(listed) == 4
        result = await client.call_tool("system_info")
        data = result.structured_content["data"]
        assert not result.is_error
        assert data["cpu_count"] == 2 and data["capabilities"]["sftp"]
        assert "MHz" not in data["cpu_model"]
        assert data["memory"]["total_bytes"] == 512 * 1024**2
