# QNX MCP Server

A read-only MCP server for diagnosing a QNX 8.0 target from a Linux development
host. The local demo reproduces a real synchronous IPC deadlock in two original
C programs and shows the wait cycle from structured QNX evidence.

## Why QNX

On QNX, a thread that sends a message can wait for a receiver (**SEND**) or for a
reply after the receiver accepted the message (**REPLY**). A thread in
**RECEIVE** can simply be an idle server. A generic process list cannot tell you
which IPC peer or channel is involved. This server reports those details from
`pidin` and leaves unknown fields empty, so an assistant can distinguish an idle
receiver from a real dependency cycle. [QNX message passing](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/m/msgsend.html)

```text
MCP client ── stdio ── Linux / WSL2 qnx-mcp ── verified SSH/SFTP ── QNX 8.0
```

The supported MVP target is **QEMU x86_64**. The tested host uses
**Ubuntu 24.04 WSL2**, **Python 3.12**, and the Linux **QNX SDP 8.0 series with
8.0.5 components**. The guest reports `QNX 8.0.0 x86pc` through `uname`.
The original demo uses `qcc -Vgcc_ntox86_64`. The MCP process itself needs no
SDK, compiler, AWS credentials, or application-side LLM key.

## Install and connect

1. Obtain your own [QNX Everywhere SDK and license](https://www.qnx.com/products/everywhere/).
   Build and boot a private guest using [the QEMU setup](docs/qemu.md).
2. Inside Linux, install project dependencies with [uv](https://docs.astral.sh/uv/getting-started/installation/):

   ```sh
   uv sync --locked
   ```

   Alternatively, use `python3 -m venv .venv` and
   `.venv/bin/python -m pip install -e .` if your Linux Python provides pip.
3. Copy [targets/qemu.yaml](targets/qemu.yaml) to a **private file outside
   the repo**. Set its SSH key, verified `known_hosts` and narrow `read_roots`.
   Relative host file paths are resolved against the profile's directory.
4. Configure your client using [Claude Desktop / VS Code instructions](docs/clients.md).
   The launcher command for Linux is:

   ```sh
   /bin/sh /absolute/repo/scripts/launch-mcp.sh --profile /absolute/private/qemu.local.yaml
   ```

The server waits for MCP on stdin. It does not listen on a network port. With no
`--profile`, it uses the loopback QEMU defaults shown in the sample YAML. An
owner-selected YAML can point at another QNX 8.0 guest without code changes;
only the local x86_64 setup has been validated for this release.

## Tools

| Tool | Inputs | Evidence |
| --- | --- | --- |
| `system_info` | None | QNX release/machine, CPU and approximate memory from `uname` and `pidin info`; observed SFTP availability. |
| `list_processes` | Optional `pid`, executable substring `name`, thread `limit` | PID/TID, scheduling state, priority, observed IPC peer/channel IDs, wait-for analysis. |
| `read_system_log` | Optional `buffer_set`, `pid`, `severity_max`, `since_epoch_ms`, `until_epoch_ms`, `limit` | Bounded `slog2info -f -s -t` snapshot, filtered locally. Lower severity numbers are more urgent. |
| `read_file` | Absolute `path`, optional byte `offset` and `max_bytes` | Bounded UTF-8 text from a regular file under an approved root. Follow `next_offset` for subsequent pages. |

Every successful response includes a target ID, observation time, status,
warnings and a truncation flag. `partial` means some evidence is unavailable or
clipped; a QNX query can return exit code zero and still have permission denials.
The parser uses the real-target-verified `%80B` width and does not invent a peer
TID when `pidin` gives only a PID. Cross-UID visibility is restricted, and the
process list is not an atomic or system-wide snapshot. [QNX pidin reference](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/p/pidin.html)

## Reproduce the diagnosis

Follow the [deadlock demo](examples/deadlock_demo/README.md) to build and stage
the two programs manually. Read-only MCP calls show **A REPLY → B** and
**B SEND → A**, plus a normal RECEIVE thread on an unrelated channel. The
assistant can connect those observations to the callback-before-reply line in
the source. The developer reruns in `--fixed` mode to demonstrate that
reply-before-callback completes the request.

Illustrative, from the synthetic fixture: trimmed `list_processes` data for
[pidin.txt](tests/fixtures/synthetic/pidin.txt), with A as PID 701 and B as PID 804.

```json
{"processes": [
  {"pid": 701, "threads": [
    {"tid": 1, "state": "REPLY", "blocked_on": {"peer_pid": 804, "peer_tid": null, "channel_id": 3}},
    {"tid": 2, "state": "RECEIVE", "blocked_on": {"channel_id": 6}}]},
  {"pid": 804, "threads": [
    {"tid": 1, "state": "SEND", "blocked_on": {"peer_pid": 701, "peer_tid": null, "channel_id": 2}}]}]}
```

A's thread 1 waits for B's reply; B's thread 1 waits for A to receive on channel 2.
A's thread 2 is idle on channel 6, and `peer_tid` stays null because `pidin` gives only the PID.

The [instrument-cluster freeze](examples/cluster_freeze/README.md) simulates a
cockpit whose radar fault freezes the whole cluster.

[Manual verification](docs/manual-testing.md) describes the tested QEMU path
and the separate SDK-free checks. [Demo storyboard](docs/demo.md) is a recording
script; no demo video is bundled. <!-- TODO: replace with the video link once the video is public. -->

## Safety

The server binds one trusted profile at startup. It accepts no arbitrary host,
shell command, target write, execution, delete or cloud action. It verifies SSH
host keys, uses a non-root account, bounds reads, checks path components and
writes a private audit log. Configure the client to ask before every call:
Claude Desktop needs **Manual** permission mode and VS Code needs the workspace
policy in [client setup](docs/clients.md). Annotations describe intent and do
not enforce consent. Target text can contain
prompt injection and must be treated as data. See [SECURITY.md](SECURITY.md) for
the trust boundary, path race limitation and planned hardening.

## Development

```sh
uv sync --locked
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv build --wheel --no-sources
```

Public CI uses Linux and hand-written synthetic fixtures with a fake SSH/SFTP
backend. It does not use QNX, credentials or target captures. Real target
validation is a separate opt-in check. [ROADMAP.md](ROADMAP.md) lists what this
release covers and the planned two-guest scenario.

Original code is [MIT licensed](LICENSE). QNX software, images, SDK files,
vendor samples and target captures are not distributed. Obtain vendor
components under their own terms. The demo presents functional behavior.
