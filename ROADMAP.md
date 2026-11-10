# Roadmap

## v0.1.0

- Four read-only MCP tools: `system_info`, `list_processes`, `read_system_log`
  and `read_file`.
- One startup-bound SSH/SFTP profile for a QNX 8.0 guest on local QEMU x86_64,
  validated on a real guest.
- An original two-program IPC deadlock demo. Read-only calls show A
  REPLY-blocked on B, B SEND-blocked on A and an unrelated idle receiver; the
  staged source shows the callback sent before the reply.
- Linux CI with hand-written synthetic fixtures and a fake SSH/SFTP backend.

## Planned next: two-guest scenario

- QNX Hypervisor 8.0.5 on an AArch64 host, with one QNX guest and one Linux
  guest.
- An original cockpit-style sample: a QNX service waits for a request that the
  Linux side never answers, while both guests and a heartbeat stay alive.
- Named target sets bound at startup, so the same four tools can read the
  hypervisor host and the QNX guest, plus optional read-only process and log
  reads on Linux.
- Diagnosis stays read-only. The developer reviews, applies and reruns the
  proposed bounded-wait fix manually.

## Out of scope

Tools that write, build, deploy, run, stop or repair anything on a target.
