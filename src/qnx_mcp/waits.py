"""Wait-for analysis over one pidin snapshot; it never invents a peer thread.

pidin names the peer *process* for SEND and REPLY. Any other thread of that process could
release the wait, because a QNX server may receive a message, return to MsgReceive and reply
later from another thread. Candidates are therefore every other thread of the target process:
"inferred" when exactly one exists, otherwise "possible". MUTEX owners are not reported, so
MUTEX candidates are always "possible". JOIN names the joined thread directly ("observed").
"""

from collections import deque

from .parsers import base_state
from .schemas import Process, Thread, ThreadRef, WaitAnalysis, WaitEdge, WaitEnd, WaitGroup

MAX_EDGES = 300
MAX_ENDS = 50
MAX_CYCLES = 20
MAX_CANDIDATES = 64

SELF_RESOLVING = frozenset({"RUNNING", "READY", "NANOSLEEP"})
UNTIMED_WAITS = frozenset(
    {"RECEIVE", "CONDVAR", "SEM", "SIGSUSPEND", "SIGWAITINFO", "INTR", "STOPPED"}
)
_STRENGTH = {"observed": 0, "inferred": 1, "possible": 2}
_END_RANK = {"untimed_wait": 0, "unresolved": 1, "not_visible": 2, "self_resolving": 3}

LIMITATIONS = {
    "peer": "SEND/REPLY name the peer process, not the peer thread; any other thread of that "
    "process may release the wait because servers can defer replies",
    "mutex": "MUTEX owners are not reported; candidates assume a mutex private to the process",
    "hidden": "Processes that are not visible to the SSH account cannot be followed",
    "snapshot": "One pidin snapshot: rows are read sequentially and states can change between them",
}

Key = tuple[int, int]


def _others(proc: Process, exclude: Key) -> list[int]:
    return [t.tid for t in proc.threads if (proc.pid, t.tid) != exclude]


def _edge(proc: Process, thread: Thread, by_pid: dict[int, Process]) -> WaitEdge | None:
    state = base_state(thread.state)
    wait = thread.blocked_on
    source = ThreadRef(pid=proc.pid, tid=thread.tid)
    key = (proc.pid, thread.tid)
    if state in {"SEND", "REPLY"} and wait.peer_pid is not None:
        target = by_pid.get(wait.peer_pid)
        tids = _others(target, key) if target else []
        return WaitEdge(
            source=source,
            relation="send" if state == "SEND" else "reply",
            target_pid=wait.peer_pid,
            target_visible=target is not None,
            channel_id=wait.channel_id,
            candidates=tids,
            candidate_basis=("inferred" if len(tids) == 1 else "possible") if tids else None,
        )
    if state == "MUTEX":
        tids = _others(proc, key)
        return WaitEdge(
            source=source,
            relation="mutex",
            target_pid=proc.pid,
            target_visible=True,
            candidates=tids,
            candidate_basis="possible" if tids else None,
        )
    if state == "JOIN" and wait.peer_tid is not None:
        found = any(t.tid == wait.peer_tid for t in proc.threads)
        return WaitEdge(
            source=source,
            relation="join",
            target_pid=proc.pid,
            target_tid=wait.peer_tid,
            target_visible=True,
            candidates=[wait.peer_tid] if found else [],
            candidate_basis="observed" if found else None,
        )
    return None


def _end_kind(thread: Thread) -> str:
    state = base_state(thread.state)
    if state in SELF_RESOLVING:
        return "self_resolving"
    if state in UNTIMED_WAITS:
        return "untimed_wait"
    return "unresolved"


def _cycles(nodes: list[Key], edges: dict[Key, WaitEdge]) -> list[list[Key]]:
    """Strongly connected components with more than one thread (iterative Tarjan)."""
    index: dict[Key, int] = {}
    low: dict[Key, int] = {}
    stack: list[Key] = []
    on_stack: set[Key] = set()
    groups: list[list[Key]] = []

    def successors(key: Key) -> list[Key]:
        edge = edges.get(key)
        return [(edge.target_pid, tid) for tid in edge.candidates] if edge else []

    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(successors(root)))]
        index[root] = low[root] = len(index)
        stack.append(root)
        on_stack.add(root)
        while work:
            node, children = work[-1]
            child = next(children, None)
            if child is not None:
                if child not in index:
                    index[child] = low[child] = len(index)
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(successors(child))))
                elif child in on_stack:
                    low[node] = min(low[node], index[child])
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                group = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    group.append(member)
                    if member == node:
                        break
                if len(group) > 1:
                    groups.append(sorted(group))
    return sorted(groups)


