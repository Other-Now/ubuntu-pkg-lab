"""Line-for-line Python port of nano-sensor's ns::version_compare
(github.com/Other-Now/nano-sensor, src/vercmp.cpp).  Kept only so the
differential test can measure how far it is from dpkg's ordering.  It was
written for matching CVE ranges across ecosystems, not for Debian."""

PRERELEASE = {"rc", "alpha", "beta", "pre", "dev", "preview", "snapshot", "nightly", "a1"}
TILDE, ALPHA, NUM = 0, 1, 2


def _tokens(v):
    out, i = [], 0
    while i < len(v):
        c = v[i]
        if c == "~":
            out.append((TILDE, None)); i += 1
        elif c.isdigit():
            j = i
            while j < len(v) and v[j].isdigit():
                j += 1
            d = v[i:j].lstrip("0")
            out.append((NUM, (2**64 - 1) if len(d) > 18 else int(d or "0"))); i = j
        elif c.isalpha():
            j = i
            while j < len(v) and v[j].isalpha():
                j += 1
            out.append((ALPHA, v[i:j].lower())); i = j
        else:
            i += 1          # separators are ignored
    return out


def _remainder(rest, k):
    if k >= len(rest):
        return 0
    kind, val = rest[k]
    if kind == TILDE or (kind == ALPHA and val in PRERELEASE):
        return -1
    return 1


def _epoch(v):
    head, sep, tail = v.partition(":")
    if sep and head.isdigit():
        return int(head), tail
    return 0, v


def compare(a, b):
    ea, a = _epoch(a)
    eb, b = _epoch(b)
    if ea != eb:
        return -1 if ea < eb else 1
    ta, tb = _tokens(a), _tokens(b)
    n = min(len(ta), len(tb))
    for x, y in zip(ta[:n], tb[:n]):
        if x[0] != y[0]:
            return -1 if x[0] < y[0] else 1
        if x[1] != y[1] and x[0] != TILDE:
            return -1 if x[1] < y[1] else 1
    if len(ta) > n:
        return _remainder(ta, n)
    if len(tb) > n:
        return -_remainder(tb, n)
    return 0
