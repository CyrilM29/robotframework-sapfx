"""Utilisateurs et rôles de TEST d'un système ABAP, logique pure.

Né du scénario 10 (2026-10-07, ABAP Platform 2023) : tester qu'un utilisateur
restreint est REFUSÉ suppose qu'un tel utilisateur existe, or les images trial
ne livrent que des comptes ``SAP_ALL`` (six comptes mesurés sur la 2023, dont
un à validité échue). Le provisionner fait partie du test, et le refaire à
chaque run serait aussi faux que de le supposer présent : les objets se
créent une fois, se marquent, et se réutilisent (règle des données propres
marquées du dépôt).

Quatre règles encodées ici, sur le patron de ``idoc_profiles`` :

* une LISTE BLANCHE de préfixes de noms est obligatoire, et une liste vide
  refuse tout au lieu d'autoriser tout ;
* les comptes livrés ou d'exploitation (``SAP*``, ``DDIC``, ``DEVELOPER``…)
  ne se créent, ne se modifient ni ne se suppriment JAMAIS, même listés ;
* un rôle déjà présent mais DIFFÉRENT n'est pas réécrit : l'écart est refusé
  transaction par transaction ;
* un contrôle d'autorisation SANS champ est refusé : le module
  ``AUTHORITY_CHECK`` répond alors « autorisé » quel que soit l'utilisateur
  (mesuré), ce qui ferait d'une assertion de refus un test vert à l'envers.

Typed.
"""
from __future__ import annotations

import secrets
import string
from typing import Any, Mapping, Sequence

from sapfx_common.robot_args import as_name_list

#: Comptes livrés avec les images, ou d'exploitation, jamais touchés.
PROTECTED_USERS = ("SAP*", "DDIC", "DEVELOPER", "BWDEVELOPER", "TMSADM",
                   "SAPCPIC", "EARLYWATCH", "WF-BATCH", "SAP_WFRT",
                   "SAPSUPPORT")

#: Préfixes de rôles livrés par SAP : un rôle de test ne s'y nomme jamais.
PROTECTED_ROLE_PREFIXES = ("SAP_", "/")

#: Issues du module ``AUTHORITY_CHECK``, qui répond par une EXCEPTION dans
#: tous les cas (mesuré sur la 758) : exception ABAP vers verdict.
AUTHORITY_OUTCOMES = {
    "USER_IS_AUTHORIZED": "authorized",
    "USER_NOT_AUTHORIZED": "not_authorized",
    "USER_DONT_EXIST": "user_missing",
    "USER_IS_LOCKED": "user_locked",
}

#: Les dix couples champ/valeur qu'accepte ``AUTHORITY_CHECK``.
MAX_CHECK_FIELDS = 10


def _allowed_prefixes(allowed: Any) -> list[str]:
    prefixes = [name.upper() for name in as_name_list(allowed, "allowed_prefixes")]
    if not prefixes:
        raise ValueError(
            "allowed_prefixes est obligatoire et ne peut pas être vide : une "
            "liste vide refuse tout (liste blanche des préfixes de noms que "
            "la suite a le droit de créer, modifier ou supprimer).")
    return prefixes


def require_test_user(name: Any, allowed: Any) -> str:
    """Le nom d'utilisateur en majuscules s'il commence par un préfixe de la
    liste blanche et n'est pas un compte protégé, sinon un refus qui nomme la
    règle violée."""
    prefixes = _allowed_prefixes(allowed)
    wanted = str(name).strip().upper()
    if not wanted:
        raise ValueError("Le nom d'utilisateur est vide.")
    if len(wanted) > 12:
        raise ValueError("Le nom d'utilisateur %r dépasse 12 caractères (USR02-BNAME)." % wanted)
    if wanted in PROTECTED_USERS:
        raise ValueError(
            "L'utilisateur %s est un compte livré ou d'exploitation : il ne se "
            "crée, ne se modifie ni ne se supprime jamais par une suite, même "
            "listé." % wanted)
    if not any(wanted.startswith(prefix) for prefix in prefixes):
        raise ValueError(
            "L'utilisateur %s n'est pas dans la liste blanche des préfixes "
            "autorisés (%s)." % (wanted, ", ".join(prefixes)))
    return wanted


