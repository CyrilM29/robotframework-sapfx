"""Ce qu'une suite Robot EXÉCUTE, lu statiquement : ses tests, les keywords
qu'ils appellent de proche en proche à travers les ressources importées, et
les variables qu'ils lisent (backlog § 2.3, 2026-10-09). Logique pure
au-dessus du parseur de Robot Framework (``robot.api.parsing``), aucun run.

Elle sert l'analyse d'impact de changement : une ressource partagée nomme
un objet SAP dans UN keyword, et seules les suites qui appellent ce keyword
l'exécutent. Croiser par fichier faisait remonter toutes les suites qui
importent la ressource (21 suites sur le transport de vol d'A4H, pour un
seul keyword qui lit ``/DMO/CARRIER``).

Une ligne est rendue avec son bloc (test, keyword, variable, réglage) et
son statut : ``executed`` vaut ``True`` quand un test ou un réglage de suite
l'atteint, ``False`` quand rien ne l'atteint ou qu'elle n'est que de la
documentation (``[Documentation]``, étiquette, commentaire), et ``None``
quand rien ne l'atteint statiquement MAIS qu'un appel par nom calculé
(``Run Keyword    ${nom}``) reste non résolu dans ce que la suite exécute :
on ne peut alors ni l'affirmer ni l'exclure, et on le dit.

Les bibliothèques Python et les fichiers de variables ``.py`` importés
sont lus aussi, par :mod:`sapfx_common.python_call_graph` : une ligne d'une
bibliothèque est exécutée quand un test appelle un keyword qui l'atteint, une
affectation d'un fichier de variables est une variable comme une autre, et
une ligne d'une fonction ``get_variables`` reste incertaine (``None``).

Les imports se résolvent comme Robot les résout
(:mod:`sapfx_common.robot_imports`) : un chemin à variable par les variables
connues à ce moment-là, et un import qui ne se résout pas rend la suite
incertaine au lieu d'être ignoré. Les fichiers de variables se lisent en
Python, YAML et JSON (:mod:`sapfx_common.variable_files`).

Ce que la lecture statique ne voit pas, et dit (rendu dans ``dynamic``) : un
nom de keyword calculé dont la variable n'a pas de valeur littérale dans les
fichiers lus, un import dont le chemin ne se résout pas.
Un argument qui porte exactement le nom d'un keyword connu est tenu pour un
appel (les ``Run Keyword`` et les enveloppes qui reçoivent un nom de
keyword) : l'erreur possible va dans le sens de trop atteindre. Typed.
"""
from __future__ import annotations

import os
import re
from typing import Any, Iterable, Optional

from .python_call_graph import LibrarySource, PythonGraph
from .robot_imports import (SuiteImports, python_sources, resource_closure, suite_imports,
                            variable_file)
from .robot_model import (_EMBEDDED, _PURE_VAR, RUNNERS, Block, RobotFile, _declared,
                          _var_base, cached_robot_file, normalize, read_robot_file)

__all__ = ["RUNNERS", "Block", "RobotFile", "SuiteImports", "find_executing_tests",
           "normalize", "python_sources", "read_robot_file", "resource_closure",
           "suite_imports"]


