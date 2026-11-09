# Connect an MCP client

Complete [QEMU setup](qemu.md) and [installation](../README.md#install-and-connect)
first. Substitute your Linux repo/profile paths. Launch the server from a
trusted workspace. The SDK is not loaded by the stdio launcher.

For **Claude Desktop on Windows**, open **Settings → Desktop app → Extensions
(Manage) → Local MCP servers → Edit config**. Use the file the app selects.
Microsoft Store build 4.16336.0 uses a folder under `%LOCALAPPDATA%\Claude-Data`.
Older builds may expose **Developer → Edit Config**. Add this entry inside
`mcpServers`:

```json
"qnx": {
  "command": "C:\\Windows\\System32\\wsl.exe",
  "args": [
    "--distribution", "Ubuntu-24.04", "--exec", "/bin/sh",
    "/ABS_REPO/scripts/launch-mcp.sh", "--profile", "/ABS_PRIVATE/qemu.local.yaml"
  ]
}
```

Once other Claude sessions and their background work have finished, exit and
relaunch the desktop app. Open a fresh chat for the approval check below.

Before the first QNX request, set the chat's **Permission mode** control, next
to the model selector, to **Manual**. In build 4.16336.0 a new chat started in
**Auto**, and Auto ran a read-only `system_info` call without asking. Manual
showed an approval card before each call. Use **Decline** to refuse a call and
**Allow once** to accept one; do not grant a persistent allow. Check the mode
again whenever you open a new chat.

For [VS Code](https://code.visualstudio.com/docs/agents/reference/mcp-configuration)
connected to WSL/Linux or Remote SSH, put the server in the **remote workspace**
configuration:

```json
{
  "servers": {
    "qnx": {
      "type": "stdio",
      "command": "/bin/sh",
      "args": [
        "/ABS_REPO/scripts/launch-mcp.sh", "--profile", "/ABS_PRIVATE/qemu.local.yaml"
      ]
    }
  }
}
```

A Windows-local VS Code workspace can use the `wsl.exe` command and arguments
from the Claude example under the VS Code `servers` key. A Mac can use VS Code
Remote SSH to a Linux development host; the stdio server and QNX toolchain stay
on Linux. Configure its development-host SSH independently of guest SSH.

The verified VS Code 1.142.0 approval route uses the **Local harness** with
**Default permissions** and the project's [.vscode/settings.json](../.vscode/settings.json).
That file sets `chat.tools.eligibleForAutoApproval` to `false` for each of the
four QNX tool reference names. If you already have workspace settings, merge
those entries. This forces a confirmation before execution even though the
server advertises read-only tools. [VS Code approval settings](https://code.visualstudio.com/docs/agents/run/approvals#prevent-tools-from-being-auto-approved)

During local acceptance, the Copilot harness with Manual permissions
automatically executed the first read before this policy was configured.
Copilot with the new policy still needs separate verification. Confirm the
active harness when reproducing the test.

Check that only four tools appear. Request `system_info`, decline once, and
confirm that no call reached the server. Approve one call, then ask for a second
and confirm the client prompts again. Do not use session-wide or persistent
allow grants. The automated smoke test uses the SDK client, so it does not
verify a GUI's approval policy.

In the tested Local harness, use **Skip** to decline a pre-call prompt.
Choose **Allow and Review Once** for an accepted call, then choose **Allow
Once** from the result-review dropdown. Result review is an additional prompt
after the target read. Its default button may grant a session-wide review
permission, so inspect the dropdown.
