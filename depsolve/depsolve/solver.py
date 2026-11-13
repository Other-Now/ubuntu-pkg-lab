"""Install-set resolver: depth-first search with backtracking.

Given an index and a list of requested package names, find a set of packages
(one version per name) such that
  * every requested package is in the set,
  * every Depends/Pre-Depends clause of every member is satisfied by a member
    (directly, or through Provides),
  * no member Conflicts with or Breaks another member.

Recommends/Suggests are ignored (like apt-get --no-install-recommends).

Choice order -- which alternative is tried first -- decides *which* valid
answer comes out, and is where this solver and apt can differ:
  1. alternatives of an "a | b" clause in the order written;
  2. for one alternative: the real package of that name (highest version first),
     then packages that Provide the name, ordered like apt 2.8 orders them
     (see provider_key).  Getting this order wrong does not make an answer
     invalid -- it makes it a *different* valid answer than apt's.
"""
import sys
from .debver import compare, satisfies
from .index import Index, Pkg, Rel
from functools import cmp_to_key


class Unsat(Exception):
    pass


class Solver:
    def __init__(self, index: Index, *, apt_provider_order="apt", max_steps=200_000):
        self.idx = index
        self.apt_provider_order = apt_provider_order
        self.max_steps = max_steps
        self.steps = 0
        self.backtracks = 0

    # ---- candidates -------------------------------------------------------
    def candidates(self, rel: Rel) -> list[Pkg]:
        real = [p for p in self.idx.by_name.get(rel.name, ())
                if rel.op is None or satisfies(p.version, rel.op, rel.ver)]
        real.sort(key=cmp_to_key(lambda a, b: compare(b.version, a.version)))
        provs = []
        for p, pver in self.idx.providers.get(rel.name, ()):
            # An unversioned dependency is met by any Provides; a versioned one
            # only by a versioned Provides that satisfies it (Policy 7.5).
            if rel.op is None or (pver is not None and satisfies(pver, rel.op, rel.ver)):
                provs.append(p)
        if self.apt_provider_order == "apt":
            provs.sort(key=self.provider_key)
        elif self.apt_provider_order == "priority-name":
            provs.sort(key=lambda p: (not p.essential, -p.priority, p.name))
        else:                                    # "name"
            provs.sort(key=lambda p: p.name)
        out, seen = [], set()
        for p in real + provs:
            if id(p) not in seen:
                seen.add(id(p))
                out.append(p)
        return out

    def provider_key(self, p: Pkg):
        # apt 2.8 depcache.cc CompareProviders, for an empty dpkg status and a
        # single architecture: essential, then Important, then higher Priority,
        # then -- "unable to decide" -- the higher package ID.
        return (not p.essential, not p.important, -p.priority, -self.idx.first_seen[p.name])

    # ---- conflict check ---------------------------------------------------
    @staticmethod
    def _hits(rel: Rel, q: Pkg) -> bool:
        """Does relation `rel` (a Conflicts/Breaks entry) match package q?"""
        if q.name == rel.name and (rel.op is None or satisfies(q.version, rel.op, rel.ver)):
            return True
        for prov in q.provides:
            if prov.name == rel.name and (rel.op is None or
                                          (prov.ver is not None and satisfies(prov.ver, rel.op, rel.ver))):
                return True
        return False

    def conflicts_with(self, p: Pkg, chosen: dict) -> Pkg | None:
        for q in chosen.values():
            if q is p:
                continue
            # A package may conflict with a virtual name it itself provides; that
            # never matches itself (the "Provides+Conflicts+Replaces" idiom).
            if any(self._hits(r, q) for r in p.conflicts) or any(self._hits(r, p) for r in q.conflicts):
                return q
        return None

    # ---- search -----------------------------------------------------------
    def solve(self, names: list[str]) -> dict[str, Pkg]:
        self.steps = self.backtracks = 0
        agenda = [[Rel(n)] for n in reversed(names)]
        old = sys.getrecursionlimit()
        sys.setrecursionlimit(max(old, 20000))
        try:
            res = self._search({}, agenda)
        finally:
            sys.setrecursionlimit(old)
        if res is None:
            raise Unsat(f"no installable set for {names}")
        return res

    def _satisfied(self, clause, chosen) -> bool:
        for rel in clause:
            q = chosen.get(rel.name)
            if q is not None and (rel.op is None or satisfies(q.version, rel.op, rel.ver)):
                return True
            for p, pver in self.idx.providers.get(rel.name, ()):
                if chosen.get(p.name) is p and (rel.op is None or
                                                (pver is not None and satisfies(pver, rel.op, rel.ver))):
                    return True
        return False

    def _search(self, chosen: dict, agenda: list):
        chosen, agenda = dict(chosen), list(agenda)
        while agenda:
            self.steps += 1
            if self.steps > self.max_steps:
                raise Unsat("step limit")
            clause = agenda.pop()
            if self._satisfied(clause, chosen):
                continue
            options = []
            for rel in clause:
                for p in self.candidates(rel):
                    if p.name in chosen:        # another version already chosen
                        continue
                    if self.conflicts_with(p, chosen) is None and p not in options:
                        options.append(p)
            if not options:
                return None
            if len(options) == 1:               # forced move: no choice point
                p = options[0]
                chosen[p.name] = p
                agenda.extend(reversed(p.depends))
                continue
            for p in options:                   # choice point
                c2 = dict(chosen)
                c2[p.name] = p
                res = self._search(c2, agenda + list(reversed(p.depends)))
                if res is not None:
                    return res
                self.backtracks += 1
            return None
        return chosen
