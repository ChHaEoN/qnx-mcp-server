"""Opt-in, read-only stdio smoke test. It assumes the developer staged a text file."""

import argparse
import asyncio
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters


async def verify(args: argparse.Namespace) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "qnx_mcp.server",
            "--profile",
            str(args.profile.resolve()),
            "--audit-log",
            str(args.audit_log.resolve()),
        ],
    )
    async with Client(params, read_timeout_seconds=20) as client:
        tools = (await client.list_tools()).tools
        if {tool.name for tool in tools} != {
            "system_info",
            "list_processes",
            "read_system_log",
            "read_file",
        }:
            raise RuntimeError("Unexpected tool list")

        async def call(name: str, arguments: dict) -> dict:
            result = await client.call_tool(name, arguments)
            if result.is_error:
                code = (result.structured_content or {}).get("code", "tool_error")
                raise RuntimeError(f"{name}: {code}")
            print(f"PASS {name} ({result.structured_content['status']})")
            return result.structured_content["data"]

        system = await call("system_info", {})
        if system["os"] != "QNX" or not system["capabilities"]["sftp"]:
            raise RuntimeError("Expected QNX and working SFTP")
        process_args = {"limit": 200}
        if args.process_name:
            process_args["name"] = args.process_name
        processes = await call("list_processes", process_args)
        if not processes["returned_threads"]:
            raise RuntimeError("Expected at least one visible thread")
        if args.expect_wait_states:
            observed = {
                thread["state"]
                for p in processes["processes"]
                for thread in p["threads"]
                if thread["blocked_on"]["availability"] == "observed"
            }
            if not {"SEND", "REPLY", "RECEIVE"} <= observed:
                raise RuntimeError("Expected observable SEND, REPLY and RECEIVE states")
        log_args = {"limit": 10}
        if args.buffer_set:
            log_args["buffer_set"] = args.buffer_set
        log = await call("read_system_log", log_args)
        if not log["entries"]:
            raise RuntimeError("Expected at least one readable slog2 record")
        data = await call("read_file", {"path": args.file, "max_bytes": 4096})
        if args.contains and args.contains not in data["content"]:
            raise RuntimeError("Staged test marker was not present")
        denied = await client.call_tool("read_file", {"path": "/proc/boot/procnto"})
        if not denied.is_error or (denied.structured_content or {}).get("code") != "path_denied":
            raise RuntimeError("Expected the out-of-root read to be denied")
        print("PASS path denial")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--audit-log", required=True, type=Path)
    parser.add_argument("--file", required=True, help="Approved text file on QNX")
    parser.add_argument("--contains", help="Optional original marker expected in that file")
    parser.add_argument("--process-name", help="Optional executable substring")
    parser.add_argument("--buffer-set", help="Optional slog2 buffer-set name")
    parser.add_argument("--expect-wait-states", action="store_true")
    asyncio.run(verify(parser.parse_args()))


if __name__ == "__main__":
    main()
