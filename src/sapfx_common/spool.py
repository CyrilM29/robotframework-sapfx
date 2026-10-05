"""Spool d'un job de fond : du pas de job au contenu, et le contenu jugé.
Logique pure, socle du mixin ``SapApiLibrary._rfc_spool``.

Le chemin, mesuré sur A4H (release 754) le 2026-10-01 (fiche scénario 9) :
le pas de job (``TBTCP``) porte le numéro de spool dans ``LISTIDENT``, la
demande de spool vit dans ``TSP01`` (propriétaire, mandant, date de
création), et le contenu se lit par l'interface XBP, de DEUX façons qui ne
rendent pas le même format :

- par le pas de job (``BAPI_XBP_JOB_SPOOLLIST_READ``) : des lignes CADRÉES,
  telles que la liste s'imprime (17 lignes pour ``SHOWCOLO``) ;
- par le numéro (``BAPI_XBP_GET_SPOOL_AS_DAT``) : des lignes TABULÉES, les
  cadres rendus vides (16 lignes pour le même spool).

Trois pièges y sont encodés. ``LISTIDENT`` vaut ``0000000000`` pour un pas
qui n'a rien imprimé : c'est « pas de spool », jamais un spool numéro 0, et
`spool_id_of` rend ``None``. XBP refuse un pas sans spool par ``XM/E/063`` :
ce n'est pas un spool VIDE, et le dire ainsi ferait passer un rapport qui
n'a rien produit pour un rapport qui n'avait rien à dire. Enfin
``RQ0NAME`` n'est PAS le programme (``LIST1S``) et ``RQ2NAME`` le tronque
(``SHOWCOLO_DEV`` : huit caractères, ``_``, trois de l'utilisateur) : un
indice, pas une preuve ; le lien au programme passe par ``TBTCP-PROGNAME``.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Sequence

#: Refus XBP par identifiant de message (classe/type/numéro, non localisés).
XM_ALREADY_LOGGED_ON = "XM/E/022"
XM_NOT_LOGGED_ON = "XM/E/028"
XM_NO_SPOOL_FOR_STEP = "XM/E/063"
XM_INVALID_SPOOL = "XM/E/065"
XM_STEP_NOT_IN_JOB = "XM/E/220"
XM_PAGE_OUT_OF_RANGE = "XM/E/273"

#: Champs de ``TBTCP`` (pas de job) lus pour le lien au spool.
STEP_FIELDS = ("STEPCOUNT", "PROGNAME", "VARIANT", "LISTIDENT", "AUTHCKNAM")

#: Champs de ``TSP01`` (demande de spool) lus pour son identité.
SPOOL_FIELDS = ("RQIDENT", "RQCLIENT", "RQOWNER", "RQ0NAME", "RQ2NAME",
                "RQCRETIME")


class JobStepWithoutSpoolError(AssertionError):
    """Le pas de job n'a produit AUCUN spool (``XM/E/063``) : distinct d'un
    spool vide, et c'est toute la raison d'être de cette exception."""


class InvalidSpoolRequestError(AssertionError):
    """Le numéro de spool n'existe pas (``XM/E/065``)."""


class JobStepNotFoundError(AssertionError):
    """Le job n'a pas ce pas (``XM/E/220``)."""


class SpoolPageOutOfRangeError(AssertionError):
    """La plage demandée commence après la dernière page (``XM/E/273``)."""


def validate_page_range(first_page: int, last_page: int) -> None:
    """Refuse AVANT tout appel une plage de pages incohérente : première
    page < 1, dernière < 0, ou dernière (non nulle) avant la première. Mesuré
    sur A4H le 2026-10-01 : XBP rend sans refus les pages 5 à 20 d'une plage
    « 5 à 3 », donc une plage inversée lirait en silence autre chose que ce
    qui était demandé."""
    if first_page < 1:
        raise ValueError("first_page=%r : la première page vaut au moins 1." % first_page)
    if last_page < 0:
        raise ValueError("last_page=%r : 0 (jusqu'à la fin) ou un numéro de page." % last_page)
    if last_page and last_page < first_page:
        raise ValueError(
            "Plage de pages inversée (%d à %d) : refusée avant l'appel, XBP la "
            "lirait de %d jusqu'à la FIN sans rien dire." % (first_page, last_page, first_page))


