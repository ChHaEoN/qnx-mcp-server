import pytest

from qnx_mcp.errors import ToolFailure
from qnx_mcp.parsers import parse_info, parse_logs, parse_processes, parse_uname

from .fakes import SYSTEM_OUTPUT, fixture


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("QNX 8.0.0 x86pc x86_64\n", ("8.0.0", "x86pc", "x86_64")),
        ("QNX 8.0.0 Imaginary_virt aarch64le\n", ("8.0.0", "Imaginary_virt", "aarch64")),
        ("QNX 8.0.2 Fictional_board aarch64le", ("8.0.2", "Fictional_board", "aarch64")),
    ],
)
def test_uname_takes_the_architecture_from_the_processor_not_the_board(text, expected):
    assert parse_uname(text) == expected


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("QNX 8.0.0 x86pc\n", "parse_error"),
        ("QNX 8.0.0 Imaginary_virt aarch64be", "unsupported_target"),
        ("QNX 8.0.0 Imaginary_virt arm64", "unsupported_target"),
        ("QNX 7.1.0 x86pc x86_64", "unsupported_target"),
    ],
)
def test_uname_rejects_unvalidated_processors_and_layouts(text, code):
    with pytest.raises(ToolFailure) as caught:
        parse_uname(text)
    assert caught.value.code == code


@pytest.mark.parametrize("arch", ["x86_64", "aarch64"])
def test_pidin_info_on_both_architectures(arch):
    count, model, memory = parse_info(SYSTEM_OUTPUT[arch][1])
    assert count == 2
    assert model == {"x86_64": "Fictional Model", "aarch64": "Fictional-A7"}[arch]
    assert memory.total_bytes and memory.free_bytes and memory.approximate


def test_aarch64_wait_rows_and_log_layout():
    processes, notes = parse_processes(fixture("pidin_aarch64.txt"))
    assert not notes
    panel, service = processes
    assert (panel.pid, panel.executable, service.executable) == (
        2203651,
        "./shift_panel",
        "./gear_svc",
    )
    reply, receive = panel.threads
    assert (reply.blocked_on.peer_pid, reply.blocked_on.channel_id) == (2207748, 1)
    assert receive.blocked_on.channel_id == 2
    send, mutex, condvar, sleep = service.threads
    assert send.blocked_on.peer_pid == 2203651
    assert (mutex.state, mutex.blocked_on.kind, mutex.blocked_on.raw) == (
        "MUTEX?",
        "other",
        "3a1f00c00c",
    )
    assert condvar.blocked_on.raw == "(0x31ab7e9010)"
    assert sleep.blocked_on.kind == "none"
    logs, notes = parse_logs(fixture("slog2_aarch64.txt"))
    assert not notes
    assert [(e.pid, e.buffer_set, e.severity) for e in logs] == [
        (2203651, "shift_panel", 5),
        (2207748, "gear_svc", 5),
        (2207748, "gear_svc", 3),
    ]
    assert logs[0].oldest and logs[2].message == "callback still pending"


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
        parse_uname("Linux 8.0.0 x86pc x86_64")


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