class _Graph:
    def __init__(self, files: list[RobotFile]) -> None:
        self.blocks = [b for f in files for b in f.blocks]
        self.exact: dict[str, list[Block]] = {}
        self.embedded: list[tuple[re.Pattern[str], Block]] = []
        self.literals: dict[str, set[str]] = {}
        for block in self.blocks:
            if block.kind == "keyword" and _EMBEDDED.search(block.name):
                parts = [re.escape(normalize(p)) for p in _EMBEDDED.split(block.name)]
                self.embedded.append((re.compile("^%s$" % ".+?".join(parts)), block))
            elif block.kind == "keyword":
                self.exact.setdefault(normalize(block.name), []).append(block)
            elif block.kind == "variable":
                self.literals.setdefault(_declared(block.name), set()).update(block.literals)

    def resolve(self, name: str, strong: bool) -> list[Block]:
        pure = _PURE_VAR.match(name)
        if pure:                                # FOR ... IN @{LISTE}, ${STRATEGIE}
            values = self.literals.get(_var_base(pure.group(1))[0], set())
            return [t for v in values for t in self.resolve(v, strong)]
        key = normalize(name)
        if key in self.exact:
            return self.exact[key]
        while "." in key:                       # ressource.Keyword, Bibliothèque.Keyword
            key = key.split(".", 1)[1]
            if key in self.exact:
                return self.exact[key]
        if not strong:
            return []
        return [b for pattern, b in self.embedded if pattern.match(normalize(name))]

    def reach(self, roots: Iterable[Block]) -> tuple[set[int], list[tuple[str, int]]]:
        """Les keywords atteints (par ``id``) depuis des blocs, et les appels
        par nom calculé restés sans valeur littérale."""
        reached: set[int] = set()
        dynamic: list[tuple[str, int]] = []
        stack = list(roots)
        while stack:
            block = stack.pop()
            targets = [t for name, _line, strong in block.calls for t in self.resolve(name, strong)]
            for var, line in block.dynamic:
                if var in self.literals and self.literals[var]:
                    targets += [t for v in self.literals[var] for t in self.resolve(v, True)]
                elif block.locals.get(var) not in ("argument", "loop"):
                    dynamic.append((block.file, line))
            for target in targets:
                if id(target) not in reached:
                    reached.add(id(target))
                    stack.append(target)
        return reached, dynamic


def _anchor(files: dict[str, RobotFile], path: str, line: int) -> tuple[Optional[Block], bool]:
    parsed = files.get(os.path.normpath(os.path.abspath(path)))
    if parsed is None:
        return None, True
    for block in parsed.blocks:
        if block.start <= line <= block.end:
            return block, line in block.doc_lines
    return None, True


def find_executing_tests(suite: str, locations: Iterable[tuple[str, int]],
                         cache: Optional[dict[Any, Any]] = None,
                         python_path: Iterable[str] = (),
                         variables: Any = None) -> dict[str, Any]:
    """Pour des lignes de la suite, de ses ressources, de ses bibliothèques
    Python ou de ses fichiers de variables (``(fichier, ligne)``), les tests
    qui les EXÉCUTENT : ``{tests, locations, dynamic}``. Chaque ligne rendue
    porte son bloc (``test:Nom``, ``keyword:Nom``, ``variable:${X}``,
    ``setting:SuiteSetup``, ``python:Classe.methode``, ``outside``...),
    ``executed`` (``True``, ``False`` ou ``None``, voir le module) et les
    ``tests`` qui l'atteignent. ``dynamic`` : les appels par nom calculé non
    résolus dans ce que la suite exécute, les imports dont le chemin ne se
    résout pas et les variables calculées d'un fichier de variables
    (``fichier``, ``ligne``). ``python_path`` : où chercher une bibliothèque
    nommée par module, comme ``--pythonpath`` ; ``variables`` : celles qu'on
    passerait par ``robot -v`` (``{NOM: valeur}`` ou ``NOM:valeur``)."""
    cache = {} if cache is None else cache
    imports = suite_imports(suite, cache, variables, python_path)
    libraries, variable_files = python_sources(suite, cache, python_path, variables)
    files = {os.path.normpath(os.path.abspath(p)): f
             for p in [suite] + imports.resources
             if (f := cached_robot_file(p, cache)) is not None}
    for path in variable_files:
        if (parsed := variable_file(path, cache)) is not None:
            files[path] = parsed
    graph = _Graph(list(files.values()))
    suite_file = files.get(os.path.normpath(os.path.abspath(suite)))
    tests = [b for b in (suite_file.blocks if suite_file else []) if b.kind == "test"]
    settings = [b for b in (suite_file.blocks if suite_file else []) if b.kind == "setting"]
    common, dynamic = graph.reach(settings)
    dynamic += [(path, line) for path, line, _text in imports.unresolved]
    per_test: dict[int, set[int]] = {}
    for test in tests:
        reached, more = graph.reach([test])
        per_test[id(test)] = reached | common | {id(test)} | {id(s) for s in settings}
        dynamic += more
    executed_ids = set(common) | {id(b) for b in settings}
    for reached in per_test.values():
        executed_ids |= reached
    locations = [(os.path.normpath(os.path.abspath(p)), line) for p, line in locations]
    python = _PythonSide(libraries, graph, tests, per_test, executed_ids, cache) \
        if {p for p, _l in locations} & {f for s in libraries for f in s.files} else None
    by_id = {id(b): b for b in graph.blocks}
    out: list[dict[str, Any]] = []
    for path, line in locations:
        if python is not None and path in python.graph.modules:
            out.append(python.locate(path, line, bool(dynamic)))
            continue
        block, documentary = _anchor(files, path, line)
        entry: dict[str, Any] = {"file": path, "line": line, "tests": [],
                                 "block": "outside" if block is None
                                 else "%s:%s" % (block.kind, block.name)}
        if block is None or documentary:
            entry["executed"] = False
        elif block.kind == "computed":
            entry["executed"] = None
            dynamic.append((path, line))
        else:
            users = _users(graph, block)
            entry["tests"] = [t.name for t in tests if per_test[id(t)] & users]
            runs = bool(users & executed_ids) or block.kind == "setting"
            could = any(by_id[u].kind == "keyword" for u in users)
            entry["executed"] = True if runs else (None if dynamic and could else False)
        out.append(entry)
    return {"tests": [t.name for t in tests if any(t.name in e["tests"] for e in out
                                                   if e["executed"])],
            "locations": out,
            "dynamic": sorted({(f, ln) for f, ln in dynamic})}