def page_coverage(first_page: int, last_page: int, declared_pages: int) -> dict[str, Any]:
    """Ce qu'une lecture a DEMANDÉ face au nombre de pages DÉCLARÉ :
    ``{declared_pages, first_page, last_page, complete}`` où ``last_page``
    est la dernière page effective (``0`` = jusqu'à la fin) et ``complete``
    vaut vrai seulement pour une plage demandée de la page 1 à la dernière
    déclarée. Ce drapeau juge la DEMANDE, pas ce que le serveur a rendu (revue
    indépendante du 2026-10-01) : la preuve de contenu est
    `last_page_is_suffix`."""
    effective_last = declared_pages if last_page in (0, None) else min(last_page, declared_pages)
    return {"declared_pages": declared_pages, "first_page": first_page,
            "last_page": effective_last,
            "complete": bool(declared_pages) and first_page == 1
            and effective_last >= declared_pages}


def check_page_range_against_declared(first_page: int, last_page: int,
                                      declared_pages: int) -> None:
    """Refuse une plage qui DÉBORDE la dernière page déclarée (« 15 à 25 »
    sur 20 pages) : XBP la ramènerait en silence à la dernière page. Une plage
    qui COMMENCE après la dernière page est laissée au serveur, qui la refuse
    par ``XM/E/273``."""
    if declared_pages and last_page and first_page <= declared_pages < last_page:
        raise SpoolPageOutOfRangeError(
            "La plage %d à %d déborde la dernière page déclarée (%d) : refusée "
            "avant l'appel, la lecture serait ramenée en silence à la page %d."
            % (first_page, last_page, declared_pages, declared_pages))


def last_page_is_suffix(all_lines: Sequence[str], last_page_lines: Sequence[str]) -> bool:
    """Vrai si la dernière page, relue SEULE, n'est pas vide et termine
    exactement la lecture entière : la preuve que la réponse n'a pas été
    amputée de sa fin (une réponse coupée par le serveur ne finirait pas par
    les lignes de la dernière page)."""
    tail = list(last_page_lines)
    if not non_blank_lines(tail) or len(tail) > len(all_lines):
        return False
    return list(all_lines[len(all_lines) - len(tail):]) == tail


def describe_spool_attributes(attributes: Mapping[str, Any]) -> dict[str, Any]:
    """Les attributs d'une demande de spool (structure ``SPOOL_ATTR`` de
    ``BAPI_XBP_GET_SPOOL_ATTRIBUTES``) en dict JSON-safe : ``spool_id``,
    ``client``, ``owner``, ``title`` (le titre que montre SP01, un indice et
    jamais le programme), ``pages`` (``SPOPAGES``, le nombre de pages
    DÉCLARÉ), ``created_at`` (heure système, ``AAAAMMJJhhmmss``),
    ``device``, ``doc_type``, ``size`` (octets TemSe), ``language``."""
    title = " ".join(part for part in (str(attributes.get("NAME", "")).strip(),
                                       str(attributes.get("SUFFIX2", "")).strip()) if part)
    created = "".join(ch for ch in str(attributes.get("CRTIME", "")) if ch.isdigit())[:14]
    return {
        "spool_id": int(attributes.get("SPOOLID") or 0),
        "client": str(attributes.get("CLIENT", "")).strip(),
        "owner": str(attributes.get("OWNER", "")).strip(),
        "title": title,
        "pages": int(attributes.get("SPOPAGES") or 0),
        "created_at": created,
        "device": str(attributes.get("DEVICE", "")).strip(),
        "doc_type": str(attributes.get("DOCTYP", "")).strip(),
        "size": int(attributes.get("TMSSIZE") or 0),
        "language": str(attributes.get("LANGU", "")).strip(),
    }


