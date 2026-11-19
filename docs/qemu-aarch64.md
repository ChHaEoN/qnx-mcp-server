# Local QNX aarch64 guest (QEMU virt)

This is the second validated target: a QNX 8.0 `aarch64le` guest on QEMU's
`virt` machine, emulated with TCG on the same x86_64 Linux host or WSL2 as
[the x86_64 guest](qemu.md). Keep this setup outside the repository too.

Besides the licensed Linux QNX SDP 8.0 with the `aarch64le` target, install the
QEMU virt BSP through QNX Software Center with your own myQNX account:
`com.qnx.qnx800.target.qemuvirt` and `com.qnx.qnx800.target.driver.virtio.devb`.
They provide `startup-qemu-virt` and the aarch64 virtio block driver that
`mkqnximage` needs. QEMU comes from the host distribution; on Ubuntu 24.04,
the `qemu-system-arm` package provides `qemu-system-aarch64`.

Use a separate lab directory so the keys and profile of each guest stay apart:

```sh
export SDK=/absolute/path/to/linux-sdp
export work="$HOME/qnx-mcp-lab-aarch64"
mkdir -p "$work/vm" "$work/tmp" "$work/keys"
chmod 700 "$work" "$work/tmp" "$work/keys"
export TMPDIR="$work/tmp"
. "$SDK/qnxsdp-env.sh"
cd "$work/vm"   # empty for the initial build
mkqnximage --type=qemu --arch=aarch64le --graphics=no --ssh-ident=none --hostname=qnx-mcp-a64
```

Start the image in a terminal with a private snapshot and a loopback-only SSH
forward. Port 22223 lets it run beside the x86_64 guest on 22222. The machine
and CPU match the image's default ARMv8.0 profile:

```sh
cd "$work/vm"
qemu-system-aarch64 -machine virt-4.2,accel=tcg -cpu cortex-a57 -m 1G -smp 2 \
  -nographic -snapshot -kernel output/ifs.bin \
  -drive file=output/disk-qemu.vmdk,format=vmdk,if=none,id=drv0 \
  -device virtio-blk-device,drive=drv0 \
  -netdev user,id=net0,restrict=on,hostfwd=tcp:127.0.0.1:22223-:22 \
  -device virtio-net-device,netdev=net0 \
  -object rng-random,filename=/dev/urandom,id=rng0 -device virtio-rng-device,rng=rng0
```

Wait for `Startup complete` on the serial console. Then follow the key,
host-key and SSH configuration steps of [the x86_64 setup](qemu.md) with this
`$work`, with port 22223 instead of 22222 and a separate `Host` alias such as
`qnx-mcp-a64`. The verified image has the same `qnxuser` account (UID/GID 1000,
home `/data/home/qnxuser`), the same host key paths and the same `/proc/boot`
utilities; confirm them on your own image. Copy the
[aarch64 profile](../targets/qemu-aarch64.yaml) to `$work/qemu-aarch64.local.yaml`
and set `key_path: keys/client_ed25519` and `known_hosts: keys/known_hosts`.

The guest's `uname -m` names the board, `QEMU_virt`, as the x86_64 guest's
names `x86pc`. The server reads the architecture from `uname -p`, which
prints `aarch64le`, and `system_info` reports it as `aarch64`.

Build the samples with `qcc -Vgcc_ntoaarch64le` instead of `-Vgcc_ntox86_64`.
The rest of each demo is unchanged.

Not validated: real ARM hardware, other BSPs and other QEMU machine or CPU
models.
