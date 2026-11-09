# Security model

Use this tool on a trusted development target with a dedicated unprivileged
SSH account. The owner controls the profile, key, known hosts and read roots.
The server uses only stdio and a fixed set of QNX query templates. It binds one
target at startup; tool arguments cannot pick a different endpoint or add
command flags. Filter arguments are applied on the host.

- **Consent:** configure the client to ask before every tool call. Verify this
  in the actual harness and disable persistent auto-approval. The server
  cannot verify that the client displayed an approval prompt. A client refusal
  that never reaches the server exists only in the client's history.
- **Target data:** file names, log messages and file contents may contain
  instructions intended to mislead an agent. Treat them as evidence only.
  The server escapes terminal controls; it cannot keep a model from being
  persuaded by malicious text. Returned contents may reach a model provider.
- **File reads:** allow-listed POSIX roots, component-wise SFTP `lstat` and
  `realpath` containment checks, and bounded UTF-8 reads. Reject traversal,
  symlinks, special files, `/dev` and `/proc`. Check/open is not atomic:
  symlink and replacement races remain possible. Keep roots narrow and
  free of untrusted concurrent writers and secrets.
- **Audit:** local protected JSONL, default
  `$XDG_STATE_HOME/qnx-mcp/audit.jsonl` or
  `~/.local/state/qnx-mcp/audit.jsonl`. The server records dispatched calls,
  validation/denials, the verified host fingerprint, command/read metadata and
  results. String arguments are hashed. Bodies and key material are excluded.
  Audit failure disables reads. There is no rotation; monitor file growth.
  Use a private directory on the Linux filesystem.

This server is not an OS sandbox. It does not constrain an agent with
independent shell or SSH access, a hostile target administrator, or a
compromised host. The MCP server exposes no mutation option. Future mutation
previews and confirmation are deferred; SQLite approvals, expiry, single-use
grants and a separate terminal approver are planned hardening, not shipped.
