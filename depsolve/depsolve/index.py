"""Parse an apt Packages index (deb822 paragraphs) and dependency fields."""
import re
from dataclasses import dataclass, field

# "name[:archqual] [(op version)] [[arch list]] [<profiles>]"
_REL = re.compile(r"^\s*([a-z0-9][a-z0-9+.\-]*)(?::[a-z0-9-]+)?\s*(?:\(\s*(<<|<=|=|>=|>>|<|>)\s*([^)\s]+)\s*\))?")

PRIORITY_RANK = {"required": 5, "important": 4, "standard": 3, "optional": 2, "extra": 1}


@dataclass(frozen=True)
class Rel:
    name: str
    op: str | None = None
    ver: str | None = None

    def __str__(self):
        return self.name + (f" ({self.op} {self.ver})" if self.op else "")


def parse_rels(text: str) -> list[list[Rel]]:
    """'a (>= 1) | b, c' -> [[Rel(a,>=,1), Rel(b)], [Rel(c)]]  (AND of ORs)."""
    out = []
    if not text:
        return out
    for clause in text.split(","):
        alts = []
        for alt in clause.split("|"):
            m = _REL.match(alt)
            if not m:
                raise ValueError(f"cannot parse relation {alt!r}")
            alts.append(Rel(m.group(1), m.group(2), m.group(3)))
        out.append(alts)
    return out


@dataclass(eq=False)
class Pkg:
    name: str
    version: str
    arch: str
    priority: int = 0
    essential: bool = False
    depends: list = field(default_factory=list)      # Pre-Depends + Depends, AND of ORs
    conflicts: list = field(default_factory=list)    # Conflicts + Breaks, flat list of Rel
    provides: list = field(default_factory=list)     # flat list of Rel (op only "=")

    def __repr__(self):
        return f"{self.name}={self.version}"


def paragraphs(path):
    para, key = {}, None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                if para:
                    yield para
                para, key = {}, None
            elif line[0] in " \t":
                para[key] += "\n" + line          # continuation
            else:
                key, _, val = line.partition(":")
                para[key] = val.strip()
    if para:
        yield para


class Index:
    def __init__(self):
        self.by_name: dict[str, list[Pkg]] = {}
        self.providers: dict[str, list[tuple[Pkg, str | None]]] = {}

    @classmethod
    def load(cls, *paths):
        idx = cls()
        for p in paths:
            for para in paragraphs(p):
                idx.add(para)
        return idx

    def add(self, para):
        rels = lambda k: parse_rels(para.get(k, ""))
        pkg = Pkg(
            name=para["Package"],
            version=para["Version"],
            arch=para.get("Architecture", "all"),
            priority=PRIORITY_RANK.get(para.get("Priority", "optional"), 0),
            essential=para.get("Essential") == "yes",
            depends=rels("Pre-Depends") + rels("Depends"),
            conflicts=[a for c in rels("Conflicts") + rels("Breaks") for a in c],
            provides=[a for c in rels("Provides") for a in c],
        )
        self.by_name.setdefault(pkg.name, []).append(pkg)
        for prov in pkg.provides:
            self.providers.setdefault(prov.name, []).append((pkg, prov.ver))
        return pkg
