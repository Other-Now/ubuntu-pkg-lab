# ubuntu-pkg-lab

Two small pieces of Ubuntu packaging work, both measured against the real thing:

1. **`nano-blk-dkms/`**: Debian packaging for [nano-blk](https://github.com/Other-Now/nano-blk),
   a blk-mq RAM-disk kernel driver, as a DKMS package. It is lintian-clean, rebuilt in a
   clean sbuild chroot, DKMS-built against Ubuntu 24.04's kernels on all five Ubuntu
   architectures, and autopkgtested in a VM that loads the module on Ubuntu's stock kernel.
2. **`depsolve/`**: a ~400-line Python dependency resolver over noble's real `Packages`
   indices, diffed against `apt-get -s` on 1,068 install requests.

Every number below comes from CI (`.github/workflows/ci.yml`) or from a script in
this repo; the raw data is in `results/` and `depsolve/results/`.
Study notes: [`docs/NOTES.md`](docs/NOTES.md).

---

## 1. nano-blk-dkms

```
nano-blk (source, 3.0 native)
├── nano-blk-dkms   Architecture: all   /usr/src/nano-blk-0.1.1/{nano_blk.c, nano_blk_compat.h, Makefile, dkms.conf}
└── nano-blk-tools  Architecture: any   /usr/sbin/blkcheck  (+ man page)
```

| CI job | What it does |
|---|---|
| `package` | `dpkg-buildpackage` (source + binary), then `lintian --pedantic --info --fail-on error,warning` |
| `sbuild` | rebuild from the `.dsc` in a fresh `mmdebstrap --variant=buildd` noble chroot (unshare mode), to catch missing Build-Depends |
| `dkms` ×5 | `ubuntu:24.04` container per arch (arm64 native, ppc64el/s390x/riscv64 under qemu-user): build the debs, install them, `dkms build` against every `linux-headers-*-generic` installed (GA + HWE) |
| `autopkgtest` | `autopkgtest … -- qemu` on a stock noble cloud image: Canonical's `dkms-autopkgtest`, plus `load-and-check` (modprobe, `blkcheck` ×2, rmmod) |

### Result: the package didn't install on Ubuntu 24.04's default kernel, and now does

The driver was written for 6.18 and calls `blk_mq_alloc_disk(set, &lim, data)`, a signature
that only exists since Linux **6.9**. Ubuntu 24.04's GA kernel is **6.8**.

**Before** (CI run 43377417965, [`results/before-fix/`](results/before-fix/)):

| arch | 6.8.0-149-generic (GA) | 7.0.0-43-generic (HWE) |
|---|---|---|
| amd64 | ✗ `macro "blk_mq_alloc_disk" passed 3 arguments, but takes just 2` | ✓ |
| arm64 | ✗ same | ✓ |
| ppc64el | ✗ same | ✓ |
| s390x | ✗ same | ✓ |
| riscv64 | (no 6.8 flavour: `linux-headers-generic` is 7.0 there) | ✓ |

The failure reaches the user as an install failure, not just a missing module: the DKMS
postinst exits 10, dpkg leaves `nano-blk-dkms` **half-configured**, and `apt install`
returns an error. autopkgtest reported both tests as `FAIL badpkg`.

**Fix** ([`nano_blk_compat.h`](nano-blk-dkms/nano_blk_compat.h), released as 0.1.1): below 6.9,
allocate the disk with the old 2-argument call and apply the same limits with the
`blk_queue_*()` setters.

**After** (CI run 43378090787, [`results/after-fix/`](results/after-fix/)):

- **9/9** kernel × architecture DKMS builds succeed: amd64, arm64, ppc64el and s390x on 6.8 and 7.0, and riscv64 on 7.0.
  `file` confirms each `.ko` targets its ISA, and s390x's is big-endian.
- **autopkgtest: `command1 PASS`, `load-and-check PASS`** on 6.8.0-149-generic in the VM.
  blkcheck ran 2 × 20,000 random write/read/discard ops against an in-memory model, then a full-device
  read-back: **0 mismatches, 0 I/O errors**.
- **lintian: 0 tags** at `--pedantic --info` (lintian 2.117.0ubuntu1.6).
- **sbuild: both binaries built** in the clean noble chroot.

### Not done

- **Launchpad PPA upload.** It needs a Launchpad account and an OpenPGP key; the procedure is in
  [`docs/PPA.md`](docs/PPA.md).
- The module was **loaded** only on amd64 (the VM). The other four architectures are
  compile-tested against Ubuntu's headers, but no system was booted on them.

---

## 2. depsolve

```sh
cd depsolve
python3 -m depsolve -i .../noble_main_binary-amd64_Packages -i .../noble_universe_binary-amd64_Packages texlive-full
```

It handles Depends, Pre-Depends, `a | b` alternatives, versioned relations, Conflicts, Breaks,
versioned and unversioned Provides, and architecture qualifiers. It searches depth-first and
backtracks fully at every choice point. `verify.py` checks any install set independently:
every clause satisfied and no conflicting pair.

### Version ordering: 0 disagreements with apt on 200,000 real pairs

[`scripts/vercmp_diff.py`](depsolve/scripts/vercmp_diff.py) takes every `Version` in
noble main+universe (22,717 distinct), builds 200,000 pairs (half random, half
neighbours in sorted order), and compares the results against `apt_pkg.version_compare`:

| comparator | disagreements |
|---|---|
| `depsolve.debver` (port of dpkg's `verrevcmp`) | **0** |
| the comparator from my earlier [nano-sensor](https://github.com/Other-Now/nano-sensor) project | **11,902 (5.95%)** |

nano-sensor's comparator was written for cross-ecosystem CVE version ranges, and it ignores
separators. So for `1.3-8build5` vs `1.3.0-3build1` it says `>`, while dpkg says `<`:
upstream `1.3` < `1.3.0`, because end-of-string sorts before `.`.

### Install sets: identical to apt on 1,067 of 1,068 requests

Reference: `apt-get -s install --no-install-recommends PKG` with an empty dpkg status, against the
same signed noble main+universe indices
([`scripts/compare_apt.py`](depsolve/scripts/compare_apt.py), summary in
[`depsolve/results/SUMMARY.md`](depsolve/results/SUMMARY.md)).

| sample | identical to apt | depsolve time, median / max |
|---|---|---|
| 500 random packages | **500/500** | 1.5 ms / 763 ms |
| 500 "choice" packages (a direct `a \| b` or a ≥2-provider virtual dependency) | **499/500** | 15.9 ms / 1.3 s |
| 68 curated large installs (ubuntu-desktop, kubuntu-desktop at 1,002 pkgs, texlive-full, libreoffice, …) | **68/68** | 21 ms / 2.4 s |

Getting there took three findings, each measured:

1. **apt's tie-break between equal providers is its internal package ID.** With providers ordered by
   Priority then name, 4 of the first 209 choice packages differed: for `www-browser` apt picked
   `wslu`, and for `phpapi-20230831` it picked `php8.3-phpdbg`. apt 2.8.3's `depcache.cc`
   `CompareProviders` ends with `return A->ID > B->ID;` ("unable to decide…"). The ID is the
   order in which apt's cache generator first met the name while parsing the indices. depsolve now
   records the same first-mention order. Ablation on the same 500:

   | provider order | identical |
   |---|---|
   | apt's (Essential, Important, Priority, **higher cache ID**) | **499/500** |
   | Priority, then name | 490/500 |
   | name only | 486/500 |

2. **A real bug in depsolve: architecture qualifiers.** `gdc-9-multilib` came out unsatisfiable,
   although apt installs 76 packages for it. The cause is noble's `libc6-x32`, which declares
   `Conflicts: libc6-i386:x32`, a conflict with the **x32 build** of libc6-i386. depsolve had
   stripped `:x32`, so it conflicted with the native package. It is fixed, with a regression test, and
   now 0 requests that apt can install are unsatisfiable in depsolve.

3. **The remaining difference is apt keeping debris from an abandoned attempt.** For `lomiri-common`,
   apt tries the first alternative of `unity-control-center | mate-control-center | …`. That subtree
   fails in context, so apt discards `unity-control-center`, but the packages it had already marked
   inside the attempt stay marked: `MarkInstall` discards only the failed package itself, and
   there is no rollback. The result is **39 of apt's 725 packages that no dependency in the final set
   needs** (gnome-bluetooth, GStreamer plugins, GTK 4, …). depsolve backtracks fully, so its answer has
   0 such packages. Both answers pass `verify()`.

   (The "unneeded" counter credits each clause to its first satisfied alternative. In the ablation rows, the php
   cases where apt shows 1 unneeded package are therefore an artefact: two providers of `phpapi-*` are both
   in the set. The 39 for lomiri-common were traced by hand.)

### Scope

- **Fresh installs only.** There is no installed state, upgrades, removals or pinning; the candidate is the highest version.
- Single architecture, and Multi-Arch is not modelled. **Recommends** are ignored, matching `--no-install-recommends`.
- **No install ordering**, which is where Pre-Depends differs from Depends.

---

## Layout

```
nano-blk-dkms/          driver source (from nano-blk @ 1350a8f) + compat header + debian/
ci/                     dkms-arch.sh (per-arch container), autopkgtest-vm.sh
results/                before-fix/ and after-fix/ CI evidence
depsolve/depsolve/      debver.py, index.py, solver.py, verify.py
depsolve/scripts/       compare_apt.py, vercmp_diff.py, nanosensor_vercmp.py, summarize.py
depsolve/tests/         pytest: version ordering (incl. cross-check vs apt_pkg), solver, verifier
docs/                   NOTES.md (study notes), PPA.md
```
