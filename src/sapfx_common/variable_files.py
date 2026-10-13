"""Les variables qu'un fichier de variables déclare, avec leurs lignes, pour
les trois formats que Robot importe (backlog § 2.3, 2026-10-09) : Python
(lu par ``ast``, rien d'exécuté), YAML et JSON (lus sans dépendance : PyYAML
n'est pas une dépendance des bibliothèques).

Le rendu est le même pour les trois : ``variables``, une entrée par
variable de premier niveau (nom Robot, première et dernière ligne, valeurs
littérales), et ``computed``, les étendues où les variables sont CALCULÉES :
un fichier Python qui définit ``get_variables`` (Robot ne lit alors que ce
qu'elle rend, et ses noms ne se lisent pas) est calculé en entier. Une valeur
littérale sert à résoudre un chemin d'import ou un nom de keyword passé par
variable ; une ligne sert à rattacher une mention à sa variable.

YAML : seules les clés de premier niveau comptent (Robot n'en lit pas
d'autres), une clé à la colonne 0, sa valeur jusqu'à la clé suivante ; une
valeur en ligne, une liste en ligne ``[a, b]`` ou une liste en bloc
(``- a``) donnent ses littéraux, un bloc de texte, une ancre ou une balise
n'en donnent pas. JSON : l'objet de premier niveau, chaque clé retrouvée à
sa ligne. Typed.
"""
from __future__ import annotations

import ast
import json
import re
from typing import Any

from .python_call_graph import normalize, read_python_module

#: Une clé YAML de premier niveau : à la colonne 0, ni commentaire, ni
#: élément de liste, ni marqueur de document.
_YAML_KEY = re.compile(
    r"""^(?!#|-\s|---|\.\.\.)("[^"]+"|'[^']+'|[^\s:#][^:#]*?)\s*:(?:\s+(.*?))?\s*$""")
_YAML_ITEM = re.compile(r"^\s+-\s+(.*?)\s*$")
_JSON_COLON = re.compile(r"\s*:")


def read_variable_file(path: str) -> dict[str, Any]:
    """Les variables d'un fichier de variables ``.py``, ``.yaml``/``.yml``
    ou ``.json`` : ``{variables, computed}``, voir le module. Un autre format
    rend un résultat vide."""
    lower = path.lower()
    if lower.endswith(".py"):
        return _python(path)
    if lower.endswith((".yaml", ".yml")):
        return _yaml(path)
    if lower.endswith(".json"):
        return _json(path)
    return {"variables": [], "computed": []}


def _python(path: str) -> dict[str, Any]:
    module = read_python_module(path)
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    tree = ast.parse(source, filename=path)
    if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
           and normalize(n.name) == "getvariables" for n in tree.body):
        return {"variables": [], "computed": [(1, max(1, len(source.splitlines())))]}
    variables: list[tuple[str, int, int, list[str]]] = []
    for unit in module.units:
        if unit.kind != "constant" or unit.owner or unit.name.startswith("_"):
            continue
        prefix, name = "$", unit.name
        for marker, sign in (("LIST__", "@"), ("DICT__", "&")):
            if name.startswith(marker):
                prefix, name = sign, name[len(marker):]
        node = next(n for n in tree.body if getattr(n, "lineno", 0) == unit.start)
        value = getattr(node, "value", None)
        items = value.elts if isinstance(value, (ast.List, ast.Tuple)) else [value]
        literals = [i.value for i in items
                    if isinstance(i, ast.Constant) and isinstance(i.value, str)]
        variables.append(("%s{%s}" % (prefix, name), unit.start, unit.end, literals))
    return {"variables": variables, "computed": []}


def _unquote(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def _inline(value: str) -> str:
    """Une valeur YAML en ligne, sans son commentaire de fin."""
    value = value.strip()
    if value and value[0] in "\"'":
        closing = value.find(value[0], 1)
        return value[:closing + 1] if closing > 0 else value
    return value.split(" #", 1)[0].strip()


def _yaml(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8-sig") as handle:
        lines = handle.read().splitlines()
    starts = [(n, m) for n, line in enumerate(lines, 1) if (m := _YAML_KEY.match(line))]
    variables: list[tuple[str, int, int, list[str]]] = []
    for index, (start, match) in enumerate(starts):
        end = starts[index + 1][0] - 1 if index + 1 < len(starts) else len(lines)
        while end > start and (not lines[end - 1].strip() or lines[end - 1].strip() in
                               ("---", "...") or lines[end - 1].lstrip().startswith("#")):
            end -= 1
        value = _inline(match.group(2) or "")
        if value.startswith("[") and value.endswith("]"):
            literals = [_unquote(v) for v in value[1:-1].split(",") if v.strip()]
        elif value and value[0] not in "|>&*!{":
            literals = [_unquote(value)]
        elif value:
            literals = []
        else:
            literals = [_unquote(_inline(m.group(1))) for line in lines[start:end]
                        if (m := _YAML_ITEM.match(line)) and m.group(1)[:1] not in "[{&*!|>"]
        variables.append(("${%s}" % _unquote(match.group(1)), start, end, literals))
    return {"variables": variables, "computed": []}


def _json_keys(text: str) -> tuple[list[tuple[str, int]], int]:
    """Les clés de l'objet de premier niveau avec leur ligne, et la ligne de
    l'accolade qui le ferme."""
    keys: list[tuple[str, int]] = []
    depth, line, closing, index = 0, 1, 1, 0
    while index < len(text):
        char = text[index]
        if char == "\n":
            line += 1
        elif char == '"':
            end = index + 1
            while end < len(text) and text[end] != '"':
                end += 2 if text[end] == "\\" else 1
            if depth == 1 and _JSON_COLON.match(text, end + 1):
                keys.append((json.loads(text[index:end + 1]), line))
            index = end
        elif char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
            closing = line if depth == 0 else closing
        index += 1
    return keys, closing


def _json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8-sig") as handle:
        text = handle.read()
    data = json.loads(text)
    if not isinstance(data, dict):
        return {"variables": [], "computed": []}
    keys, closing = _json_keys(text)
    last = closing - 1 if text.splitlines()[closing - 1].strip() == "}" else closing
    variables: list[tuple[str, int, int, list[str]]] = []
    for index, (key, start) in enumerate(keys):
        end = max(start, keys[index + 1][1] - 1 if index + 1 < len(keys) else last)
        value = data.get(key)
        items = value if isinstance(value, list) else [value]
        variables.append(("${%s}" % key, start, end, [v for v in items if isinstance(v, str)]))
    return {"variables": variables, "computed": []}
