"""Debian version comparison, following dpkg (lib/dpkg/version.c, verrevcmp).

A version is   [epoch:]upstream[-revision]
  * epoch: integer, default 0; compared first.
  * revision: everything after the LAST '-'; default "" (compares like "0").
  * upstream and revision are compared with the same string algorithm:
      alternate "non-digit run" / "digit run";
      non-digit runs compare character by character with the order
          '~'  <  end-of-string  <  letters  <  everything else ('+', '.', '-')
      digit runs compare numerically (leading zeros ignored).
"""
from functools import lru_cache


def _order(c: str) -> int:
    if c == "~":
        return -1
    if c.isdigit():
        return 0          # never reached for a char inside a non-digit run
    if c.isalpha():
        return ord(c)
    return ord(c) + 256


def _verrevcmp(a: str, b: str) -> int:
    i = j = 0
    while i < len(a) or j < len(b):
        first_diff = 0
        # non-digit prefix
        while (i < len(a) and not a[i].isdigit()) or (j < len(b) and not b[j].isdigit()):
            ac = _order(a[i]) if i < len(a) and not a[i].isdigit() else 0
            bc = _order(b[j]) if j < len(b) and not b[j].isdigit() else 0
            if ac != bc:
                return ac - bc
            i += 1
            j += 1
        # digit run: skip leading zeros, then the longer run wins, else first differing digit
        while i < len(a) and a[i] == "0":
            i += 1
        while j < len(b) and b[j] == "0":
            j += 1
        while i < len(a) and a[i].isdigit() and j < len(b) and b[j].isdigit():
            if not first_diff:
                first_diff = ord(a[i]) - ord(b[j])
            i += 1
            j += 1
        if i < len(a) and a[i].isdigit():
            return 1
        if j < len(b) and b[j].isdigit():
            return -1
        if first_diff:
            return first_diff
    return 0


def parse(v: str):
    epoch = 0
    if ":" in v:
        e, v = v.split(":", 1)
        epoch = int(e)
    if "-" in v:
        upstream, rev = v.rsplit("-", 1)
    else:
        upstream, rev = v, ""
    return epoch, upstream, rev


@lru_cache(maxsize=1 << 16)
def compare(a: str, b: str) -> int:
    """<0, 0, >0 like dpkg --compare-versions (sign only is meaningful)."""
    ea, ua, ra = parse(a)
    eb, ub, rb = parse(b)
    if ea != eb:
        return -1 if ea < eb else 1
    c = _verrevcmp(ua, ub)
    if c:
        return c
    return _verrevcmp(ra, rb)


def satisfies(version: str, op: str, ref: str) -> bool:
    c = compare(version, ref)
    if op == "<<":
        return c < 0
    if op in ("<=", "<"):      # "<" and ">" are obsolete spellings of <= and >=
        return c <= 0
    if op == "=":
        return c == 0
    if op in (">=", ">"):
        return c >= 0
    if op == ">>":
        return c > 0
    raise ValueError(f"bad relation {op!r}")
