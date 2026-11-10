# Demo video script — 2:40

| Time | Show |
| --- | --- |
| 0:00–0:20 | An embedded developer asks why two QNX programs hang. Show Linux/WSL → MCP → SSH → QNX/QEMU and the original sample. |
| 0:20–0:45 | Manually launch the fault case. Show the agent requesting approval for a read-only call. |
| 0:45–1:25 | Match A's REPLY and B's SEND to the actual peer/channel IDs. The unrelated RECEIVE thread is idle, so it is not part of the cycle. |
| 1:25–1:55 | Read B's phase log and original source. The assistant points to the callback-before-reply ordering and proposes the fix. |
| 1:55–2:25 | Title card: “Developer manually reruns the fixed case.” Show reply-before-callback and the functional success message. |
| 2:25–2:40 | Show a denied out-of-root read, a sanitized audit entry and the MIT repository instructions. |

Use permitted functional evidence and original code. Keep QNX images,
binaries, SDK content, vendor samples, credentials and captures out of the
repo and video. Do not show benchmark or timing comparisons. This script does
not claim a video has been recorded or published.
<!-- TODO: replace with the video link once the video is public. -->
