# Manual verification

The public test suite uses invented fixtures and a fake backend. The
opt-in target check requires a running QNX guest and a text file you staged
under a configured read root. It makes real calls through an SDK stdio client
and prints only pass/fail summaries:

```sh
uv run --frozen python scripts/manual_target_check.py \
  --profile "$work/qemu.local.yaml" \
  --audit-log "$work/audit/check.jsonl" \
  --file /data/home/qnxuser/qnx-mcp-demo/peer_b.c \
  --contains 'late MsgReply'
```

Run [the sample](../examples/deadlock_demo/README.md) and use
`--process-name peer_ --expect-wait-states --buffer-set qnx_mcp_peer_b` while the
faulty pair is alive. Check that the observed PID/channel values match the
sample's handshake output and that the idle receiver is on a different channel.
Verify the fixed run manually. The SDK check does not start programs, configure
guest permissions, or substitute for the GUI approval check in [clients.md](clients.md).

For the [instrument-cluster freeze](../examples/cluster_freeze/README.md), run the
check while the faulty cockpit is frozen with `--process-name cluster_display
--buffer-set qnx_mcp_cluster_fusion --expect-end-in radar_svc`, and point
`--file` at the staged `vehicle_fusion.c`. The last option requires the
top-ranked `wait_analysis` end to be an untimed wait in `radar_svc`.

The WSL2 acceptance used the Linux SDP 8.0 installation with 8.0.5 components,
QEMU 8.2.2 with the local AVX2 mask, `qnxuser`, and MCP Python SDK 2.3.0. The
non-root test observed SEND/REPLY peer PIDs, connection and channel details with
`%80B`, and RECEIVE channel IDs on two same-UID processes. Cross-UID process
visibility remains limited. The combined `slog2info -f -s -t` layout and Unix
epoch time basis were checked against the guest clock. Real-target evidence
remains outside Git. Record the actual client and toolchain versions when
repeating the check.

The VS Code 1.142.0 GUI approval check passed on November 5, 2026, with the
Local harness, Default permissions and the workspace policy in
[clients.md](clients.md). The test used `system_info({})` over the Windows
`wsl.exe` stdio bridge to the real QEMU guest.

| GUI action | New server audit requests | Result |
| --- | --- | --- |
| Decline the pre-call prompt with Skip | 0 | Client reported the denial and stopped. |
| Approve the first call once | 1 | One successful result. |
| Approve a second call in the same conversation once | 1 | A new pre-call prompt appeared before the second request. |

Both result reviews used Allow Once. Private checkpoints verified distinct
request IDs and one successful result per accepted call. Counts retain a
separate initial call that the default Copilot harness automatically approved
before the workspace policy was added. The table describes the subsequent
Local harness checks. Raw audit records and target observations stay outside
the repository.

The Claude Desktop 4.16336.0 (Microsoft Store) approval check passed on
November 6, 2026, in **Manual** permission mode. It used a temporary local MCP
entry, the same `wsl.exe` bridge, a separate audit log and `system_info({})`
against the real QEMU guest. All three actions happened in one conversation.

| GUI action | New server audit requests | Result |
| --- | --- | --- |
| Decline the approval card | 0 | Client showed `Didn't run`; no request reached the server. |
| Allow the first call once | 1 | One successful result. |
| Allow a second call once | 1 | A new approval card appeared before the second request. |

No request was logged while each card was pending. The two accepted calls had
distinct request IDs and `ok` results. A control call in the default **Auto**
mode ran without a prompt; the counts above exclude it. The chat used Haiku
5.5. The temporary entry was removed from the desktop configuration afterwards.

The same VS Code Local harness diagnosed the live deadlock in a fresh chat.
Twelve QNX calls were approved individually. The agent found A's main thread
REPLY-blocked on B, B's main thread SEND-blocked on A's callback channel and
A's idle thread RECEIVE-blocked on a separate channel. It used B's phase log
and staged source to locate the callback `MsgSend` before the late `MsgReply`.
Check source statements when reviewing the diagnosis. The first answer gave
inaccurate line numbers, and the follow-up cited the correct statements.

The developer reran the fixed branch over SSH and checked exit code zero.
The agent read the saved `DEMO_OK` marker and found no remaining peers in the
account-visible process list. The named slog2 buffers returned no entries
after exit. The [sample instructions](../examples/deadlock_demo/README.md)
reproduce the approval window and the manual rerun.

## Instrument-cluster freeze

The [cluster sample](../examples/cluster_freeze/README.md) was checked on
November 10, 2026, on the same QEMU guest and `qnxuser` account, with a
temporary key and a separate audit log. All five programs built with
`qcc -Vgcc_ntox86_64 -Wall -Wextra -Werror`, using both the default watchdog and
`-DWATCHDOG_SECONDS=900`.

| Run | Operator result | SDK stdio check |
| --- | --- | --- |
| Default fault | Panel froze at frame 3; `DEMO_HANG` after the display watchdog. | All four tools passed; the top `wait_analysis` end was `radar_svc` in `RECEIVE`. |
| `--fixed` | 12 frames; later frames showed ADAS unavailable; `DEMO_OK`. | Read `fixed-run.txt` with its `DEMO_OK` marker. |
| `--healthy` | 12 frames with live radar data; `DEMO_OK`. | Read `healthy-run.txt` with its `DEMO_OK` marker. |

During the freeze, `list_processes` for `cluster_display` reported three blocked
display threads and followed them through `vehicle_fusion` to `radar_svc`. The
radar's `RECEIVE` and `CONDVAR` threads ranked first, and the heartbeat's
`NANOSLEEP` thread ranked last. There were no cycles. All candidate threads were
`possible`, except the observed JOIN target. The fixed run's fusion log showed
the 2-second deadline expiring, confirming that `TimerTimeout` returned
`ETIMEDOUT` to `MsgSend`. A later radar request was SEND-blocked and also
timed out.

This guest printed the MUTEX state as `MUTEX?`, with a hexadecimal sync ID and no
owner. The parser keeps the reported text, and the analysis treats it as MUTEX.
`use pidin` on the guest does not explain the question mark. The launcher's
`waitpid` appeared as REPLY to `procnto` (PID 1), which `qnxuser` cannot inspect.
Slog2 entries carry thread IDs, so the logs, not `pidin`, show which fusion
thread held `state_lock`. Raw snapshots stay outside the repository.

Later on November 10, an assistant received the sample's prompt and only the four
tools through a stdio client, without the sample README or local sources. It
reported the lock held across the unbounded `MsgSend` and proposed the
bounded-wait fix, and its source citations matched the staged files. It had to
guess file names, and narrow log reads with `pid` and `until_epoch_ms`, because
heartbeats crowded the fusion buffer set and every marker was INFO.

On November 11 the sample moved heartbeats to `qnx_mcp_cluster_heartbeat` and
logged faults at warning severity, and the prompt now names the files and
buffer sets. A rerun on the same guest returned the radar's `front end lost`
entry with `severity_max` 3, only phase markers from `qnx_mcp_cluster_fusion`,
and the fixed run's timeouts at severity 3. No GUI client chat has been run
against this sample yet.
