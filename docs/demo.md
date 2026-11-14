# Demo video script — 2:40

| Time | Show |
| --- | --- |
| 0:00–0:20 | Title card: “Simulated cockpit, development only.” Show Linux/WSL → MCP → SSH → QNX/QEMU and the [cluster sample](../examples/cluster_freeze/README.md): display, fusion, radar. |
| 0:20–0:40 | Manually launch the fault case. The text cluster updates speed, then freezes at one frame while the fusion heartbeat keeps logging “alive”. |
| 0:40–1:15 | The agent requests approval for `list_processes`. Show the wait analysis: display REPLY/SEND to fusion, fusion MUTEX and REPLY to the radar, radar RECEIVE on another channel and CONDVAR ranked first, heartbeat NANOSLEEP last. |
| 1:15–1:50 | Approved log and source reads. Request IDs and thread IDs show the lock held across the radar call and the radar front end lost. The agent explains which links are observed and which are inferred. |
| 1:50–2:20 | Title card: “Developer manually applies and reruns the fix.” Show `sync_radar_with_deadline`: unlock before the call, `TimerTimeout`, degrade on `ETIMEDOUT`. The rerun keeps updating speed with ADAS unavailable. |
| 2:20–2:40 | Show a denied out-of-root read, a sanitized audit entry and the MIT repository instructions. |

Use permitted functional evidence and original code. Keep QNX images,
binaries, SDK content, vendor samples, credentials and captures out of the
repo and video. Do not show benchmark or timing comparisons. This script does
not claim a video has been recorded or published.
<!-- TODO: replace with the video link once the video is public. -->
