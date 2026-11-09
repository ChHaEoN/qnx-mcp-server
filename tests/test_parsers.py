import pytest

from qnx_mcp.errors import ToolFailure
from qnx_mcp.parsers import parse_logs, parse_processes, parse_uname

from .fakes import fixture


def test_ipc_fields_do_not_invent_a_peer_tid():
    processes, notes = parse_processes(fixture("pidin.txt"))
    caller, responder, clipped, future = processes
    reply, receive = caller.threads
    assert caller.executable.endswith("peer one")
    assert (reply.priority, reply.policy) == (12, "r")
    assert reply.blocked_on.peer_pid == responder.pid
    assert reply.blocked_on.channel_id == 3
    assert reply.blocked_on.peer_tid is None
    assert (reply.blocked_on.coid, reply.blocked_on.scoid) == (901, 47)
    assert receive.blocked_on.kind == "channel"
    assert receive.blocked_on.channel_id == 6
    assert receive.blocked_on.peer_pid is None
    assert responder.threads[0].blocked_on.peer_pid == caller.pid
    assert clipped.threads[0].blocked_on.availability == "unknown"
    assert notes["unknown IPC endpoints"] == 1
    assert future.threads[0].state == "FUTURE_STATE"


def test_duplicate_and_malformed_rows_are_partial():
    lines = fixture("pidin.txt").splitlines()
    rows, notes = parse_processes("\n".join(lines[:2] + [lines[1], "no|complete|row"]))
    assert len(rows[0].threads) == 1
    assert notes == {"duplicate thread rows": 1, "malformed thread rows": 1}


def test_wrong_format_does_not_look_like_empty_success():
    with pytest.raises(ToolFailure, match="thread header"):
        parse_processes("Linux ps output\n")
    with pytest.raises(ToolFailure, match="epoch records"):
        parse_logs("Nov 04 not the selected epoch format\n")
    with pytest.raises(ToolFailure, match="recognized QNX"):
        parse_uname("Linux 8.0.0 x86_64")


def test_log_order_owner_and_multiline():
    logs, notes = parse_logs(fixture("slog2.txt"))
    assert not notes
    assert logs[0].epoch_ms == 1_700_000_800_015
    assert logs[0].pid == 701
    assert logs[0].buffer_set == "fixture_a"
    assert logs[0].oldest and not logs[1].oldest
    assert (logs[0].tid, logs[0].code, logs[0].severity) == (2, 110, 5)
    assert logs[0].message.endswith("\n   second line of the original message")
    assert parse_logs("") == ([], {})
