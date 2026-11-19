# Roadmap

## v0.1.0

- Four read-only MCP tools: `system_info`, `list_processes`, `read_system_log`
  and `read_file`.
- One startup-bound SSH/SFTP profile, validated on a local QNX 8.0 QEMU x86_64
  guest.
- An original IPC deadlock demo: A REPLY-blocked on B and B SEND-blocked on A,
  beside an idle receiver.
- Linux CI with hand-written synthetic fixtures and a fake SSH/SFTP backend.

## Since v0.1.0

- `list_processes` adds `wait_analysis`, which follows waits across visible
  processes and ranks untimed waits first.
- An original instrument-cluster sample: a failed radar freezes the cluster
  because fusion holds a lock across an unbounded `MsgSend`.
- Second validated target: aarch64 QEMU virt.

## Planned next: two-guest scenario

- QNX Hypervisor 8.0.5 on an AArch64 host, with QNX and Linux guests.
- The cockpit sample spans both guests: a QNX service waits on a request the
  Linux guest never answers, while a heartbeat stays alive.
- Named target sets bound at startup, so the four tools can read the hypervisor
  host, the QNX guest and optional Linux processes and logs.
- Diagnosis stays read-only; the developer applies and reruns the fix manually.

## Out of scope

Tools that write, build, deploy, run, stop or repair anything on a target.
