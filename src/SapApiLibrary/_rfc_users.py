"""Mixin des utilisateurs de TEST du canal RFC : `Ensure Test User`,
`Delete Test User`, `Get User Logon State`, `Check User Authorization`,
`User Should Be Authorized` et `User Should Not Be Authorized`. Les rôles
(`Ensure Test Role`, `Delete Test Role`) vivent dans ``_rfc_roles.py``, dont
ce mixin hérite (découpés le 2026-10-08, convention #13).

Né du scénario 10 (2026-10-07, ABAP Platform 2023) : un test de refus
d'autorisation exige un utilisateur RESTREINT, que les images trial ne livrent
pas (tous leurs comptes portent ``SAP_ALL`` ou sont expirés). L'utilisateur se
crée par ``BAPI_USER_CREATE1`` avec un
mot de passe initial aléatoire, que l'utilisateur change lui-même
(``SUSR_USER_CHANGE_PASSWORD_RFC``) : la seule voie vers un mot de passe
PRODUCTIF sans SNC, ``BAPI_USER_CHANGE`` refusant son drapeau par un simple
avertissement (sans quoi la première connexion exige un changement, un écran
que le test ne veut pas). Aucun geste d'écriture dans le mandant ``000``.
Les objets sont faits pour RESTER : ils se créent une fois, se marquent par
leur description, et les runs suivants les retrouvent.

Le contrôle d'autorisation passe par ``AUTHORITY_CHECK``, qui accepte un
utilisateur en paramètre : le second canal, indépendant de l'écran, qui dit
si un utilisateur DÉTIENT un droit. Il répond par une exception dans tous les
cas, et « autorisé » quand on ne lui donne aucun champ (mesuré) : d'où un
champ exigé. Logique pure dans ``sapfx_common.user_provisioning``.

Typed.
"""
from __future__ import annotations

import time
from typing import Any

from sapfx_common.robot_args import NameListInput, OptionalNameListInput
from sapfx_common import security_baseline, user_provisioning
from sapfx_common.secrets import reveal_secret

from ._rfc_idoc_profiles import abap_key
from ._rfc_roles import RfcRoleKeywords


