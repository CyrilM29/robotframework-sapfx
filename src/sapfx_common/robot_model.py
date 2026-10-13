"""Un fichier Robot lu par le parseur de Robot Framework
(``robot.api.parsing``), aucun run (backlog § 2.3, 2026-10-09) : ses blocs
(tests, keywords, variables, réglages de suite qui appellent), les appels de
chaque bloc, ses variables lues et locales, ses lignes de documentation, et
ses imports avec leur ligne. Le socle de :mod:`sapfx_common.robot_imports`
et de :mod:`sapfx_common.robot_call_graph`. Typed.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from robot.api.parsing import ModelVisitor, get_model, get_resource_model

_VAR_REF = re.compile(r"[$@&%]\{([^{}]+)\}")
_BARE_REF = re.compile(r"(?<![\w{])\$([A-Za-z_]\w*)")
_PURE_VAR = re.compile(r"^[$@&]\{([^{}]+)\}$")
_EMBEDDED = re.compile(r"\$\{[^}]+\}")

#: Instructions qui ne s'exécutent pas : leurs lignes nomment sans agir.
_DOCUMENTARY = frozenset({"Documentation", "Tags", "Comment", "EmptyLine", "Metadata",
                          "TestTags", "DefaultTags", "KeywordTags", "SectionHeader"})

#: Réglages de suite qui APPELLENT un keyword (pour tous les tests).
_SUITE_CALLS = frozenset({"SuiteSetup", "SuiteTeardown", "TestSetup", "TestTeardown",
                          "TestTemplate"})

#: Keywords de BuiltIn qui exécutent un keyword passé en argument, avec la
#: position de cet argument (``Run Keywords`` : tous).
RUNNERS = {
    "runkeyword": 0, "runkeywords": 0, "runkeywordandcontinueonfailure": 0,
    "runkeywordandexpecterror": 1, "runkeywordandignoreerror": 0, "runkeywordandreturn": 0,
    "runkeywordandreturnif": 1, "runkeywordandreturnstatus": 0,
    "runkeywordandwarnonfailure": 0, "runkeywordif": 1, "runkeywordunless": 1,
    "runkeywordifalltestspassed": 0, "runkeywordifanytestsfailed": 0,
    "runkeywordiftestfailed": 0, "runkeywordiftestpassed": 0,
    "runkeywordiftimeoutoccurred": 0, "waituntilkeywordsucceeds": 2, "repeatkeyword": 1,
}


def normalize(name: str) -> str:
    """Un nom de keyword ou de variable comme Robot le compare : sans casse,
    sans espace ni souligné."""
    return re.sub(r"[\s_]", "", name).lower()


def _var_base(inner: str) -> list[str]:
    """Les noms qu'une référence ``${a.b}[0]`` peut viser (nom entier, puis
    la base d'une syntaxe étendue)."""
    full = normalize(inner.split("[")[0].split("=")[0])
    return [full, full.split(".")[0]] if "." in full else [full]


def _declared(token: str) -> str:
    """Le nom normalisé d'une variable DÉCLARÉE (``${r}=``, ``${t}=défaut``,
    ``@{L}``), vide si le jeton n'en porte pas."""
    match = _VAR_REF.search(token)
    return _var_base(match.group(1))[0] if match else ""


@dataclass
class Block:
    """Un test, un keyword, une variable ou un réglage de suite qui appelle."""
    kind: str
    name: str
    file: str
    start: int
    end: int
    calls: list[tuple[str, int, bool]] = field(default_factory=list)
    dynamic: list[tuple[str, int]] = field(default_factory=list)
    locals: dict[str, str] = field(default_factory=dict)
    refs: set[str] = field(default_factory=set)
    literals: list[str] = field(default_factory=list)
    doc_lines: set[int] = field(default_factory=set)


@dataclass
class RobotFile:
    path: str
    blocks: list[Block]
    imports: list[tuple[str, int]]
    libraries: list[tuple[str, int]] = field(default_factory=list)
    variable_files: list[tuple[str, int]] = field(default_factory=list)


