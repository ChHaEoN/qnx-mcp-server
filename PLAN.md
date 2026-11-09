# QNX MCP Server — implementation plan

## Changelog versus the previous plan

- Claude Desktop 4.16336.0 per-call approval passed on November 6 in Manual permission mode: a declined call never reached the server, and two successive calls each prompted. New chats default to Auto, which ran a read without asking; [client setup](docs/clients.md) now requires Manual. Recording, the November 17 scan and publication remain release work.
- Verified the single-guest deadlock diagnosis in VS Code Local and documented the manual fixed rerun. The sample has a bounded build-time watchdog override for interactive approvals.
- Started the local read-only MVP on November 5 after local preflight passed. Added the four MCP tools, synthetic Linux checks and the original QEMU deadlock pair. VS Code Local harness approval checks passed with an explicit workspace policy.
- Replaced the hard 50h ceiling with an initial **60–75h working estimate**, to be revised from actual progress; learning and a complete, defensible demonstration take priority over matching the estimate.
- Expanded cloud setup/verification to 6–10h, the full cloud milestone to 20–30h and final validation/documentation/video to 12–16h; added explicit learning and completion outcomes.
- Preserved the November 17 QEMU read-only release, November 29–30 recovery rule, November 18–28 blocked dates, November 29 script, December 6 cloud decision, December 10 freeze, December 13 submission and December 14 buffer.
- Effort flexibility does not relax AWS spending/session guards, local preflight stop rules, read-only diagnosis/manual repair, licensing, synthetic fixtures, vendor-material scans or the no-benchmark policy.

Planning date: 2026-11-04. Local MVP implementation began on 2026-11-05.

## 1. Deliverable and scope

