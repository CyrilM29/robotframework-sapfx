"""Les imports d'une suite Robot, résolus comme Robot les résout (backlog
§ 2.3, 2026-10-09) : ses ressources de proche en proche, ses bibliothèques,
ses fichiers de variables, et ce qui ne se résout pas.

Un chemin d'import peut porter des variables, que Robot remplace au moment
de l'import par ce qu'il connaît alors. On fait de même avec, dans cet ordre
de priorité : celles qu'on passerait par ``robot -v`` (``variables``), les
variables intégrées (``${CURDIR}``, le dossier du fichier qui importe,
``${EXECDIR}``, ``${/}``, ``${TEMPDIR}``, ``${SPACE}``, ``${EMPTY}``) et
d'environnement (``%{NOM}``), puis les variables à valeur littérale des
sections ``*** Variables ***`` et des fichiers de variables déjà lus, la
première définie l'emportant. Un chemin relatif se cherche depuis le fichier
qui importe, puis dans ``python_path`` et ``sys.path``, comme Robot.

Un import qui ne se résout pas (variable inconnue, fichier introuvable)
n'est jamais ignoré en silence : il est rendu dans ``unresolved`` avec son
fichier et sa ligne, et l'analyse d'impact en fait une suite INCERTAINE, une
ressource inconnue pouvant appeler n'importe quel keyword. Une bibliothèque
nommée par module qu'on ne trouve pas (paquet non installé) est seulement
non lue. Typed.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional

from .python_call_graph import LibrarySource, find_library_source
from .robot_model import Block, RobotFile, _declared, cached_robot_file, normalize
from .variable_files import read_variable_file

_VARIABLE = re.compile(r"([$%])\{([^{}]+)\}")
_VARIABLE_FILES = (".py", ".yaml", ".yml", ".json")


@dataclass
class SuiteImports:
    """Ce qu'une suite importe, de proche en proche : ``resources`` et
    ``variable_files`` (chemins), ``libraries`` (nom résolu et dossier du
    fichier qui l'importe), ``unresolved`` (fichier, ligne, import écrit)."""
    resources: list[str] = field(default_factory=list)
    libraries: list[tuple[str, str]] = field(default_factory=list)
    variable_files: list[str] = field(default_factory=list)
    unresolved: list[tuple[str, int, str]] = field(default_factory=list)


def as_variables(value: Any) -> dict[str, str]:
    """``{nom normalisé: valeur}`` depuis un dict, ou des ``NOM:valeur``
    comme ``robot -v`` (liste, ou chaîne à virgules)."""
    if not value:
        return {}
    if isinstance(value, Mapping):
        pairs = [(str(k), str(v)) for k, v in value.items()]
    else:
        pairs = []
        for entry in value.split(",") if isinstance(value, str) else value:
            name, sep, text = str(entry).partition(":")
            if not sep:
                raise ValueError("variable %r : attendu NOM:valeur, comme robot -v" % entry)
            pairs.append((name, text))
    return {normalize(name.strip().removeprefix("${").removesuffix("}")): text
            for name, text in pairs}


def resolve_import(text: str, base: str, known: Mapping[str, str]) -> Optional[str]:
    """Un chemin d'import, variables connues remplacées (``${CURDIR}`` par
    ``base``, ``%{NOM}`` par l'environnement) ; ``None`` quand une variable
    reste inconnue."""
    def value(match: re.Match[str]) -> str:
        if match.group(1) == "%":
            return os.environ.get(match.group(2), match.group(0))
        key = normalize(match.group(2))
        return base if key == "curdir" else known.get(key, match.group(0))
    resolved = _VARIABLE.sub(value, text)
    return None if _VARIABLE.search(resolved) else resolved


def _builtins() -> dict[str, str]:
    return {"execdir": os.path.abspath(os.getcwd()), "/": os.sep,
            "tempdir": tempfile.gettempdir(), "space": " ", "empty": ""}


def suite_imports(suite: str, cache: Optional[dict[Any, Any]] = None, variables: Any = None,
                  python_path: Iterable[str] = ()) -> SuiteImports:
    """Ce que la suite importe, de proche en proche, et ce qui ne se résout
    pas (voir le module)."""
    cache = {} if cache is None else cache
    known = as_variables(variables)
    for name, text in _builtins().items():
        known.setdefault(name, text)
    path = os.path.normpath(os.path.abspath(suite))
    folders = tuple(python_path)
    key = ("imports", path, tuple(sorted(known.items())), folders)
    if key not in cache:
        found = SuiteImports()
        _walk(path, cache, known, found, {path}, folders)
        cache[key] = found
    return cache[key]  # type: ignore[no-any-return]


def _remember(blocks: Iterable[Block], known: dict[str, str]) -> None:
    for block in blocks:
        if block.kind == "variable" and block.name.startswith("$") and len(block.literals) == 1:
            known.setdefault(_declared(block.name), block.literals[0])


def _locate(name: str, base: str, known: Mapping[str, str],
            folders: tuple[str, ...]) -> tuple[Optional[str], bool]:
    """Le fichier d'un import, et s'il s'est résolu (variables connues)."""
    resolved = resolve_import(name, base, known)
    if resolved is None:
        return None, False
    for folder in (base,) + folders + tuple(sys.path):
        candidate = os.path.normpath(os.path.join(folder, resolved))
        if folder and os.path.isfile(candidate):
            return candidate, True
        if os.path.isabs(resolved):
            break
    return None, True


def _walk(path: str, cache: dict[Any, Any], known: dict[str, str], found: SuiteImports,
          seen: set[str], folders: tuple[str, ...]) -> None:
    parsed = cached_robot_file(path, cache)
    if parsed is None:
        return
    base = os.path.dirname(path)
    _remember(parsed.blocks, known)
    for name, line in parsed.variable_files:
        target, _ok = _locate(name, base, known, folders)
        if target is None or not target.lower().endswith(_VARIABLE_FILES):
            found.unresolved.append((path, line, name))
        elif target not in found.variable_files:
            found.variable_files.append(target)
            variables = variable_file(target, cache)
            _remember(variables.blocks if variables else [], known)
    for name, line in parsed.libraries:
        resolved = resolve_import(name, base, known)
        if resolved is None:
            found.unresolved.append((path, line, name))
        elif (resolved, base) not in found.libraries:
            found.libraries.append((resolved, base))
    for name, line in parsed.imports:
        target, _ok = _locate(name, base, known, folders)
        if target is None:
            found.unresolved.append((path, line, name))
        elif target not in seen:
            seen.add(target)
            found.resources.append(target)
            _walk(target, cache, known, found, seen, folders)


def resource_closure(path: str, cache: Optional[dict[Any, Any]] = None, variables: Any = None,
                     python_path: Iterable[str] = ()) -> list[str]:
    """Les ressources qu'un fichier Robot importe, transitivement."""
    return list(suite_imports(path, cache, variables, python_path).resources)


def python_sources(suite: str, cache: Optional[dict[Any, Any]] = None,
                   python_path: Iterable[str] = (), variables: Any = None
                   ) -> tuple[list[LibrarySource], list[str]]:
    """Les bibliothèques (sources Python, voir
    :func:`sapfx_common.python_call_graph.find_library_source`) et les
    fichiers de variables que la suite et ses ressources importent."""
    cache = {} if cache is None else cache
    folders = tuple(python_path)
    imports = suite_imports(suite, cache, variables, folders)
    libraries: dict[str, LibrarySource] = {}
    for name, base in imports.libraries:
        by_path = name.endswith(".py") or "/" in name or "\\" in name
        key = ("library", os.path.join(base, name) if by_path else name, folders)
        if key not in cache:
            cache[key] = find_library_source(name, base, folders)
        if cache[key] is not None:
            libraries.setdefault(cache[key].entry[0], cache[key])
    return list(libraries.values()), list(imports.variable_files)


def variable_file(path: str, cache: dict[Any, Any]) -> Optional[RobotFile]:
    """Un fichier de variables vu comme un fichier Robot : un bloc
    ``variable`` par variable déclarée, un bloc ``computed`` pour ce qui est
    calculé ; ``None`` pour un fichier illisible."""
    key = ("variables", path)
    if key not in cache:
        try:
            info = read_variable_file(path)
        except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
            cache[key] = None
            return None
        blocks = [Block("variable", name, path, start, end, literals=literals)
                  for name, start, end, literals in info["variables"]]
        blocks += [Block("computed", "get_variables", path, start, end)
                   for start, end in info["computed"]]
        cache[key] = RobotFile(path, blocks, [])
    return cache[key]  # type: ignore[no-any-return]