class _Collector(ModelVisitor):
    def __init__(self, path: str, lines: list[str]) -> None:
        self.path, self.lines = path, lines
        self.blocks: list[Block] = []
        self.imports: list[tuple[str, int]] = []
        self.libraries: list[tuple[str, int]] = []
        self.variable_files: list[tuple[str, int]] = []
        self.current: Optional[Block] = None

    # --- blocs ------------------------------------------------------------------------
    def _open(self, kind: str, node: Any, name: str) -> Block:
        block = Block(kind, name, self.path, node.lineno, node.end_lineno)
        self.blocks.append(block)
        return block

    def _within(self, block: Block, node: Any) -> None:
        previous, self.current = self.current, block
        self.generic_visit(node)
        self.current = previous

    def visit_TestCase(self, node: Any) -> None:   # noqa: N802 (API du visiteur)
        self._within(self._open("test", node, node.name), node)

    def visit_Keyword(self, node: Any) -> None:    # noqa: N802
        self._within(self._open("keyword", node, node.name), node)

    def visit_Variable(self, node: Any) -> None:   # noqa: N802
        if not _declared(node.name or ""):
            return
        block = self._open("variable", node, node.name)
        values = [str(v) for v in node.value]
        for value in values:
            block.refs.update(_refs(value))
        block.literals = [v for v in values if "${" not in v and "@{" not in v]

    # --- instructions -----------------------------------------------------------------
    def generic_visit(self, node: Any) -> None:
        kind = type(node).__name__
        if kind in _DOCUMENTARY and hasattr(node, "lineno"):
            if self.current is not None:
                self.current.doc_lines.update(
                    range(node.lineno, (node.end_lineno or node.lineno) + 1))
        elif kind == "ResourceImport" and node.name:
            self.imports.append((node.name, node.lineno))
        elif kind == "LibraryImport" and node.name:
            self.libraries.append((node.name, node.lineno))
        elif kind == "VariablesImport" and node.name:
            self.variable_files.append((node.name, node.lineno))
        elif kind in _SUITE_CALLS and self.current is None:
            block = self._open("setting", node, kind)
            self._call(block, node.value if kind == "TestTemplate" else node.name,
                       () if kind == "TestTemplate" else node.args, node.lineno)
        elif self.current is not None:
            self._statement(self.current, kind, node)
        super().generic_visit(node)

    def _statement(self, block: Block, kind: str, node: Any) -> None:
        if kind == "KeywordCall":
            for name in node.assign:
                block.locals.setdefault(_declared(name), "assigned")
            self._call(block, node.keyword, node.args, node.lineno)
        elif kind in ("Setup", "Teardown"):
            self._call(block, node.name, node.args, node.lineno)
        elif kind == "Template":
            self._call(block, node.value, (), node.lineno)
        elif kind == "TemplateArguments":
            block.calls.extend((str(a), node.lineno, False) for a in node.args)
        elif kind == "ForHeader":
            for name in node.assign:
                block.locals[_declared(name)] = "loop"
            block.calls.extend((str(v), node.lineno, False) for v in node.values)
        elif kind == "Arguments":
            for value in node.values:
                block.locals[_declared(str(value))] = "argument"
        elif kind == "Var" and node.name:
            block.locals.setdefault(_declared(node.name), "assigned")

    def _call(self, block: Block, name: Optional[str], args: Iterable[Any], line: int) -> None:
        if not name or name.upper() == "NONE":
            return
        block.calls.append((name, line, True))
        args = [str(a) for a in args]
        position = RUNNERS.get(normalize(name).removeprefix("builtin."))
        for index, arg in enumerate(args):
            pure = _PURE_VAR.match(arg)
            # Seule la position du NOM est un appel calculé : ce qui suit sont
            # ses arguments, sauf après AND (Run Keywords) et ELSE.
            named = position is not None and (
                index == position or (index > position and args[index - 1].upper() in
                                      ("AND", "ELSE")))
            if named and pure:
                block.dynamic.append((_var_base(pure.group(1))[0], line))
            block.calls.append((arg, line, position is not None and index >= position))


def _refs(text: str) -> set[str]:
    found: set[str] = set()
    for inner in _VAR_REF.findall(text):
        found.update(_var_base(inner))
    found.update(normalize(name) for name in _BARE_REF.findall(text))
    return found


def read_robot_file(path: str) -> RobotFile:
    """Les blocs d'un fichier Robot (suite ou ressource), ses imports
    (ressources, bibliothèques, fichiers de variables, avec leur ligne) et ses
    lignes de documentation, lus par le parseur de Robot."""
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    model = (get_resource_model if path.endswith(".resource") else get_model)(path)
    collector = _Collector(path, lines)
    collector.visit(model)
    for block in collector.blocks:
        if block.kind in ("test", "keyword", "setting"):
            for number in range(block.start, block.end + 1):
                if number not in block.doc_lines and number <= len(lines):
                    block.refs.update(_refs(lines[number - 1]))
    return RobotFile(path, collector.blocks, collector.imports, collector.libraries,
                     collector.variable_files)


def cached_robot_file(path: str, cache: dict[Any, Any]) -> Optional[RobotFile]:
    """``read_robot_file`` une fois par analyse ; ``None`` pour un fichier
    illisible."""
    key = os.path.normpath(os.path.abspath(path))
    if key not in cache:
        try:
            cache[key] = read_robot_file(path)
        except (OSError, UnicodeDecodeError):
            return None
    return cache[key]  # type: ignore[no-any-return]
