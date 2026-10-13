"""Ce qu'un keyword d'une bibliothèque Python EXÉCUTE, et les variables d'un
fichier de variables ``.py``, lus statiquement par ``ast`` : rien n'est
importé ni exécuté (backlog § 2.3, 2026-10-09).

Le complément de :mod:`sapfx_common.robot_call_graph` pour l'analyse
d'impact. Les bibliothèques citent des objets SAP (``TBTCO`` dans le
keyword qui lit un job, ``T000`` dans des dizaines de modules) : un
transport qui touche ``TBTCO`` concerne les suites qui APPELLENT ce
keyword, pas toutes celles qui importent la bibliothèque.

Du keyword appelé à ce qu'il exécute : ses appels se résolvent par module
(``rfc_reads.build_options``, alias et ``from ... import`` compris), par
nom local, et ``self.methode`` vers les méthodes de toutes les classes lues
(une bibliothèque Robot se compose de mixins). Une constante lue par une
fonction atteinte est atteinte. Une docstring ou un commentaire nomme sans
exécuter. Un attribut sur un objet inconnu (``connexion.call``) vise les
méthodes de ce nom, sauf celles des types de base (``append``, ``split``) :
l'erreur possible va dans le sens de trop atteindre.

Une bibliothèque se trouve comme Robot la trouve (chemin relatif, ou nom de
module cherché dans ``python_path`` puis par ``importlib.util.find_spec`` du
paquet de tête, sans l'importer) ; ses imports ne sont suivis que sous la
même racine, et jamais hors projet (``site-packages``, bibliothèque
standard). Les bibliothèques standard de Robot ne sont pas lues. Typed.
"""
from __future__ import annotations

import ast
import importlib.util
import os
import re
import site
import sysconfig
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

from robot.libraries import STDLIBS

#: Méthodes des types de base : ``x.append`` sur un objet inconnu ne vise
#: pas une méthode de la bibliothèque qui porterait ce nom.
_BUILTIN_ATTRS = frozenset(n for t in (str, list, dict, set, tuple, bytes, int, float)
                           for n in dir(t))
#: Ce que construire une classe exécute.
_CONSTRUCTORS = ("__init__", "__post_init__", "__new__")


def normalize(name: str) -> str:
    return re.sub(r"[\s_]", "", name).lower()


@dataclass
class Unit:
    """Une fonction, une méthode ou une constante (module ou classe)."""
    kind: str
    name: str
    owner: str
    file: str
    start: int
    end: int
    keyword: str = ""
    docs: list[tuple[int, int]] = field(default_factory=list)
    refs: list[tuple[str, ...]] = field(default_factory=list)


@dataclass
class Module:
    path: str
    dotted: str
    units: list[Unit]
    docs: list[tuple[int, int]]
    comments: set[int]
    aliases: dict[str, str]
    names: dict[str, tuple[str, str]]
    exported: Optional[list[str]]


def _doc(body: Sequence[ast.stmt]) -> list[tuple[int, int]]:
    first = body[0] if body else None
    if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)):
        return [(first.lineno, first.end_lineno or first.lineno)]
    return []


def _chain(node: ast.Attribute) -> tuple[str, ...]:
    parts: list[str] = [node.attr]
    value: ast.expr = node.value
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    parts.append(value.id if isinstance(value, ast.Name) else "?")
    return tuple(reversed(parts))


def _refs(node: ast.AST) -> list[tuple[str, ...]]:
    out: list[tuple[str, ...]] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
            out.append(("name", sub.id))
        elif isinstance(sub, ast.Attribute):
            out.append(("attr",) + _chain(sub))
    return out