def spool_id_of(listident: Any) -> Optional[int]:
    """Numéro de spool depuis ``TBTCP-LISTIDENT`` : ``None`` pour un pas sans
    spool (``0000000000`` ou vide), jamais ``0``. Une valeur non numérique
    est refusée (``ValueError``) : un numéro deviné serait pire qu'absent."""
    text = str(listident if listident is not None else "").strip()
    if not text:
        return None
    if not text.isdigit():
        raise ValueError("LISTIDENT non numérique %r : pas un numéro de spool." % listident)
    number = int(text)
    return number or None


def spool_id_argument(value: Any, argument: str = "spool_id") -> int:
    """Numéro de spool d'un argument Robot/MCP (chaîne ``"0000023203"``,
    ``"23203"`` ou entier) : un entier strictement positif, sinon
    ``ValueError`` nommant l'argument. pyrfc refuse une chaîne pour
    ``SPOOL_REQUEST`` (``TypeError``) : la conversion se fait ICI."""
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        number = 0
    if number <= 0:
        raise ValueError("%s : numéro de spool invalide %r (entier > 0 attendu)."
                         % (argument, value))
    return number


def normalize_spool_lines(rows: Optional[Iterable[Any]]) -> list[str]:
    """Lignes de spool en chaînes, blancs de fin retirés : accepte la table
    ``SPOOL_LIST`` de ``BAPI_XBP_JOB_SPOOLLIST_READ`` (dicts ``{"LINE"}``) et
    celle de ``BAPI_XBP_GET_SPOOL_AS_DAT`` (chaînes nues). Les lignes vides
    sont CONSERVÉES : elles portent la structure (cadres, sauts)."""
    lines: list[str] = []
    for row in rows or []:
        if isinstance(row, Mapping):
            text = row.get("LINE", row.get("line", ""))
        else:
            text = row
        lines.append(str(text if text is not None else "").rstrip())
    return lines


def non_blank_lines(lines: Sequence[str]) -> list[str]:
    """Les lignes qui portent du texte (un cadre fait de ``-`` et ``|`` seuls
    n'en porte pas)."""
    return [line for line in lines if line.strip(" \t-|")]


def split_dat_cells(lines: Sequence[str]) -> list[list[str]]:
    """Cellules des lignes TABULÉES de ``BAPI_XBP_GET_SPOOL_AS_DAT`` : une
    liste de cellules dépouillées par ligne non vide (la première cellule,
    vide, qui précède la première tabulation est retirée)."""
    cells: list[list[str]] = []
    for line in lines:
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split("\t")]
        while parts and not parts[0]:
            parts.pop(0)
        cells.append(parts)
    return cells


def spool_summary(lines: Sequence[str]) -> dict[str, Any]:
    """``{lines, line_count, non_blank_lines}`` : le contenu tel que lu et le
    compte de lignes qui portent du texte (le critère « pas vide »)."""
    return {"lines": list(lines), "line_count": len(lines),
            "non_blank_lines": len(non_blank_lines(lines))}


