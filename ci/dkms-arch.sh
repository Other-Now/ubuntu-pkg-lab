#!/bin/bash
# Runs inside an ubuntu:24.04 container of the target architecture (native,
# or under qemu-user).  Builds the .debs, installs them, and asks DKMS to build
# nano_blk against every Ubuntu kernel-headers flavour we could install.
# Writes one JSON line per kernel to /src/results/dkms-<arch>.jsonl.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
ARCH=$(dpkg --print-architecture)
OUT=/src/results/dkms-$ARCH.jsonl
mkdir -p /src/results; : > "$OUT"

sed -i 's/^Components: main$/Components: main universe/' /etc/apt/sources.list.d/ubuntu.sources
apt-get update -q
apt-get install -y -q --no-install-recommends build-essential debhelper dh-dkms dkms kmod file \
    linux-headers-generic >/dev/null
# HWE headers are a second, newer kernel series; not every arch has them.
apt-get install -y -q --no-install-recommends linux-headers-generic-hwe-24.04 >/dev/null \
    || echo "no HWE headers on $ARCH"

cp -r /src/nano-blk-dkms /tmp/pkg && cd /tmp/pkg
dpkg-buildpackage -us -uc -b 2>&1 | tail -3
apt-get install -y -q ../nano-blk-dkms_*_all.deb ../nano-blk-tools_*_"$ARCH".deb 2>&1 | tail -3
VER=$(dpkg-query -W -f '${Version}' nano-blk-dkms)

fail=0
for kdir in /usr/src/linux-headers-*; do
    [ -e "$kdir/Module.symvers" ] || continue        # only the per-flavour trees
    k=${kdir#/usr/src/linux-headers-}
    t0=$(date +%s)
    if dkms build "nano-blk/$VER" -k "$k" >/tmp/b.log 2>&1; then
        ko=$(find /var/lib/dkms/nano-blk/"$VER"/"$k" -name 'nano_blk.ko*' | head -1)
        what=$(file -b "$ko" | cut -d, -f1-2)
        printf '{"arch":"%s","kernel":"%s","ok":true,"secs":%d,"ko":"%s"}\n' "$ARCH" "$k" $(( $(date +%s)-t0 )) "$what" | tee -a "$OUT"
    else
        fail=1
        err=$(grep -m1 -E 'error:' /var/lib/dkms/nano-blk/"$VER"/build/make.log 2>/dev/null | sed 's/"/\\"/g; s/^.*nano_blk/nano_blk/' || true)
        printf '{"arch":"%s","kernel":"%s","ok":false,"secs":%d,"first_error":"%s"}\n' "$ARCH" "$k" $(( $(date +%s)-t0 )) "$err" | tee -a "$OUT"
        grep -E 'error|warning' /var/lib/dkms/nano-blk/"$VER"/build/make.log | head -20 || cat /tmp/b.log
    fi
done
exit $fail
