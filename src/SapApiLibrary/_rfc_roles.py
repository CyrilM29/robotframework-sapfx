"""Mixin des rôles PFCG de TEST du canal RFC : `Ensure Test Role` et
`Delete Test Role`.

Extrait de ``_rfc_users.py`` le 2026-10-08 (convention #13), quand la
vérification du profil généré l'aurait fait dépasser 500 lignes : les rôles
d'un côté, les utilisateurs et les contrôles d'autorisation de l'autre, qui
héritent d'ici.

Un rôle se crée par ``PRGN_RFC_CREATE_ACTIVITY_GROUP`` et son profil se
génère par ``PRGN_AUTO_GENERATE_PROFILE_NEW``. Ce qu'un rôle ACCORDE n'est
pas ce qu'il DÉCLARE : ses utilisateurs ont les droits du profil généré, et
un rôle modifié sans régénération garde ceux de l'ancien profil. Mesuré le
2026-10-08 sur la 754 : la modification vide ``AGR_1016-PSTATE`` (``A``
après génération), laisse ``GENERATED`` à ``X``, et le profil (``UST12``)
garde ses anciennes valeurs. `Ensure Test Role` confronte donc les valeurs du
rôle (``AGR_1251``) à celles du profil actif, en plus de l'état de génération.
Logique pure dans ``sapfx_common.user_provisioning``.

Typed.
"""
from __future__ import annotations

from typing import Any, Optional

from sapfx_common.robot_args import NameListInput
from sapfx_common.argument_types import TableNameInput
from sapfx_common import user_provisioning
from sapfx_common.rfc_tables import abap_quote

from ._rfc_idoc_profiles import abap_key
from ._rfc_surface import RfcSurfaceKeywords