def analyze_waits(processes: list[Process], roots: set[Key]) -> WaitAnalysis:
    """Follow waits from the returned threads through the whole visible snapshot."""
    by_pid = {proc.pid: proc for proc in processes}
    threads = {(proc.pid, t.tid): (proc, t) for proc in processes for t in proc.threads}
    edges: dict[Key, WaitEdge] = {}
    for key, (proc, thread) in threads.items():
        if (edge := _edge(proc, thread, by_pid)) is not None:
            edges[key] = edge
    starts = sorted(key for key in roots if key in edges)
    if not starts:
        return WaitAnalysis()

    def reach(start: Key, allow_possible: bool) -> tuple[set[Key], set[tuple[str, Key]]]:
        seen, queue, ends = {start}, deque([start]), set()
        while queue:
            key = queue.popleft()
            edge = edges.get(key)
            if edge is None:
                ends.add(("thread", key))
            elif not edge.target_visible:
                ends.add(("hidden", (edge.target_pid, -1)))
            elif not edge.candidates:
                ends.add(("thread", key))
            elif allow_possible or edge.candidate_basis != "possible":
                for tid in edge.candidates:
                    if (node := (edge.target_pid, tid)) not in seen:
                        seen.add(node)
                        queue.append(node)
        return seen, ends

    closure: set[Key] = set()
    dependents: dict[tuple[str, Key], int] = {}
    certain: set[tuple[str, Key]] = set()
    for start in starts:
        seen, ends = reach(start, allow_possible=True)
        closure |= seen
        for end in ends:
            dependents[end] = dependents.get(end, 0) + 1
        certain |= reach(start, allow_possible=False)[1]

    nodes = sorted(closure)
    closure_edges = [edges[key] for key in nodes if key in edges]
    truncated = len(closure_edges) > MAX_EDGES
    shown = []
    for edge in closure_edges[:MAX_EDGES]:
        if len(edge.candidates) > MAX_CANDIDATES:
            truncated = True
            edge = edge.model_copy(update={"candidates": edge.candidates[:MAX_CANDIDATES]})
        shown.append(edge)

    ends = []
    for (kind, (pid, tid)), count in dependents.items():
        if kind == "hidden":
            end = WaitEnd(
                thread=ThreadRef(pid=pid),
                kind="not_visible",
                dependents=count,
                reached_without_possible=(kind, (pid, tid)) in certain,
            )
        else:
            proc, thread = threads[(pid, tid)]
            end = WaitEnd(
                thread=ThreadRef(pid=pid, tid=tid),
                executable=proc.executable,
                state=thread.state,
                blocked=thread.blocked_on.raw,
                kind="unresolved" if (pid, tid) in edges else _end_kind(thread),
                dependents=count,
                reached_without_possible=(kind, (pid, tid)) in certain,
            )
        ends.append(end)
    ends.sort(
        key=lambda e: (
            _END_RANK[e.kind],
            -e.dependents,
            not e.reached_without_possible,
            e.thread.pid,
            e.thread.tid or 0,
        )
    )
    truncated |= len(ends) > MAX_ENDS

    groups = []
    for members in _cycles(nodes, edges):
        inside = set(members)
        basis = max(
            (
                edges[key].candidate_basis or "possible"
                for key in members
                if any((edges[key].target_pid, tid) in inside for tid in edges[key].candidates)
            ),
            key=_STRENGTH.__getitem__,
        )
        groups.append(WaitGroup(threads=[ThreadRef(pid=p, tid=t) for p, t in members], basis=basis))
    truncated |= len(groups) > MAX_CYCLES

    relations = {edge.relation for edge in closure_edges}
    notes = []
    if relations & {"send", "reply"}:
        notes.append(LIMITATIONS["peer"])
    if "mutex" in relations:
        notes.append(LIMITATIONS["mutex"])
    if any(not edge.target_visible for edge in closure_edges):
        notes.append(LIMITATIONS["hidden"])
    notes.append(LIMITATIONS["snapshot"])
    return WaitAnalysis(
        blocked_threads=len(starts),
        edges=shown,
        ends=ends[:MAX_ENDS],
        cycles=groups[:MAX_CYCLES],
        limitations=notes,
        truncated=truncated,
    )