def require_test_role(name: Any, allowed: Any) -> str:
    """Le nom de rôle en majuscules s'il commence par un préfixe de la liste
    blanche et n'est pas un rôle livré (``SAP_*``, espace de noms), sinon un
    refus."""
    prefixes = _allowed_prefixes(allowed)
    wanted = str(name).strip().upper()
    if not wanted:
        raise ValueError("Le nom de rôle est vide.")
    if len(wanted) > 30:
        raise ValueError("Le nom de rôle %r dépasse 30 caractères (AGR_NAME)." % wanted)
    if wanted.startswith(PROTECTED_ROLE_PREFIXES):
        raise ValueError(
            "Le rôle %s porte un préfixe livré par SAP (%s) : un rôle de test "
            "ne s'y nomme jamais." % (wanted, ", ".join(PROTECTED_ROLE_PREFIXES)))
    if not any(wanted.startswith(prefix) for prefix in prefixes):
        raise ValueError(
            "Le rôle %s n'est pas dans la liste blanche des préfixes autorisés "
            "(%s)." % (wanted, ", ".join(prefixes)))
    return wanted


def require_assignable_roles(roles: Any) -> list[str]:
    """Les rôles à attribuer à un utilisateur de test, en majuscules ; un rôle
    livré (``SAP_*``, espace de noms) est refusé : attribué à un compte de
    test, il lui donnerait des droits qu'aucun test restreint ne doit
    porter."""
    names = normalize_names(roles, "roles")
    delivered = [name for name in names if name.startswith(PROTECTED_ROLE_PREFIXES)]
    if delivered:
        raise ValueError(
            "Rôle(s) livré(s) par SAP refusé(s) pour un utilisateur de test : %s. "
            "Un compte de test ne porte que des rôles de test." % ", ".join(delivered))
    return names


def require_writable_client(client: Any) -> str:
    """Le mandant de la connexion s'il n'est pas ``000`` : on n'y crée, ne
    modifie ni ne supprime jamais un utilisateur ou un rôle (mandant de
    référence, règle du dépôt)."""
    value = str(client or "").strip()
    if not value:
        raise ValueError(
            "Le mandant de la connexion RFC est illisible : aucun utilisateur ni "
            "rôle de test n'est écrit sans le connaître.")
    if value == "000":
        raise ValueError(
            "La connexion RFC est ouverte dans le mandant 000 (mandant de "
            "référence) : on n'y écrit jamais un utilisateur ni un rôle de test.")
    return value


def normalize_names(value: Any, argument: str) -> list[str]:
    """Liste de noms en majuscules, dédoublonnée, ordre conservé."""
    seen: list[str] = []
    for name in as_name_list(value, argument):
        upper = name.strip().upper()
        if upper and upper not in seen:
            seen.append(upper)
    return seen


def transaction_differences(existing: Sequence[str], wanted: Sequence[str]) -> list[str]:
    """Écarts entre les transactions d'un rôle existant et celles demandées,
    en phrases (vide = identiques, l'ordre ne compte pas)."""
    have = {name.strip().upper() for name in existing if name.strip()}
    want = {name.strip().upper() for name in wanted if name.strip()}
    diffs = []
    missing = sorted(want - have)
    extra = sorted(have - want)
    if missing:
        diffs.append("absentes du rôle : %s" % ", ".join(missing))
    if extra:
        diffs.append("en trop dans le rôle : %s" % ", ".join(extra))
    return diffs


