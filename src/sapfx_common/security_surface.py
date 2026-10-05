"""Surface d'attaque d'un système ABAP, logique pure.

Troisième voisin de `security_baseline.py` (qui juge des PARAMÈTRES) et de
`security_inventory.py` (qui classe le journal d'audit et les destinations
RFC). Ici on classe ce qui est ATTEIGNABLE : les comptes réellement
utilisables, les services web réellement servis, les commandes du système
d'exploitation réellement déclarées, et la couverture d'audit réellement
obtenue.

Quatre mesures du 2026-09-14 sur ABAP Platform 2023 (release 758) ont motivé
ce module, et chacune est un écart entre ce qu'une lecture naïve conclut et ce
que le système fait.

**Un compte non verrouillé n'est pas un compte utilisable.** Le masque de
verrouillage disait « aucun compte verrouillé » sur les six comptes du
mandant, ce qui est vrai. Deux d'entre eux portaient pourtant une date de fin
de validité échue depuis vingt mois : ils sont inutilisables, et une campagne
qui ne lit que le verrouillage les compte comme des comptes actifs. Les deux
lectures répondent à deux questions différentes, et `classify_account_usability`
refuse de les confondre.

**Un service web déclaré n'est pas un service servi.** Le dictionnaire porte
3410 noeuds de services, dont 219 seulement sont actifs. Compter les premiers
donne une surface d'exposition seize fois trop grande, donc inexploitable ;
compter les seconds donne la surface réelle.

**Une commande externe qui accepte des arguments additionnels n'est pas la
même chose qu'une commande figée.** Sur 117 commandes déclarées, 109
acceptent que l'appelant ajoute des arguments à l'exécution. La distinction
n'est pas cosmétique : c'est elle qui sépare « exécuter une sauvegarde » de
« exécuter ce que l'appelant voudra ».

**Un journal armé ne prouve pas un enregistrement.** Le paramètre du noyau
répond « actif », aucun filtre n'est configuré, et la lecture du journal sur
quatre ans rend zéro entrée et zéro fichier. La configuration et le contenu
doivent donc être CROISÉS, et c'est le seul moyen de transformer « armé sans
filtre » d'une déduction en un constat.

Typé, sans dépendance : les E/S vivent dans le mixin `_rfc_surface.py`.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

__all__ = [
    "AUDIT_COVERAGE_VERDICTS",
    "classify_account_usability",
    "summarize_accounts",
    "summarize_icf_exposure",
    "classify_external_command",
    "summarize_external_commands",
    "corroborate_audit_coverage",
    "summarize_trust_surface",
]

#: Les verdicts de couverture d'audit. Nommés pour qu'une suite puisse les
#: asserter sans réécrire la règle, et documentés dans
#: :func:`corroborate_audit_coverage`.
AUDIT_COVERAGE_VERDICTS = (
    "not_measured",
    "disabled_and_silent",
    "entries_while_disabled",
    "armed_without_filter_and_silent",
    "entries_without_filter",
    "filtering_but_silent",
    "filtering_and_recording",
)

#: La valeur que SAP écrit dans une date vide. Ce n'est pas « aucune donnée »,
#: c'est « pas de limite », et les deux ne se traitent pas pareil.
_EMPTY_DATE = {"", "00000000", "0"}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _is_date(value: str) -> bool:
    return len(value) == 8 and value.isdigit()


def classify_account_usability(account: Mapping[str, Any],
                               today: str) -> dict[str, Any]:
    """Dit si un compte est réellement UTILISABLE, et pourquoi il ne l'est pas.

    ``account`` porte au minimum ``user``; les clés reconnues sont ``locked``
    (le verdict du masque de verrouillage, calculé par
    ``security_baseline.classify_user_lock``), ``valid_from`` et ``valid_to``
    (les dates de validité ``GLTGV`` et ``GLTGB``), ``user_group`` et
    ``user_type``. ``today`` est une date ``AAAAMMJJ`` fournie par l'appelant,
    jamais lue ici : une logique pure qui interroge l'horloge n'est pas
    testable.

    Rend ``{"user", "usable", "status", "reasons", "valid_from", "valid_to"}``
    où ``status`` vaut ``active``, ``locked``, ``expired``, ``not_yet_valid``
    ou ``unknown``.

    **Pourquoi ce keyword ne se déduit pas du verrouillage**, et c'est la
    mesure qui l'a fait naître : sur la cible, les six comptes du mandant sont
    tous non verrouillés, et deux portent une date de fin échue. Un rapport
    qui dit « aucun compte verrouillé » est exact et laisse croire que six
    comptes sont ouverts, quand quatre le sont. Les deux constats sont utiles,
    ils ne sont pas interchangeables.

    Un compte verrouillé ET expiré porte les DEUX raisons : la première
    trouvée ne masque pas la seconde, parce que lever le verrou ne suffirait
    pas à le rendre utilisable.

    Une date illisible rend ``unknown`` plutôt que ``active`` : le repli sûr,
    ici comme ailleurs dans ce domaine, est de ne jamais inventer une
    disponibilité.
    """
    user = _clean(account.get("user"))
    if not user:
        raise ValueError("Un compte doit porter un nom.")
    today = _clean(today)
    if not _is_date(today):
        raise ValueError(
            f"`today` doit être une date AAAAMMJJ, reçu {today!r}. Elle est "
            f"fournie par l'appelant à dessein : une logique pure qui lit "
            f"l'horloge n'est pas reproductible.")

    valid_from = _clean(account.get("valid_from"))
    valid_to = _clean(account.get("valid_to"))
    reasons: list[str] = []
    unknown = False

    if account.get("locked"):
        reasons.append("locked")

    if valid_to in _EMPTY_DATE:
        pass
    elif not _is_date(valid_to):
        unknown = True
    elif valid_to < today:
        reasons.append("expired")

    if valid_from in _EMPTY_DATE:
        pass
    elif not _is_date(valid_from):
        unknown = True
    elif valid_from > today:
        reasons.append("not_yet_valid")

    if unknown and not reasons:
        status = "unknown"
    elif not reasons:
        status = "active"
    elif "locked" in reasons:
        status = "locked"
    elif "expired" in reasons:
        status = "expired"
    else:
        status = "not_yet_valid"

    return {
        "user": user,
        "usable": status == "active",
        "status": status,
        "reasons": reasons,
        "valid_from": valid_from or None,
        "valid_to": valid_to or None,
        "user_group": _clean(account.get("user_group")) or None,
        "user_type": _clean(account.get("user_type")) or None,
    }


def summarize_accounts(accounts: Iterable[Mapping[str, Any]],
                       today: str) -> dict[str, Any]:
    """Résume un inventaire de comptes : combien sont utilisables, et qui ne
    l'est pas pour quelle raison.

    Les listes sont triées, donc deux relevés identiques produisent le même
    résumé, ce dont dépend toute comparaison entre deux passages.

    ``usable`` et ``locked`` ne sont pas complémentaires : c'est voulu, et
    c'est tout l'objet du module. Un compte peut être ni verrouillé ni
    utilisable.
    """
    fiches = [classify_account_usability(a, today) for a in accounts]
    par_statut: dict[str, list[str]] = {}
    for fiche in fiches:
        par_statut.setdefault(fiche["status"], []).append(fiche["user"])
    return {
        "total": len(fiches),
        "usable": sorted(f["user"] for f in fiches if f["usable"]),
        "unusable": sorted(f["user"] for f in fiches if not f["usable"]),
        "by_status": {k: sorted(v) for k, v in sorted(par_statut.items())},
        "accounts": sorted(fiches, key=lambda f: f["user"]),
    }


def summarize_icf_exposure(nodes: Iterable[Mapping[str, Any]],
                           sensitive: Optional[Iterable[str]] = None
                           ) -> dict[str, Any]:
    """Résume la surface d'exposition web : ce qui est DÉCLARÉ contre ce qui
    est ACTIF, et ce qui est actif sans chiffrement.

    ``nodes`` porte une entrée par noeud de service, avec ``name``, ``active``
    (booléen), ``ssl`` (booléen), ``stored_user`` (le compte qu'un service
    utilise sans en demander un, quand il y en a un) et ``named`` (vrai quand
    la fiche descriptive du noeud a bien été retrouvée).

    Rend ``{"declared", "active", "active_without_ssl", "with_stored_user",
    "sensitive_active", "exposure_ratio", "matched", "unmatched"}``.

    **Pourquoi compter les deux**, mesuré sur la cible : 3410 noeuds déclarés
    pour 219 actifs. Rapporter le premier chiffre donne une surface seize fois
    trop grande, que personne ne peut auditer ; rapporter le second donne
    exactement ce qui répond sur le réseau.

    ``stored_user`` est distingué parce qu'un service qui porte un compte de
    service s'exécute SANS authentifier son appelant : c'est la propriété la
    plus intéressante de cet inventaire, et elle ne se déduit pas de
    l'activation.
    """
    fiches = [dict(n) for n in nodes]
    actifs = [f for f in fiches if f.get("active")]
    motifs = {str(m).strip().lower() for m in (sensitive or ()) if str(m).strip()}
    sensibles = sorted({
        _clean(f.get("name")) for f in actifs
        if motifs and any(m in _clean(f.get("name")).lower() for m in motifs)
        and _clean(f.get("name"))})
    apparies = len([f for f in actifs if f.get("named")])
    return {
        "declared": len(fiches),
        "active": len(actifs),
        "active_without_ssl": len([f for f in actifs if not f.get("ssl")]),
        "with_stored_user": sorted(
            _clean(f.get("name")) for f in actifs if _clean(f.get("stored_user"))),
        "sensitive_active": sensibles,
        "exposure_ratio": round(len(actifs) / len(fiches), 4) if fiches else 0.0,
        # Le témoin de la JOINTURE, et il ne se déduit d'aucun autre champ.
        # Les deux décomptes ci-dessus viennent de la table d'activation seule :
        # comparer « actifs » et « déclarés » ne dit donc RIEN de la seconde
        # table. Si l'appariement se casse (clé de noeud qui ne correspond
        # plus), le résumé garde exactement la même forme, avec des noms
        # repliés sur l'identifiant, aucun compte de service et aucun service
        # sensible : la signature d'un système sain. `matched` est le seul
        # champ qui distingue les deux situations.
        "matched": apparies,
        "unmatched": len(actifs) - apparies,
    }


def classify_external_command(command: Mapping[str, Any]) -> dict[str, Any]:
    """Classe UNE commande du système d'exploitation déclarée dans le système.

    Rend ``{"name", "os", "command", "arguments", "accepts_additional",
    "customer_defined"}``.

    ``accepts_additional`` est la propriété qui compte : une commande dont
    l'appelant peut compléter les arguments à l'exécution n'offre pas la même
    surface qu'une commande figée. Mesuré sur la cible, 109 des 117 commandes
    déclarées l'acceptent.

    ``customer_defined`` distingue les commandes ajoutées sur le système
    (espace de noms client) de celles livrées par SAP : les premières sont
    celles qu'un audit regarde en premier, puisqu'elles ne viennent d'aucun
    standard.
    """
    name = _clean(command.get("name") or command.get("NAME"))
    if not name:
        raise ValueError("Une commande externe doit porter un nom.")
    raw = (command.get("accepts_additional") if "accepts_additional" in command
           else command.get("ADDPAR"))
    # Un booléen déjà normalisé passe tel quel ; le marqueur ABAP brut est la
    # lettre X. Normaliser le booléen en chaîne d'abord donnerait "True", que
    # la comparaison au marqueur rejette en silence.
    accepts = raw if isinstance(raw, bool) else _clean(raw).upper() == "X"
    return {
        "name": name,
        "os": _clean(command.get("os") or command.get("OPSYSTEM")) or None,
        "command": _clean(command.get("command") or command.get("OPCOMMAND")) or None,
        "arguments": _clean(command.get("arguments")
                            or command.get("PARAMETERS")) or None,
        "accepts_additional": accepts,
        "customer_defined": name.startswith(("Z", "Y")) or name.startswith("/"),
    }


def summarize_external_commands(commands: Iterable[Mapping[str, Any]]
                                ) -> dict[str, Any]:
    """Résume les commandes du système d'exploitation déclarées.

    Rend les comptes et les listes triées : total, celles qui acceptent des
    arguments additionnels, et celles définies sur le système plutôt que
    livrées. Ce sont les deux axes qu'un audit croise, une commande client
    acceptant des arguments étant le cas le plus ouvert.
    """
    fiches = [classify_external_command(c) for c in commands]
    return {
        "total": len(fiches),
        "accepting_additional": len([f for f in fiches if f["accepts_additional"]]),
        "fixed": len([f for f in fiches if not f["accepts_additional"]]),
        "customer_defined": sorted(f["name"] for f in fiches
                                   if f["customer_defined"]),
        "customer_defined_accepting_additional": sorted(
            f["name"] for f in fiches
            if f["customer_defined"] and f["accepts_additional"]),
        "by_os": dict(sorted(
            {o: len([f for f in fiches if f["os"] == o])
             for o in {f["os"] for f in fiches}}.items(),
            key=lambda kv: str(kv[0]))),
    }


def corroborate_audit_coverage(configuration: Mapping[str, Any],
                               entries_read: Optional[int],
                               files_seen: Optional[int] = None,
                               window_days: Optional[int] = None,
                               read_succeeded: bool = True) -> dict[str, Any]:
    """Croise la CONFIGURATION du journal d'audit et son CONTENU réel.

    ``configuration`` est le verdict de
    ``security_inventory.classify_audit_configuration``. ``entries_read`` est
    le nombre d'entrées effectivement lues sur la fenêtre ``window_days``, et
    ``read_succeeded`` dit si la lecture a eu lieu.

    Rend ``{"verdict", "configuration_verdict", "entries", "files",
    "window_days", "consistent", "note"}``, ``verdict`` étant l'une des
    valeurs de :data:`AUDIT_COVERAGE_VERDICTS`.

    **Ce que ce croisement apporte, et pourquoi il fallait une fonction pour
    ça.** Le paramètre du noyau dit « armé », la configuration dit « aucun
    filtre actif », et jusqu'ici la conclusion « donc il n'enregistre rien »
    restait une déduction. La lecture du journal sur quatre ans, qui rend zéro
    entrée et zéro fichier, la transforme en constat. Inversement, des entrées
    trouvées alors qu'aucun filtre n'est actif signalent que quelque chose
    enregistre en dehors de ce que la configuration décrit, ce qui mérite
    d'être vu plutôt que supposé impossible.

    **Une lecture qui a échoué ne vaut JAMAIS zéro.** ``read_succeeded=False``
    rend ``not_measured``, distinct de tout verdict de silence : confondre
    « le journal est vide » et « je n'ai pas su le lire » est exactement le
    faux positif que ce module existe pour empêcher, et il est d'autant plus
    facile à commettre que le module de lecture rend zéro entrée sans erreur
    quand on l'appelle mal.
    """
    conf_verdict = _clean(configuration.get("verdict")) or "unknown"
    if not read_succeeded or entries_read is None:
        return {
            "verdict": "not_measured",
            "configuration_verdict": conf_verdict,
            "entries": None, "files": files_seen, "window_days": window_days,
            "consistent": None,
            "note": ("La lecture du journal n'a pas abouti : aucun verdict de "
                     "couverture. Une lecture absente n'est pas un journal "
                     "vide."),
        }

    entries = int(entries_read)
    if conf_verdict == "disabled":
        verdict = "entries_while_disabled" if entries else "disabled_and_silent"
    elif conf_verdict == "armed_without_filter":
        verdict = ("entries_without_filter" if entries
                   else "armed_without_filter_and_silent")
    elif conf_verdict == "filtering":
        verdict = "filtering_and_recording" if entries else "filtering_but_silent"
    else:
        verdict = "not_measured"

    notes = {
        "disabled_and_silent":
            "Journal désarmé et vide : cohérent, et aucun incident ne sera "
            "reconstituable.",
        "entries_while_disabled":
            "Des entrées existent alors que le journal est désarmé : elles "
            "datent d'avant le désarmement, ou la configuration lue n'est pas "
            "celle qui s'applique.",
        "armed_without_filter_and_silent":
            "Journal armé, aucun filtre actif, aucune entrée : le paramètre "
            "annonce une couverture qui n'existe pas. C'est le faux positif de "
            "conformité de ce domaine, ici CONSTATÉ et non déduit.",
        "entries_without_filter":
            "Des entrées existent alors qu'aucun filtre n'est actif : quelque "
            "chose enregistre en dehors de la configuration lue.",
        "filtering_but_silent":
            "Des filtres sont actifs et le journal est vide : soit rien "
            "d'auditable ne s'est produit sur la fenêtre, soit les filtres ne "
            "portent pas sur ce qui se produit.",
        "filtering_and_recording":
            "Journal armé, filtrant et alimenté : la couverture annoncée est "
            "confirmée par le contenu.",
        "not_measured":
            "Configuration non classée : aucun verdict de couverture.",
    }
    return {
        "verdict": verdict,
        "configuration_verdict": conf_verdict,
        "entries": entries,
        "files": files_seen,
        "window_days": window_days,
        "consistent": verdict in ("disabled_and_silent",
                                  "armed_without_filter_and_silent",
                                  "filtering_and_recording"),
        "note": notes.get(verdict, ""),
    }


def summarize_trust_surface(trusted: Iterable[Mapping[str, Any]],
                            trusting: Iterable[Mapping[str, Any]],
                            callback_allowlist: Iterable[Mapping[str, Any]]
                            ) -> dict[str, Any]:
    """Résume les relations de confiance RFC et la liste blanche des rappels.

    Rend les trois décomptes et les listes triées de systèmes concernés.

    **Pourquoi cet inventaire vaut d'exister même quand il est vide**, et il
    l'est sur la cible : une campagne qui ne lit pas ces tables ne peut pas
    distinguer « aucune relation de confiance n'est configurée » de « personne
    n'a regardé ». Le jour où une relation apparaît, seule la première
    situation la rend visible. Un inventaire vide mesuré est un résultat ; un
    inventaire jamais lu est un angle mort.

    La liste blanche des rappels est jointe ici plutôt que dans les
    destinations parce qu'elle répond à la même question : quel système peut
    faire exécuter quoi chez l'autre.
    """
    entrants = [dict(t) for t in trusted]
    sortants = [dict(t) for t in trusting]
    rappels = [dict(c) for c in callback_allowlist]
    return {
        "trusted_systems": len(entrants),
        "trusting_systems": len(sortants),
        "callback_allowlist_entries": len(rappels),
        "trusted_ids": sorted({_clean(t.get("system") or t.get("RFCTRUSTSY"))
                               for t in entrants} - {""}),
        "trusting_ids": sorted({_clean(t.get("system") or t.get("RFCSYSID"))
                                for t in sortants} - {""}),
        "callback_destinations": sorted({_clean(c.get("destination")
                                                or c.get("DESTINATION"))
                                         for c in rappels} - {""}),
        "any_trust_configured": bool(entrants or sortants),
    }
