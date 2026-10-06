"""Mixin des PROFILS partenaire d'ALE/EDI du canal RFC (``EDP13`` sortant,
``EDP21`` entrant) : `Ensure Idoc Outbound Profile`,
`Ensure Idoc Inbound Profile`, `Remove Idoc Outbound Profile`,
`Remove Idoc Inbound Profile` et `Get Idoc Partner Profiles`.

Né du scénario 8 (IDoc sortant sur A4H 1909, 2026-10-01) : l'image ne livre
que les profils du système BW (``RSRQST``, ``RSINFO``, ``RSSEND``), donc
émettre un IDoc de vol suppose de provisionner DEUX profils, et le défaire
exige de ne toucher qu'à ceux que l'on a créés. Les modules ``EDI_AGREE_*``
écrivent sans écran ; la logique pure (liste blanche, profils protégés,
écarts) est dans ``sapfx_common.idoc_profiles``.

Typed.
"""
from __future__ import annotations

from typing import Any, Optional

from sapfx_common import idoc_profiles

from ._rfc_reads import RfcReadKeywords


def abap_key(err: BaseException) -> str:
    """Le code d'exception ABAP d'une erreur pyrfc (``ENTRY_NOT_EXIST`` …),
    vide pour toute autre erreur."""
    return str(getattr(err, "key", "") or "")


