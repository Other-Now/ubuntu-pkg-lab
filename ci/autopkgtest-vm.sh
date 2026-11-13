#!/bin/bash
# amd64: run the package's autopkgtests in a QEMU/KVM VM booted from a stock
# Ubuntu 24.04 cloud image -- so the module is built and loaded on Ubuntu's own
# generic kernel, not the CI host's Azure kernel.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p results
IMG=$HOME/autopkgtest-noble-amd64.img
[ -f "$IMG" ] || (cd "$HOME" && sudo autopkgtest-buildvm-ubuntu-cloud -r noble -a amd64 -s 10G --ram-size 2048 && sudo chown "$USER" autopkgtest-noble-amd64.img)
set +e
autopkgtest -o results/autopkgtest-amd64 build/nano-blk-dkms_*_all.deb build/nano-blk-tools_*_amd64.deb nano-blk-dkms/ \
    -- qemu --ram-size 2048 --cpus 2 "$IMG"
rc=$?
set -e
cat results/autopkgtest-amd64/summary || true
exit $rc
