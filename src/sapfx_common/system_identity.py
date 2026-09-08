"""Identité d'un système SAP lue à l'ÉCRAN (System > Status), logique pure.

Un registre ou un artefact qui ne porte que le SID, le mandant et l'utilisateur
ne prouve pas SA cible : sur un poste de laboratoire, deux conteneurs annoncent
le même ``A4H``, le même hôte ``vhcala4hci`` et le même utilisateur, et seuls la
release (``754`` contre ``758``) et le kernel (``777`` contre ``793``) les
distinguent (relevé live 2026-08-28 par le canal RFC, réserve de la revue
indépendante du registre de capacités le 2026-09-07). Le canal RFC lit cette
identité dans ``RFC_SYSTEM_INFO`` ; le canal SAP GUI la lit dans le modal
« System: Status » (programme ``SAPLSHSY``, dynpro ``700``), son popup « Kernel
information » (dynpro ``701``) et son dialogue « Installed Software » (grille
des composants, ``SAP_BASIS`` en tête). Relevé live le 2026-09-07 sur A4H (SAP
GUI 8.00) : les champs portent des ids TECHNIQUES (``txtSYST-MANDT``,
``txtKINFOSTRUC-KERNEL_RELEASE``...), ce qui rend la lecture indépendante de
la langue de session ; la grille des composants expose ``COMPONENT`` /
``RELEASE`` / ``EXTRELEASE`` / ``HIGH_PATCH`` en colonnes techniques.

Ce module ne touche à aucun écran : il connaît les champs, en dérive une
identité JSON-safe, isole les clés d'ANCRE (celles qui prouvent une cible)
des clés VOLATILES (l'adresse IP, mesurée changeante entre deux relevés du
même conteneur), et compare deux identités. Typé, testé hors SAP.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

STATUS_PROGRAM = "SAPLSHSY"
STATUS_SCREEN = "700"

# Champs du modal « System: Status » (``wnd[N]/usr/<suffixe>``) -> clé.
STATUS_FIELDS: Mapping[str, str] = {
    "txtSYST-MANDT": "client",
    "txtSYST-UNAME": "user",
    "txtSYST-LANGU": "language",
    "txtSHKONTEXT-TCODE": "transaction",
    "txtCVERS_TXT-STEXT": "product_version_text",
    "txtCUSTOMER": "installation_name",
    "txtSERVERNAME": "server_name",
    "txtSYST-OPSYS": "operating_system",
    "txtSTATUS_INFO-MACHINETYPE": "machine_type",
    "txtSTATUS_INFO-SYSTEM_ID": "platform_id",
    "txtDBNAME": "database_system",
    "txtSTATUS_INFO-DATABASE_RELEASE": "database_release",
    "txtSTATUS_INFO-DATABASE_NAME": "database_name",
    "txtSTATUS_INFO-DATABASE_HOST": "database_host",
    "txtSTATUS_INFO-DB_SCHEMA": "database_schema",
}

# Champs du popup « System: Kernel information » (``wnd[N]/usr/<suffixe>``).
KERNEL_FIELDS: Mapping[str, str] = {
    "txtKINFOSTRUC-KERNEL_RELEASE": "kernel_release",
    "txtKINFOSTRUC-KERNEL_PATCH_LEVEL": "kernel_patch_level",
    "txtKINFOSTRUC-KERNEL_COMPILATION": "kernel_compilation",
    "txtKINFOSTRUC-ABAP_LOAD": "abap_load",
    "txtKINFOSTRUC-CUA_LOAD": "cua_load",
    "txtKINFOSTRUC-KERNEL_KIND": "kernel_kind",
    "txtKINFOSTRUC-SUPPORTED_SAP_VERS": "supported_sap_releases",
    "txtKINFOSTRUC-IP_ADDRESS": "ip_address",
    "txtKINFOSTRUC-VALID_OP_SYSTEM": "kernel_operating_system",
    "txtKINFOSTRUC-OP_SYSTEM_RELEASE": "operating_system_release",
    "txtDBINFO-CLIREL": "database_client_library",
    "txtDBINFO-RELEASES": "database_releases_supported",
    "txtDBINFO-DBSL_VERS": "dbsl_version",
    "txtDBINFO-PATCHLEVEL": "dbsl_patch_level",
}

# Colonnes TECHNIQUES de la grille « Installed Software Component Versions ».
COMPONENT_COLUMNS: tuple[str, ...] = (
    "COMPONENT", "RELEASE", "EXTRELEASE", "HIGH_PATCH", "DESC_TEXT")
BASIS_COMPONENT = "SAP_BASIS"

# Les clés qui PROUVENT une cible : stables d'un relevé à l'autre tant que le
# système ne change pas, et différentes entre deux systèmes qui partagent un
# SID. C'est le sous-ensemble que `compare_identities` confronte.
ANCHOR_KEYS: tuple[str, ...] = (
    "system_id", "client", "basis_release", "basis_sp_level",
    "kernel_release", "kernel_patch_level", "product_version_text",
    "server_name", "database_system", "database_release",
)
# Ce qui bouge sans que la cible change (adresse IP reprise au redémarrage
# d'un conteneur, transaction courante, utilisateur de session) : rendu,
# jamais comparé.
VOLATILE_KEYS: tuple[str, ...] = ("ip_address", "transaction", "user", "language")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def parse_release_list(text: Any) -> list[str]:
    """``"753, 754, 777"`` -> ``["753", "754", "777"]`` (vide -> liste vide)."""
    return [part.strip() for part in _text(text).split(",") if part.strip()]


def parse_server_name(text: Any) -> dict[str, str]:
    """Le nom de serveur d'application ``<hôte>_<SID>_<instance>``
    (``vhcala4hci_A4H_00``) décomposé ; dict vide si la forme n'est pas celle-là
    (le SID vient alors de la session)."""
    parts = _text(text).rsplit("_", 2)
    if len(parts) != 3 or not all(parts):
        return {}
    host, sid, instance = parts
    if len(sid) != 3 or not instance.isdigit():
        return {}
    return {"host": host, "system_id": sid, "instance_number": instance}


def map_fields(raw: Mapping[str, Any] | None, fields: Mapping[str, str]) -> dict[str, str]:
    """``{suffixe d'id: texte}`` -> ``{clé: texte}`` selon ``fields`` ; un suffixe
    inconnu est ignoré, une clé absente de ``raw`` n'apparaît pas."""
    mapped: dict[str, str] = {}
    for suffix, key in fields.items():
        if raw is not None and suffix in raw:
            mapped[key] = _text(raw[suffix])
    return mapped


def components_from_rows(rows: Iterable[Mapping[str, Any]] | None) -> list[dict[str, str]]:
    """Les lignes de la grille des composants (clés techniques `Read Grid`
    ``columns=``) -> ``[{component, release, sp_level, support_package,
    description}]`` dans l'ordre d'affichage, lignes sans composant ignorées."""
    components: list[dict[str, str]] = []
    for row in rows or ():
        name = _text(row.get("COMPONENT"))
        if not name:
            continue
        components.append({
            "component": name,
            "release": _text(row.get("RELEASE")),
            "sp_level": _text(row.get("EXTRELEASE")),
            "support_package": _text(row.get("HIGH_PATCH")),
            "description": _text(row.get("DESC_TEXT")),
        })
    return components


def basis_component(components: Sequence[Mapping[str, Any]]) -> dict[str, str] | None:
    """La ligne ``SAP_BASIS`` (celle qui porte LA release ABAP), ou ``None``."""
    for component in components:
        if _text(component.get("component")).upper() == BASIS_COMPONENT:
            return {key: _text(value) for key, value in component.items()}
    return None


def build_identity(status_fields: Mapping[str, Any] | None,
                   kernel_fields: Mapping[str, Any] | None = None,
                   component_rows: Iterable[Mapping[str, Any]] | None = None,
                   session_system: Any = None,
                   unread: Iterable[str] = ()) -> dict[str, Any]:
    """Assemble l'identité JSON-safe d'une cible à partir des champs BRUTS lus
    à l'écran (``{suffixe d'id: texte}`` pour le statut et le kernel, lignes de
    grille pour les composants) et du SID de la session.

    Clés plates (``client``, ``basis_release``, ``kernel_release``...), plus
    ``components`` (liste), ``unread`` (les sections NON lues, avec leur
    raison : jamais une valeur plausible à la place), ``missing_fields`` (par
    section lue, les champs que le dialogue n'affichait pas : vides dans
    l'identité, nommés ici) et ``anchor`` (le sous-ensemble comparable,
    `ANCHOR_KEYS`). Le SID vient du nom de serveur
    d'application quand il a la forme ``hôte_SID_instance``, sinon de la
    session ; les deux sont rendus quand ils divergent (``session_system``).
    """
    # Toutes les clés connues existent, VIDES tant qu'elles ne sont pas lues :
    # une section non lue se voit (clé vide + ``unread``), elle ne manque pas.
    identity: dict[str, Any] = {key: "" for key in STATUS_FIELDS.values()}
    identity.update({key: "" for key in KERNEL_FIELDS.values()})
    identity.update(map_fields(status_fields, STATUS_FIELDS))
    server = parse_server_name(identity.get("server_name"))
    identity["application_host"] = server.get("host", "")
    identity["instance_number"] = server.get("instance_number", "")
    identity["system_id"] = server.get("system_id") or _text(session_system)
    identity["session_system"] = _text(session_system)
    kernel = map_fields(kernel_fields, KERNEL_FIELDS)
    identity.update(kernel)
    identity["supported_sap_releases"] = parse_release_list(
        kernel.get("supported_sap_releases"))
    components = components_from_rows(component_rows)
    identity["components"] = components
    basis = basis_component(components)
    identity["basis_release"] = basis["release"] if basis else ""
    identity["basis_sp_level"] = basis["sp_level"] if basis else ""
    identity["basis_support_package"] = basis["support_package"] if basis else ""
    identity["unread"] = [_text(item) for item in unread if _text(item)]
    # Les CHAMPS absents d'un dialogue pourtant lu (une autre release peut ne
    # pas les afficher) : nommés à part, jamais confondus avec une section
    # non lue, et jamais rendus comme une valeur.
    missing: dict[str, list[str]] = {}
    if status_fields is not None:
        missing["status"] = [key for suffix, key in STATUS_FIELDS.items()
                             if suffix not in status_fields]
    if kernel_fields is not None:
        missing["kernel"] = [key for suffix, key in KERNEL_FIELDS.items()
                             if suffix not in kernel_fields]
    identity["missing_fields"] = {section: keys for section, keys in missing.items() if keys}
    identity["anchor"] = {key: identity.get(key, "") for key in ANCHOR_KEYS}
    return identity


def describe_identity(identity: Mapping[str, Any]) -> str:
    """Une ligne lisible : ``A4H/001 SAP_BASIS 754 SP 0007, kernel 777 PL 500,
    vhcala4hci_A4H_00 (HDB)``, avec les sections non lues nommées."""
    parts = ["%s/%s" % (_text(identity.get("system_id")) or "?",
                        _text(identity.get("client")) or "?")]
    if _text(identity.get("basis_release")):
        parts.append("SAP_BASIS %s SP %s" % (identity["basis_release"],
                                            _text(identity.get("basis_sp_level")) or "?"))
    if _text(identity.get("kernel_release")):
        parts.append("kernel %s PL %s" % (identity["kernel_release"],
                                          _text(identity.get("kernel_patch_level")) or "?"))
    if _text(identity.get("server_name")):
        parts.append(_text(identity["server_name"]))
    if _text(identity.get("database_system")):
        parts.append("(%s)" % identity["database_system"])
    unread = [_text(item) for item in identity.get("unread", ()) if _text(item)]
    line = " ".join(parts)
    if unread:
        line += " ; non lu : " + "; ".join(unread)
    missing = identity.get("missing_fields") or {}
    if isinstance(missing, Mapping) and missing:
        line += " ; champs absents : " + "; ".join(
            "%s (%s)" % (section, ", ".join(keys)) for section, keys in missing.items())
    return line


def compare_identities(a: Mapping[str, Any], b: Mapping[str, Any]) -> list[dict[str, str]]:
    """Les clés d'ANCRE qui diffèrent entre deux identités (``[{key, a, b}]``,
    vide = même cible). Les clés volatiles ne sont jamais comparées."""
    anchor_a = a.get("anchor", a)
    anchor_b = b.get("anchor", b)
    return [{"key": key, "a": _text(anchor_a.get(key)), "b": _text(anchor_b.get(key))}
            for key in ANCHOR_KEYS
            if _text(anchor_a.get(key)) != _text(anchor_b.get(key))]


def expected_mismatches(identity: Mapping[str, Any],
                        expected: Mapping[str, Any]) -> list[dict[str, str]]:
    """Les attentes non tenues : ``[{key, expected, actual}]``. Une clé
    attendue inconnue de l'identité est un écart (jamais ignorée en silence)."""
    mismatches: list[dict[str, str]] = []
    for key, wanted in expected.items():
        actual = identity.get(key)
        if actual is None or _text(actual) != _text(wanted):
            mismatches.append({"key": str(key), "expected": _text(wanted),
                               "actual": "" if actual is None else _text(actual)})
    return mismatches
