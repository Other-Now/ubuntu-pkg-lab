import textwrap

import pytest

from depsolve import Index, Solver, Unsat, parse_rels


def idx_from(text, tmp_path):
    p = tmp_path / "Packages"
    p.write_text(textwrap.dedent(text).strip() + "\n")
    return Index.load(str(p))


def solve(text, tmp_path, *names, **kw):
    return {k: v.version for k, v in Solver(idx_from(text, tmp_path), **kw).solve(list(names)).items()}


def test_parse_rels():
    r = parse_rels("a (>= 1.0) | b:any, c [amd64], d (<<2)")
    assert [[str(x) for x in c] for c in r] == [["a (>= 1.0)", "b"], ["c"], ["d (<< 2)"]]


def test_simple_chain(tmp_path):
    got = solve("""
        Package: a
        Version: 1
        Depends: b

        Package: b
        Version: 1
        Pre-Depends: c

        Package: c
        Version: 1
        """, tmp_path, "a")
    assert got == {"a": "1", "b": "1", "c": "1"}


def test_versioned_dependency_picks_satisfying_version(tmp_path):
    got = solve("""
        Package: a
        Version: 1
        Depends: lib (<< 2)

        Package: lib
        Version: 2

        Package: lib
        Version: 1.5
        """, tmp_path, "a")
    assert got["lib"] == "1.5"


def test_first_alternative_preferred(tmp_path):
    got = solve("""
        Package: a
        Version: 1
        Depends: x | y

        Package: x
        Version: 1

        Package: y
        Version: 1
        """, tmp_path, "a")
    assert set(got) == {"a", "x"}


def test_backtracks_out_of_a_conflict(tmp_path):
    # x is tried first but conflicts with c, which a also needs -> must pick y.
    got = solve("""
        Package: a
        Version: 1
        Depends: x | y, c

        Package: x
        Version: 1
        Conflicts: c

        Package: y
        Version: 1

        Package: c
        Version: 1
        """, tmp_path, "a")
    assert set(got) == {"a", "y", "c"}


def test_breaks_is_versioned(tmp_path):
    got = solve("""
        Package: a
        Version: 1
        Depends: b, c

        Package: b
        Version: 1
        Breaks: c (<< 2)

        Package: c
        Version: 2

        Package: c
        Version: 1
        """, tmp_path, "a")
    assert got["c"] == "2"


def test_virtual_unversioned_and_versioned_provides(tmp_path):
    text = """
        Package: app
        Version: 1
        Depends: mta

        Package: app2
        Version: 1
        Depends: mta (>= 2)

        Package: exim
        Version: 4
        Priority: extra
        Provides: mta

        Package: postfix
        Version: 3
        Priority: optional
        Provides: mta (= 2)
        """
    # apt ordering: higher Priority first -> postfix
    assert "postfix" in solve(text, tmp_path, "app")
    # name ordering would pick exim
    assert "exim" in solve(text, tmp_path, "app", apt_provider_order=False)
    # only a versioned Provides can satisfy a versioned dependency
    assert "postfix" in solve(text, tmp_path, "app2", apt_provider_order=False)


def test_provides_conflicts_replaces_idiom(tmp_path):
    # Each MTA provides and conflicts with "mta": only one can be installed,
    # and a package never conflicts with itself.
    got = solve("""
        Package: exim
        Version: 4
        Provides: mta
        Conflicts: mta

        Package: postfix
        Version: 3
        Provides: mta
        Conflicts: mta
        """, tmp_path, "exim")
    assert got == {"exim": "4"}
    with pytest.raises(Unsat):
        solve("""
            Package: exim
            Version: 4
            Provides: mta
            Conflicts: mta

            Package: postfix
            Version: 3
            Provides: mta
            Conflicts: mta
            """, tmp_path, "exim", "postfix")


def test_unsatisfiable(tmp_path):
    with pytest.raises(Unsat):
        solve("""
            Package: a
            Version: 1
            Depends: missing
            """, tmp_path, "a")
