# Local QNX guest for the read-only MVP

Keep this setup outside the repository. Install a licensed Linux QNX SDP 8.0
toolchain and QEMU on an x86_64 Linux development host or WSL2. This setup uses
the SDK's [mkqnximage](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/m/mkqnximage.html).
Use an existing verified image or generate a fresh one in an empty directory:

```sh
export SDK=/absolute/path/to/linux-sdp
export work="$HOME/qnx-mcp-lab"
mkdir -p "$work/vm" "$work/tmp" "$work/keys"
chmod 700 "$work" "$work/tmp" "$work/keys"
export TMPDIR="$work/tmp"
. "$SDK/qnxsdp-env.sh"
cd "$work/vm"   # empty for the initial build
mkqnximage --type=qemu --arch=x86_64 --graphics=no --ssh-ident=none --hostname=qnx-mcp-dev
```

Start the image manually in a terminal. Use a private snapshot and bind the
guest SSH forward to loopback. Keep this lab guest off exposed interfaces;
the generated image may have default accounts and passwords.

```sh
cd "$work/vm"
qemu-system-x86_64 -machine pc,accel=tcg -cpu max,avx2=off -m 1024 -smp 2 \
  -nographic -snapshot \
  -kernel output/ifs.bin -drive file=output/disk-qemu.vmdk,format=vmdk,if=ide \
  -netdev user,id=net0,restrict=on,hostfwd=tcp:127.0.0.1:22222-:22 \
  -device virtio-net-pci,netdev=net0 -device virtio-rng-pci
```

The verified WSL2 QEMU build needed `avx2=off` for this image's OpenSSL SHA-512
path. Without it, `sshd -t` faulted at the page boundary in `vinserti128`.
See [the upstream QEMU fix](https://qemu.googlesource.com/qemu/+/feea87cd6b645d5166bdd304aac88f47f63dc2ef).
The CPU flag is a local VM compatibility setting. The image and SDK packages
stay unchanged.

On the Linux host, create a dedicated test key in your private lab directory:

```sh
ssh-keygen -t ed25519 -N '' -f "$work/keys/client_ed25519"
cat "$work/keys/client_ed25519.pub"
```

In the **guest's serial console**, check that `qnxuser` exists and record
`id qnxuser`. This image has UID/GID 1000 and home `/data/home/qnxuser`.
Use the confirmed values for your image. Install only the **public** key:

```sh
dir=/data/home/qnxuser/.ssh
mkdir -p "$dir"
printf '%s\n' 'PASTE_THE_SINGLE_PUBLIC_KEY_LINE_HERE' >> "$dir/authorized_keys"
chown 1000:1000 "$dir" "$dir/authorized_keys"
chmod 700 "$dir"
chmod 600 "$dir/authorized_keys"
/system/bin/sshd -t -f /system/etc/ssh/sshd_config
ssh-keygen -lf /data/var/ssh/ssh_host_ed25519_key.pub
```

The normal image boot starts sshd; confirm it listens on guest port 22. Read
the ED25519 fingerprint from the trusted console. On the host, compare it with
the key offered over the forward before trusting that key:

```sh
expected='SHA256:PASTE_THE_CONSOLE_FINGERPRINT'
ssh-keyscan -p 22222 -t ed25519 127.0.0.1 > "$work/keys/known_hosts.candidate"
observed=$(ssh-keygen -lf "$work/keys/known_hosts.candidate" | awk 'NR==1 {print $2}')
test "$observed" = "$expected" &&
  mv "$work/keys/known_hosts.candidate" "$work/keys/known_hosts"
```

Stop if the comparison fails. Copy the [QEMU profile](../targets/qemu.yaml) to
`$work/qemu.local.yaml`, and set `key_path: keys/client_ed25519` and
`known_hosts: keys/known_hosts`. For the **manual operator** commands in the demo,
you can create this independent OpenSSH config:

```sh
cat >"$work/ssh.conf" <<EOF
Host qnx-mcp-demo
  HostName 127.0.0.1
  Port 22222
  User qnxuser
  IdentityFile $work/keys/client_ed25519
  IdentityAgent none
  IdentitiesOnly yes
  UserKnownHostsFile $work/keys/known_hosts
  GlobalKnownHostsFile /dev/null
  StrictHostKeyChecking yes
  BatchMode yes
  PasswordAuthentication no
  KbdInteractiveAuthentication no
EOF
ssh -F "$work/ssh.conf" qnx-mcp-demo 'id -u; mkdir -p /data/home/qnxuser/qnx-mcp-demo'
sftp -F "$work/ssh.conf" qnx-mcp-demo
```

Confirm non-root identity and SFTP, then exit SFTP with `bye`. Stop the VM
after testing. The temporary snapshot discards guest changes on exit; repeat
key staging and verification on the next boot as needed.
