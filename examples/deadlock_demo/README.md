# Two QNX peers and a callback deadlock

Both programs run as the same non-root user. A creates a callback channel and a
separate idle receive channel. B returns its request channel ID through a
bootstrap pipe. A then sends a request. In fault mode B receives the request
and synchronously sends a callback before replying, so both main threads wait.

```text
A main  -- REPLY on B's request channel --> B main
B main  -- SEND on A's callback channel --> A main
A idle  -- RECEIVE on a separate local channel (normal)
```

Compile manually from Linux with the SDK environment already loaded. Keep
binaries in your private lab:

```sh
repo=/absolute/path/to/qnx-mcp-server
mkdir -p "$work/demo-build"
for p in a b; do
  qcc -Vgcc_ntox86_64 -Wall -Wextra -O0 -g \
    -o "$work/demo-build/peer_$p" "$repo/examples/deadlock_demo/peer_$p.c" -lslog2
done
```

For interactive approvals, add `-DWATCHDOG_SECONDS=900` to both builds. Each
process has its own watchdog. The default is 30 seconds and the compile-time
limit is 900 seconds.

Use the [lab SSH configuration](../../docs/qemu.md) and SFTP to upload
`peer_a`, `peer_b`, their C source and `demo.h` into
`/data/home/qnxuser/qnx-mcp-demo`. In an operator terminal:

```sh
ssh -F "$work/ssh.conf" qnx-mcp-demo \
  'cd /data/home/qnxuser/qnx-mcp-demo && chmod 700 peer_a peer_b && ./peer_a ./peer_b'
```

Open a fresh VS Code Local harness chat with the [approval policy](../../docs/clients.md).
Leave the sample source out of the chat attachments so the agent has to find it
through the target. Use this prompt and approve the reads individually.

> Two QNX programs named `peer_a` and `peer_b` have stopped making progress.
> Diagnose them using only the QNX MCP tools. The staged C sources are in
> `/data/home/qnxuser/qnx-mcp-demo`. Cite the observed thread states, wait
> endpoints and exact source statements that support your diagnosis.

Check `list_processes` with name filter `peer_`, `read_system_log` with buffer
set `qnx_mcp_peer_b`, and `read_file` for the staged sources. Match the wait
edges against the `A_READY` and `B_READY` IDs. B's phase log and the source
locate the callback before the missing reply. Repeat the manual launch if
the watchdog expires during the inspection.

After the faulty processes exit, run the fixed branch manually:

```sh
ssh -F "$work/ssh.conf" qnx-mcp-demo \
  'cd /data/home/qnxuser/qnx-mcp-demo || exit 1
   ./peer_a ./peer_b --fixed >fixed-run.txt
   result=$?
   cat fixed-run.txt
   exit "$result"'
```

The fixed branch calls `MsgReply` before the callback. Expect
`DEMO_OK request and callback completed` and successful exit. Have the agent
read `fixed-run.txt` and check that the peers have exited. This gives it
evidence even if the named slog2 buffers are unavailable after exit. The
operator launches both cases and checks the fixed run's exit status.