def describe_step_spool(step: Mapping[str, Any],
                        spool_row: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    """Une entrée par pas de job : ``{step, program, variant, user,
    spool_id, owner, client, created_at, title}``. ``spool_id`` vaut ``None``
    pour un pas sans spool, et les champs de la demande restent vides ;
    ``created_at`` est l'horodatage technique ``TSP01-RQCRETIME`` (heure
    SYSTÈME, ``AAAAMMJJhhmmss`` : SP01, lui, affiche l'heure du fuseau de
    l'utilisateur) ; ``title`` assemble ``RQ0NAME`` et ``RQ2NAME``, le titre
    que montre SP01, jamais une preuve du programme."""
    spool_id = spool_id_of(step.get("LISTIDENT"))
    row = spool_row or {}
    created = "".join(ch for ch in str(row.get("RQCRETIME", "")) if ch.isdigit())[:14]
    title = " ".join(part for part in (str(row.get("RQ0NAME", "")).strip(),
                                       str(row.get("RQ2NAME", "")).strip()) if part)
    return {
        "step": int(str(step.get("STEPCOUNT", "0")).strip() or 0),
        "program": str(step.get("PROGNAME", "")).strip(),
        "variant": str(step.get("VARIANT", "")).strip(),
        "user": str(step.get("AUTHCKNAM", "")).strip(),
        "spool_id": spool_id,
        "owner": str(row.get("RQOWNER", "")).strip(),
        "client": str(row.get("RQCLIENT", "")).strip(),
        "created_at": created,
        "title": title,
    }


def missing_spool_message(jobname: str, jobcount: str, step: Mapping[str, Any]) -> str:
    """Le refus d'un pas dont le ``LISTIDENT`` est non nul mais absent de
    ``TSP01`` : un spool RÉORGANISÉ (supprimé), qui n'est ni « pas de
    spool » ni un spool vide."""
    return ("Le pas %s du job %s/%s désigne le spool %s, absent de TSP01 : la "
            "demande a été supprimée (réorganisation du spool, RSPO0041 ou "
            "SP01) depuis l'exécution. Ce n'est ni « pas de spool » ni un "
            "spool vide." % (step.get("STEPCOUNT"), jobname, jobcount,
                             spool_id_of(step.get("LISTIDENT"))))


def lines_text(lines: Iterable[Any]) -> list[str]:
    """Une ligne de texte par élément, quelle que soit sa forme : chaîne,
    liste de cellules (jointes par une espace), ou dict (valeurs jointes, les
    clés techniques préfixées ``_`` exclues, la forme de `Read Abap List
    Rows`)."""
    texts: list[str] = []
    for line in lines or []:
        if isinstance(line, Mapping):
            texts.append(" ".join(str(value) for key, value in line.items()
                                  if not str(key).startswith("_")))
        elif isinstance(line, (list, tuple)):
            texts.append(" ".join(str(cell) for cell in line))
        else:
            texts.append(str(line))
    return texts


def find_in_order(lines: Iterable[Any], markers: Sequence[str],
                  same_line: bool = False) -> dict[str, Any]:
    """Cherche ``markers`` DANS L'ORDRE dans ``lines`` (sous-chaînes exactes,
    sensibles à la casse : ce sont des constantes techniques, pas du texte
    localisé), chaque marqueur sur une ligne STRICTEMENT plus basse que le
    précédent ; ``same_line=True`` autorise plusieurs marqueurs sur une même
    ligne (une seule ligne portant tous les noms passerait alors, d'où le
    défaut strict, relevé par la revue indépendante du 2026-10-01). Rend
    ``{"found": [{marker, line, column}], "missing": None}``
    ou, au premier marqueur introuvable, ``missing`` = ``{marker, after_line,
    present_earlier}`` : ``present_earlier`` distingue un marqueur ABSENT
    d'un marqueur présent mais dans le désordre."""
    texts = lines_text(lines)
    found: list[dict[str, Any]] = []
    line_index, column = 0, 0
    for marker in markers:
        hit = None
        for index in range(line_index, len(texts)):
            start = column if index == line_index else 0
            position = texts[index].find(marker, start)
            if position >= 0:
                hit = (index, position)
                break
        if hit is None:
            earlier = any(marker in text for text in texts)
            return {"found": found,
                    "missing": {"marker": marker, "after_line": line_index,
                                "present_earlier": earlier}}
        found.append({"marker": marker, "line": hit[0], "column": hit[1]})
        if same_line:
            line_index, column = hit[0], hit[1] + len(marker)
        else:
            line_index, column = hit[0] + 1, 0
    return {"found": found, "missing": None}


def format_order_failure(result: Mapping[str, Any], total_lines: int) -> str:
    """Le message d'échec de `find_in_order` : quel marqueur, où la
    recherche reprenait, et s'il existait AVANT (désordre) ou nulle part."""
    missing = result["missing"]
    found = ", ".join("%s@%d" % (hit["marker"], hit["line"]) for hit in result["found"])
    cause = ("présent plus haut, donc dans le DÉSORDRE"
             if missing["present_earlier"] else "absent du contenu")
    return ("Marqueur %r introuvable à partir de la ligne %d sur %d (%s). "
            "Trouvés dans l'ordre : %s."
            % (missing["marker"], missing["after_line"], total_lines, cause,
               found or "aucun"))
