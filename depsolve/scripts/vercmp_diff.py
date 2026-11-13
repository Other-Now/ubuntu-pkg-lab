"""Differential test of version comparators against apt_pkg.version_compare
(libapt's implementation of dpkg's ordering) on real version pairs.

  python3 scripts/vercmp_diff.py LISTS_DIR N SEED
Pairs are drawn from every Version string in the index; half are random pairs,
half are "near" pairs (same package name prefix, so they share structure).
"""
import os
import random
import sys

import apt_pkg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from depsolve import Index, compare  # noqa: E402
from nanosensor_vercmp import compare as ns_compare  # noqa: E402

sign = lambda x: (x > 0) - (x < 0)


def main(lists, n, seed):
    apt_pkg.init_system()
    files = [os.path.join(lists, f) for f in os.listdir(lists) if f.endswith("_Packages")]
    idx = Index.load(*files)
    versions = sorted({p.version for ps in idx.by_name.values() for p in ps})
    rnd = random.Random(seed)
    pairs = [(rnd.choice(versions), rnd.choice(versions)) for _ in range(n // 2)]
    for _ in range(n - n // 2):          # neighbours in sorted order: similar strings
        i = rnd.randrange(len(versions) - 1)
        pairs.append((versions[i], versions[i + 1]))
    bad_ds = bad_ns = 0
    examples = []
    for a, b in pairs:
        ref = sign(apt_pkg.version_compare(a, b))
        if sign(compare(a, b)) != ref:
            bad_ds += 1
        if sign(ns_compare(a, b)) != ref:
            bad_ns += 1
            if len(examples) < 8:
                examples.append((a, b, ref, sign(ns_compare(a, b))))
    print(f"distinct versions: {len(versions)}, pairs: {len(pairs)}")
    print(f"depsolve.debver disagrees with apt_pkg: {bad_ds}")
    print(f"nano-sensor comparator disagrees with apt_pkg: {bad_ns} ({100 * bad_ns / len(pairs):.2f}%)")
    for a, b, r, g in examples:
        sym = {-1: "<", 0: "=", 1: ">"}
        print(f"  {a!r} vs {b!r}: dpkg says {sym[r]}, nano-sensor says {sym[g]}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
