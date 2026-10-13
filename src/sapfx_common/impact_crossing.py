"""Le croisement d'un impact de changement avec les suites Robot, et son
rapport (backlog § 2.3, 2026-10-09) : quelles suites NOMMENT un objet
impacté, et lesquelles l'EXÉCUTENT.

Une suite nomme un objet dans son fichier, dans une ressource qu'elle
importe, ou dans une bibliothèque Python ou un fichier de variables ``.py``
qu'elle importe ; ce qu'elle en exécute se lit statiquement, de keyword en
keyword (:mod:`sapfx_common.robot_call_graph`) et de fonction en fonction
(:mod:`sapfx_common.python_call_graph`). Une mention de bibliothèque que la
suite n'exécute pas parle de la bibliothèque, pas de la suite : elle n'est
pas rendue. Nommer n'est pas exécuter, et une exécution lue statiquement
n'est pas un run : le résultat dit quoi REJOUER pour en juger.

Les deux fonctions publiques s'atteignent comme keywords par
``Library    sapfx_common.change_impact``, qui les réexporte. Typed.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from .impact_decisions import render_decisions
from .release_facts import suite_traceability
from .robot_args import as_name_list
from .robot_call_graph import find_executing_tests, python_sources, suite_imports

__all__ = ["suites_impacted_by_change", "render_change_impact_report"]


def _clean(value: Any) -> str:
    return str(value or "").strip()


Patterns = tuple[dict[str, str], Optional["re.Pattern[str]"]]


def _mentions(path: str, patterns: Patterns,
              cache: Optional[dict[Any, Any]] = None) -> list[dict[str, Any]]:
    """Les mentions d'un nom de l'impact dans un fichier, une par nom et par
    ligne ; le fichier n'est lu qu'une fois par analyse (``cache``)."""
    kinds, regex = patterns
    key = ("mentions", os.path.normpath(os.path.abspath(path)))
    if cache is None or key not in cache:
        hits: list[dict[str, Any]] = []
        try:
            with open(path, encoding="utf-8") as handle:
                lines = handle.read().splitlines()
        except (OSError, UnicodeDecodeError):
            lines = []
        for number, line in enumerate(lines if regex is not None else [], 1):
            found = (m.group(1) for m in regex.finditer(line)
                     if not _NAMESPACE_BEFORE.search(line[:m.start()])) if regex else ()
            for name in dict.fromkeys(found):
                hits.append({"name": name, "kind": kinds[name], "file": path, "line": number})
        if cache is None:
            return hits
        cache[key] = hits
    return [dict(hit) for hit in cache[key]]


def _patterns(impact: Mapping[str, Any]) -> Patterns:
    """Les noms de l'impact et leur famille, et UNE expression qui les
    trouve tous, délimitée pour qu'un nom n'en touche pas un plus long."""
    objects = impact.get("object_names")
    if objects is None:                        # impact sans les deux familles
        objects = impact.get("names") or []
    kinds: dict[str, str] = {}
    for kind, names in (("object", objects), ("user", impact.get("user_names") or [])):
        for name in names:
            text = _clean(name)
            if len(text) >= 3:
                kinds.setdefault(text, kind)
    if not kinds:
        return kinds, None
    choice = "|".join(re.escape(n) for n in sorted(kinds, key=len, reverse=True))
    return kinds, re.compile(r"(?<![A-Za-z0-9_])(%s)(?![A-Za-z0-9_])" % choice)


#: Un espace de noms SAP juste avant une mention : ``CARRIER`` lu dans
#: ``/DMO/CARRIER`` n'est pas l'objet ``CARRIER``. Un segment d'URL en
#: minuscules (``/sap/SEPMRA_PROD_MAN``, ``srvd/dmo/...``) n'en est pas un.
_NAMESPACE_BEFORE = re.compile(r"(?:^|[^A-Za-z0-9_])/[A-Z0-9_]+/$")


def _display(path: str, base: str, outside: Optional[str] = None) -> str:
    """Un chemin RELATIF à ``base`` quand il y est, sinon ``outside`` (le
    chemin d'un module dans sa bibliothèque) ou le seul nom du fichier :
    jamais un chemin de poste dans un rapport ou un artefact."""
    full = os.path.abspath(path)
    try:
        relative = os.path.relpath(full, os.path.abspath(base))
    except ValueError:                        # autre lecteur sous Windows
        relative = ".."
    shown = (outside or os.path.basename(full)) if relative.startswith("..") else relative
    return shown.replace("\\", "/")


def suites_impacted_by_change(impact: Mapping[str, Any], root: str = ".",
                              exclude: Any = None, relative_to: Optional[str] = None,
                              python_path: Any = None,
                              variables: Any = None) -> list[dict[str, Any]]:
    """Les suites Robot sous ``root`` qui NOMMENT un nom de l'impact, et ce
    qu'elles en EXÉCUTENT : une entrée par suite, ``{suite, reach, strength,
    tests, spec, spec_status, direct, via_resource, via_library, dynamic}``.

    Chaque mention porte son nom, sa famille (``object`` : un objet
    transporté ; ``user`` : un programme ou une transaction qui l'utilise),
    son fichier, sa ligne, son bloc (``test:Nom``, ``keyword:Nom``,
    ``variable:${X}``, ``python:Classe.methode``...) et ``executed`` ;
    ``direct`` rend les mentions du fichier de la suite, ``via_resource``
    celles de ses ressources, ``via_library`` celles des bibliothèques Python
    et des fichiers de variables ``.py`` qu'elle importe (une bibliothèque
    nommée par module se cherche dans ``python_path``, comme
    ``--pythonpath``, puis là où Python la trouve, sans l'importer). Un
    chemin d'import à variable se résout comme Robot le résout, avec
    ``variables`` comme ``robot -v`` (``{NOM: valeur}`` ou ``NOM:valeur``) ;
    un import qui ne se résout pas rend la suite ``dynamic`` (listé dans
    ``dynamic``), et une suite qui ne nomme rien mais a un import non résolu
    est rendue ``dynamic`` de force ``unknown`` : on ne peut pas l'exclure.
    ``reach`` dit la force de la preuve : ``called`` (un test ou un réglage
    de suite exécute la mention, de keyword en keyword), ``dynamic`` (rien ne
    l'exécute statiquement, mais la suite appelle un keyword par un nom
    calculé non résolu, listé dans ``dynamic`` : on ne peut pas l'exclure) ou
    ``named`` (la suite ne fait que la nommer : documentation, ressource
    importée dont aucun appel n'atteint le keyword). ``strength`` vaut
    ``object`` dès qu'une mention qui porte ``reach`` nomme un objet
    transporté, ``user`` sinon ; ``tests`` sont les tests qui l'exécutent ;
    ``spec`` et ``spec_status`` le plan de la suite (marqueur ``Spec:``,
    statut de ``release_facts.suite_traceability``). Triées par ``reach``,
    puis ``strength``, puis les suites qui nomment l'objet elles-mêmes.

    La correspondance est exacte et sensible à la casse (un nom SAP s'écrit
    en majuscules), délimitée pour qu'un nom n'en touche pas un plus long.
    ``exclude`` : chemins (ou préfixes) de suites à ignorer. Les chemins
    rendus sont relatifs à ``relative_to`` (défaut : le dossier courant), pour
    qu'un rapport ne porte aucun chemin de poste. Nommer n'est pas exécuter,
    et une exécution lue statiquement n'est pas un run : la liste dit quoi
    REJOUER pour en juger.

    Exemple :
    | ${suites}=    `Suites Impacted By Change`    ${impact}    root=tests/robot
    | Should Be Equal    ${suites}[0][strength]    object
    """
    patterns = _patterns(impact)
    folders = as_name_list(python_path, "python_path") if python_path else []
    base = relative_to or os.getcwd()
    skip = [os.path.normpath(os.path.abspath(e)) for e in (exclude or [])]
    cache: dict[str, Any] = {}
    found: list[dict[str, Any]] = []
    for folder, _dirs, files in os.walk(root):
        for file in sorted(files):
            if not file.endswith(".robot"):
                continue
            suite = os.path.normpath(os.path.join(folder, file))
            if any(os.path.abspath(suite).startswith(s) for s in skip):
                continue
            entry = _suite_entry(suite, patterns, cache, base, folders, variables)
            if entry is not None:
                found.append(entry)
    return sorted(found, key=lambda s: (_REACH.index(s["reach"]), s["strength"] != "object",
                                        not any(h["executed"] is not False
                                                for h in s["direct"]), s["suite"]))


_REACH = ("called", "dynamic", "named")


def _carries(hit: Mapping[str, Any], level: str) -> bool:
    """Une mention porte-t-elle le niveau de preuve de sa suite ?"""
    if level == "named":
        return True
    return hit.get("executed", True) is (True if level == "called" else None)


def _suite_entry(suite: str, patterns: Patterns, cache: dict[Any, Any], base: str,
                 folders: Sequence[str], variables: Any) -> Optional[dict[str, Any]]:
    imports = suite_imports(suite, cache, variables, folders)
    direct = _mentions(suite, patterns, cache)
    via = [hit for resource in imports.resources
           for hit in _mentions(resource, patterns, cache)]
    libraries, variable_files = python_sources(suite, cache, folders, variables)
    modules = {f: d.replace(".", "/") + ("/__init__.py" if f.endswith("__init__.py") else ".py")
               for source in libraries for f, d in source.files.items()}
    library = [hit for path in sorted(set(modules) | set(variable_files))
               for hit in _mentions(path, patterns, cache)]
    unresolved = {(f, line): text for f, line, text in imports.unresolved}

    def listed(points: Any) -> list[str]:
        return ["%s:%s%s" % (_display(f, base, modules.get(f)), line,
                             " %s" % unresolved[(f, line)] if (f, line) in unresolved else "")
                for f, line in points]
    trace = suite_traceability(Path(suite))
    hits = direct + via + library
    if not hits:
        return None if not unresolved else {
            "suite": _display(suite, base), "reach": "dynamic", "strength": "unknown",
            "tests": [], "spec": trace["spec"], "spec_status": trace["status"], "direct": [],
            "via_resource": [], "via_library": [], "dynamic": listed(sorted(unresolved))}
    try:
        reach = find_executing_tests(suite, [(h["file"], h["line"]) for h in hits], cache,
                                     folders, variables)
    except Exception:                         # fichier que le parseur refuse : incertain
        reach = {"locations": [{"executed": None, "block": "unparsed", "tests": []}
                               for _ in hits], "dynamic": []}
    for hit, where in zip(hits, reach["locations"], strict=True):
        hit.update(block=where["block"], executed=where["executed"], tests=where["tests"])
    # Une bibliothèque que la suite n'exécute pas parle d'elle, pas de la suite.
    library = [h for h in library if h["executed"] is not False]
    hits = direct + via + library
    if not hits:
        return None
    level = ("called" if any(h["executed"] is True for h in hits)
             else "dynamic" if any(h["executed"] is None for h in hits) else "named")
    basis = [h for h in hits if _carries(h, level)]
    strength = "object" if any(h["kind"] == "object" for h in basis) else "user"
    tests = sorted({t for h in basis if h["kind"] == strength for t in h["tests"]})
    return {"suite": _display(suite, base), "reach": level, "strength": strength,
            "tests": tests, "spec": trace["spec"], "spec_status": trace["status"],
            "direct": _portable(direct, base), "via_resource": _portable(via, base),
            "via_library": _portable(library, base, modules),
            "dynamic": listed(reach["dynamic"]) if level == "dynamic" else []}


def _portable(hits: list[dict[str, Any]], base: str,
              outside: Optional[Mapping[str, str]] = None) -> list[dict[str, Any]]:
    return [{**{k: v for k, v in hit.items() if k != "tests"},
             "file": _display(str(hit["file"]), base, (outside or {}).get(hit["file"]))}
            for hit in hits]


def _proof(suite: Mapping[str, Any], strength: str) -> str:
    """Les trois premières mentions qui portent la preuve de la suite, avec
    leur bloc (le test, le keyword appelé, la variable lue)."""
    level = suite.get("reach", "called")
    hits = [h for key in ("direct", "via_resource", "via_library")
            for h in suite.get(key) or []
            if h.get("kind", strength) == strength and _carries(h, level)]
    return "; ".join("%s (%s:%s%s)" % (h["name"], h["file"], h["line"],
                                       ", %s" % h["block"] if h.get("block") else "")
                     for h in hits[:3])


def render_change_impact_report(impact: Mapping[str, Any],
                                suites: Sequence[Mapping[str, Any]] = (),
                                decisions: Optional[Mapping[str, Any]] = None) -> str:
    """Rapport Markdown : le transport, ses objets, ce qui les utilise, les
    suites à rejouer avec leurs preuves et leurs tests (celles qui exécutent
    un objet transporté, puis celles qui n'exécutent qu'un utilisateur, puis
    celles dont l'atteinte reste incertaine), celles qui ne font que nommer,
    les plans concernés, et les LIMITES (plafond atteint, objets non
    analysés, nature du croisement). ``decisions`` : le résumé rendu par
    `Apply Change Impact Decisions` ; chaque suite décidée dit alors sa
    décision, et une section « Décisions humaines » liste ce qui a été
    rejoué, écarté (avec la raison et l'auteur) et ce qui reste à décider.

    Exemple :
    | ${report}=    `Render Change Impact Report`    ${impact}    ${suites}
    | Should Contain    ${report}    TTZCU
    """
    req = impact.get("request") or {}
    lines = ["# Impact du transport %s" % req.get("request", "?"), "",
             "- Texte : %s" % (req.get("text") or "-"),
             "- Propriétaire : %s, date %s, fonction %s"
             % (req.get("owner") or "-", req.get("date") or "-", req.get("function") or "-"),
             "- Objets principaux : %d, programmes utilisateurs : %d, transactions : %d"
             % (len(impact.get("usages") or []), len(impact.get("programs") or []),
                len(impact.get("transactions") or [])), ""]
    if impact.get("truncated"):
        lines += ["**Plafond atteint (utilisations incomplètes)** : %s"
                  % ", ".join(impact["truncated"]), ""]
    if impact.get("skipped"):
        lines += ["Non analysés : %s" % ", ".join(
            "%s %s" % (s.get("type"), s.get("name")) for s in impact["skipped"]), ""]
    groups = (("called", "object", "Suites qui exécutent un objet transporté"),
              ("called", "user", "Suites qui n'exécutent qu'un utilisateur (programme, "
                                 "transaction)"),
              ("dynamic", None, "Atteinte incertaine : un keyword appelé par un nom calculé"),
              ("named", None, "Suites qui nomment sans exécuter (pour information)"))
    for level, strength, title in groups:
        group = [s for s in suites if s.get("reach", "called") == level
                 and strength in (None, s.get("strength", "object"))]
        lines += ["## %s" % title, ""]
        if not group:
            lines.append("Aucune.")
        for suite in group:
            proof = _proof(suite, suite.get("strength", "object"))
            line = "- `%s`%s" % (suite["suite"], " : " + proof if proof else "")
            if suite.get("tests"):
                line += " ; tests : %s" % ", ".join(suite["tests"])
            if suite.get("dynamic"):
                line += " ; non résolus : %s" % ", ".join(suite["dynamic"][:3])
            if decisions is not None:
                d = suite.get("decision")
                line += (" ; décision : %s par %s" % ("rejouer" if d["decision"] == "replay"
                                                      else "écartée", d["by"])
                         if d else " ; non décidée")
            lines.append(line)
        lines.append("")
    lines += render_decisions(decisions, suites)
    lines += _plans_section(suites)
    lines += ["Aucune suite listée ne prouve l'absence d'impact : le croisement est "
              "textuel et l'exécution lue statiquement, de keyword en keyword (un nom "
              "calculé ou un import qui ne se résout pas est dit, jamais tenu pour "
              "non appelé). "
              "Limites : %s." % impact.get("limits", "")]
    return "\n".join(lines) + "\n"


def _plans_section(suites: Sequence[Mapping[str, Any]]) -> list[str]:
    """Les plans ``specs/`` des suites à rejouer, avec leur statut, et les
    suites sans plan."""
    plans: dict[str, list[str]] = {}
    untraced: list[str] = []
    for suite in suites:
        if suite.get("reach", "called") == "named":
            continue
        if suite.get("spec"):
            key = "%s (%s)" % (suite["spec"], suite.get("spec_status") or "?")
            plans.setdefault(key, []).append(suite["suite"])
        else:
            untraced.append(suite["suite"])
    lines = ["## Plans concernés", ""]
    lines += ["- `%s` : %s" % (plan, ", ".join("`%s`" % s for s in names))
              for plan, names in sorted(plans.items())] or ["Aucun."]
    if untraced:
        lines.append("- Sans plan : %s" % ", ".join("`%s`" % s for s in untraced))
    return lines + [""]