class RfcIdocProfileKeywords(RfcReadKeywords):
    """Mixin de :class:`SapApiLibrary` : les profils partenaire d'IDoc."""

    def get_idoc_partner_profiles(self, direction: str = "outbound",
                                  alias: str = "default") -> list[dict[str, str]]:
        """Lit les profils partenaire ``outbound`` (``EDP13``) ou ``inbound``
        (``EDP21``) du mandant de la connexion, en clés parlantes
        (``partner``, ``partner_type``, ``message_type``, puis ``idoc_type``,
        ``port``, ``output_mode``, ``package_size`` côté sortant ou
        ``process_code``, ``processing`` côté entrant), triés. C'est
        l'INSTANTANÉ qui permet de prouver qu'une suite rend la configuration
        qu'elle a trouvée : l'utilisateur de service n'y figure pas, il
        dépend de qui a créé la ligne.

        Exemple :
        | ${profiles}=    `Get Idoc Partner Profiles`    outbound    alias=a4h
        | Should Not Be Empty    ${profiles}
        """
        side = str(direction).strip().lower()
        if side not in ("outbound", "inbound"):
            raise ValueError("direction vaut 'outbound' ou 'inbound', reçu %r." % (direction,))
        if side == "outbound":
            rows = self.read_rfc_table("EDP13", list(idoc_profiles.OUTBOUND_READ_FIELDS),
                                       alias=alias)
            return idoc_profiles.sort_profiles(
                [idoc_profiles.normalize_outbound(row) for row in rows])
        rows = self.read_rfc_table("EDP21", list(idoc_profiles.INBOUND_READ_FIELDS),
                                   alias=alias)
        return idoc_profiles.sort_profiles(
            [idoc_profiles.normalize_inbound(row) for row in rows])

    def ensure_idoc_outbound_profile(self, partner: str, message_type: str,
                                     idoc_type: str, port: str,
                                     allowed_message_types: Any,
                                     partner_type: str = "LS",
                                     output_mode: str = "2",
                                     package_size: Any = "1",
                                     alias: str = "default") -> dict[str, Any]:
        """Garantit un profil SORTANT (``EDP13``) pour (partenaire, type de
        message), de façon idempotente. Absent : créé (``EDI_AGREE_OUT_MESSTYPE
        _INSERT`` puis commit), rend ``{"state": "created", "key": {...}}``.
        Présent et identique sur le type d'IDoc, le port, le mode de sortie et
        la taille de paquet : laissé, rend ``{"state": "present"}`` (la suite
        ne le retire alors PAS). Présent mais différent : REFUSÉ en listant les
        écarts champ par champ, jamais écrasé.

        ``allowed_message_types`` est OBLIGATOIRE (liste blanche, une liste
        vide refuse tout) et les profils livrés avec l'image (``RSRQST``,
        ``RSINFO``, ``RSSEND``) sont refusés même listés. ``output_mode`` :
        ``2`` transfert immédiat (défaut), ``1`` et ``4`` collecte.

        Exemple :
        | ${outbound}=    `Ensure Idoc Outbound Profile`    A4HCLNT001    TXTRAW    TXTRAW01    A000000001
        | ...    allowed_message_types=TXTRAW    alias=a4h
        """
        wanted_type = idoc_profiles.require_allowed(message_type, allowed_message_types)
        attributes = self.get_rfc_connection_attributes(alias)
        key = idoc_profiles.outbound_key(
            attributes.get("client", ""), partner, partner_type, wanted_type)
        record = idoc_profiles.outbound_record(
            key, idoc_type, port, output_mode, package_size,
            attributes.get("user", ""), attributes.get("language", "E"))
        existing = self._read_profile(
            "EDI_AGREE_OUT_MESSTYPE_READ", "REC_EDK13", "REC_EDD13", key, alias)
        label = {"partner": str(partner).strip(), "partner_type": str(partner_type).strip(),
                 "message_type": wanted_type}
        if existing is None:
            self.call_rfc("EDI_AGREE_OUT_MESSTYPE_INSERT", alias=alias, REC_EDP13=record)
            self.commit_bapi_transaction(alias)
            return {"state": "created", "key": label}
        diffs = idoc_profiles.profile_differences(
            existing, record, ("IDOCTYP", "RCVPOR", "OUTMOD", "PCKSIZ"))
        if diffs:
            raise AssertionError(
                "Le profil sortant %s/%s/%s existe déjà et DIFFÈRE de celui "
                "demandé (%s) ; il n'est pas écrasé. Le retirer à la main ou "
                "demander le profil tel qu'il est."
                % (label["partner"], label["partner_type"], wanted_type, "; ".join(diffs)))
        return {"state": "present", "key": label}

    def ensure_idoc_inbound_profile(self, partner: str, message_type: str,
                                    process_code: str, allowed_message_types: Any,
                                    partner_type: str = "LS", processing: str = "1",
                                    alias: str = "default") -> dict[str, Any]:
        """Garantit un profil ENTRANT (``EDP21``) pour (partenaire émetteur,
        type de message) : sans lui, le sortant reste vert à 03 pendant que
        l'entrant naît en 56 (mesuré sur A4H). Mêmes règles que
        `Ensure Idoc Outbound Profile` : idempotent, liste blanche obligatoire, profils
        livrés refusés, profil différent refusé champ par champ.

        ``process_code`` est celui du traitement entrant (``BAPI`` pour le
        modèle de vol, qui poste vraiment ; ``TXT1`` pour un texte, envoyé à la
        boîte de l'utilisateur). ``processing`` : ``1`` tout de suite (défaut),
        ``3`` par programme d'arrière-plan : l'entrant reste alors à 64 (prêt à
        être passé à l'application) tant qu'aucun programme ne le traite.

        Exemple :
        | ${inbound}=    `Ensure Idoc Inbound Profile`    A4HCLNT001    TXTRAW    TXT1
        | ...    allowed_message_types=TXTRAW    processing=3    alias=a4h
        """
        wanted_type = idoc_profiles.require_allowed(message_type, allowed_message_types)
        attributes = self.get_rfc_connection_attributes(alias)
        key = idoc_profiles.inbound_key(
            attributes.get("client", ""), partner, partner_type, wanted_type)
        record = idoc_profiles.inbound_record(
            key, process_code, processing, attributes.get("user", ""),
            attributes.get("language", "E"))
        existing = self._read_profile(
            "EDI_AGREE_IN_MESSTYPE_READ", "REC_EDK21", "REC_EDD21", key, alias)
        label = {"partner": str(partner).strip(), "partner_type": str(partner_type).strip(),
                 "message_type": wanted_type}
        if existing is None:
            self.call_rfc("EDI_AGREE_IN_MESSTYPE_INSERT", alias=alias, REC_EDP21=record)
            self.commit_bapi_transaction(alias)
            return {"state": "created", "key": label}
        diffs = idoc_profiles.profile_differences(existing, record, ("EVCODE", "INMOD"))
        if diffs:
            raise AssertionError(
                "Le profil entrant %s/%s/%s existe déjà et DIFFÈRE de celui "
                "demandé (%s) ; il n'est pas écrasé."
                % (label["partner"], label["partner_type"], wanted_type, "; ".join(diffs)))
        return {"state": "present", "key": label}

    def remove_idoc_outbound_profile(self, partner: str, message_type: str,
                                     allowed_message_types: Any,
                                     partner_type: str = "LS",
                                     alias: str = "default") -> dict[str, Any]:
        """Retire un profil sortant PAR SA CLÉ, seulement pour un type de
        message de la liste blanche et jamais pour un profil livré. Un profil
        déjà absent rend ``{"removed": False}`` (le nettoyage est idempotent) ;
        retiré, ``{"removed": True}``.

        Exemple :
        | `Remove Idoc Outbound Profile`    A4HCLNT001    TXTRAW    allowed_message_types=TXTRAW    alias=a4h
        """
        wanted_type = idoc_profiles.require_allowed(message_type, allowed_message_types)
        client = self.get_rfc_connection_attributes(alias).get("client", "")
        key = idoc_profiles.outbound_key(client, partner, partner_type, wanted_type)
        return self._delete_profile("EDI_AGREE_OUT_MESSTYPE_DELETE", "REC_EDK13",
                                    key, partner, partner_type, wanted_type, alias)

    def remove_idoc_inbound_profile(self, partner: str, message_type: str,
                                    allowed_message_types: Any,
                                    partner_type: str = "LS",
                                    alias: str = "default") -> dict[str, Any]:
        """Retire un profil entrant PAR SA CLÉ, mêmes garde-fous
        que `Remove Idoc Outbound Profile`.

        Exemple :
        | `Remove Idoc Inbound Profile`    A4HCLNT001    TXTRAW    allowed_message_types=TXTRAW    alias=a4h
        """
        wanted_type = idoc_profiles.require_allowed(message_type, allowed_message_types)
        client = self.get_rfc_connection_attributes(alias).get("client", "")
        key = idoc_profiles.inbound_key(client, partner, partner_type, wanted_type)
        return self._delete_profile("EDI_AGREE_IN_MESSTYPE_DELETE", "REC_EDK21",
                                    key, partner, partner_type, wanted_type, alias)

    def _read_profile(self, function: str, key_param: str, out_param: str,
                      key: dict[str, str], alias: str) -> Optional[dict[str, Any]]:
        """Le profil lu par son module ``EDI_AGREE_*_READ``, ou ``None`` s'il
        n'existe pas (``ENTRY_NOT_EXIST``)."""
        try:
            result = self.call_rfc(function, alias=alias, **{key_param: key})
        except Exception as err:
            if abap_key(err) == "ENTRY_NOT_EXIST":
                return None
            raise
        return dict(result[out_param])

    def _delete_profile(self, function: str, key_param: str, key: dict[str, str],
                        partner: str, partner_type: str, message_type: str,
                        alias: str) -> dict[str, Any]:
        label = {"partner": str(partner).strip(), "partner_type": str(partner_type).strip(),
                 "message_type": message_type}
        try:
            self.call_rfc(function, alias=alias, **{key_param: key})
        except Exception as err:
            if abap_key(err) == "ENTRY_NOT_EXIST":
                return {"removed": False, "key": label}
            raise
        self.commit_bapi_transaction(alias)
        return {"removed": True, "key": label}