Build an MIT-licensed Python MCP server connected over SSH to **QNX OS / SDP 8.0**. The single supported development host route is **Linux on x86_64, either native or inside WSL2 on Windows**; use WSL2 on this workstation. The server, Linux SDP, qcc, SSH/SFTP and local QEMU run there. Windows may host the GUI client only. Prove **local QEMU/x86_64** first; the later cloud target is **QNX Hypervisor 8.0.5 on AWS Marketplace c7g.metal (AArch64)** with one QNX guest and one Linux guest. The owner reports the vCPU quota is approved; boot, guest availability, networking and access remain **VERIFY**. [AMI release notes](https://www.qnx.com/developers/docs/relnotes8.0/com.qnx.doc.release_notes/topic/qnxami_prod_release_notes/qnxcloud_hv805_ami_rn.html)

Primary story: a cockpit-style split places illustrative safety-relevant services in QNX and infotainment in Linux. A QNX service waits indefinitely for a cross-partition request that Linux never answers, although both guests and a separate heartbeat remain alive. The assistant diagnoses through read-only tools and proposes a bounded-wait fix in **QNX source**. **The developer manually edits, builds, deploys and reruns it; the server performs no repair actions.** This is a development simulation, with no safety certification claim: Hypervisor 8.0.5 is not approved for safety-related production use. [Product release notes](https://www.qnx.com/developers/docs/relnotes8.0/com.qnx.doc.release_notes/topic/qh8.0_prod_release_notes/hypervisor8.0.5_rn.html)

**Owner priority:** gain practical QNX/Hypervisor experience and produce the intended, reproducible diagnostic story. Hours are planning estimates, not an acceptance criterion or fixed ceiling. Prefer deeper understanding, reliable evidence and clear documentation; use the dated release gates to protect submission readiness. This changes the effort budget, not the AWS monetary/session controls.

**Mandatory fallback by November 17, unchanged:** a public, independently submittable **read-only QNX diagnostics MCP server**, with all four inspection tools working on real local QEMU/x86_64, instructions, license, synthetic CI and a short real-target screencast of the original single-guest deadlock pair. Cloud work cannot delay or replace it. Build/deploy/run MCP tools leave the committed hackathon scope. Local preflight steps 1–6 passed on Ubuntu 24.04 WSL2, using a licensed Linux SDP 8.0 installation with 8.0.5 components and a QNX 8.0.0 guest. Non-root IPC inspection is verified for processes under the same UID. [Manual verification](docs/manual-testing.md)

The category is **Developer Tooling & Host Tools**. Finish and submit by **December 13**, reserve December 14 for recovery. The official deadline is **December 15, 2026, 14:00 EST = 20:00 Europe/Berlin**. Publish a GitHub repository, detectable MIT license, reproducible instructions, QNX evidence and a public YouTube demo under three minutes. [Official rules](https://qnx.devpost.com/rules)

Keep QNX image/binary files, SDK files/content and copied vendor samples out of the repo and video; keep core dumps and real-target fixture captures out of Git. Use only original project/sample source and hand-written synthetic test data; video evidence may show permitted functional output without displaying or distributing vendor files/content. README/video contain no performance measurements, benchmark comparisons or build/run timing claims.

## 2. Technology and client setup

| Choice | Decision and reason |
| --- | --- |
| MCP | Official Python `mcp` SDK pinned to 2.3.0. Use its low-level server with Pydantic input/output schemas so the tool handler can audit invalid calls and return structured failures. The separate FastMCP package adds another dependency. TypeScript would add a second language without helping the parsers. [SDK](https://py.sdk.modelcontextprotocol.io/) |
| Transport | Local **stdio** only: no HTTP listener, authentication service or network deployment. Protocol on stdout; diagnostics on stderr. |
| SSH | **AsyncSSH**: asynchronous commands, SFTP and host-key verification fit the SDK. Paramiko is viable but would need a blocking-worker adapter. Use an injectable backend interface. [AsyncSSH](https://asyncssh.readthedocs.io/en/stable/) |
| Packaging | Python **3.12**, `pyproject.toml`, Hatchling, console entry point `qnx-mcp`; Pydantic models and safe YAML loading. Develop with `uv`, commit `uv.lock`, use `uv sync --frozen`; also document `python -m pip install -e .`. No runtime SDK downloads. |
| Checks | pytest / pytest-asyncio, Ruff and **Linux-only CI**, Python 3.12. No application-side LLM SDK or API key: the MCP client owns reasoning. |

Linux development launch: `uv run --frozen --directory ABS_REPO qnx-mcp --profile ABS_PROFILE`. The trusted `scripts/launch-mcp.sh` locates the repository and starts `qnx_mcp.server` with its virtual environment. Load the local SDK environment only for the manual build steps. The launcher reserves stdout for MCP. All SDK, key, profile and workspace paths use Linux syntax. For the cloud increment, an owner-selected `--target-set ABS_SET.yaml` binds multiple named profiles at startup; replace the GUI's profile arguments accordingly. Neither launch form starts AWS instances or guests.

Native Linux GUI clients launch `/bin/sh` with args `["/ABS_REPO/scripts/launch-mcp.sh", "--profile", "/ABS_PROFILE"]`. For a Windows GUI with WSL2, use JSON command value `"C:\\Windows\\System32\\wsl.exe"` and args `["--distribution", "DISTRO", "--exec", "/bin/sh", "/ABS_REPO/scripts/launch-mcp.sh", "--profile", "/ABS_PROFILE"]`. Replace placeholders with verified Linux paths/distribution and verify each GUI client using the [client setup](docs/clients.md). [WSL interop](https://learn.microsoft.com/en-us/windows/dev-environment/wsl-interop)

| Client | Configuration to document and verify |
| --- | --- |
| Claude Desktop | Use the app's **Edit config** action in [client setup](docs/clients.md). On Windows, add the WSL command above under `mcpServers.qnx`. Restart, set the chat's Permission mode to **Manual** and call `system_info`. Verified in 4.16336.0: Manual prompts before every call; the default Auto mode does not. [Local-server setup](https://modelcontextprotocol.io/docs/develop/connect-local-servers) |
| VS Code / Copilot | `MCP: Add Server` → Command (stdio); `.vscode/mcp.json` uses `servers.qnx` with `type: "stdio"`. A Windows-local launch uses `wsl.exe` above; a native Linux or WSL-side session uses the direct Linux launcher. Verify which environment actually starts the process. [Configuration reference](https://code.visualstudio.com/docs/agents/reference/mcp-configuration), [WSL development](https://code.visualstudio.com/docs/remote/wsl) |
| Codex, optional | In Linux/WSL: `codex mcp add qnx -- /ABS_REPO/scripts/launch-mcp.sh --profile /ABS_PROFILE`. Validate per-call approval in the actual client. [Official OpenAI documentation](https://developers.openai.com/codex/mcp) |

Configure clients to **ask for every call**: no persistent allow grants, automatic approval or autonomous permission mode. In VS Code, verify the actual harness/settings still prompt; some sandbox configurations auto-approve tools. Test a declined read and two successive calls each requiring approval. MVP does not require elicitation. Record client/model versions. Any future mutation tools retain the opt-in and preview contract in section 5. [VS Code approvals](https://code.visualstudio.com/docs/agents/run/approvals)

## 3. Repository and profiles

```text
README.md, PLAN.md, LICENSE, SECURITY.md
pyproject.toml, uv.lock, .gitignore
src/qnx_mcp/
  server.py, config.py, schemas.py
  transport.py                 # backend protocol + AsyncSSH implementation
  policy.py, audit.py          # read-only capabilities, paths, JSONL; no approval DB
  tools.py                    # four inspection tools
  parsers.py                  # pidin and slog2info
targets/qemu.yaml              # sanitized default profile
targets/cloud.example.yaml     # named target set with placeholders; later increment
examples/deadlock_demo/
  peer_a.c, peer_b.c, demo.h   # original channels/connections + synchronous IPC
  README.md                   # bad/fixed flow, manual staging, fixed qcc recipe
examples/cockpit_demo/         # later: original QNX service/bridge + Linux responder
  README.md                   # chosen transport, request IDs, manual fault/fix/rerun
tests/
  fixtures/synthetic/          # README states provenance; never target captures
  fakes.py                    # scripted SSH/SFTP, distinct named target identities
  test_parsers.py, test_policy.py, test_mcp.py
scripts/manual_target_check.py # opt-in read checks; sample setup remains manual
scripts/launch-mcp.sh          # trusted Linux/WSL stdio launcher
docs/qemu.md, docs/clients.md, docs/manual-testing.md, docs/demo.md
docs/cloud.md                  # later increment
.github/workflows/ci.yml
```

November release: one startup profile, default `targets/qemu.yaml`. Cloud increment: one process binds an immutable, developer-owned target set referencing named profile files: `hv-host` and `qnx-guest` (`os: qnx`), optionally `linux-guest` (`os: linux`, read-only). Each profile has `target_id`, `host`, `port`, `user`, `key_path`, `known_hosts`, `arch: x86_64|aarch64`, `read_roots`, fixed utility paths and allowed read capabilities. The target-set file also records the manually verified guest/channel endpoint map. Validate fields, unique names and unknown keys at startup.

Tools may select only a startup-bound `target` enum; they cannot supply hosts/ports/keys, load profiles, change the endpoint map or discover new targets. Omit `target` only for a single-profile session, preserving the November API. The same four QNX tools must work on hypervisor host and QNX guest; return permission/capability failures explicitly. Linux permits only process-state and log reads, never QNX commands, general file reads or control operations. Hypervisor host visibility into its `qvm` processes does not imply visibility into guest threads.

Keep a loopback QEMU default with a **verified** forwarded port, placeholder key path and narrow application directories. Accept external developer-owned profile/target-set files without code changes, including the private guest; publish none of its details. Cloud SSH may use only a startup-configured fixed jump route, if needed and verified; no arbitrary forwarding tool. Ignore `targets/*.local.yaml`, keys, environment files, local state, build outputs, images, cores and traces. Keep SDK/toolchain paths in manual build configuration, outside the server's tool inputs.

## 4. Tool contract

All tools return structured MCP content backed by output schemas. Common envelope: `{schema_version, target_id, observed_at, status, data, warnings, truncated}`. Errors use `isError` and `{code, message, retryable}`; distinguish unavailable utilities, permissions, connection failure, parse failure and denied approval. Missing fields are `null` with a warning, never guessed or silently reported as an empty successful result.

Input sketches below omit optional `target`; in multi-target sessions it is a required enum of bound names. Set finite deadlines and output limits. **VERIFY** means availability, layout or behavior needs a real-target check before parser work; a documentation link is not a passed gate.

### MVP: four read tools; no action-tool milestone

| Tool and input sketch | Output `data` sketch | Implementation / checks |
| --- | --- | --- |
| `system_info({})` | `{os, release, arch, cpu_count, cpu_model?, memory:{free_bytes?, total_bytes?}, capabilities}` | Fixed `uname -srm`, `pidin info`; capability checks for configured utilities and SFTP. **VERIFY** CPU records, memory units and missing/permission-limited fields. Exclude CPU speed and utilization from the schema. |
| `list_processes({pid?:int, name?:string, limit?:int})` | `{processes:[{pid, executable, threads:[Thread]}]}` | Fixed `pidin -v -F` format with pipe-delimited PID, TID, priority, state, `%80B` blocked-on detail and name. Filter locally. Local QEMU verification found SEND/REPLY peer PID and RECEIVE channel ID for the same UID. Peer TID and cross-UID fields can be unavailable. **VERIFY** field layout and visibility on each additional QNX target. |
| `read_system_log({buffer_set?:string, pid?:int, severity_max?:0..7, since_epoch_ms?:int, until_epoch_ms?:int, limit?:int})` | `{clock_basis, entries:[{timestamp, pid?, tid?, buffer_set, buffer, severity, code, message}]}` | Fixed snapshot `slog2info -f -s -t`; filter locally. Severity 0 is most urgent. Prefer buffer-set/PID filters because buffer names need not equal process names. **VERIFY** combined-column layout, multiline records, PID suffix and timestamp basis; reject wall-clock filtering if logs use an unknown/monotonic basis. |
| `read_file({path:string, offset?:int, max_bytes?:int})` | `{path, content, encoding:"utf-8", bytes_read, next_offset?, eof}` | SFTP metadata + bounded read, **regular text files inside read roots only**; no `cat`, devices or `/proc` access. Default 16 KiB, maximum 64 KiB. Reject unsupported binary data. |

`Thread = {tid, state, priority, policy, blocked_on:{kind, peer_pid?, peer_tid?, channel_id?, coid?, scoid?, raw, availability}}`. Preserve QNX states and scheduling-policy suffixes. SEND/REPLY peer PID and RECEIVE's **local** channel have different meanings; never invent a peer TID. Missing/unstable details remain null with warnings. Preflight requires usable blocked-on evidence on local QEMU, then revalidation on cloud host/guest. [pidin blocked-on formats](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/p/pidin.html)

**Cross-partition evidence contract:** native `MsgSend`/`MsgReceive` endpoints belong to one QNX kernel. The sample uses local QNX service → QNX bridge IPC, followed by an explicitly chosen transport to Linux. `pidin` identifies the local bridge, not a Linux PID or a global cross-VM channel. Namespace every process/thread by `(target_id, pid, tid)`. Correlate the remote dependency using original application request IDs, logged endpoint/phase markers and the configured partition map; use optional Linux logs to corroborate it. Label local kernel observations **observed**, cross-partition application links **correlated/inferred**, and missing links **unknown**. Do not turn clock coincidence, host `qvm` state or identical guest PIDs into proof of a remote edge.

Optional internal helper: derive `Graph = {edges:[{from:{target_id,pid,tid}, to:{target_id,pid?,tid?,endpoint?}, basis, evidence_refs}], candidate_cycles, limitations}`. No new tool/target helper. RECEIVE alone creates no wait-for edge; PID-only cycles need thread/channel/source confirmation. The cloud case is an unbounded dependency, not necessarily a cycle. Skip graph automation if behind; retain structured evidence and let the assistant explain it.

**Optional Linux adapters:** `list_processes` returns `{os:"linux", processes:[{pid, name, threads:[{tid,state,wait_channel?}]}]}`; `read_system_log` returns bounded original service log entries. **VERIFY** fixed `ps` fields (`pid,tid,stat,wchan,comm`) on the chosen guest and SFTP access to the configured original application's regular log file. No caller-supplied log path or Linux general-purpose `read_file`; reject QNX-only tools there. Linux wait channels are not QNX IPC peers. Linux access/adapter is optional; if omitted, state that remote evidence is limited to QNX-side request logs and the known sample behavior.

Manual qcc recipes use `gcc_ntox86_64` locally and `gcc_ntoaarch64le` for cloud; **VERIFY** installed `qcc -V` variants and matching SDK 8.0.5 compatibility. No general exec, shell, delete, service-control, AWS-control, guest-start or PID-kill tool. Read-only diagnosis never starts/stops a process, edits source or attaches a debugger. [slog2info](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/s/slog2info.html), [qcc](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/q/qcc.html)

### Stretch, in priority order

| Feature / schema sketch | Commands, limits and justification |
| --- | --- |
| `why_is_it_hung` MCP prompt: `{target, program_id}` → guided instructions | Chain system → blocked-on evidence → request/log/source correlation → explanation/proposed patch → developer's manual repair and rerun. Instructions confer no authority. README already documents the sequence. |
| `analyze_core_dump({core_path, artifact_id, confirm?:bool=false, preview_digest?})` → `{local_core_id, signal?, threads?, frames?, warnings}` | Optional second crash case: copy an **existing completed** core by SFTP to local state, then fixed batch `ntox86_64-gdb` / `ntoaarch64-gdb` backtrace commands with init files and auto-loading disabled. Approval covers local writes and debugger execution. Configure `dumper -d DIR` manually beforehand; no live dump/attach tool. **VERIFY** permissions, naming/completion, core limits, matching unstripped binary and local target libraries. [dumper](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/d/dumper.html), [QNX GDB](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/g/gdb.html) |
| `list_pathspace({prefix?:approved_enum, limit?})` → `{entries:[{path,type,owner_pid?}], completeness}` | Bounded SFTP directory metadata for `/dev` and QNX's `/proc/mount`; never open device nodes. **VERIFY** virtual-entry representation and owner mapping; unknown owner stays null. Rename the proposed `list_resource_managers`: directory entries alone are not a complete manager inventory. [QNX pathname-space entries](https://qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/p/procnto.html) |
| `capture_trace({duration_s, confirm?:bool=false, preview_digest?})` → `{capture_id, event_summary, truncated}` | Fixed bounded `tracelogger` capture and `traceprinter` decoding. **VERIFY** flags, instrumented-kernel requirements, privileges and output layout first. Changes tracing state and creates files; requires approval, disk cap and cleanup policy. No latency/throughput summaries. [tracelogger](https://qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/t/tracelogger.html) |

**Deferred action tools, no hackathon hours:** `build_program({program_id,confirm=false,preview_digest?})` → artifact/hash/diagnostics via a fixed qcc recipe; `deploy_program({artifact_id,confirm=false,preview_digest?})` → versioned path/hash via bounded SFTP; `run_program({deployment_id,timeout_s,confirm=false,preview_digest?})` → stdout/stderr/exit/cleanup. Keep build and deployment separate, use registered IDs and no arbitrary flags/paths; verify architecture, atomic deployment and supervised cleanup before exposing them. They are not needed for either demo/release and must not displace cloud acceptance or the QEMU fallback.

## 5. Safety design

**Threat model:** logs/files/output may contain prompt injection; a runaway agent may repeat reads, expand paths or confuse partitions. Trust owner-controlled profiles and the client's per-call approval UI. Use unprivileged accounts. This does not constrain a hostile administrator, compromised host or agent with independent unrestricted SSH/shell access. Setup, edits and reruns remain owner actions.

- **Read-only release.** Only four inspection tools ship, with per-OS capabilities and bound targets. Client approval is required per call; startup authorizes internal audit writes. No write/execute/delete/repair or AWS tool. `--enable-mutations` must not unlock unfinished features.
- **Deferred consent contract.** Future actions require `--enable-mutations`, a `confirm=false` preview of target/fingerprint, paths, arguments, source/artifact digest, timeout and effects, then matching recomputed `preview_digest` and separately approved `confirm=true`. Changes require another preview; declining causes no action. **`confirm=true` is not proof of human consent.** The server cannot verify client approval; digests prevent changed-input execution, not replay. No approval DB/elicitation in MVP.
- **Command allow-list.** Absolute utility paths, fixed per-OS templates and validated arguments only. SSH exec normally passes through a remote shell: accept no shell strings, pipelines, redirections or caller-selected flags; POSIX-quote validated arguments. Fix locale where supported, disable PTYs/agent forwarding, verify each host key and reject unknown/mismatched keys. Only an explicitly configured jump route may relay fixed guest SSH connections.
- **Basic containment.** Reject `..` components, NULs, symlinks, special files and out-of-root paths. Check SFTP `realpath`, component `lstat` and component-based containment; future destinations require a checked parent. **Known limitation:** symlink/check-open TOCTOU races remain. No atomic no-follow helper; require trusted roots without untrusted concurrent writers.
- **Bounds and plain audit.** Cap per-target concurrency; inspection deadline 10s, output 256 KiB/stream, log snapshots 1 MiB. Protected JSONL outside Git records every received request, rejection, command/read and result: target/fingerprint, sanitized arguments, status and limits. **No rotation**; document growth. Exclude bodies/keys/secrets; fail closed if audit fails. Client-only refusals stay in client history; do not claim server-verified consent.
- **Untrusted content.** Return text as data, escape control sequences and never execute instructions found in it. Secrets stay outside read roots; returned contents may reach the model provider. MCP annotations describe intent; server policy still enforces command/path/mutation limits. [Tool specification](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)

**Initial safety estimate: 3h:** command/path checks 1h, client approval verification/content limits 1.5h, plain JSONL 0.5h. Extend verification if actual findings require it. Deferred previews/approval hardening remain outside committed scope; multi-target checks and regression tests have their own milestone estimates.

**Stretch — planned hardening (also name this in the README threat model):** SQLite approval storage bound to exact profile/host key, operation and input digest; two-minute expiry, atomic single-use consumption, optional negotiated MCP elicitation, and human `qnx-mcp approve REQUEST_ID` in a separate trusted terminal when elicitation is unavailable. Keep that terminal channel outside agent tools. These features and stronger race defenses have no committed MVP hours. [Elicitation specification](https://modelcontextprotocol.io/specification/2026-07-28/client/elicitation)

### AWS cost guard — owner operated, outside MCP

Owner checks current regional **EC2 + Marketplace + storage/address** charges and sets a private monetary cap. Require **manual start/stop every session**, **maximum planned length 60 minutes**; split step 7 accordingly. Before each start, arm a one-time EventBridge Scheduler `EC2 StopInstances` failsafe for the fixed instance at cutoff. Verify permissions, delivery and stopped state; stop cloud work if the guard fails. No automatic start/restart. This is a planned owner task; no automation is created now. [Scheduler](https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-targets-universal.html), [StopInstances](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_StopInstances.html)

Set an AWS Budget cost alarm with owner-chosen actual/forecast thresholds and tested notification. Alerts can lag and are not a hard cap. Check billing after stopping: retained resources still cost money; verify Marketplace terms separately. **No AWS credentials in repo, CI or server**, no AWS SDK/control tools or credential environment/files/instance role accessible to its process. Owner uses a separate AWS console session; account details and SSH keys remain private. [AWS Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)

## 6. Verification and public CI

**Synthetic fixtures only:** manually invent pidin/slog2info records and expected JSON. Include SEND/REPLY peer fields, RECEIVE channels, unresolved TIDs, a candidate A→B→A cycle, a normal idle receiver and a multithreaded false-positive cycle. Also cover priorities/policies, unknown states, disappearance, permissions, malformed/truncated rows, spaces in names, multiline logs, empty buffers and severity/time boundaries. Later add hand-written host/guest PID collisions, request-ID correlations, unknown remote peers and optional Linux records. Real-target observations inform parser behavior locally; never commit captured output or convert captures into fixtures.

**Fake backend:** scripted SSH results and SFTP trees; assert exact commands/reads. Exercise missing utilities, host-key rejection, disconnects, caps, deadlines, nonzero exits and partial parsing. Security cases: injection, sibling-prefix paths, basic symlink/traversal rejection, special files, audit failure and absence of write/control tools. Cloud increment adds unknown-target rejection, immutable bindings and Linux capability denials; no target's numeric PID may resolve in another namespace. No claim that CI proves client UI consent or closes TOCTOU races. Test declined client calls manually; mutation previews/expiry/replay tests belong to deferred work. Include SDK-client stdio discovery/structured-result tests.

**CI:** Linux only (`ubuntu-latest`), Python 3.12: locked install, Ruff, unit/async tests, wheel build and fake-backend stdio smoke test. No QNX SDK, target, credentials, proprietary files, binaries or captured target outputs. Distinguish CI simulation clearly from QNX evidence.

**Manual acceptance:** November 17: all four QEMU tools, blocked-on reliability, allowed/denied paths, logs, approvals and audit. Later repeat on cloud host/QNX guest; test optional Linux reads and capability denials. Demonstrate healthy completion → withheld Linux response with heartbeat alive → QNX evidence → manual QNX deadline fix → timeout/degraded result with Linux unchanged. Verify pending/late-response handling and repeatability. Owner performs setup/fault/repair/rerun/cleanup outside diagnosis. Keep observations outside the repo; record tested OS/SDP patch, target/arch, toolchain, WSL/client versions. Never run these checks in CI.

## 7. Calendar: outcome-led effort estimates

| Calendar week | Available work | Hours | Exit condition |
| --- | --- | ---: | --- |
| Nov 2–8 | **Nov 4–8:** ordered preflight 2h; package/profile/SSH + system info 3h; original deadlock pair/manual staging 3h | 8 | Gate passes; stdio/system info work; sample pair reproduces the intended wait cycle. |
| Nov 9–15 | Process/blocked-on + log parsers 4h; file reads 1h; simplified safety 3h; fake tests/Linux CI 2h; client setup/basic docs 2h | 12 | Four read tools work on QEMU; no approval-store dependency. |
| Nov 16–22 | **Only Nov 16–17:** real-target acceptance 3h; fixes 1h; fallback README/license, brief unscripted screencast, vendor-material scan and release 2h | 6 | **November 17: independently submittable read-only release**, subject to the clean scan, or invoke the slip rule below. No work Nov 18–22. |
| Nov 23–29 | **Only Nov 29:** write the main video script in `docs/demo.md` 1h; reconnect/owner Marketplace EULA and cost-guard preparation 1–2h | 2–3 | Script completed **November 29**, with cloud and QEMU endings; owner publication review recorded before any cloud recording. No work Nov 23–28. |
| Nov 30–Dec 6 | Cloud preflight step 7 **6–10h**; named-profile routing/tests + optional Linux reads **4–6h**; original cockpit sample/QNX deadline fix **6–8h**; read-only diagnosis + manual fix/rerun acceptance **4–6h** | 20–30 | By **Dec 6**, AMI/two guests/transport/access work, four QNX reads pass on host and guest, and the manual repair story is reproducible; otherwise invoke cloud fallback. No action-tool implementation. |
| Dec 7–13 | Failure/acceptance fixes 4–5h; README/reproduction 3–4h; record/edit video 3–4h; final review/submission, including Dec 10 vendor-material scan, 2–3h | 12–16 | **Feature freeze and pre-release scan Dec 10**; release/video/Devpost entry complete **Dec 13**. |

Working estimate: **26h before November 17 + 2–3h on November 29 + 20–30h cloud work + 12–16h finishing = 60–75h**. This is not a new cap or a promise of available evenings. Re-estimate after the local gate and first cloud sessions; an estimate overrun alone does not invalidate the scenario. No work November 18–28; December 14 remains buffer. Prefer stock supported components for the submitted scenario; custom driver/vdev development remains separate scope rather than an automatic workaround for a failed gate.

**Where extra effort should go:**

- Reproduce the two-guest boot/network/SSH setup from the owner's notes and explain the selected transport's configuration, ownership and failure behavior. Record why alternatives were not selected; no performance comparisons.
- Explain the complete QNX service → local IPC bridge → inter-guest request → Linux responder dependency, retaining observed/inferred/unknown evidence and target namespaces.
- Verify healthy, missing-response and late-response cases, including QNX deadline/error handling and pending-request cleanup. Produce a repeatable manual fix/rerun and instructions another developer can follow.

Use these outcomes to judge completeness. Extra hours do not automatically add action tools, custom drivers or approval infrastructure. Keep the November fallback usable throughout; learning that cannot reach submission quality by the dated gates can continue as a documented post-submission roadmap.

**Fallback is a release gate, not an unfinished branch:** by November 17 publish/tag the four-tool version, tested quickstart, safety limitations, MIT license, green synthetic CI and a public short **local QEMU/x86_64 single-guest deadlock** demonstration. The first three calendar rows and their 26h allocation stay unchanged. Reserve its acceptance/docs/video time before cloud work. The polished main video script is still written November 29.

**Local slip rule retained:** if the November 17 read-only gate is not met, finish/release it on **November 29–30** before cloud work. Keep November 18–28 blocked and the main script on November 29. Re-estimate the cloud work against remaining calendar availability; reduce or drop its submission scope if necessary. The former action-tool milestone remains replaced. **December 10 freeze, December 13 submission and December 14 buffer do not move.**

**Cloud slip rule:** if the complete cloud story is not working by **December 6**, stop cloud feature work for this submission, manually stop the instance, and ship the QEMU read-only release with the single-guest deadlock story. Unresolved capability, EULA or cost-control failures also require fallback; exceeding an effort estimate alone does not. Publish only tested capabilities, with no mock cloud evidence. December 7–10 fixes/freezes the selected release; unfinished cloud learning goes on the post-submission roadmap.

**November 17 and December 10 pre-release scans:** inspect repo files, staged changes, publishable Git history and release contents for QNX images/binaries, SDK files/headers/libraries and copied vendor samples; combine file-type/extension checks with provenance review. Review footage/frames/attachments for vendor files or contents, keeping only original project code and permitted functional evidence. Both dates are mandatory even if a gate slips; repeat before a delayed release and after later video edits. Block publication until clean. Real-target captures, credentials and build artifacts stay outside the repo. The no-benchmark policy remains unchanged.

Keep the existing cut order: trace capture → core automation → path-space inventory → extra hardware/architecture validation → optional MCP prompt and presentation polish. Primary cloud validation is committed work with effort estimates and dated readiness gates. Graph automation/approval hardening remain optional; if calendar pressure requires a cloud-scope cut, omit optional Linux reads first and state the reduced evidence. Never cut consent, containment, audit, synthetic CI or real QNX evidence. Action tools remain deferred; repair/rerun stays manual.

## 8. Demo storyboard — 2 minutes 45 seconds

### Primary: cross-partition cockpit hang

Write original sample code: a QNX service, a QNX bridge and a minimal Linux infotainment responder. The QNX service uses `MsgSend` to the local bridge; the bridge receives it, logs a request ID and sends the corresponding request over the transport verified in step 7. Healthy mode replies normally. In faulty mode Linux accepts/logs the request but never returns its application response; an independent heartbeat continues. The bridge defers `MsgReply`, leaving the QNX caller **REPLY-blocked without a deadline**. Keep the hypervisor and diagnostic SSH responsive. This is a software dependency failure despite partition isolation; no claim that the hypervisor itself deadlocks.

Diagnosis uses the four QNX reads on host/guest, plus optional Linux process/log reads. Show the local IPC peer, bridge request ID/endpoint, unresolved application response and the QNX source's missing deadline. Do not claim that `pidin` directly observes a Linux peer. Stage matching original source snapshots in allowed QNX read roots. Show which links are observed versus inferred; a missing log response alone cannot prove every remote failure mode. The controlled Linux fault and source make the demonstrated cause reproducible.

Proposed **QNX-only** fix: apply `TimerTimeout(CLOCK_MONOTONIC, _NTO_TIMEOUT_SEND | _NTO_TIMEOUT_REPLY, …)` immediately before `MsgSend`, handle `ETIMEDOUT` and return an explicit degraded/unavailable result. **VERIFY** channel flags and `_NTO_CHF_UNBLOCK` behavior, cancellation/pending-request cleanup and late replies; timeout does not automatically cancel remote work. If the chosen bridge requires asynchronous notification instead, select and verify that pattern within the same allocation. Keep Linux in no-response mode for the repaired demonstration. The owner manually reviews/applies the source edit, compiles for AArch64, copies and restarts the sample. No agent-initiated edit, deployment, process control or AWS action. [TimerTimeout semantics and unblock caveat](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/t/timertimeout.html)

**Before any cloud recording:** owner completes the Marketplace EULA publication review in section 10. Record only permitted functional output and original source. Use title cards stating **“Read-only AI diagnosis”** and **“Developer manually applies, builds, deploys and reruns the fix.”** Cuts may omit waiting but must not suggest autonomous repair or performance gains.

| Time | What viewers see |
| --- | --- |
| 0:00–0:20 | Audience/problem: developers of partitioned cockpits. Diagram Linux/WSL → MCP → fixed SSH profiles → Hypervisor 8.0.5/c7g.metal → QNX services + Linux infotainment. Label this a development simulation. |
| 0:20–0:45 | Already staged fault: both guests/processes and heartbeat remain alive, but the QNX request makes no progress. “Diagnose using reads only.” |
| 0:45–1:30 | Approved read calls select the bound host and QNX guest; structured blocked-on data identifies the local bridge. Agent correlates request IDs/logs/source across the configured partition boundary; optional Linux logs corroborate receipt without response. Explain observed/inferred links. |
| 1:30–1:50 | Agent points to the unbounded QNX call and proposes deadline/error handling. Developer reviews the original source diff. |
| 1:50–2:20 | Explicit manual-fix title card; developer edits/builds/copies/restarts through the IDE/terminal. With Linux still withholding the response, QNX reports the expected timeout/degraded result. Read-only checks support the result. No timing overlays or benchmark figures. |
| 2:20–2:45 | Refused out-of-root read or unknown target; sanitized JSONL entry; public MIT repo, synthetic CI and tested setup. State the shipped scope and local QEMU fallback. |

### Mandatory fallback: single-guest QEMU deadlock

Keep **two original C programs**, `peer_a.c`/`peer_b.c`, using `ChannelCreate`, `ConnectAttach`, `MsgSend`, `MsgReceive`, `MsgReply` and slog2 phase markers. A handshake establishes their channels/connections. A sends to B; B receives but sends a callback to A before replying: **A main = REPLY to B; B main = SEND to A**. A's idle receiver on a **different** channel supplies a normal **RECEIVE** row and cannot service that callback. The proposed fix makes B reply before sending its callback, allowing A to receive/reply. Verify exact endpoint/state rows and permissions on real QNX. [MsgSend](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/m/msgsend.html)

The developer manually compiles/stages/starts the bad pair before diagnosis, under a verified finite watchdog that cleans up both processes. Stage original source under the read root. The four tools expose A→B→A and the callback-before-reply code; no process control or debugger. November 17's brief screencast can end with the proposed fix. If cloud slips, use the same 2:45 sequence with the QEMU topology and local wait cycle, followed by a clearly manual fix/rerun where ready; no cloud claim. Drop the NULL-pointer crash unless all committed work finishes early; any retained core case needs real evidence and permitted log retention. [slogger2](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/s/slogger2.html)

## 9. README outline

1. One-sentence purpose, real screenshot/video link and current support status.
2. **Why QNX:** microkernel message passing supplies actionable SEND/REPLY/RECEIVE and channel/peer evidence. For cockpit developers, hypervisor partition isolation does not remove application-level wait dependencies between QNX services and Linux infotainment. Explain the QNX deadline fix, observed local IPC versus correlated remote edges, and why a living process/heartbeat does not establish request progress. Include the sourced prior-project comparison below and the QEMU single-guest case. [QNX IPC](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/m/msgsend.html)
3. Architecture, four read tools, target capabilities, evidence limitations and explicit shipped/stretch status. State that repair is manual and the cockpit is a development simulation.
4. Prerequisites: exact tested QNX OS/SDP 8.0 patch, local QEMU/x86_64, Linux/WSL2/toolchain/client versions; separately list verified Hypervisor 8.0.5 AMI build/region, AArch64 guests and transport. Obtain vendor software separately under its license.
5. Install with uv or pip **inside Linux**; manual SDK environment/build steps, launcher, SSH keys/host trust and narrow directories.
6. Default/external profiles and immutable named target sets; Windows GUI → WSL launcher and Linux/WSL-side client examples; optional Codex. No arbitrary hosts or AWS credentials.
7. Reproduction: original QEMU pair plus the verified cockpit sample; manual setup/fault injection, read-only diagnosis, developer's manual QNX fix/build/deploy/rerun and cleanup. Link `docs/cloud.md` for owner-only session/cost guards and EULA publication review.
8. Safety/threat model: required client per-call approval, read-only capabilities, containment, **known symlink/TOCTOU races**, plain JSONL growth and data exposure. Label mutation opt-in/confirm previews as deferred, and SQLite/expiry/single-use/terminal approval as **planned hardening**, not shipped guarantees.
9. Tests: public synthetic CI versus opt-in manual QNX acceptance; troubleshooting missing utilities and permissions.
10. Evidence of QNX use: original sample/API calls, qcc variants, parsed diagnostics and video, separating observations from inference. MIT license for original code; dependency licenses retained; owner-reviewed Marketplace publication status and Nov 17/Dec 10 scan checklists. No QNX images, binaries, SDK files/content or copied vendor samples in repo/video; no benchmark results.

### Positioning against prior QNX projects

| Prior project | Documented focus | This project's intended distinction |
| --- | --- | --- |
| **QNXtainer — cuHacking 6 (2025), software first place** | Build/package/deploy/run applications on a QNX target, with remote monitoring/control. | Diagnose a QNX blocking dependency from native IPC evidence and source rather than add another deployment interface. |
| **RPM — cuHacking 6 (2025), software runner-up** | Remote process states, historical resource monitoring and process suspension. | Explain why a live thread cannot progress, including its IPC peer/channel and application request dependency across partitions. |
| **QNX Device Doctor — UC Berkeley AI Hackathon 2026** | Managed QNX processes and heartbeat detection, hardware-adapter diagnostics and approved repair/verification. | Demonstrate a request hang while processes/heartbeats remain healthy, with read-only evidence leading to a QNX bounded-wait source fix. |

Sources: QNX's [cuHacking 6 report](https://qnx.software/en/blog/2026/qnx-at-cuhacking-6) and Device Doctor's [author submission](https://devpost.com/software/device-doctor). Device Doctor includes more than heartbeats; no award is asserted for it. Claim only the demonstrated distinction: liveness checks alone miss this request hang; blocked-on IPC plus request correlation explains it. No blanket competitor limitation, “first ever” claim or benchmark comparison.

### Judging criteria → submission evidence

The official rules have a viability/QNX-fit pass first, followed by four **equally weighted** criteria. The mapping below uses their names; README references are outline items above. [Official judging criteria, section 6](https://qnx.devpost.com/rules)

| Official criterion | Concrete README evidence | Video segment |
| --- | --- | --- |
| Technological Implementation | Items 4, 7, 9, 10: actual QNX 8.0 diagnostics, original IPC/transport sample, typed parsers, manual target checks and verified TimerTimeout behavior; distinguish synthetic CI. | 0:20–1:30 real fault/blocked-on evidence; 1:50–2:20 manually repaired QNX behavior. |
| Design | Items 3, 5–8: reproducible setup, fixed named targets, coherent read-only workflow, approval/path boundaries, manual repair and cost controls. | 0:45–2:45 target selection → explanation → explicit manual fix → refused read/audit/repo. |
| Potential Impact | Item 2: a specific cockpit-development problem—partition isolation and heartbeats do not ensure a cross-partition request completes; QNX-aware evidence and bounded IPC help expose that dependency. | 0:00–0:45 audience, QNX/Linux split and healthy-heartbeat counterexample; 1:50–2:20 degraded handling. |
| Innovation & AI Creativity | Items 2, 7, 10: assistant links native IPC evidence with original request logs/source across named partitions, distinguishes inference from observation and proposes a QNX-side fix. | 0:45–1:50 evidence → dependency explanation → bounded-wait proposal. |

The QEMU fallback covers the same criteria with a real single-guest IPC cycle, complete read-only workflow, named developer audience and source-level explanation. Make no cloud or automated-repair claim if those features do not ship.

## 10. Ordered preflight: 2h local gate, then a separate cloud gate

Run **steps 1–6 strictly in order within their existing 2h time box**, before local feature work; the relaxed total estimate does not waive this diagnostic checkpoint or its stop rules. Keep commands, summarized observations and open VERIFY items privately outside the repo; no captured QNX contents. Stop/report local failures or exhausted step budgets. **Step 7 runs only after 1–6 pass and the local release is secured**, in the November 30–December 6 milestone, initially estimated at **6–10h**. This revision executes no preflight.

| Order | Check | Budget |
| --- | --- | ---: |
| 1 | Confirm **Linux/WSL2 on x86_64**, a Linux-host SDP 8.0 installation usable there, and existing valid activation. Identify distribution and SDK/image directories. A Windows-host SDK under `/mnt/c` does not qualify. If installation/activation is missing, stop and ask the owner to install/activate; never enter/store myQNX credentials. No native Windows toolchain alternative. | 10 min |
| 2 | **VERIFY** whether the installed SDP 8.0 ships `mkqnximage` and which documented image-generation options produce a **QEMU x86_64** image. Generate the image outside the repo using that verified workflow, then boot it from Linux and verify target identity/network reachability. Do not assume option names or that the local package matches online documentation. [mkqnximage reference](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/m/mkqnximage.html) | 20 min |
| 3 | **VERIFY** which installed `mkqnximage` options or documented image customizations enable/provide **sshd and SFTP** and install an SSH public key for a **non-root account**; do not assume flags or treat root-only key setup as non-root support. Then verify actual non-root key authentication/SFTP, forwarded port and manually trusted host fingerprint. | 30 min |
| 4 | Linux **qcc compiles an original hello-world** for that target with the installed SDK/variant and license environment. | 20 min |
| 5 | Run documented **pidin thread-state and blocked-on** queries (`%J`, `%B`, `-v`) as that account. Describe the exact column layout and whether SEND/REPLY peer PID and RECEIVE channel ID are present, plus peer TID reliability/permission limits. Unavailable fields stay unknown; require usable blocked-on evidence and recheck known demo endpoints during acceptance. | 30 min |
| 6 | Verify **slog2info is readable** as that account; inspect the candidate snapshot flags and clock basis. | 10 min |
| 7 | **Cloud only, after 1–6 PASS:** owner publication/license and cost controls checked; **VERIFY** exact Marketplace Hypervisor 8.0.5 AMI build/region and c7g.metal boot; obtain/configure one QNX and one Linux guest; verify a usable inter-guest channel and SSH reachability of host and both guests, including non-root keys/SFTP needed by QNX reads. Recheck pidin blocked-on and slog2 access separately on QNX host/guest. Estimates below. | **6–10h initial estimate**, inside the 20–30h cloud milestone |

**Local stop rule unchanged:** step 3 SSH/non-root key/SFTP or step 5 blocked-on failure means stop, report observations/options and do not work around it or proceed. Options: owner enables licensed SSH/SFTP, verifies pidin formats/permissions or selects a supported image exposing the missing capability. A target helper needs new scope approval; state-only/Linux assumptions do not pass. Resolve other failed/time-boxed checks before continuing. Ask before package installation or changes outside the repo/QEMU image directory. [QNX sshd](https://qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/s/sshd.html)

### Step 7 VERIFY checklist and owner tasks

Owner manually authorizes/controls cloud account, instance and guest changes; no AWS start now or agent credential/activation handling. Approved vCPU quota does not establish the checks below.

| Order within step 7 | VERIFY / acceptance | Effort estimate |
| --- | --- | ---: |
| 7a | Owner confirms the **Marketplace EULA publication review before any cloud recording**, applicable guest/SDK entitlements, private cost cap, budget notification and independently armed auto-stop. Verify current AMI build, region/c7g.metal availability and host boot/identity; trust its SSH fingerprint manually. | 1–2h |
| 7b | Verify where QNX 8.0.5/AArch64 and Linux guest images/BSPs/configuration come from and whether the AMI includes ready guests. Bring up one of each using documented stock support; do not assume bundled images. Verify host/guest SDK compatibility and the local Linux `gcc_ntoaarch64le` recipe. No bespoke host-image/driver project. | 2–4h |
| 7c | Evaluate **shared memory / virtio / vdev** channel options and choose one already supported by both guests. Prefer stock virtio-net plus a small original request protocol if verified; `vdev-shmem` requires Linux module/driver support and an explicit notification mechanism. A vdev is not automatically an RPC channel. Verify actual guest-to-guest delivery, configured endpoint mapping, host/guest SSH routes and non-root read access; no custom vdev/virtio driver. | 2–3h |
| 7d | Verify all four QNX read prerequisites on host and guest, including actual pidin column/blocked-on differences and readable slog2. Verify optional Linux read-only process/log access; document any omission. Record the supported topology/transport and remaining unknown evidence before sample work. Check that the failsafe stops the instance and owner verifies its stopped state/billing. | 1h |

QNX lists foundational VirtIO/`vdev-shmem` and tested QNX 8.0.5/Ubuntu 22.04 guests, not a verified ready two-guest setup for this owner. Linux shared memory needs a kernel module. Review progress after each cloud session: missing capability means stop/report options; an estimate overrun means re-estimate remaining work against December 6, not assume incompatibility. Do not bypass a failed gate; unresolved failures or the December 6 cutoff select QEMU for submission. AWS sessions retain their 60-minute guard throughout. [AMI notes](https://www.qnx.com/developers/docs/relnotes8.0/com.qnx.doc.release_notes/topic/qnxami_prod_release_notes/qnxcloud_hv805_ami_rn.html), [guest/build requirements](https://www.qnx.com/developers/docs/relnotes8.0/com.qnx.doc.release_notes/topic/qh8.0_prod_release_notes/hypervisor8.0.5_rn.html), [shared memory](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.hypervisor.user/topic/share/share_mem.html)

**Owner publication task, prepared November 29:** open the EULA linked by the exact [Marketplace listing](https://aws.amazon.com/marketplace/pp/prodview-dxrf5qzsdwnpm?applicationId=AWSMPContessa), review recording/publication, redistribution and benchmark restrictions, and record the decision privately before any cloud recording. Do not assume QNX Everywhere terms cover the Hypervisor AMI or guest images. Obtain clarification from QNX if terms are unclear; use QEMU if unresolved. No QNX images, binaries, SDK files or copied vendor samples enter the repo or video, even if used privately to boot. The November 17/December 10 scans and no-benchmark rule apply to both scenarios.

Remaining risks, resolved in their assigned milestone:

- **Sample permissions/determinism:** verify channel/connection abilities, including `PROCMGR_AID_PUBLIC_CHANNEL` where needed, and request manual least-privilege setup. Confirm handshake/state rows rather than sleep-dependent races. Verify both-process watchdog cleanup; SSH closure proves nothing about it. [ChannelCreate](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/c/channelcreate.html)
- **Diagnostics/fix:** complete every parser VERIFY, retain unknown blocked-on fields and verify logger clock basis. Cloud acceptance must test the TimerTimeout/unblock and pending/late-response cases in section 8.
- **SDK compatibility:** cross-compile AArch64 from local x86_64 Linux; no ARM EC2 SDK host. Owner handles any separate SDP 8.0.5/Hypervisor installation/entitlement; stop/report if missing and reassess readiness after owner resolution. Preserve the working QEMU baseline.
- **Client/safety:** verify GUI → Linux/WSL stdio and per-call approvals in the actual harness. Show manual repair clearly even if the client has independent terminal/edit powers.
- **Core stretch:** verify dumper, limits, architecture-specific Linux-host QNX GDB and matching libraries/artifact; generic Linux GDB is not assumed sufficient.
- **Publication:** original MIT samples only, licensed materials/raw observations outside the repo, owner EULA review, Nov 17/Dec 10 scans and no benchmark figures.

A green synthetic CI run does not establish QNX compatibility; the November 17 fallback requires actual target acceptance.
