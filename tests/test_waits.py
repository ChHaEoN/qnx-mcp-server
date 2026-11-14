from qnx_mcp.parsers import parse_processes
from qnx_mcp.waits import MAX_CANDIDATES, MAX_EDGES, MAX_ENDS, analyze_waits

from .fakes import fixture

HEADER = "pid | tid | prio | STATE | Blocked | name\n"


def snapshot(text):
    processes, notes = parse_processes(text)
    return processes, {(p.pid, t.tid) for p in processes for t in p.threads}, notes


def edge(analysis, pid, tid):
    return next(e for e in analysis.edges if (e.source.pid, e.source.tid) == (pid, tid))


def test_qualified_state_and_join_target_are_parsed():
    processes, _, notes = snapshot(fixture("pidin_cluster.txt"))
    assert not notes
    states = {(p.pid, t.tid): t for p in processes for t in p.threads}
    assert states[(320, 1)].state == "MUTEX?"
    join = states[(340, 1)].blocked_on
    assert (join.kind, join.peer_tid, join.peer_pid) == ("thread", 2, None)


def test_two_peer_cycle_is_a_candidate_that_needs_confirmation():
    processes, everything, _ = snapshot(fixture("pidin.txt"))
    analysis = analyze_waits(processes, everything)
    reply = edge(analysis, 701, 1)
    assert (reply.relation, reply.target_pid, reply.target_tid) == ("reply", 804, None)
    assert (reply.candidates, reply.candidate_basis) == ([1], "inferred")
    send = edge(analysis, 804, 1)
    assert (send.candidates, send.candidate_basis) == ([1, 2], "possible")
    [cycle] = analysis.cycles
    assert [(t.pid, t.tid) for t in cycle.threads] == [(701, 1), (804, 1)]
    assert cycle.basis == "possible"
    [idle] = analysis.ends
    assert (idle.thread.pid, idle.thread.tid, idle.kind, idle.dependents) == (
        701,
        2,
        "untimed_wait",
        2,
    )
    assert not idle.reached_without_possible
    assert all(e.source.pid != 960 for e in analysis.edges)


def test_frozen_display_chain_ranks_untimed_waits_first():
    processes, everything, _ = snapshot(fixture("pidin_cluster.txt"))
    analysis = analyze_waits(processes, everything)
    assert analysis.blocked_threads == 6 and not analysis.cycles and not analysis.truncated
    join = edge(analysis, 340, 1)
    assert (join.relation, join.target_tid, join.candidates, join.candidate_basis) == (
        "join",
        2,
        [2],
        "observed",
    )
    mutex = edge(analysis, 320, 1)
    assert (mutex.candidates, mutex.candidate_basis) == ([2, 3], "possible")
    for tid in (2, 3):
        wait = edge(analysis, 340, tid)
        assert (wait.target_pid, wait.target_tid, wait.candidates) == (320, None, [1, 2, 3])
    ranked = [(e.thread.pid, e.thread.tid, e.kind, e.dependents) for e in analysis.ends]
    assert ranked == [
        (310, 1, "untimed_wait", 5),
        (310, 2, "untimed_wait", 5),
        (1, None, "not_visible", 1),
        (320, 3, "self_resolving", 4),
    ]
    assert [e.reached_without_possible for e in analysis.ends] == [False, False, True, False]
    assert all(e.thread.pid != 330 for e in analysis.ends)
    assert any("MUTEX owners" in note for note in analysis.limitations)


def test_analysis_follows_only_the_returned_threads():
    processes, _, _ = snapshot(fixture("pidin_cluster.txt"))
    analysis = analyze_waits(processes, {(340, 1), (340, 2), (340, 3)})
    assert analysis.blocked_threads == 3
    assert {e.source.pid for e in analysis.edges} == {320, 340}
    assert [(e.thread.pid, e.thread.tid, e.dependents) for e in analysis.ends] == [
        (310, 1, 3),
        (310, 2, 3),
        (320, 3, 3),
    ]
    idle = analyze_waits(processes, {(330, 1), (330, 2)})
    assert idle.blocked_threads == 0 and not idle.edges and not idle.ends and not idle.limitations


def test_hidden_targets_and_unresolvable_waits_are_reported():
    text = HEADER + (
        "50 | 1 | 10r | REPLY | other(77) 1s-1-1s | /data/demo/client\n"
        "51 | 1 | 10r | JOIN | 4 | /data/demo/joiner\n"
        "52 | 1 | 10r | SEND | self(52) 1s-1-1s | /data/demo/self caller\n"
    )
    processes, everything, _ = snapshot(text)
    analysis = analyze_waits(processes, everything)
    ends = {(e.thread.pid, e.thread.tid): e.kind for e in analysis.ends}
    assert ends == {(77, None): "not_visible", (51, 1): "unresolved", (52, 1): "unresolved"}
    assert edge(analysis, 50, 1).target_visible is False
    assert any("not visible" in note for note in analysis.limitations)


def test_large_snapshots_are_capped_and_flagged():
    rows = [f"9000 | {tid} | 10r | RECEIVE | 1 | /data/demo/pool\n" for tid in range(1, 71)]
    rows += [
        f"{pid} | 1 | 10r | REPLY | pool(9000) 1s-1-1s | /data/demo/c\n" for pid in range(1, 401)
    ]
    processes, everything, _ = snapshot(HEADER + "".join(rows))
    analysis = analyze_waits(processes, everything)
    assert analysis.truncated
    assert len(analysis.edges) == MAX_EDGES and len(analysis.ends) == MAX_ENDS
    assert all(len(e.candidates) == MAX_CANDIDATES for e in analysis.edges)
    assert analysis.ends[0].dependents == 400
