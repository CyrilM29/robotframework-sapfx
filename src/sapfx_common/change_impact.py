"""Analyse d'impact d'un changement SAP, logique pure (backlog § 2.3,
2026-10-09) : d'un transport à ses objets, de ses objets à leurs
utilisateurs (UN niveau de références croisées), puis aux suites de test qui
les nomment.

**Un MVP annoncé comme tel, jamais un graphe d'appel complet.** Ce que la
chaîne voit : les objets que le transport porte (``E071``), leur objet
principal (une méthode appartient à sa classe, un include à son programme),
les programmes qui les utilisent d'après les tables de références du système
(``D010TAB`` pour les tables, ``WBCROSSGT`` pour les classes et
interfaces, ``CROSS`` pour les modules fonction), et les transactions de
ces programmes (``TSTC``). Ce qu'elle ne voit pas, et dit : l'accès
dynamique (SQL dynamique, appel par nom calculé), plus d'un niveau
d'utilisation, les transactions OO et à paramètres. Un plafond de lignes
atteint est toujours annoncé (``truncated``), jamais tu.

Le croisement avec les suites vit dans :mod:`sapfx_common.impact_crossing`
(réexporté ici) : une suite NOMME un objet impacté dans son fichier, ses
ressources, ses bibliothèques Python ou ses fichiers de variables, et
l'EXÉCUTE quand un test l'atteint, de keyword en keyword. Chaque
correspondance porte son fichier et sa ligne, pour qu'un humain juge.

Les fonctions publiques s'atteignent aussi comme bibliothèque Robot
(``Library    sapfx_common.change_impact``). Typed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from typing import Any, Iterable, Mapping, Optional, Sequence

from .impact_crossing import render_change_impact_report, suites_impacted_by_change
from .impact_decisions import apply_decisions as apply_change_impact_decisions
from .impact_decisions import decision_template as get_change_impact_decision_template
from .impact_decisions import read_decisions, still_to_replay

#: Ce que ``Library    sapfx_common.change_impact`` expose comme keywords ;
#: les règles de nommage restent des fonctions du mixin RFC.
__all__ = [
    "build_change_impact", "change_impact_hash", "suites_impacted_by_change",
    "render_change_impact_report", "get_change_impact_decision_template",
    "apply_change_impact_decisions",
]

#: Types d'objets principaux (``R3TR``) dont un objet partiel (``LIMU``) relève.
LIMU_MAIN = {
    "METH": "CLAS", "CLSD": "CLAS", "CPUB": "CLAS", "CPRI": "CLAS", "CPRO": "CLAS",
    "CINC": "CLAS", "CPAK": "CLAS", "INTD": "INTF",
    "FUNC": "FUNC", "REPS": "PROG", "REPT": "PROG", "DYNP": "PROG", "CUAD": "PROG",
    "TABD": "TABL", "TABT": "TABL", "INDX": "TABL", "VIED": "VIEW", "VIET": "VIEW",
    "DTED": "DTEL", "DOMD": "DOMA", "WAPP": "WAPA", "SOTU": None, "DOCU": None,
    "ADIR": None, "MESS": None, "TTYD": "TTYP",
}

#: Ce qui se cherche dans quelle table de références (un niveau).
USAGE = {
    "TABL": "tables", "TABU": "tables", "VIEW": "tables", "VDAT": "tables",
    "TDAT": "tables", "DDLS": "cds", "DDLX": "cds", "CLAS": "types", "INTF": "types",
    "TTYP": "types", "BDEF": "types", "FUNC": "functions", "FUGR": "function_group",
    "PROG": "programs", "TRAN": "transactions", "DTEL": "data_element",
    "DOMA": "domain", "ENQU": "lock_object", "SRVD": "service_definition",
    "SRVB": "service_binding",
}

#: Objets Gateway nommés « NOM<blancs>VERSION » dans ``E071``.
VERSIONED = frozenset({"IWSV", "IWMO", "IWVB"})

#: Ce qu'une suite peut écrire dans une URL OData (voir `service_url_names`).
SERVICES = frozenset({"IWSV", "SRVB", "SRVD"})

#: Objets transportés qui ne désignent rien d'exécutable : rendus, pas analysés.
NOT_ANALYZED = frozenset({"CORR", "NOTE", "CINS", "DEVC", "SUSH", "SUSC", "SUSO",
                          "WDCC", "WDCA", "SMIM", "DOCV", "DOCT", "SOTR", "SOTS",
                          "MSAG", "SPRX", "IWPR"})

CLASS_NAME_WIDTH = 30


def _clean(value: Any) -> str:
    return str(value or "").strip()


#: Suffixes des includes d'un pool de classe ou d'interface, après le nom
#: complété à 30 caractères.
_POOL_SUFFIX = re.compile(r"^(CP|CU|CO|CI|CT|CS|CCIMP|CCDEF|CCMAC|CCAU|CM[0-9A-Z]{3}|IP|IU)$")


def class_of_include(include: str) -> Optional[str]:
    """La classe (ou l'interface) d'un include de pool (``CL_X=====CCIMP`` ->
    ``CL_X``), ``None`` si le nom n'en a pas la forme : le nom de classe est
    complété à 30 caractères par ``=``, puis vient un suffixe connu."""
    name = _clean(include)
    if len(name) <= CLASS_NAME_WIDTH or not _POOL_SUFFIX.match(name[CLASS_NAME_WIDTH:]):
        return None
    return name[:CLASS_NAME_WIDTH].rstrip("=") or None


def include_master(include: str) -> Optional[str]:
    """Le programme principal d'un include qui le dit par son NOM : pool de
    classe (``CL_X====CCIMP`` -> ``CL_X====CP``). Pour les autres, ``None`` :
    l'appelant lit ``D010INC``, la seule source sûre."""
    name = _clean(include)
    if class_of_include(name) is None:
        return None
    pool = "IP" if name[CLASS_NAME_WIDTH:] in ("IP", "IU") else "CP"
    return name[:CLASS_NAME_WIDTH] + pool


def function_group_master(group: str) -> str:
    """Le programme d'un groupe de fonctions (``SZON`` -> ``SAPLSZON``,
    ``/NS/GRP`` -> ``/NS/SAPLGRP``)."""
    name = _clean(group).upper()
    match = re.match(r"^(/[^/]+/)(.+)$", name)
    return "%sSAPL%s" % match.groups() if match else "SAPL%s" % name


def main_object(pgmid: str, object_type: str, obj_name: str) -> Optional[dict[str, str]]:
    """L'objet principal d'une ligne de transport (``E071``), ou ``None`` pour
    ce qui ne désigne rien d'analysable (libération, note, documentation)."""
    pid, kind, name = _clean(pgmid).upper(), _clean(object_type).upper(), str(obj_name or "")
    if pid == "CORR" or kind in NOT_ANALYZED:
        return None
    if pid == "R3TR":
        if kind in VERSIONED:                  # « NOM<blancs>0001 » : nom et version
            parts = name.split()
            return {"type": kind, "name": parts[0] if parts else "",
                    "version": parts[1] if len(parts) > 1 else ""}
        return {"type": kind, "name": name.strip()}
    if pid != "LIMU" or kind not in LIMU_MAIN or LIMU_MAIN[kind] is None:
        return None
    main = str(LIMU_MAIN[kind])
    if kind == "METH":
        return {"type": main, "name": name[:CLASS_NAME_WIDTH].strip(),
                "part": name[CLASS_NAME_WIDTH:].strip()}
    if kind == "CINC":
        klass = class_of_include(name)
        return {"type": main, "name": klass or name.strip(), "part": name.strip()}
    if kind == "DYNP":                         # programme sur 40 + numéro d'écran
        return {"type": main, "name": name[:40].strip(), "part": name[40:].strip()}
    if kind == "WAPP":
        return {"type": main, "name": name[:CLASS_NAME_WIDTH].strip(),
                "part": name[CLASS_NAME_WIDTH:].strip()}
    return {"type": main, "name": name.strip()}


def usage_strategy(object_type: str) -> Optional[str]:
    """La famille de références qui dit qui utilise un objet de ce type, ou
    ``None`` si le MVP n'en lit aucune (l'objet reste NOMMÉ dans l'impact)."""
    return USAGE.get(_clean(object_type).upper())


def service_url_names(name: str) -> list[str]:
    """Les formes qu'un nom de service prend dans une URL OData, en plus de
    lui-même : l'espace de noms sans sa barre de tête
    (``/IWFND/CATALOGSERVICE`` est servi sous ``.../odata/IWFND/CATALOGSERVICE``)
    et la même forme en minuscules, celle des URL OData v4
    (``/DMO/UI_TRAVEL_D_D_O4`` sous ``.../odata4/dmo/ui_travel_d_d_o4/srvd/...``)."""
    text = _clean(name)
    stripped = text.lstrip("/")
    return sorted({stripped, stripped.lower()} - {text, ""})


def _nameable(name: Any) -> bool:
    """Un nom assez long pour qu'une mention dans une suite signifie quelque
    chose (deux lettres matcheraient n'importe quel mot)."""
    return len(_clean(name)) >= 3


def _sorted_unique(values: Iterable[Any]) -> list[str]:
    return sorted({_clean(v) for v in values if _clean(v)})


def build_change_impact(request: Mapping[str, Any],
                        usages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Assemble l'impact JSON-safe d'un transport : ``request`` (vue de
    `Read Transport Request`) et une usage par objet principal (vue de
    `Get Object Usage`).

    Deux familles de noms, qu'une suite peut écrire et qui ne pèsent pas
    pareil : ``object_names``, les objets TRANSPORTÉS et leurs noms dérivés
    (vues SQL d'une vue CDS, groupe d'un module) ; ``user_names``, ceux qui
    les UTILISENT (rapports, classes des pools, transactions). ``names`` est
    leur réunion."""
    objects = list(request.get("objects") or [])
    object_names: set[str] = set()
    programs: set[str] = set()
    transactions: set[str] = set()
    truncated: list[str] = []
    for usage in usages:
        obj = usage.get("object") or {}
        object_names.update(_clean(n) for n in usage.get("names") or [])
        object_names.add(_clean(obj.get("name")))
        programs.update(_clean(p) for p in usage.get("programs") or [])
        transactions.update(_clean(t) for t in usage.get("transactions") or [])
        if not usage.get("complete", True):
            truncated.append("%s %s" % (obj.get("type"), obj.get("name")))
    user_names = {class_of_include(p) or p for p in programs} | transactions
    user_names -= object_names
    return {
        "request": {key: request.get(key) for key in (
            "request", "function", "status", "owner", "date", "text", "parent", "tasks")},
        "objects": objects,
        "skipped": list(request.get("skipped") or []),
        "usages": [dict(u) for u in usages],
        "programs": _sorted_unique(programs),
        "transactions": _sorted_unique(transactions),
        "object_names": _sorted_unique(n for n in object_names if _nameable(n)),
        "user_names": _sorted_unique(n for n in user_names if _nameable(n)),
        "names": _sorted_unique(n for n in object_names | user_names if _nameable(n)),
        "truncated": sorted(truncated),
        "limits": ("un niveau d'utilisation ; références statiques seulement (D010TAB, "
                   "WBCROSSGT, CROSS, DD03L, DD04L, ENLFDIR, SRVB_SERVICES) ; transactions "
                   "de TSTC sans les transactions OO ni à paramètres ; croisement avec les "
                   "suites textuel"),
    }


def change_impact_hash(impact: Mapping[str, Any]) -> str:
    """Empreinte SHA-256 de l'impact (clés triées) : deux lectures du même
    transport sur le même système ont la même."""
    text = json.dumps(impact, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: Optional[Sequence[str]] = None) -> int:
    """``python -m sapfx_common.change_impact impact.json --root tests/robot``
    : le rapport Markdown d'un impact écrit par `Get Change Impact` (un
    fichier JSON), croisé avec les suites. ``--write-decisions modele.json``
    écrit le modèle qu'un humain remplit, ``--decisions rempli.json`` le
    rapporte sur les suites. Code retour 0 quand aucune suite n'est à
    rejouer (aucune n'exécute un objet transporté, ou un humain a écarté
    chacune avec sa raison), 1 sinon, 2 sur une erreur d'usage ou un fichier
    de décisions invalide."""
    parser = argparse.ArgumentParser(
        prog="python -m sapfx_common.change_impact",
        description="Suites à rejouer après un transport SAP (MVP, croisement textuel).")
    parser.add_argument("impact_json")
    parser.add_argument("--root", default=".")
    parser.add_argument("--markdown", dest="markdown_path", default=None)
    parser.add_argument("--decisions", default=None,
                        help="fichier de décisions humaines rempli (JSON)")
    parser.add_argument("--write-decisions", dest="template_path", default=None,
                        help="écrit le modèle de décisions à remplir (JSON)")
    parser.add_argument("--variable", "-v", action="append", default=[],
                        help="NOM:valeur, comme robot -v, pour résoudre un chemin d'import")
    parser.add_argument("--pythonpath", action="append", default=[],
                        help="où chercher les bibliothèques nommées par module")
    args = parser.parse_args(argv)
    try:
        with open(args.impact_json, encoding="utf-8-sig") as handle:
            impact = json.load(handle)
        suites = suites_impacted_by_change(impact, args.root,
                                           python_path=args.pythonpath or None,
                                           variables=args.variable or None)
        applied = (apply_change_impact_decisions(impact, suites, read_decisions(args.decisions))
                   if args.decisions else None)
    except (OSError, ValueError) as exc:
        print("Rapport impossible : %s" % exc, file=sys.stderr)
        return 2
    if applied is not None:
        suites = applied["suites"]
    if args.template_path:
        with open(args.template_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(get_change_impact_decision_template(impact, suites), handle,
                      ensure_ascii=False, indent=2)
            handle.write("\n")
    report = render_change_impact_report(impact, suites,
                                         applied["summary"] if applied else None)
    if args.markdown_path:
        with open(args.markdown_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(report)
    sys.stdout.write(report)
    return 1 if still_to_replay(suites) else 0


if __name__ == "__main__":                   # pragma: no cover
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    sys.exit(main())