def manual_authorizations(authorizations: Any,
                          transactions: Sequence[str] = ()) -> list[dict[str, str]]:
    """Lignes ``TVORDATA`` (objet, numéro, champ, bas, haut) depuis une liste
    de dicts ``{object, field, low, high?, auth?}``, précédées d'une valeur
    ``S_TCODE`` ``TCD`` par transaction. Le rôle est ainsi ENTIÈREMENT
    explicite : le générateur, appelé sans reconstruction depuis le menu,
    n'y ajoute rien (ni proposition SU24, ni étoile).

    ``LFDNR`` numérote l'AUTORISATION, pas la valeur (mesuré sur la 758 : un
    second ``RFC_NAME`` en ``LFDNR`` 002 devenait une seconde autorisation sans
    ``RFC_TYPE`` ni ``ACTVT``, et la génération échouait par ``S#/S/336``).
    Toutes les valeurs d'un objet vont donc dans la même autorisation (une
    ligne par valeur, même ``LFDNR``) ; ``auth`` (1, 2…) en sépare plusieurs.
    Objet ou champ manquant refusé : une autorisation sans champ ouvre tout."""
    entries: list[Any] = [{"object": "S_TCODE", "field": "TCD", "low": code}
                          for code in transactions]
    if isinstance(authorizations, Mapping):
        entries.append(authorizations)
    elif authorizations not in (None, ""):
        entries.extend(authorizations)
    rows: list[dict[str, str]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise ValueError("authorizations[%d] doit être un dictionnaire "
                             "{object, field, low}, reçu %r." % (index, entry))
        obj = str(entry.get("object", "")).strip().upper()
        field = str(entry.get("field", "")).strip().upper()
        low = str(entry.get("low", "")).strip()
        high = str(entry.get("high", "") or "").strip()
        if not obj or not field or not low:
            raise ValueError(
                "authorizations[%d] exige object, field et low non vides (reçu "
                "%r) : une valeur vide n'autorise rien et un champ absent "
                "ouvre tout." % (index, dict(entry)))
        try:
            group = int(entry.get("auth", 1) or 1)
        except (TypeError, ValueError) as err:
            raise ValueError("authorizations[%d] : auth doit être un entier, reçu %r."
                             % (index, entry.get("auth"))) from err
        rows.append({"OBJECT": obj, "LFDNR": "%03d" % group,
                     "FIELD": field, "LOW": low, "HIGH": high})
    return rows


#: Issues de ``SUSR_LOGIN_CHECK_RFC`` (exception ABAP vers verdict). Une
#: vérification qui ne lève rien vaut ``valid``.
LOGIN_CHECK_OUTCOMES = {
    "WRONG_PASSWORD": "wrong_password",
    "PASSWORD_EXPIRED": "must_change",
    "USER_LOCKED": "locked",
    "USER_NOT_ACTIVE": "inactive",
    "PASSWORD_ATTEMPTS_LIMITED": "attempts_limited",
    "WAIT": "wait",
    "NO_CHECK_FOR_THIS_USER": "no_check",
}


def login_check_verdict(exception_key: str) -> str:
    """Le verdict d'une vérification de mot de passe depuis la clé
    d'exception ABAP ; une clé inconnue est REFUSÉE, jamais lue comme un
    mot de passe valide."""
    key = str(exception_key or "").strip().upper()
    if key in LOGIN_CHECK_OUTCOMES:
        return LOGIN_CHECK_OUTCOMES[key]
    raise AssertionError(
        "SUSR_LOGIN_CHECK_RFC a rendu %r, une issue hors carte (%s)."
        % (exception_key, ", ".join(sorted(LOGIN_CHECK_OUTCOMES))))


def temporary_password(length: int = 20) -> str:
    """Un mot de passe initial aléatoire, jetable, qui satisfait les
    politiques usuelles (majuscule, minuscule, chiffre, caractère spécial) :
    il ne sert qu'entre la création et le premier changement."""
    alphabet = string.ascii_letters + string.digits
    body = "".join(secrets.choice(alphabet) for _ in range(max(length - 4, 8)))
    return "Qa7" + body + "!"


def require_password_changed(user: str, answer: Mapping[str, Any]) -> None:
    """Échoue sauf si ``SUSR_USER_CHANGE_PASSWORD_RFC`` a rendu un succès
    (type ``S``), en nommant le refus par son identifiant (``00/E/193`` :
    mot de passe dans l'historique)."""
    kind = str(answer.get("TYPE", "")).strip().upper()
    if kind == "S":
        return
    identity = "%s/%s/%s" % (str(answer.get("ID", "")).strip(), kind or "?",
                             str(answer.get("NUMBER", "")).strip())
    raise AssertionError(
        "Le changement de mot de passe de %s a été refusé (%s) : %s"
        % (user, identity, str(answer.get("MESSAGE", "")).strip()))


def check_fields(fields: Mapping[str, Any]) -> dict[str, str]:
    """Les paramètres ``FIELDn``/``VALUEn`` d'``AUTHORITY_CHECK`` depuis
    ``{champ: valeur}``. Zéro champ est REFUSÉ (le module répond alors
    « autorisé » à tout utilisateur), plus de dix aussi."""
    items = [(str(k).strip().upper(), str(v).strip()) for k, v in fields.items()]
    items = [(k, v) for k, v in items if k]
    if not items:
        raise ValueError(
            "Un contrôle d'autorisation exige au moins un champ (ex. "
            "TCD=SEPM_SO) : sans champ, AUTHORITY_CHECK répond « autorisé » "
            "quel que soit l'utilisateur, mesuré sur la 758.")
    if len(items) > MAX_CHECK_FIELDS:
        raise ValueError("AUTHORITY_CHECK accepte au plus %d champs, reçu %d."
                         % (MAX_CHECK_FIELDS, len(items)))
    params: dict[str, str] = {}
    for position, (field, value) in enumerate(items, 1):
        params["FIELD%d" % position] = field
        params["VALUE%d" % position] = value
    return params


def authority_verdict(exception_key: str) -> str:
    """Le verdict d'un appel ``AUTHORITY_CHECK`` depuis sa clé d'exception
    ABAP ; une clé inconnue est REFUSÉE plutôt que lue comme un refus."""
    key = str(exception_key or "").strip().upper()
    if key in AUTHORITY_OUTCOMES:
        return AUTHORITY_OUTCOMES[key]
    raise AssertionError(
        "AUTHORITY_CHECK a rendu %r, une issue hors carte (%s) : ni un refus "
        "ni une autorisation ne peuvent en être déduits."
        % (exception_key, ", ".join(sorted(AUTHORITY_OUTCOMES))))


def describe_check(user: str, obj: str, fields: Mapping[str, Any]) -> str:
    """Le contrôle en clair, pour un message : ``S_TCODE (TCD=SEPM_SO) pour X``."""
    pairs = ", ".join("%s=%s" % (str(k).upper(), v) for k, v in fields.items())
    return "%s (%s) pour %s" % (str(obj).upper(), pairs, str(user).upper())


def user_state(usr02: Mapping[str, Any] | None, roles: Sequence[str],
               lock: Mapping[str, Any] | None, profiles: Sequence[str] = (),
               generated_profiles: Any = ()) -> dict[str, Any]:
    """L'état JSON-safe d'un utilisateur : existence, verrou (bits
    ``UFLAG`` déjà classés), échecs de connexion, validité, type, rôles,
    profils, et profils DIRECTS (ceux qu'aucun rôle n'a générés)."""
    direct = sorted(set(profiles) - set(generated_profiles))
    if not usr02:
        return {"exists": False, "locked": False, "lock_reasons": [],
                "failed_logons": 0, "valid_to": "", "user_type": "",
                "roles": sorted(roles), "profiles": [], "direct_profiles": []}
    raw = str(usr02.get("LOCNT", "0")).strip() or "0"
    try:
        failed = int(raw)
    except ValueError as err:
        raise AssertionError("USR02-LOCNT illisible : %r." % raw) from err
    valid_to = str(usr02.get("GLTGB", "")).strip()
    return {
        "exists": True,
        "locked": bool((lock or {}).get("locked")),
        "lock_reasons": list((lock or {}).get("reasons", [])),
        "failed_logons": failed,
        "valid_to": "" if valid_to in ("", "00000000") else valid_to,
        "user_type": str(usr02.get("USTYP", "")).strip(),
        "roles": sorted(roles),
        "profiles": sorted(profiles),
        "direct_profiles": direct,
    }


def valid_roles(assignments: Sequence[Mapping[str, Any]], today: str) -> list[str]:
    """Les rôles dont l'attribution (``AGR_USERS``) est valide le jour
    ``today`` (``AAAAMMJJ``) ; une date vide ne borne rien."""
    names = set()
    for row in assignments:
        name = str(row.get("AGR_NAME", "")).strip()
        start = str(row.get("FROM_DAT", "")).strip().replace("00000000", "")
        end = str(row.get("TO_DAT", "")).strip().replace("00000000", "")
        if name and (not start or start <= today) and (not end or today <= end):
            names.add(name)
    return sorted(names)


def describe_values(values: Any) -> list[str]:
    """Valeurs d'autorisation ``(objet, champ, bas, haut)`` en clair, triées."""
    return ["%s %s=%s%s" % (obj, field, low, "-" + high if high else "")
            for obj, field, low, high in sorted(values)]


def role_profile_verdict(role: str, profile_rows: Sequence[Mapping[str, Any]],
                         role_values: Any, profile_values: Any) -> dict[str, Any]:
    """Le profil GÉNÉRÉ d'un rôle porte-t-il ses droits actuels ?

    ``profile_rows`` : les lignes ``AGR_1016`` du rôle (``PROFILE``,
    ``GENERATED``, ``PSTATE``) ; ``role_values`` : les valeurs du rôle
    (``AGR_1251`` hors lignes supprimées) ; ``profile_values`` : celles que
    porte réellement le profil actif (``UST12``), en ``(objet, champ, bas,
    haut)``. Mesuré le 2026-10-08 sur la 754 : une modification des
    autorisations SANS génération laisse ``GENERATED`` à ``X``, vide
    ``PSTATE`` (``A`` après génération) et laisse le profil à ses anciennes
    valeurs, donc les droits EFFECTIFS restent ceux d'avant. Rend
    ``{"current", "profiles", "reasons", "missing_in_profile",
    "extra_in_profile"}`` ; ``current`` n'est vrai que sans aucune raison."""
    profiles = sorted({str(r.get("PROFILE", "")).strip() for r in profile_rows} - {""})
    reasons: list[str] = []
    if not profiles:
        reasons.append("aucun profil généré (aucune ligne AGR_1016)")
    for row in profile_rows:
        name = str(row.get("PROFILE", "")).strip()
        if str(row.get("GENERATED", "")).strip() != "X":
            reasons.append("profil %s non généré (GENERATED vide)" % name)
        elif str(row.get("PSTATE", "")).strip() != "A":
            reasons.append("profil %s modifié depuis sa génération (PSTATE %r, A "
                           "attendu)" % (name, str(row.get("PSTATE", "")).strip()))
    missing = describe_values(set(role_values) - set(profile_values))
    extra = describe_values(set(profile_values) - set(role_values))
    if missing:
        reasons.append("valeurs du rôle absentes du profil : %s" % ", ".join(missing))
    if extra:
        reasons.append("valeurs du profil absentes du rôle : %s" % ", ".join(extra))
    return {"current": not reasons, "profiles": profiles, "reasons": reasons,
            "missing_in_profile": missing, "extra_in_profile": extra}


def require_current_profile(role: str, verdict: Mapping[str, Any]) -> None:
    """Échoue en nommant l'écart quand le profil du rôle ne porte pas ses
    droits actuels : un rôle modifié sans régénération passerait sinon pour
    conforme alors que ses utilisateurs ont les droits de l'ancien profil."""
    if not verdict["current"]:
        raise AssertionError(
            "Le profil du rôle %s ne porte pas ses droits actuels (%s) : ses "
            "utilisateurs ont les droits de l'ancien profil. Le régénérer dans PFCG "
            "(onglet Authorizations), ou supprimer le rôle par `Delete Test Role` "
            "et le recréer ; il n'est pas régénéré d'office."
            % (role, "; ".join(verdict["reasons"])))


def require_marker(user: str, description: Any) -> str:
    """Le marquage (description technique) d'un utilisateur de test : exigé,
    80 caractères au plus (``TECHDESC``)."""
    marker = str(description or "").strip()
    if not marker:
        raise ValueError(
            "description est obligatoire pour l'utilisateur de test %s : c'est "
            "son MARQUAGE, sans lequel un compte existant au préfixe admis ne se "
            "distingue pas d'un compte humain." % user)
    if len(marker) > 80:
        raise ValueError("La description de %s dépasse 80 caractères (TECHDESC)." % user)
    return marker


def require_same_marker(user: str, found: str, expected: str) -> None:
    """Échoue si le compte existant ne porte pas le marquage attendu."""
    if found.strip() != expected.strip():
        raise AssertionError(
            "Le compte %s existe mais n'est pas marqué comme cet utilisateur de "
            "test (description technique %r, attendue %r) : il n'est ni "
            "vérifié, ni déverrouillé, ni supprimé." % (user, found, expected))


#: Le groupe d'autorisation contrôlé pour une table qui n'en déclare aucun.
DEFAULT_TABLE_GROUP = "&NC&"


def table_authorization_group(table: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Le groupe d'autorisation EFFECTIF d'une table, depuis ses lignes
    ``TDDAT`` (``CCLASS``) : ``{table, declared, class, group}``. Une table
    sans ligne OU à classe vide est contrôlée sous ``&NC&`` (mesuré le
    2026-10-12 sur la 758 : SU53 nomme ``DICBERCLS=&NC&`` pour ``SCARR``, sans
    ligne, comme pour ``DD02L``, à classe vide). Plus d'une ligne est refusée :
    la clé de ``TDDAT`` est le nom de table, deux lignes désignent une lecture
    fausse, jamais un choix à faire."""
    name = str(table).strip().upper()
    if len(rows) > 1:
        raise AssertionError("TDDAT carries %d lines for table %s: one at most is "
                             "expected, the read is wrong." % (len(rows), name))
    declared_class = str(rows[0].get("CCLASS", "")).strip() if rows else ""
    return {"table": name, "declared": bool(rows), "class": declared_class,
            "group": declared_class or DEFAULT_TABLE_GROUP}
