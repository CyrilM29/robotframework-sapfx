"""Simulation d'écriture réversible : périmètre, perception de l'écran de
saisie, observation de réversibilité.

Logique **pure** (aucune E/S, aucun COM, aucun HTTP) de la campagne « écrire
par un canal, constater par l'autre, puis prouver le retour à l'état initial »
(plan ``specs/simulation-ecriture-lecture-cross-canal.md``). Elle complète
``cross_channel``, qui qualifie des candidats à l'écriture SANS écrire et
laisse par construction ``reversibility_observed`` à ``unknown`` : c'est ce
module qui produit l'observation datée qui remplit ce champ.

Il est **importé comme bibliothèque Robot** par la couche ``resources/`` : d'où
des fonctions de module aux signatures JSON-safe, comme dans
``ddic_inventory`` et ``cross_channel``.

Trois enseignements live (A4H, 2026-08-22) sont encodés ici plutôt que dans un
commentaire de suite :

- **une écriture d'écran se refuse au niveau du DICTIONNAIRE, pas des droits**.
  Les onze tables ``/DMO/*`` du modèle de démonstration RAP portent un
  ``MAINFLAG`` vide : SE16 répond « maintenance not allowed » en type ``E``
  quelle que soit l'autorisation de l'utilisateur. Une cible d'écriture se
  qualifie donc AUSSI par le dictionnaire, jamais par le seul fait qu'elle soit
  lisible par les deux canaux ;
- **les champs de l'écran de saisie SE16 ne se déclarent pas, ils se
  perçoivent**. Leurs identifiants suivent ``<préfixe><TABLE>-<CHAMP>``, où le
  préfixe est le type de contrôle et varie d'un champ à l'autre. Dérivés de la
  perception, ils restent justes quand l'écran est régénéré ;
- **le périmètre d'écriture est une liste blanche, et son défaut est
  RIEN**. Une liste vide n'autorise pas tout : elle refuse tout.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable, Mapping

__all__ = [
    "normalize_table_name",
    "validate_write_target",
    "table_entry_fields",
    "build_reversibility_observation",
    "reversibility_observation_json",
]

#: Version du schéma de l'observation, comme l'artefact de croisement porte la
#: sienne : une observation relue plus tard doit savoir ce qu'elle promet.
OBSERVATION_SCHEMA_VERSION = 1

#: Identifiant d'un champ de l'écran de saisie SE16 :
#: ``wnd[0]/usr/<type de contrôle><TABLE>-<CHAMP>``. Le préfixe de type
#: (``ctxt``, ``txt``, ``chk``…) varie par champ, la structure non.
_ENTRY_FIELD = re.compile(
    r"wnd\[\d+\]/usr/(?:[a-z]+)(?P<table>[A-Z0-9_/]+)-(?P<field>[A-Z0-9_/]+)$")


def normalize_table_name(table: Any) -> str:
    """Nom de table normalisé pour COMPARAISON : majuscules, espaces retirés.

    Les barres d'espace de noms sont conservées (``/DMO/CARRIER`` reste
    distinct de ``DMOCARRIER``) ; seule la comparaison avec un identifiant
    d'écran les ignore, parce que SAP ne les reproduit pas toujours dans un
    identifiant de contrôle.
    """
    return str(table or "").strip().upper()


def _screen_form(table: str) -> str:
    return table.replace("/", "")


def validate_write_target(table: Any, allowlist: Any = None) -> str:
    """Refuse toute écriture hors de la liste blanche, et retourne la cible.

    C'est la règle de sûreté n°6 du plan rendue MÉCANIQUE : elle vit au point
    de passage obligé des mots-clés d'écriture, pas dans la discipline de
    l'appelant. Deux refus, tous deux volontairement bloquants :

    - une cible vide (rien à écrire, donc rien à autoriser) ;
    - une cible absente de la liste blanche, l'erreur nommant la liste.

    Une liste blanche vide n'autorise **pas tout** : elle refuse tout. Un
    périmètre d'écriture par défaut ne peut pas être « le système entier ».
    """
    target = normalize_table_name(table)
    if not target:
        raise ValueError(
            "Aucune cible d'écriture fournie : le périmètre d'écriture est "
            "une liste blanche explicite, jamais une valeur par défaut.")
    allowed = [normalize_table_name(name)
               for name in _as_list(allowlist) if normalize_table_name(name)]
    if not allowed:
        raise ValueError(
            f"Périmètre d'écriture vide : {target!r} refusée. Une liste "
            "blanche vide refuse tout, elle n'autorise rien.")
    if target not in allowed:
        raise ValueError(
            f"Cible {target!r} hors du périmètre d'écriture déclaré "
            f"({', '.join(sorted(allowed))}) : ajouter la table à la liste "
            "blanche de la couche resources/ est une décision explicite.")
    return target


def _as_list(values: Any) -> list[str]:
    """Liste de chaînes, robuste au SCALAIRE : une chaîne seule devient
    ``[chaîne]`` au lieu d'être itérée caractère par caractère (le piège des
    variables ``-v`` de Robot, toujours scalaires)."""
    if values is None:
        return []
    if isinstance(values, str):
        return [values]
    return [str(value) for value in values]


def table_entry_fields(signature: Any, table: Any) -> dict[str, str]:
    """Carte ``{CHAMP: localisateur}`` de l'écran de SAISIE SE16 courant,
    DÉRIVÉE de la perception au lieu d'être maintenue à la main.

    ``signature`` : la vue texte de l'écran (``Get Screen Signature``, mode
    complet ou sémantique : les deux portent l'identifiant en deuxième
    colonne ou en première, la fonction lit les jetons de la ligne). ``table``
    : la table visée, dont le nom sert de garde-fou (un identifiant d'une AUTRE
    table ne peut pas entrer dans la carte par accident).

    Les noms de champ sont TECHNIQUES (``CATEGORY``, ``MAIN_CATEGORY``), donc
    indépendants de la langue : le libellé affiché à côté du champ, lui, est
    traduit et ne sert jamais d'ancre (convention 3).

    Retourne un dict vide quand l'écran n'est pas un écran de saisie de cette
    table : c'est à l'appelant d'en faire un échec actionnable, avec le
    contexte qu'il est seul à connaître.
    """
    target = normalize_table_name(table)
    wanted = _screen_form(target)
    lines: Iterable[str]
    if isinstance(signature, str):
        lines = signature.splitlines()
    else:
        lines = [str(line) for line in (signature or [])]
    fields: dict[str, str] = {}
    for line in lines:
        for token in re.split(r"[\t ]+", line.strip()):
            match = _ENTRY_FIELD.match(token)
            if match is None:
                continue
            if _screen_form(match.group("table")) != wanted:
                continue
            fields.setdefault(match.group("field"), token)
    return fields


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1", "x")
    return bool(value)


def _as_int(value: Any, name: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{name} doit être un entier, reçu {value!r}.")


def build_reversibility_observation(
        target: Any, key_field: Any, key_value: Any, observed_at_utc: Any,
        write_channel: str = "ecc", observation_channel: str = "api",
        entity_set: Any = "", service: Any = "",
        screen_count_before: Any = 0, screen_count_after_write: Any = 0,
        screen_count_after_delete: Any = 0, api_count_before: Any = 0,
        api_count_after_write: Any = 0, api_count_after_delete: Any = 0,
        seen_by_observation_channel: Any = False,
        values_match: Any = False,
        gone_from_observation_channel: Any = False) -> dict[str, Any]:
    """Observation DATÉE de réversibilité d'un cycle d'écriture, JSON-safe.

    C'est la preuve que ``cross_channel`` ne peut pas produire : une annotation
    de métadonnées dit ce que le SERVICE permet, jamais ce qui est réellement
    réversible ni nettoyable. Le champ ``reversibility_observed`` de l'artefact
    de croisement se remplit avec ``verdict``, et avec rien d'autre.

    Le verdict est CALCULÉ, jamais fourni, et il exige les quatre preuves à la
    fois : l'écriture a été vue par l'autre canal, avec les bonnes VALEURS, la
    ligne a disparu de ce canal après suppression, et les deux comptes sont
    revenus à leur valeur initiale. Un compte revenu à l'initial ne suffit
    pas : deux écritures et une suppression donneraient le même nombre.

    Trois verdicts, et leur asymétrie porte le sens : ``reversible`` (tout est
    prouvé), ``not_observed`` (l'écriture n'a jamais été vue par l'autre canal,
    donc le cycle ne prouve rien), ``not_reversible`` (l'écriture a été vue et
    l'état initial n'est pas revenu : c'est une donnée LAISSÉE dans le
    système, la seule anomalie qui appelle une action humaine).

    L'observation ne porte ni identifiant d'utilisateur ni secret : cible,
    canaux, clé technique, entiers et horodatage UTC.
    """
    screen_before = _as_int(screen_count_before, "screen_count_before")
    screen_after_write = _as_int(screen_count_after_write,
                                 "screen_count_after_write")
    screen_after_delete = _as_int(screen_count_after_delete,
                                  "screen_count_after_delete")
    api_before = _as_int(api_count_before, "api_count_before")
    api_after_write = _as_int(api_count_after_write, "api_count_after_write")
    api_after_delete = _as_int(api_count_after_delete,
                               "api_count_after_delete")
    seen = _as_bool(seen_by_observation_channel)
    matched = _as_bool(values_match)
    gone = _as_bool(gone_from_observation_channel)
    restored = (screen_after_delete == screen_before
                and api_after_delete == api_before)
    if not (seen and matched):
        verdict = "not_observed"
    elif gone and restored:
        verdict = "reversible"
    else:
        verdict = "not_reversible"
    return {
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "target": normalize_table_name(target),
        "key_field": normalize_table_name(key_field),
        "key_value": str(key_value or ""),
        "entity_set": str(entity_set or ""),
        "service": str(service or ""),
        "write_channel": str(write_channel or ""),
        "observation_channel": str(observation_channel or ""),
        "observed_at_utc": str(observed_at_utc or ""),
        "screen_counts": {
            "before": screen_before,
            "after_write": screen_after_write,
            "after_delete": screen_after_delete,
        },
        "api_counts": {
            "before": api_before,
            "after_write": api_after_write,
            "after_delete": api_after_delete,
        },
        "seen_by_observation_channel": seen,
        "values_match": matched,
        "gone_from_observation_channel": gone,
        "initial_state_restored": restored,
        "verdict": verdict,
        "reversible": verdict == "reversible",
    }


def reversibility_observation_json(observation: Any) -> str:
    """Sérialisation déterministe de l'observation : clés triées, indentation
    fixe, fins LF. Même contrat que l'artefact de croisement, pour que deux
    exécutions sur les mêmes faits produisent le même fichier."""
    payload: Mapping[str, Any] = dict(observation or {})
    return json.dumps(payload, ensure_ascii=False, indent=2,
                      sort_keys=True) + "\n"
