# Instrument-cluster freeze

A simulated cockpit for development only, written for this project. It makes no
safety claim. The instrument cluster shows speed, gear and the forward-collision
warning (FCW) status. After a few frames, the front radar's simulated front end
stops. The radar only feeds ADAS, yet the whole cluster freezes, speedometer
included, while `vehicle_fusion` keeps logging `heartbeat N: vehicle_fusion alive`.

```text
cluster_display ── GET_PANEL / GET_TELLTALES ──> vehicle_fusion ── GET_OBJECTS ──> radar_svc
  tid 1  main: JOIN on the panel thread          tid 1  request worker            tid 1  request loop
  tid 2  panel thread, refresh every 500 ms      tid 2  radar sync                tid 2  front end
  tid 3  telltale thread, poll every 500 ms      tid 3  heartbeat
diag_svc: two idle RECEIVE threads, unrelated    cockpit_launch: starts, waits and stops the rest
```

**The bug.** The radar-sync thread takes `state_lock`, then calls `radar_svc`
with `MsgSend` and no deadline. `radar_svc` accepts the request and defers its
reply until the next radar frame. Once the front end has stopped, that frame
never arrives. The request worker then waits for `state_lock`. One cluster
request has been received and is waiting for its reply (REPLY); the other has
not been received yet (SEND).

On the tested QEMU guest the faulty run showed these states:

| Thread | `pidin` state and Blocked field | Meaning |
| --- | --- | --- |
| `cluster_display` 1 | `JOIN` `2` | Waits for the panel thread. |
| `cluster_display` 2, 3 | `REPLY` / `SEND` to `vehicle_fusion` channel 1 | One request accepted, one not yet received. |
| `vehicle_fusion` 1 | `MUTEX?` and a sync ID | Waits for `state_lock`; `pidin` names no owner. |
| `vehicle_fusion` 2 | `REPLY` to `radar_svc` channel 1 | The radar accepted the object request. |
| `vehicle_fusion` 3 | `NANOSLEEP` | Heartbeat; it wakes by itself. |
| `radar_svc` 1 | `RECEIVE` `2` | Waits on its private frame channel, not the request channel. |
| `radar_svc` 2 | `CONDVAR` | The front end waits for re-initialisation. |
| `diag_svc` 1, 2 | `RECEIVE` `1` | Idle server, unrelated to the freeze. |

The launcher, `cockpit_launch`, has three modes:

| Command | Radar | Fusion | Result |
| --- | --- | --- | --- |
| `./cockpit_launch` | Front end lost after frame 10 | Holds the lock, no deadline | Panel freezes; `DEMO_HANG` after the display watchdog. |
| `./cockpit_launch --healthy` | Keeps running | Holds the lock, no deadline | 12 frames with live radar data; `DEMO_OK`. |
| `./cockpit_launch --fixed` | Front end lost after frame 10 | Releases the lock and waits at most 2 s | 12 frames, ADAS shown unavailable; `DEMO_OK`. |

## Build and stage

Compile from Linux with the SDK environment loaded and keep the binaries in your
private lab:

```sh
repo=/absolute/path/to/qnx-mcp-server
mkdir -p "$work/cluster-build"
for p in radar_svc vehicle_fusion cluster_display diag_svc cockpit_launch; do
  qcc -Vgcc_ntox86_64 -Wall -Wextra -O0 -g \
    -o "$work/cluster-build/$p" "$repo/examples/cluster_freeze/$p.c" -lslog2
done
```

The display's watchdog defaults to 30 seconds and ends a frozen run. Services
stop 3 seconds later and the launcher 5 seconds later. For interactive
approvals, add `-DWATCHDOG_SECONDS=900` to every build; 900 is the limit.

Use the [lab SSH configuration](../../docs/qemu.md) and SFTP to upload the five
binaries, the five C files and `cockpit.h` to
`/data/home/qnxuser/qnx-mcp-demo/cluster`, inside the profile's read root. Make
the binaries executable. Run the launcher from that directory, because it starts
`./radar_svc` and the other programs by relative path.

## Diagnose the freeze

Start the faulty run in an operator terminal. It prints a `COCKPIT_READY` line
with the PIDs and channel IDs, then a panel every 500 ms until the freeze:

```sh
ssh -F "$work/ssh.conf" qnx-mcp-demo \
  'cd /data/home/qnxuser/qnx-mcp-demo/cluster && ./cockpit_launch'
```

```text
+------------------ CLUSTER frame  3 ------------------+
|  SPEED  51 km/h   GEAR D   ADAS FCW ready, 2 objects |
+------------------------------------------------------+
```

Open a fresh assistant chat with the [approval policy](../../docs/clients.md),
leave the sources out of the attachments and approve each read:

> The instrument cluster stopped updating: `cluster_display` repeats its last
> frame while `vehicle_fusion` keeps logging heartbeats. Diagnose it using only
> the QNX MCP tools. The staged sources are in
> `/data/home/qnxuser/qnx-mcp-demo/cluster`. Separate observed thread states from
> inferences and cite the source statements.

`list_processes` with name `cluster_display` returns the display threads and a
`wait_analysis` that follows their waits into the other processes. It ranks the
radar's `RECEIVE` and `CONDVAR` threads first as untimed waits, and the
heartbeat's `NANOSLEEP` last because it wakes by itself. Candidate threads are
marked `possible`: `pidin` names the peer process, not the peer thread, and gives
no MUTEX owner. `read_system_log` with buffer sets `qnx_mcp_cluster_fusion` and
`qnx_mcp_cluster_radar` links the request IDs. Its thread IDs show which fusion
thread logged `sent while holding state_lock` and which logged
`waiting for state_lock`. They also show the radar's `front end lost` marker.
`read_file` on `vehicle_fusion.c` shows `sync_radar_holding_lock`. The mutex owner
comes from those logs and the source, not from `pidin`.

## Manual fix and rerun

The fixed path, `sync_radar_with_deadline`, releases `state_lock` before the call
and sets `TimerTimeout(CLOCK_MONOTONIC, _NTO_TIMEOUT_SEND | _NTO_TIMEOUT_REPLY,
…)` for 2 seconds. On `ETIMEDOUT` it marks ADAS unavailable. The radar keeps
failing, but the cluster keeps updating its speed:

```sh
ssh -F "$work/ssh.conf" qnx-mcp-demo \
  'cd /data/home/qnxuser/qnx-mcp-demo/cluster || exit 1
   ./cockpit_launch --fixed >fixed-run.txt
   result=$?
   tail -4 fixed-run.txt
   exit "$result"'
```

Expect `ADAS FCW UNAVAILABLE` in the later frames and a final `DEMO_OK` line.
Have the assistant read `fixed-run.txt` and confirm that the cockpit processes
have exited. The timeout does not cancel the radar's pending request.
`radar_svc` logs an error if a late reply finds the requester gone; this sample
never exercises that path. `--healthy` shows that the bug stays hidden while the
radar answers.