class RfcUserKeywords(RfcRoleKeywords):
    """Mixin de :class:`SapApiLibrary` : utilisateurs de test."""

    def ensure_test_user(self, user: str, password: Any, allowed_prefixes: NameListInput,
                         roles: OptionalNameListInput = None, description: str = "",
                         alias: str = "default") -> dict[str, Any]:
        """Garantit un utilisateur de dialogue de TEST et rend ``{"state",
        "user", "roles", "was_locked", "failed_logons_before"}``.

        Absent : créé (``created``), avec ``description`` en description
        technique, le marquage qui le rend reconnaissable et réutilisable. Il
        reçoit d'abord un mot de passe initial ALÉATOIRE, puis change lui-même
        pour ``password`` (``SUSR_USER_CHANGE_PASSWORD_RFC``), ce qui le rend
        PRODUCTIF : aucun changement exigé à la connexion. La voie directe,
        le drapeau productif de ``BAPI_USER_CHANGE``, est refusée sur une
        connexion sans SNC par un simple AVERTISSEMENT (``SUID01/041``) qui
        laisse le mot de passe initial (mesuré sur la 758).

        Présent : son mot de passe est VÉRIFIÉ (``SUSR_LOGIN_CHECK_RFC``),
        jamais reposé, parce que la cible refuse les 15 derniers mots de passe
        (``00/E/193``) et qu'une remise à zéro laisserait le compte sur un
        mot de passe temporaire inconnu. S'il fonctionne : ``present``. Sinon
        (mot de passe d'une autre époque, état initial) : l'utilisateur de
        test est supprimé puis recréé (``recreated``, avec ``reason``), seule
        voie vers un historique neuf (la vérification ratée a incrémenté de
        un son compteur d'échecs ; la recréation le remet à zéro). Un compte verrouillé est déverrouillé
        AVANT la vérification et ce qui a été trouvé est rendu
        (``was_locked``, ``failed_logons_before``), pour qu'un verrouillage
        par échecs d'un run précédent se voie au lieu d'être effacé en
        silence. Dans tous les cas les rôles deviennent EXACTEMENT ``roles`` ;
        un profil attribué EN DIRECT (hors rôle) fait échouer, en le nommant,
        puisque les droits du compte ne seraient plus ceux de ses rôles.

        ``description`` est OBLIGATOIRE : c'est le MARQUAGE de l'utilisateur
        de test (sa description technique). Un compte existant dont la
        description diffère n'est JAMAIS touché, ni vérifié, ni déverrouillé,
        ni supprimé : un préfixe admis ne suffit pas à faire d'un compte un
        compte de test (une vérification ratée incrémente son compteur
        d'échecs, mesuré).

        ``password`` est un `Secret` de préférence (déballé ici seulement, à
        la frontière RFC, jamais journalisé) et doit satisfaire la politique
        de mot de passe de la cible (``login/*``) : un refus est rendu avec
        son identifiant de message. ``allowed_prefixes`` est OBLIGATOIRE et
        les comptes livrés ou d'exploitation (``SAP*``, ``DDIC``,
        ``DEVELOPER`` et les autres) sont refusés. Un rôle livré (``SAP_*``,
        espace de noms) est refusé dans ``roles``, et rien n'est écrit quand la
        connexion est ouverte dans le mandant ``000``.

        Exemple :
        | ${user}=    `Ensure Test User`    SAPFX_EPM_RO    ${TEST_USER_PASSWORD}
        | ...    allowed_prefixes=SAPFX_    roles=ZSAPFX_EPM_DISPLAY
        | ...    description=SAPFX test user: EPM display only    alias=abap2023
        """
        name = user_provisioning.require_test_user(user, allowed_prefixes)
        description = user_provisioning.require_marker(name, description)
        wanted_roles = user_provisioning.require_assignable_roles(roles)
        self._require_writable_client(alias)
        before = self.get_user_logon_state(name, alias=alias)
        clear = reveal_secret(password)
        if not str(clear or ""):
            raise ValueError("Le mot de passe de l'utilisateur de test %s est vide." % name)
        result: dict[str, Any] = {"state": "present", "user": name,
                                  "was_locked": before["locked"],
                                  "failed_logons_before": before["failed_logons"]}
        if before["exists"]:
            self._require_test_marker(name, description, alias)
            if before["locked"]:
                self.call_bapi("BAPI_USER_UNLOCK", alias=alias, USERNAME=name)
                self.commit_bapi_transaction(alias)
            check = self._check_password(name, clear, alias)
            if check != "valid":
                self.call_bapi("BAPI_USER_DELETE", alias=alias, USERNAME=name)
                self.commit_bapi_transaction(alias)
                self._create_user(name, clear, description, alias)
                result.update(state="recreated", reason=check)
        else:
            self._create_user(name, clear, description, alias)
            result["state"] = "created"
        self.call_bapi(
            "BAPI_USER_ACTGROUPS_ASSIGN", alias=alias, USERNAME=name,
            ACTIVITYGROUPS=[{"AGR_NAME": role} for role in wanted_roles])
        self.commit_bapi_transaction(alias)
        after = self.get_user_logon_state(name, alias=alias)
        result["roles"] = after["roles"]
        result["direct_profiles"] = after["direct_profiles"]
        if after["direct_profiles"]:
            raise AssertionError(
                "L'utilisateur de test %s porte des profils attribués EN DIRECT (%s) : "
                "ses droits ne sont pas ceux de ses rôles. Les retirer dans SU01, ils "
                "ne sont pas retirés d'office." % (name, ", ".join(after["direct_profiles"])))
        return result

    def _create_user(self, name: str, password: str, description: str,
                     alias: str) -> None:
        """Crée l'utilisateur avec un mot de passe initial aléatoire, puis le
        fait changer par lui-même vers ``password`` : la seule voie vers un
        mot de passe productif sur une connexion sans SNC."""
        initial = user_provisioning.temporary_password()
        self.call_bapi(
            "BAPI_USER_CREATE1", alias=alias, USERNAME=name,
            LOGONDATA={"USTYP": "A"}, PASSWORD={"BAPIPWD": initial},
            ADDRESS={"FIRSTNAME": "SAPFX", "LASTNAME": name},
            DESCRIPTION={"TECHDESC": str(description)[:80]})
        self.commit_bapi_transaction(alias)
        answer = self.call_rfc(
            "SUSR_USER_CHANGE_PASSWORD_RFC", alias=alias, BNAME=name,
            PASSWORD=initial, NEW_PASSWORD=password, USE_BAPI_RETURN=1)
        user_provisioning.require_password_changed(name, answer.get("RETURN", {}))
        check = self._check_password(name, password, alias)
        if check != "valid":
            raise AssertionError(
                "L'utilisateur de test %s a été créé mais son mot de passe "
                "n'est pas utilisable (%s)." % (name, check))

    def _require_test_marker(self, name: str, description: str, alias: str) -> None:
        """Refuse tout geste sur un compte dont la description technique n'est
        pas le marquage attendu."""
        detail = self.call_bapi("BAPI_USER_GET_DETAIL", alias=alias, USERNAME=name)
        found = str((detail.get("DESCRIPTION") or {}).get("TECHDESC", "")).strip()
        user_provisioning.require_same_marker(name, found, description)

    def _check_password(self, name: str, password: str, alias: str) -> str:
        """Le verdict de ``SUSR_LOGIN_CHECK_RFC`` (``valid``,
        ``wrong_password``, ``must_change``…), sans ouvrir de session."""
        try:
            self.call_rfc("SUSR_LOGIN_CHECK_RFC", alias=alias, BNAME=name,
                          PASSWORD=password)
        except Exception as err:
            key = abap_key(err)
            if key:
                return user_provisioning.login_check_verdict(key)
            raise
        return "valid"

    def delete_test_user(self, user: str, allowed_prefixes: NameListInput, description: str,
                         alias: str = "default") -> dict[str, Any]:
        """Supprime un utilisateur de TEST et rend ``{"deleted", "user"}``.
        Un utilisateur déjà absent rend ``deleted`` faux (le nettoyage est
        idempotent) ; supprimé, ``deleted`` vrai, après avoir RELU son absence
        dans ``USR02`` (une BAPI qui répond sans erreur ne prouve rien).

        ``allowed_prefixes`` est OBLIGATOIRE (une liste vide refuse tout) et
        les comptes livrés ou d'exploitation (``SAP*``, ``DDIC``,
        ``DEVELOPER`` et les autres) sont refusés même listés, AVANT tout
        appel. ``description`` est le MARQUAGE posé par `Ensure Test User` :
        un compte dont la description technique diffère n'est pas supprimé.
        Les données que l'utilisateur a créées restent : seule son identité
        disparaît. Rien n'est supprimé dans le mandant ``000``.

        Exemple :
        | ${removed}=    `Delete Test User`    SAPFX_TMPDEL    allowed_prefixes=SAPFX_
        | ...    description=SAPFX test user: throwaway    alias=abap2023
        | Should Be True    ${removed}[deleted]
        """
        name = user_provisioning.require_test_user(user, allowed_prefixes)
        description = user_provisioning.require_marker(name, description)
        self._require_writable_client(alias)
        if not self.get_user_logon_state(name, alias=alias)["exists"]:
            return {"deleted": False, "user": name}
        self._require_test_marker(name, description, alias)
        self.call_bapi("BAPI_USER_DELETE", alias=alias, USERNAME=name)
        self.commit_bapi_transaction(alias)
        if self.get_user_logon_state(name, alias=alias)["exists"]:
            raise AssertionError(
                "BAPI_USER_DELETE a répondu sans erreur mais l'utilisateur %s "
                "est toujours dans USR02." % name)
        return {"deleted": True, "user": name}

    def get_user_logon_state(self, user: str, alias: str = "default") -> dict[str, Any]:
        """L'état d'un utilisateur, en lecture seule : ``{"exists", "locked",
        "lock_reasons", "failed_logons", "valid_to", "user_type", "roles",
        "profiles", "direct_profiles"}``. ``roles`` ne retient que les
        attributions VALIDES aujourd'hui ; ``profiles`` liste tous les profils
        de l'utilisateur et ``direct_profiles`` ceux qui ne viennent d'aucun de
        ses rôles (un ``SAP_ALL`` attribué en direct s'y voit, alors que la
        liste des rôles le tairait).

        C'est la preuve de RÉJOUABILITÉ d'un test de refus : un utilisateur
        restreint qu'une suite fait échouer à répétition finit verrouillé par
        ses échecs de connexion (``login/fails_to_user_lock``), et la suite
        suivante échoue alors pour une raison sans rapport. Lire
        ``failed_logons`` et ``locked`` en fin de run le rend visible. Un
        utilisateur absent rend ``exists`` faux, jamais une erreur.

        Exemple :
        | ${state}=    `Get User Logon State`    SAPFX_EPM_RO    alias=abap2023
        | Should Not Be True    ${state}[locked]
        """
        name = str(user).strip().upper()
        rows = self.read_rfc_table(
            "USR02", ["BNAME", "UFLAG", "LOCNT", "GLTGB", "USTYP"], alias=alias,
            options="BNAME = '%s'" % name.replace("'", "''"))
        usr02 = rows[0] if rows else None
        roles: list[str] = []
        profiles: list[str] = []
        generated: set[str] = set()
        lock = None
        if usr02 is not None:
            lock = security_baseline.classify_user_lock(usr02.get("UFLAG", "0"))
            assigned = self.read_rfc_table(
                "AGR_USERS", ["AGR_NAME", "FROM_DAT", "TO_DAT"], alias=alias,
                options="UNAME = '%s'" % name.replace("'", "''"))
            roles = user_provisioning.valid_roles(assigned, time.strftime("%Y%m%d"))
            profiles = sorted({str(r.get("PROFILE", "")).strip() for r in self.read_rfc_table(
                "UST04", ["PROFILE"], alias=alias,
                options="BNAME = '%s'" % name.replace("'", "''"))} - {""})
            generated = {str(r.get("PROFILE", "")).strip()
                         for role in roles for r in self.read_rfc_table(
                             "AGR_1016", ["PROFILE"], alias=alias,
                             options="AGR_NAME = '%s'" % role)}
        return user_provisioning.user_state(usr02, roles, lock, profiles, generated)

    def check_user_authorization(self, user: str, authorization_object: str,
                                 alias: str = "default", **fields: Any) -> str:
        """Demande au système si ``user`` détient ``authorization_object``
        pour les valeurs de champ données en arguments nommés (``TCD=SEPM_SO``,
        ``ACTVT=02``), et rend ``authorized``, ``not_authorized``,
        ``user_missing`` ou ``user_locked``.

        Le contrôle est celui du noyau (``AUTHORITY_CHECK``), sur les
        autorisations EFFECTIVES de l'utilisateur, sans qu'il ait à se
        connecter : la preuve par un second canal de ce qu'un refus d'écran
        constate. Au moins un champ est exigé, car sans champ le module répond
        « autorisé » quel que soit l'utilisateur (mesuré sur la 758), ce qui
        ferait passer une assertion de refus pour de mauvaises raisons.

        Exemple :
        | ${verdict}=    `Check User Authorization`    DEVELOPER    S_TCODE    TCD=SEPM_SO    alias=abap2023
        | Should Be Equal    ${verdict}    authorized
        """
        params = user_provisioning.check_fields(fields)
        try:
            self.call_rfc("AUTHORITY_CHECK", alias=alias, USER=str(user).strip().upper(),
                          OBJECT=str(authorization_object).strip().upper(), **params)
        except Exception as err:
            key = abap_key(err)
            if key:
                return user_provisioning.authority_verdict(key)
            raise
        raise AssertionError(
            "AUTHORITY_CHECK est revenu sans exception pour %s, une issue que "
            "le module ne produit pas sur les releases mesurées : aucun "
            "verdict n'en est déduit."
            % user_provisioning.describe_check(user, authorization_object, fields))

    def user_should_be_authorized(self, user: str, authorization_object: str,
                                  alias: str = "default", **fields: Any) -> None:
        """Échoue sauf si `Check User Authorization` rend ``authorized``.

        Exemple :
        | `User Should Be Authorized`    DEVELOPER    S_TCODE    TCD=SEPM_SO    alias=abap2023
        """
        verdict = self.check_user_authorization(user, authorization_object,
                                                alias=alias, **fields)
        if verdict != "authorized":
            raise AssertionError(
                "Autorisation attendue, verdict %s : %s."
                % (verdict, user_provisioning.describe_check(user, authorization_object, fields)))

    def user_should_not_be_authorized(self, user: str, authorization_object: str,
                                      alias: str = "default", **fields: Any) -> None:
        """Échoue sauf si `Check User Authorization` rend ``not_authorized``.
        Un utilisateur ABSENT ou VERROUILLÉ échoue aussi : son refus ne
        prouverait rien sur ses droits.

        Exemple :
        | `User Should Not Be Authorized`    SAPFX_EPM_RO    S_TCODE    TCD=SEPM_SO    alias=abap2023
        """
        verdict = self.check_user_authorization(user, authorization_object,
                                                alias=alias, **fields)
        if verdict != "not_authorized":
            raise AssertionError(
                "Refus attendu, verdict %s : %s. Un utilisateur absent ou "
                "verrouillé ne prouve rien sur ses droits."
                % (verdict, user_provisioning.describe_check(user, authorization_object, fields)))
