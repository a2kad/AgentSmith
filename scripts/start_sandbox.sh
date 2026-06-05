#!/bin/bash
set -euo pipefail

SANDBOX_ID=${1:?Usage: start_sandbox.sh <sandbox-id>}
ROOTFS_IMAGE="/opt/sandboxes/rootfs/alpine-dev.ext4"
KERNEL="/opt/sandboxes/kernels/vmlinux-5.10"
JAILER_BIN="/usr/bin/jailer"
FC_BIN="/usr/bin/firecracker"
CONFIG_DIR="/opt/sandboxes/configs"
CONFIG_FILE="${CONFIG_DIR}/${SANDBOX_ID}.json"

# Создаём изолированный chroot для каждого запуска
"$JAILER_BIN" \
  --id "$SANDBOX_ID" \
  --uid 10001 \
  --gid 10001 \
  --exec-file "$FC_BIN" \
  --cgroup-version 2 \
  -- \
  --config-file "$CONFIG_FILE"

# FC config example
cat > "$CONFIG_FILE" <<EOF
{
  "boot-source": {
    "kernel_image_path": "$KERNEL",
    "boot_args": "console=ttyS0 reboot=k panic=1 pci=off"
  },
  "drives": [
    {
      "drive_id": "rootfs",
      "path_on_host": "$ROOTFS_IMAGE",
      "is_root_device": true,
      "is_read_only": false
    }
  ],
  "machine-config": {
    "vcpu_count": 2,
    "mem_size_mib": 512,
    "ht_enabled": false
  }
}
EOF