class RfcRoleKeywords(RfcSurfaceKeywords):
    """Mixin de :class:`SapApiLibrary` : rôles de test."""

    def ensure_test_role(self, role: str, transactions: NameListInput,
                         allowed_prefixes: NameListInput,
                         description: str = "", authorizations: Any = None,
                         alias: str = "default") -> dict[str, Any]:
        """Garantit un rôle PFCG de test, de façon idempotente, et rend
        ``{"state", "role", "transactions", "profile"}``.

        Absent : créé avec ses ``transactions`` (menu du rôle), puis son
        profil GÉNÉRÉ (``state`` vaut ``created``). Le rôle est ENTIÈREMENT
        explicite : ``S_TCODE`` pour chaque transaction, plus
        ``authorizations``, une liste de ``{object, field, low, high?}`` (par
        exemple ``S_TABU_NAM`` ``ACTVT`` ``03`` pour un affichage seul). Rien
        d'autre n'y entre, ni proposition SU24 ni étoile : un rôle de test
        restreint ne s'élargit pas en silence, et il ne dépend pas de SU25,
        jamais exécuté sur les images trial (le générateur refuse alors de
        reconstruire depuis le menu, ``S#/S/318``). Un rôle dont la création
        s'est interrompue avant la génération est COMPLÉTÉ (``completed``),
        à condition que son titre soit ``description`` : compléter est une
        écriture, refusée sur un rôle que ce marqueur ne désigne pas.

        Présent avec exactement les mêmes transactions et exactement les
        mêmes valeurs (``S_TCODE`` compris) : laissé (``present``). Présent
        mais différent, une valeur manquante comme une valeur EN TROP : REFUSÉ
        en nommant l'écart, jamais réécrit (un rôle restreint élargi par
        ailleurs ne passe pas pour le rôle demandé).

        Le PROFIL est vérifié aussi (depuis le 2026-10-08) : un rôle n'accorde
        que ce que porte son profil généré. Un rôle modifié dans PFCG sans
        régénération (``AGR_1016-PSTATE`` vide), ou dont le profil actif ne
        porte pas exactement ses valeurs, est REFUSÉ en nommant l'écart, même
        quand ses valeurs déclarées sont celles demandées : ses utilisateurs
        auraient les droits de l'ancien profil. Il n'est pas régénéré d'office.

        ``allowed_prefixes`` est OBLIGATOIRE (liste blanche, une liste vide
        refuse tout) et un rôle livré (``SAP_*``, espace de noms) est refusé
        même listé. Rien n'est écrit quand la connexion est ouverte dans le
        mandant ``000``.

        Exemple :
        | ${role}=    `Ensure Test Role`    ZSAPFX_EPM_DISPLAY    SE16
        | ...    allowed_prefixes=ZSAPFX_    description=SAPFX test role: EPM tables display only
        | ...    authorizations=${display_only}    alias=abap2023
        """
        name = user_provisioning.require_test_role(role, allowed_prefixes)
        self._require_writable_client(alias)
        tcodes = user_provisioning.normalize_names(transactions, "transactions")
        if not tcodes and authorizations in (None, "", []):
            raise ValueError(
                "Le rôle %s n'aurait ni transaction ni autorisation : il "
                "n'accorderait rien et ne prouverait rien." % name)
        manual = user_provisioning.manual_authorizations(authorizations, tcodes)
        if not self._role_exists(name, alias):
            self.call_rfc(
                "PRGN_RFC_CREATE_ACTIVITY_GROUP", alias=alias,
                ACTIVITY_GROUP=name, ACTIVITY_GROUP_TEXT=str(description)[:80],
                NO_DIALOG="X", ONLY_TCODE_ASSIGNMENT="X",
                TCODES=[{"TCODE": code} for code in tcodes])
            self._generate_role_profile(name, manual, alias)
            user_provisioning.require_current_profile(
                name, self._role_profile_verdict(name, alias))
            return {"state": "created", "role": name, "transactions": tcodes,
                    "profile": self._role_profile(name, alias)}
        existing = self._role_transactions(name, alias)
        diffs = user_provisioning.transaction_differences(existing, tcodes)
        if not diffs and self._role_profile(name, alias) is None:
            # Un rôle jamais généré est l'état qu'une création interrompue
            # laisse (mesuré : PROFGEN_TABLES_NOT_UPDATED après l'écriture de
            # la définition). Le compléter n'est pas le réécrire, mais c'est
            # une ÉCRITURE sur un objet existant : son titre doit être le
            # marqueur demandé, comme avant une suppression (relevé au rejeu
            # des exemples du 2026-10-14, la vérification manquait ici).
            user_provisioning.require_same_marker(
                name, self._role_title(name, alias), str(description or ""), kind="role")
            self._generate_role_profile(name, manual, alias)
            missing, extra = self._role_value_differences(name, manual, alias)
            if missing or extra:
                raise AssertionError(
                    "Le rôle %s a été complété mais ne porte pas exactement les "
                    "valeurs demandées (absentes : %s ; en trop : %s)."
                    % (name, ", ".join(missing) or "aucune", ", ".join(extra) or "aucune"))
            user_provisioning.require_current_profile(
                name, self._role_profile_verdict(name, alias))
            return {"state": "completed", "role": name, "transactions": sorted(existing),
                    "profile": self._role_profile(name, alias)}
        missing, extra = self._role_value_differences(name, manual, alias)
        if missing:
            diffs.append("valeurs d'autorisation absentes : %s" % ", ".join(missing))
        if extra:
            diffs.append("valeurs d'autorisation EN TROP : %s" % ", ".join(extra))
        if diffs:
            raise AssertionError(
                "Le rôle %s existe déjà et DIFFÈRE de celui demandé (%s) ; il "
                "n'est pas réécrit. Le corriger dans PFCG ou demander le rôle "
                "tel qu'il est." % (name, "; ".join(diffs)))
        user_provisioning.require_current_profile(name, self._role_profile_verdict(name, alias))
        return {"state": "present", "role": name, "transactions": sorted(existing),
                "profile": self._role_profile(name, alias)}

    def _require_writable_client(self, alias: str) -> None:
        """Refuse d'écrire dans le mandant ``000``, lu sur la connexion."""
        attributes = self.get_rfc_connection_attributes(alias)
        user_provisioning.require_writable_client(attributes.get("client"))

    def get_role_authorizations(self, role: str, alias: str = "default") -> dict[str, Any]:
        """Lit un rôle PFCG SANS rien écrire et rend ``{"role", "exists",
        "title", "values", "profile"}`` : ``values`` est la liste triée des
        valeurs DÉCLARÉES (``AGR_1251`` hors lignes supprimées, ``{object,
        field, low, high}``, ``S_TCODE`` compris), ``profile`` le verdict du
        profil GÉNÉRÉ (``current``, ``profiles``, ``reasons``,
        ``missing_in_profile``, ``extra_in_profile``) : ce qu'un rôle accorde
        est ce que porte son profil, pas ce qu'il déclare. Un rôle absent rend
        ``exists`` faux, des valeurs vides et ``profile`` à ``None``.

        La voie de lecture d'une campagne d'habilitations, là où `Ensure Test
        Role` est un keyword d'ÉCRITURE soumis à la politique de session.

        Exemple :
        | ${role}=    `Get Role Authorizations`    ZSAPFX_TABU_DIS_SC    alias=abap2023
        | Should Be True    ${role}[exists]
        | Should Be True    ${role}[profile][current]
        """
        name = str(role).strip().upper()
        if not self._role_exists(name, alias):
            return {"role": name, "exists": False, "title": "", "values": [],
                    "profile": None}
        values = [{"object": obj, "field": field, "low": low, "high": high}
                  for obj, field, low, high in sorted(self._role_values(name, alias))]
        return {"role": name, "exists": True, "title": self._role_title(name, alias),
                "values": values, "profile": self._role_profile_verdict(name, alias)}

    def get_table_authorization_group(self, table: TableNameInput,
                                      alias: str = "default") -> dict[str, Any]:
        """Le groupe d'autorisation EFFECTIF de ``table``, celui que contrôle
        ``S_TABU_DIS`` (champ ``DICBERCLS``), lu dans ``TDDAT`` : rend
        ``{table, declared, class, group}``. ``declared`` dit si la table a une
        ligne, ``class`` la classe lue, ``group`` le groupe contrôlé. Une table
        SANS ligne ou à classe VIDE est contrôlée sous ``&NC&`` (mesuré sur la
        758 : SU53 nomme ``&NC&`` pour ``SCARR``, sans ligne, et pour
        ``DD02L``, à classe vide). Lecture seule.

        Exemple :
        | ${t000}=    `Get Table Authorization Group`    T000    alias=abap2023
        | Should Be Equal    ${t000}[group]    SS
        | ${scarr}=    `Get Table Authorization Group`    SCARR    alias=abap2023
        | Should Be Equal    ${scarr}[group]    &NC&
        """
        name = str(table).strip().upper()
        rows = self.read_rfc_table("TDDAT", ["TABNAME", "CCLASS"], alias=alias,
                                   options="TABNAME = %s" % abap_quote(name))
        return user_provisioning.table_authorization_group(name, rows)

    def role_should_grant_exactly(self, role: str, transactions: NameListInput,
                                  authorizations: Any = None,
                                  alias: str = "default") -> dict[str, Any]:
        """Échoue sauf si le rôle ``role`` existe, déclare EXACTEMENT
        ``S_TCODE`` pour chaque transaction de ``transactions`` plus les
        ``authorizations`` (liste de ``{object, field, low, high?}``, la forme
        d'`Ensure Test Role`), ni moins ni plus, et si son profil généré porte
        exactement ces valeurs. L'échec nomme les valeurs absentes, en trop, ou
        la raison pour laquelle le profil n'est pas à jour. Lecture seule ; rend
        `Get Role Authorizations`.

        Exemple :
        | ${a1}=    Create Dictionary    object=S_TABU_DIS    field=ACTVT    low=03
        | ${a2}=    Create Dictionary    object=S_TABU_DIS    field=DICBERCLS    low=SC
        | ${auths}=    Create List    ${a1}    ${a2}
        | `Role Should Grant Exactly`    ZSAPFX_TABU_DIS_SC    SE16
        | ...    authorizations=${auths}    alias=abap2023
        """
        name = str(role).strip().upper()
        tcodes = user_provisioning.normalize_names(transactions, "transactions")
        manual = user_provisioning.manual_authorizations(authorizations, tcodes)
        read = self.get_role_authorizations(name, alias)
        if not read["exists"]:
            raise AssertionError("Le rôle %s n'existe pas sur cette cible." % name)
        missing, extra = self._role_value_differences(name, manual, alias)
        reasons = []
        if missing:
            reasons.append("valeurs absentes : %s" % ", ".join(missing))
        if extra:
            reasons.append("valeurs EN TROP : %s" % ", ".join(extra))
        if not read["profile"]["current"]:
            reasons.append("profil : %s" % "; ".join(read["profile"]["reasons"]))
        if reasons:
            raise AssertionError("Le rôle %s n'accorde pas exactement ce qui est "
                                 "attendu (%s)." % (name, " ; ".join(reasons)))
        return read

    def delete_test_role(self, role: str, allowed_prefixes: NameListInput, description: str,
                         alias: str = "default") -> dict[str, Any]:
        """Supprime un rôle PFCG de TEST (et son profil généré) et rend
        ``{"deleted", "role"}``, après avoir RELU son absence. Un rôle déjà
        absent rend ``deleted`` faux.

        Un rôle encore ATTRIBUÉ est refusé en nommant les utilisateurs qui le
        portent : le retirer en silence changerait les droits d'un compte
        qu'un autre test réutilise peut-être (les utilisateurs de test sont
        archivés pour cela). Supprimer d'abord ces utilisateurs, ou leur
        réattribuer d'autres rôles par `Ensure Test User`. ``allowed_prefixes``
        est OBLIGATOIRE et un rôle livré (``SAP_*``, espace de noms) est
        refusé même listé. ``description`` est le MARQUAGE posé par
        `Ensure Test Role` (le titre du rôle) : un rôle dont le titre diffère
        n'est pas supprimé, comme pour les utilisateurs. Rien n'est supprimé
        dans le mandant ``000``.

        Exemple :
        | ${removed}=    `Delete Test Role`    ZSAPFX_TMP_DEL    allowed_prefixes=ZSAPFX_
        | ...    description=SAPFX test role: throwaway    alias=abap2023
        | Should Be True    ${removed}[deleted]
        """
        name = user_provisioning.require_test_role(role, allowed_prefixes)
        description = user_provisioning.require_marker(name, description)
        self._require_writable_client(alias)
        if not self._role_exists(name, alias):
            return {"deleted": False, "role": name}
        user_provisioning.require_same_marker(name, self._role_title(name, alias), description,
                                             kind="role")
        holders = sorted({str(r.get("UNAME", "")).strip() for r in self.read_rfc_table(
            "AGR_USERS", ["UNAME"], alias=alias, options="AGR_NAME = '%s'" % name)} - {""})
        if holders:
            raise AssertionError(
                "Le rôle %s est encore attribué (%s) : il n'est pas supprimé."
                % (name, ", ".join(holders)))
        answer = self.call_rfc("PRGN_ACTIVITY_GROUP_DELETE", alias=alias,
                               ACTIVITY_GROUP=name, SHOW_DIALOG="",
                               ENQUEUE_AND_TRANSPORT="")
        self.commit_bapi_transaction(alias)
        if str(answer.get("ERROR_FLAG", "")).strip() or self._role_exists(name, alias):
            raise AssertionError(
                "La suppression du rôle %s n'a pas abouti (ERROR_FLAG=%r)."
                % (name, answer.get("ERROR_FLAG", "")))
        return {"deleted": True, "role": name}

    def _generate_role_profile(self, role: str, manual: list[dict[str, str]],
                               alias: str) -> None:
        """Génère le profil du rôle depuis ses seules autorisations
        explicites. ``REBUILD_AUTH_DATA`` vide est ce qui saute le contrôle
        SU25 (``PRGN_CHECK_PROFGEN_TABLES``, lu dans la source du module sur la
        758) : le générateur ne reconstruit rien depuis le menu."""
        self.call_rfc(
            "PRGN_AUTO_GENERATE_PROFILE_NEW", alias=alias,
            ACTIVITY_GROUP=role, NO_DIALOG="X", GENERATE_PROFILE="X",
            REBUILD_AUTH_DATA=" ", FILL_EMPTY_FIELDS_WITH_STAR="",
            ORG_LEVELS_WITH_STAR="", MANUAL_AUTHS=manual)
        self.commit_bapi_transaction(alias)
        if self._role_profile(role, alias) is None:
            raise AssertionError(
                "Le profil du rôle %s n'a pas été généré (aucune ligne AGR_1016) "
                "alors que le générateur n'a rien levé." % role)

    def _role_title(self, role: str, alias: str) -> str:
        """Le titre du rôle (``AGR_TEXTS``, ligne 0), son marquage."""
        rows = self.read_rfc_table("AGR_TEXTS", ["LINE", "TEXT"], alias=alias,
                                   options="AGR_NAME = '%s'" % role)
        titles = [str(r.get("TEXT", "")).strip() for r in rows
                  if str(r.get("LINE", "")).strip().lstrip("0") == ""]
        return titles[0] if titles else ""

    def _role_exists(self, role: str, alias: str) -> bool:
        rows = self.read_rfc_table("AGR_DEFINE", ["AGR_NAME"], alias=alias,
                                   options="AGR_NAME = '%s'" % role)
        return bool(rows)

    def _role_transactions(self, role: str, alias: str) -> list[str]:
        try:
            result = self.call_rfc("PRGN_RFC_READ_TRANSACTIONS", alias=alias,
                                   ACTIVITY_GROUP=role)
        except Exception as err:
            if abap_key(err) == "ACTIVITY_GROUP_DOES_NOT_EXIST":
                return []
            raise
        return sorted({str(r.get("TCODE", "")).strip() for r in result.get("TCODES", [])} - {""})

    def _role_profile(self, role: str, alias: str) -> Optional[str]:
        rows = self.read_rfc_table("AGR_1016", ["PROFILE"], alias=alias,
                                   options="AGR_NAME = '%s'" % role)
        return str(rows[0].get("PROFILE", "")).strip() if rows else None

    def _role_values(self, role: str, alias: str) -> set[tuple[str, str, str, str]]:
        """Les valeurs déclarées du rôle, ``(objet, champ, bas, haut)``
        (``AGR_1251`` hors lignes supprimées)."""
        rows = self.read_rfc_table(
            "AGR_1251", ["OBJECT", "FIELD", "LOW", "HIGH", "DELETED"], alias=alias,
            options="AGR_NAME = '%s'" % role)
        return {(str(r.get("OBJECT", "")).strip(), str(r.get("FIELD", "")).strip(),
                 str(r.get("LOW", "")).strip(), str(r.get("HIGH", "")).strip())
                for r in rows if not str(r.get("DELETED", "")).strip()}

    def _role_value_differences(self, role: str, manual: list[dict[str, str]],
                                alias: str) -> tuple[list[str], list[str]]:
        """Valeurs demandées absentes du rôle, et valeurs du rôle non
        demandées (``AGR_1251`` hors lignes supprimées, bornes comprises)."""
        have = self._role_values(role, alias)
        want = {(m["OBJECT"], m["FIELD"], m["LOW"], m["HIGH"]) for m in manual}
        return (user_provisioning.describe_values(want - have),
                user_provisioning.describe_values(have - want))

    def _role_profile_verdict(self, role: str, alias: str) -> dict[str, Any]:
        """L'état de génération du rôle (``AGR_1016``) et les valeurs que son
        profil actif porte réellement (``UST10S`` puis ``UST12``, version
        ``A``), confrontés à ses valeurs déclarées."""
        rows = self.read_rfc_table("AGR_1016", ["PROFILE", "GENERATED", "PSTATE"],
                                   alias=alias, options="AGR_NAME = '%s'" % role)
        granted: set[tuple[str, str, str, str]] = set()
        for profile in sorted({str(r.get("PROFILE", "")).strip() for r in rows} - {""}):
            for auth in self.read_rfc_table(
                    "UST10S", ["OBJCT", "AUTH"], alias=alias,
                    options="PROFN = '%s' AND AKTPS = 'A'" % profile):
                for value in self.read_rfc_table(
                        "UST12", ["OBJCT", "FIELD", "VON", "BIS"], alias=alias,
                        options=["OBJCT = '%s' AND AKTPS = 'A'"
                                 % str(auth.get("OBJCT", "")).strip(),
                                 "AND AUTH = '%s'" % str(auth.get("AUTH", "")).strip()]):
                    granted.add((str(value.get("OBJCT", "")).strip(),
                                 str(value.get("FIELD", "")).strip(),
                                 str(value.get("VON", "")).strip(),
                                 str(value.get("BIS", "")).strip()))
        return user_provisioning.role_profile_verdict(
            role, rows, self._role_values(role, alias), granted)