class _PythonSide:
    """Les bibliothèques Python d'une suite : ce que chaque test en atteint,
    depuis les noms qu'appellent ses blocs Robot."""

    def __init__(self, libraries: list[LibrarySource], graph: _Graph, tests: list[Block],
                 per_test: dict[int, set[int]], executed: set[int],
                 cache: dict[Any, Any]) -> None:
        key = ("python", tuple(sorted(s.entry[0] for s in libraries)))
        if key not in cache:
            cache[key] = PythonGraph(libraries)
        self.graph: PythonGraph = cache[key]
        by_id = {id(b): b for b in graph.blocks}

        def reach(ids: set[int]) -> set[int]:
            return self.graph.reach(u for i in ids for name, _l, _s in by_id[i].calls
                                    for u in self.graph.keyword_units(name))
        self.tests = tests
        self.per_test = {id(t): reach(per_test[id(t)]) for t in tests}
        self.executed = reach(executed)

    def locate(self, path: str, line: int, dynamic: bool) -> dict[str, Any]:
        unit, documentary = self.graph.anchor(path, line)
        entry: dict[str, Any] = {"file": path, "line": line, "tests": [], "executed": False,
                                 "block": "outside" if unit is None else "python:%s%s"
                                 % (unit.owner + "." if unit.owner else "", unit.name)}
        if unit is not None and not documentary:
            entry["tests"] = [t.name for t in self.tests if id(unit) in self.per_test[id(t)]]
            entry["executed"] = True if id(unit) in self.executed else (
                None if dynamic and id(unit) in self.graph.live else False)
        return entry


def _users(graph: _Graph, block: Block) -> set[int]:
    """Les blocs dont l'exécution exécute ``block`` : lui-même, ou, pour une
    variable, chaque test et keyword qui la lit (de variable en variable)."""
    if block.kind != "variable":
        return {id(block)}
    naming = {_declared(block.name)}
    grew = True
    while grew:
        grew = False
        for other in graph.blocks:
            if other.kind == "variable" and other.refs & naming:
                names = {_declared(other.name)}
                if not names <= naming:
                    naming |= names
                    grew = True
    return {id(b) for b in graph.blocks
            if b.kind in ("test", "keyword", "setting") and b.refs & naming}