def _keyword_name(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Le nom de keyword normalisé : ``@keyword("Nom")`` d'abord, sinon le nom
    d'une fonction publique, vide pour une fonction privée."""
    for deco in node.decorator_list:
        call = deco if isinstance(deco, ast.Call) else None
        target = call.func if call is not None else deco
        named = (target.attr if isinstance(target, ast.Attribute)
                 else target.id if isinstance(target, ast.Name) else "")
        if named != "keyword" or call is None:
            continue
        for value in list(call.args) + [k.value for k in call.keywords if k.arg == "name"]:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return normalize(value.value)
    return "" if node.name.startswith("_") else normalize(node.name)


_MODULES: dict[tuple[str, str, int], Module] = {}


def read_python_module(path: str, dotted: str = "") -> Module:
    """Les fonctions, méthodes et constantes d'un fichier Python, avec leurs
    références, docstrings et commentaires, et ses imports. Un fichier n'est
    analysé qu'une fois tant qu'il ne change pas."""
    key = (os.path.normpath(os.path.abspath(path)), dotted, os.stat(path).st_mtime_ns)
    if key not in _MODULES:
        _MODULES[key] = _parse_module(path, dotted)
    return _MODULES[key]


def _parse_module(path: str, dotted: str) -> Module:
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    tree = ast.parse(source, filename=path)
    module = Module(path, dotted, [], _doc(tree.body),
                    {n for n, line in enumerate(source.splitlines(), 1)
                     if line.lstrip().startswith("#")}, {}, {}, None)
    package = dotted if path.endswith("__init__.py") else dotted.rpartition(".")[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module.aliases[alias.asname or alias.name.split(".")[0]] = (
                    alias.name if alias.asname else alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            base = _absolute(package, node.module or "", node.level)
            for alias in node.names:
                module.names[alias.asname or alias.name] = (base, alias.name)
    _collect(module, tree.body, "")
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            try:
                module.exported = [str(v) for v in ast.literal_eval(node.value)]
            except ValueError:
                module.exported = None
    return module


def _absolute(package: str, name: str, level: int) -> str:
    if not level:
        return name
    parts = package.split(".") if package else []
    parts = parts[:len(parts) - (level - 1)] if level > 1 else parts
    return ".".join(p for p in parts + ([name] if name else []) if p)


def _collect(module: Module, body: Sequence[ast.stmt], owner: str) -> None:
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            module.units.append(Unit("function", node.name, owner, module.path, node.lineno,
                                     node.end_lineno or node.lineno, _keyword_name(node),
                                     _doc(node.body), _refs(node)))
        elif isinstance(node, ast.ClassDef):
            module.docs += _doc(node.body)
            _collect(module, node.body, node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and node.value is not None:
                    module.units.append(Unit("constant", target.id, owner, module.path,
                                             node.lineno, node.end_lineno or node.lineno,
                                             refs=_refs(node.value)))


# --- trouver une bibliothèque -------------------------------------------------------

def _external_roots() -> list[str]:
    roots = list(site.getsitepackages()) + [site.getusersitepackages()]
    roots += [p for k in ("stdlib", "platstdlib", "purelib", "platlib")
              if (p := sysconfig.get_paths().get(k))]
    return [os.path.normcase(os.path.abspath(r)) for r in roots if r]


def _is_external(path: str) -> bool:
    full = os.path.normcase(os.path.abspath(path))
    return any(full == r or full.startswith(r + os.sep) for r in _external_roots())


def _module_file(root: str, dotted: str) -> Optional[str]:
    base = os.path.join(root, *dotted.split("."))
    for candidate in (base + ".py", os.path.join(base, "__init__.py")):
        if os.path.isfile(candidate):
            return os.path.normpath(os.path.abspath(candidate))
    return None


def _top_root(top: str, python_path: Iterable[str]) -> Optional[str]:
    for folder in python_path:
        if _module_file(folder, top):
            return os.path.normpath(os.path.abspath(folder))
    try:
        spec = importlib.util.find_spec(top)
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.origin or spec.origin in ("built-in", "frozen"):
        return None
    origin = os.path.dirname(spec.origin) if spec.origin.endswith("__init__.py") else spec.origin
    return os.path.dirname(origin)


@dataclass
class LibrarySource:
    """Les fichiers d'une bibliothèque : ceux qui portent ses keywords
    (``entry``) et ceux qu'ils importent sous la même racine (``files``),
    chacun avec son nom de module."""
    name: str
    entry: list[str]
    files: dict[str, str]


def find_library_source(name: str, base_dir: str,
                        python_path: Iterable[str] = ()) -> Optional[LibrarySource]:
    """Les fichiers d'une bibliothèque importée par ``Library    <name>``,
    sans l'importer ; ``None`` pour une bibliothèque standard de Robot ou
    introuvable."""
    name = name.replace("${CURDIR}", base_dir)
    if name in STDLIBS or "${" in name:
        return None
    if name.endswith(".py") or "/" in name or "\\" in name:
        path = os.path.normpath(os.path.join(base_dir, name))
        if not os.path.isfile(path):
            return None
        root = os.path.dirname(path)
    else:
        found = _top_root(name.split(".")[0], list(python_path))
        located = _module_file(found, name) if found else None
        if not found or located is None:
            return None
        root, path = found, located
    if path.endswith("__init__.py"):
        folder = os.path.dirname(path)
        entry = sorted(os.path.normpath(os.path.join(d, f)) for d, _s, fs in os.walk(folder)
                       for f in fs if f.endswith(".py"))
    else:
        entry = [path]
    files = {p: _dotted(root, p) for p in entry}
    if not _is_external(path):
        _follow_imports(root, files)
    return LibrarySource(name, entry, files)


def _dotted(root: str, path: str) -> str:
    rel = os.path.splitext(os.path.relpath(path, root))[0].replace(os.sep, ".")
    return rel[:-len(".__init__")] if rel.endswith(".__init__") else rel


def _follow_imports(root: str, files: dict[str, str]) -> None:
    pending = list(files)
    while pending:
        path = pending.pop()
        try:
            module = read_python_module(path, files[path])
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        targets = set(module.aliases.values())
        targets |= {m for m, _n in module.names.values()}
        targets |= {"%s.%s" % (m, n) for m, n in module.names.values() if m}
        for dotted in targets:
            found = _module_file(root, dotted) if dotted else None
            if found and found not in files:
                files[found] = dotted
                pending.append(found)


# --- le graphe ----------------------------------------------------------------------

class PythonGraph:
    """Les unités des fichiers lus et leurs liens ; ``keywords`` : les
    fonctions et méthodes PUBLIQUES des fichiers d'entrée, par nom de keyword
    normalisé (``@keyword("Nom")`` respecté)."""

    def __init__(self, sources: Iterable[LibrarySource]) -> None:
        self.modules: dict[str, Module] = {}
        self.keywords: dict[str, list[Unit]] = {}
        self.methods: dict[str, list[Unit]] = {}
        entry: set[str] = set()
        for source in sources:
            entry |= set(source.entry)
            for path, dotted in source.files.items():
                if path not in self.modules:
                    try:
                        self.modules[path] = read_python_module(path, dotted)
                    except (OSError, SyntaxError, UnicodeDecodeError):
                        continue
        self.by_dotted = {m.dotted: m for m in self.modules.values()}
        self._targets: dict[int, list[Unit]] = {}
        self._live: Optional[set[int]] = None
        self.owner: dict[int, Module] = {}
        for module in self.modules.values():
            for unit in module.units:
                self.owner[id(unit)] = module
                if unit.owner:
                    self.methods.setdefault(unit.name, []).append(unit)
                public = module.exported is None or unit.name in module.exported or unit.owner
                if (module.path in entry and unit.kind == "function" and unit.keyword
                        and public):
                    self.keywords.setdefault(unit.keyword, []).append(unit)

    def keyword_units(self, call: str) -> list[Unit]:
        key = normalize(call)
        while key not in self.keywords and "." in key:     # Bibliotheque.Keyword
            key = key.split(".", 1)[1]
        return self.keywords.get(key, [])

    def _symbols(self, module: Module, name: str) -> list[Unit]:
        found = [u for u in module.units if not u.owner and u.name == name]
        return found or [u for u in module.units if u.owner == name and u.name in _CONSTRUCTORS]

    def _module(self, current: Module, base: str) -> Optional[Module]:
        if base in current.aliases:
            return self.by_dotted.get(current.aliases[base])
        if base in current.names:
            mod, name = current.names[base]
            return self.by_dotted.get("%s.%s" % (mod, name) if mod else name)
        return None

    @property
    def live(self) -> set[int]:
        """Ce que l'ensemble des keywords atteint : le code vivant."""
        if self._live is None:
            self._live = self.reach(u for units in self.keywords.values() for u in units)
        return self._live

    def targets(self, unit: Unit) -> list[Unit]:
        if id(unit) not in self._targets:
            self._targets[id(unit)] = self._resolve(unit)
        return self._targets[id(unit)]

    def _resolve(self, unit: Unit) -> list[Unit]:
        module = self.owner[id(unit)]
        out: list[Unit] = []
        for ref in unit.refs:
            if ref[0] == "name":
                local = self._symbols(module, ref[1])
                if not local and ref[1] in module.names:
                    mod, name = module.names[ref[1]]
                    target = self.by_dotted.get(mod)
                    local = self._symbols(target, name) if target else []
                out += local
                continue
            base, attrs = ref[1], ref[2:]
            if base in ("self", "cls"):
                out += self.methods.get(attrs[0], [])
                continue
            target = self._module(module, base)
            while target is not None and len(attrs) > 1 and \
                    self.by_dotted.get("%s.%s" % (target.dotted, attrs[0])):
                target, attrs = self.by_dotted["%s.%s" % (target.dotted, attrs[0])], attrs[1:]
            if target is not None:
                out += self._symbols(target, attrs[0])
            elif attrs[-1] not in _BUILTIN_ATTRS:
                out += self.methods.get(attrs[-1], [])
        return out

    def reach(self, roots: Iterable[Unit]) -> set[int]:
        reached: set[int] = set()
        stack = list(roots)
        while stack:
            unit = stack.pop()
            if id(unit) in reached:
                continue
            reached.add(id(unit))
            stack.extend(self.targets(unit))
        return reached

    def anchor(self, path: str, line: int) -> tuple[Optional[Unit], bool]:
        """L'unité qui porte une ligne (la plus intérieure) et si la ligne est
        documentaire (docstring, commentaire, hors de toute unité)."""
        module = self.modules.get(os.path.normpath(path))
        if module is None:
            return None, True
        inside = [u for u in module.units if u.start <= line <= u.end]
        if not inside:
            return None, True
        unit = min(inside, key=lambda u: u.end - u.start)
        documentary = line in module.comments or any(
            a <= line <= b for a, b in unit.docs + module.docs)
        return unit, documentary
