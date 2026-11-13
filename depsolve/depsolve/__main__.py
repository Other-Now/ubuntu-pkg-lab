"""python -m depsolve -i Packages [-i Packages ...] PKG [PKG ...]"""
import argparse
import sys
import time

from . import Index, Solver, Unsat


def main(argv=None):
    ap = argparse.ArgumentParser(prog="depsolve")
    ap.add_argument("-i", "--index", action="append", required=True, help="apt Packages file")
    ap.add_argument("packages", nargs="+")
    a = ap.parse_args(argv)
    idx = Index.load(*a.index)
    s = Solver(idx)
    t = time.perf_counter()
    try:
        res = s.solve(a.packages)
    except Unsat as e:
        print(f"E: {e}", file=sys.stderr)
        return 1
    for name in sorted(res):
        print(f"{name} {res[name].version}")
    print(f"# {len(res)} packages, {s.steps} steps, {s.backtracks} backtracks, "
          f"{(time.perf_counter() - t) * 1e3:.1f} ms", file=sys.stderr)
    return 0


sys.exit(main())
