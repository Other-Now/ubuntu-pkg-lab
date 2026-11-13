"""Resolve N sampled packages with depsolve and with `apt-get -s install`
(empty dpkg status, --no-install-recommends) and record where they differ.

  APT_CONFIG=~/upl-data/aptroot/apt.conf python3 scripts/compare_apt.py LISTS_DIR N SEED OUT.jsonl
"""
import json
import os
import random
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from depsolve import Index, Solver, Unsat, problems, unneeded  # noqa: E402

INST = re.compile(r"^Inst (\S+) \((\S+)")


_CACHE_PATH = os.environ.get("APT_RESULT_CACHE")
_cache = json.load(open(_CACHE_PATH)) if _CACHE_PATH and os.path.exists(_CACHE_PATH) else {}


def apt_resolve(pkg):
    """apt's answer for one request (memoised in $APT_RESULT_CACHE across runs)."""
    if pkg not in _cache:
        _cache[pkg] = _apt_resolve(pkg)
    return _cache[pkg]


def _apt_resolve(pkg):
    r = subprocess.run(["apt-get", "-s", "-q", "install", "--no-install-recommends", pkg],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None, (r.stdout + r.stderr).strip().splitlines()[-3:]
    return {m.group(1): m.group(2) for m in map(INST.match, r.stdout.splitlines()) if m}, None


def hard_names(idx):
    """Packages with a direct dependency that needs a choice: an OR group, or a
    virtual name with two or more providers."""
    out = []
    for name, pkgs in sorted(idx.by_name.items()):
        for clause in pkgs[0].depends:
            if len(clause) > 1 or (clause[0].name not in idx.by_name and
                                   len(idx.providers.get(clause[0].name, ())) > 1):
                out.append(name)
                break
    return out


def main(lists, n, seed, out, *, provider_order="apt"):
    files = sorted(os.path.join(lists, f) for f in os.listdir(lists) if f.endswith("_Packages"))
    t = time.perf_counter()
    idx = Index.load(*files)
    print(f"index: {sum(map(len, idx.by_name.values()))} packages, {len(idx.providers)} virtual names, "
          f"{time.perf_counter() - t:.1f}s", file=sys.stderr)
    names = sorted(idx.by_name)
    if os.environ.get("NAMES"):               # explicit list instead of a random sample
        sample = [x.split("#")[0].strip() for x in open(os.environ["NAMES"])]
        sample = [x for x in sample if x and x in idx.by_name][:n]
    elif os.environ.get("HARD"):              # packages that reach a real choice
        sample = random.Random(seed).sample(hard_names(idx), n)
    else:
        sample = random.Random(seed).sample(names, n)
    solver = Solver(idx, apt_provider_order=provider_order)
    agree = 0
    with open(out, "w", newline="") as f:
        for i, name in enumerate(sample):
            apt, apt_err = apt_resolve(name)
            t = time.perf_counter()
            try:
                ds, ds_err = {k: v.version for k, v in solver.solve([name]).items()}, None
            except Unsat as e:
                ds, ds_err = None, str(e)
            ms = (time.perf_counter() - t) * 1e3
            row = {"pkg": name, "apt_ok": apt is not None, "ds_ok": ds is not None,
                   "apt_n": len(apt or {}), "ds_n": len(ds or {}), "ds_ms": round(ms, 1),
                   "backtracks": solver.backtracks}
            if apt is not None and ds is not None:
                row["only_apt"] = sorted(set(apt) - set(ds))
                row["only_ds"] = sorted(set(ds) - set(apt))
                row["ver_diff"] = sorted(k for k in set(apt) & set(ds) if apt[k] != ds[k])
                row["same"] = not (row["only_apt"] or row["only_ds"] or row["ver_diff"])
                if not row["same"]:
                    # Both answers checked by the same independent verifier.
                    pick = lambda s: {k: next(p for p in idx.by_name[k] if p.version == v) for k, v in s.items()}
                    a, d = pick(apt), pick(ds)
                    row["apt_problems"] = problems(idx, a)[:5]
                    row["ds_problems"] = problems(idx, d)[:5]
                    row["apt_unneeded"] = unneeded(idx, a, [name])
                    row["ds_unneeded"] = unneeded(idx, d, [name])
            else:
                row["same"] = apt is None and ds is None
                row["apt_err"], row["ds_err"] = apt_err, ds_err
            agree += row["same"]
            f.write(json.dumps(row) + "\n")
            if (i + 1) % 50 == 0:
                print(f"{i + 1}/{len(sample)}: {agree} identical", file=sys.stderr)
    if _CACHE_PATH:
        json.dump(_cache, open(_CACHE_PATH, "w"))
    print(f"identical install sets: {agree}/{len(sample)} (provider order: {provider_order})", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4],
         provider_order=os.environ.get("PROVIDER_ORDER", "apt"))
