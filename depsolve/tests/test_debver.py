import pytest

from depsolve.debver import compare, satisfies

sign = lambda x: (x > 0) - (x < 0)

# (a, b, expected sign of compare(a, b)) -- cases from Debian Policy 5.6.12 and dpkg's tests
CASES = [
    ("1.0", "1.0", 0),
    ("1.0", "1.0-0", 0),            # missing revision == "0"
    ("1.10", "1.9", 1),             # numeric, not lexical
    ("1.0~rc1", "1.0", -1),         # ~ sorts before end of string
    ("1.0~~", "1.0~", -1),
    ("1.0~", "1.0", -1),
    ("1.0", "1.0a", -1),            # end of string before letters
    ("1.0a", "1.0+", -1),           # letters before non-letters
    ("1.0+dfsg", "1.0.1", -1),      # '+' (non-letter) vs '.': '+' < '.'
    ("1:0.1", "2.0", 1),            # epoch wins
    ("1.3-8build5", "1.3.0-3build1", -1),
    ("007", "7", 0),                # leading zeros
    ("1.2-3ubuntu1", "1.2-3", 1),
    ("2.39-0ubuntu8.12", "2.39-0ubuntu8.2", 1),
    ("1.0-1~bpo1", "1.0-1", -1),    # backports sort below the release
]


@pytest.mark.parametrize("a,b,want", CASES)
def test_compare(a, b, want):
    assert sign(compare(a, b)) == want
    assert sign(compare(b, a)) == -want


def test_relations():
    assert satisfies("1.2", ">=", "1.2")
    assert not satisfies("1.2", ">>", "1.2")
    assert satisfies("1.1", "<<", "1.2")
    assert satisfies("1.2", "<", "1.2")     # obsolete '<' means '<='
    assert satisfies("1:1.0", "=", "1:1.0")


apt_pkg = pytest.importorskip("apt_pkg")


def test_matches_apt_pkg_on_tricky_strings():
    apt_pkg.init_system()
    vs = ["0", "0.0", "1", "1.0", "1.0-1", "1.0~", "1.0+", "1.0a", "1.0.a", "1:0", "1.0-1+b1",
          "1.0-1build1", "1.0~rc1-1", "1.0+really0.9-1", "a", "a1", "1a", "1~", "~", "1-1-1", "10", "9"]
    for a in vs:
        for b in vs:
            assert sign(compare(a, b)) == sign(apt_pkg.version_compare(a, b)), (a, b)
