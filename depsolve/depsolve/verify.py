"""Check an install set independently of how it was produced."""
from collections import deque

from .debver import satisfies
from .index import Index


def _sat(rel, chosen, index):
    q = chosen.get(rel.name)
    if q is not None and (rel.op is None or satisfies(q.version, rel.op, rel.ver)):
        return q.name
    for p, pver in index.providers.get(rel.name, ()):
        if chosen.get(p.name) is p and (rel.op is None or (pver is not None and satisfies(pver, rel.op, rel.ver))):
            return p.name
    return None


def problems(index: Index, chosen: dict) -> list[str]:
    """Unsatisfied dependency clauses and conflicting pairs in `chosen` (name -> Pkg)."""
    from .solver import Solver
    out = []
    for p in chosen.values():
        for clause in p.depends:
            if not any(_sat(r, chosen, index) for r in clause):
                out.append(f"{p.name}: unsatisfied {' | '.join(map(str, clause))}")
        for r in p.conflicts:
            for q in chosen.values():
                if q is not p and Solver._hits(r, q):
                    out.append(f"{p.name} conflicts/breaks {q.name}")
    return out


def unneeded(index: Index, chosen: dict, roots) -> list[str]:
    """Members not reachable from `roots` when each clause is credited to the
    first alternative already in the set -- i.e. packages no dependency needs."""
    seen, dq = set(roots), deque(roots)
    while dq:
        for clause in chosen[dq.popleft()].depends:
            for r in clause:
                t = _sat(r, chosen, index)
                if t:
                    if t not in seen:
                        seen.add(t)
                        dq.append(t)
                    break
    return sorted(set(chosen) - seen)
