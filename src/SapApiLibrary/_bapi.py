"""Mixin du pattern **BAPI** au-dessus du canal RFC : `Call Bapi` jugé par
TYPE de BAPIRET2 (convention #3), `Commit/Rollback Bapi Transaction` qui
ferment la LUW, et le refus asserté ou toléré par IDENTIFIANT de message.

Extrait de ``_rfc.py`` (convention #13) le 2026-09-28, quand la campagne du
rôle Business Partner (A4H 1909) a eu besoin de nommer des refus précis :
``R11/E/657`` (rôle déjà absent : le nettoyage idempotent le TOLÈRE),
``R11/E/579`` (partenaire sans rôle : la BAPI de lecture REFUSE au lieu de
rendre une liste vide), ``R1/E/206`` (rôle inexistant), ``R1/E/084``
(partenaire tenu en modification par l'écran). `Rfc Should Fail With
Message Id` ne voit que les exceptions RFC, pas la table ``RETURN`` : un
refus de BAPI ne s'y exprimait que par son TEXTE, donc de façon localisée.
Logique pure dans ``sapfx_common.bapi_return``.
"""
from __future__ import annotations

from typing import Any

from robot.api import logger

from sapfx_common import bapi_return

from ._http import _as_bool
from ._rfc import RfcKeywords


class BapiKeywords(RfcKeywords):
    """Mixin de :class:`SapApiLibrary` : le pattern BAPI du canal RFC."""

    def call_bapi(self, function_name: str, alias: str = "default",
                  return_key: str = "RETURN", accept: Any = None,
                  **params: Any) -> Any:
        """Appelle une **BAPI** et vérifie sa table ``RETURN`` (BAPIRET2) :
        un message de type ``E``/``A``/``X`` = échec listant les messages
        bloquants (décision par TYPE, jamais par texte localisé : convention
        n°3) et rappelant `Rollback Bapi Transaction`. Sinon retourne le
        résultat complet (dict pyrfc). Le pattern SAP de préparation de
        données robuste : `Call Bapi` puis `Commit Bapi Transaction`.

        ``accept`` : identifiants de refus TOLÉRÉS (``R11/E/657``, liste ou
        chaîne à virgules), pour un geste idempotent comme un nettoyage qui
        retire un rôle peut-être déjà absent. Un refus toléré est journalisé,
        tout autre refus échoue ; un identifiant mal formé ou d'un type non
        bloquant est refusé AVANT l'appel. Pour ASSERTER un refus, utiliser
        `Bapi Should Fail With Message Id`.

        Piège mesuré (A4H, 2026-09-26, deux fois sur deux) : une BAPI
        d'ÉCRITURE Business Partner sur une connexion qui a LU ce partenaire
        plus tôt, sans commit ni rollback depuis, réécrit l'objet depuis son
        tampon et EFFACE en silence ce que l'écran a changé entre-temps, sans
        document de modification. Appeler `Rollback Bapi Transaction` juste
        avant une BAPI d'écriture ferme ce risque."""
        accepted = bapi_return.expected_message_ids(accept) if accept else []
        result = self.call_rfc(function_name, alias=alias, **params)
        messages = bapi_return.iter_bapi_messages(result, return_key)
        tolerated, blocking = bapi_return.split_by_identity(
            bapi_return.failing_messages(messages), accepted)
        if blocking:
            raise AssertionError(
                bapi_return.format_bapi_failure(function_name, blocking))
        if tolerated:
            logger.info("La BAPI %s a refusé avec %s, refus toléré (accept)."
                        % (function_name, ", ".join(
                            bapi_return.message_identity(m) for m in tolerated)))
        return result

    def bapi_should_fail_with_message_id(self, expected_message_id: str,
                                         function_name: str,
                                         alias: str = "default",
                                         return_key: str = "RETURN",
                                         rollback: bool = True,
                                         **params: Any) -> dict[str, Any]:
        """Vérifie qu'une BAPI REFUSE avec l'**identifiant de message**
        attendu dans sa table ``RETURN`` (``R11/E/579``) et retourne la fiche
        du refus : ``{function, message_id, messages}``, chaque message avec
        son ``message_id``, JSON-safe.

        Le miroir, pour la table ``RETURN``, de `Rfc Should Fail With Message
        Id` (qui ne voit que les exceptions RFC) : classe, type et numéro
        désignent le refus exact sans toucher à son libellé (convention n°3).

        Deux échecs distincts : la BAPI n'a rien refusé (le refus attendu ne
        se produit plus), ou elle a refusé avec un AUTRE identifiant (les
        deux sont nommés). ``rollback`` (défaut vrai) annule la LUW APRÈS
        l'appel, dans tous les cas : une BAPI qui réussit là où un refus était
        attendu ne doit jamais laisser une écriture en attente de commit."""
        expected = bapi_return.expected_message_ids(
            expected_message_id, "expected_message_id")
        if len(expected) != 1:
            raise ValueError("Bapi Should Fail With Message Id attend UN "
                             "identifiant, reçu %r." % (expected_message_id,))
        try:
            result = self.call_rfc(function_name, alias=alias, **params)
        except Exception:
            # Le refus d'origine prime : un rollback qui échoue à son tour ne
            # doit pas le masquer (revue indépendante du 2026-09-28).
            if _as_bool(rollback):
                try:
                    self.rollback_bapi_transaction(alias)
                except Exception as rollback_error:   # noqa: BLE001
                    logger.warn("Rollback après l'échec de %s impossible : %s"
                                % (function_name, rollback_error))
            raise
        if _as_bool(rollback):
            self.rollback_bapi_transaction(alias)
        messages = bapi_return.iter_bapi_messages(result, return_key)
        failing = bapi_return.failing_messages(messages)
        if not failing:
            raise AssertionError(bapi_return.format_bapi_missing_failure(
                function_name, expected[0], messages))
        if expected[0] not in (bapi_return.message_identity(m) for m in failing):
            raise AssertionError(bapi_return.format_bapi_message_id_mismatch(
                function_name, expected[0], failing))
        return {"function": function_name, "message_id": expected[0],
                "messages": bapi_return.describe_bapi_messages(messages)}

    def commit_bapi_transaction(self, alias: str = "default",
                                wait: bool = True) -> Any:
        """``BAPI_TRANSACTION_COMMIT`` sur la connexion RFC ``alias`` :
        rend durables les écritures des BAPIs précédentes. ``wait=True``
        (défaut) attend la fin de la mise à jour (``WAIT='X'``) : le réglage
        sûr pour enchaîner une vérification. La table RETURN est vérifiée
        comme dans `Call Bapi`."""
        params = {"WAIT": "X"} if _as_bool(wait) else {}
        return self.call_bapi("BAPI_TRANSACTION_COMMIT", alias=alias, **params)

    def rollback_bapi_transaction(self, alias: str = "default") -> Any:
        """``BAPI_TRANSACTION_ROLLBACK`` sur la connexion RFC ``alias`` :
        annule la LUW en cours (le réflexe après un `Call Bapi` en échec, un
        teardown sûr des préparations de données interrompues, et la remise
        à zéro du tampon avant une BAPI d'écriture, voir `Call Bapi`)."""
        return self.call_rfc("BAPI_TRANSACTION_ROLLBACK", alias=alias)
