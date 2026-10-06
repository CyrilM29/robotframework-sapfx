"""Mixin du rafraîchissement d'une tuile du launchpad : `Refresh Flp Tile
Counter`.

Extrait de ``_flp_tiles`` le 2026-10-06 (convention #13) : c'est le seul
keyword des tuiles qui AGIT, en demandant au shell de réinterroger le service
de la tuile (aucune donnée n'est écrite) ; les autres lisent. Né de la revue
indépendante de la fiche scénario 7 (2026-09-29) : une tuile chargée au
démarrage du launchpad garde sa valeur jusqu'à son prochain rafraîchissement
(450 s pour celle du scénario), donc encadrer sa LECTURE par deux mesures d'un
autre canal n'encadre pas sa REQUÊTE. La logique (fraîcheur des réponses, lien
au corps) vit dans ``sapfx_common.flp_tiles``, les sondes dans ``_flp_js``.
"""

import json

from robot.utils import timestr_to_secs

from sapfx_common import flp_tiles
from sapfx_common.polling import poll_until

from .._flp_js import (
    FLP_TILE_REFRESH_CLEANUP_JS,
    FLP_TILE_REFRESH_PROBE_JS,
    PAGE_RESOURCE_RESPONSES_PROBE_JS,
)


class FlpTileRefreshKeywords:
    """Mixin composé dans :class:`SapFioriLibrary` (voir ce module). Suppose
    ``self._evaluate``, ``self._flp_result``, ``self.ui5_timeout``,
    ``self.poll_interval`` et les lectures de ``FlpTileKeywords`` (`Get Flp
    Tile Configuration`, `Get Flp Tile Counter`) disponibles par
    composition."""

    def refresh_flp_tile_counter(self, intent, timeout=None,
                                 accept_truncated=False, index=None,
                                 ignore_parameters=False):
        """Fait RÉINTERROGER son service par la tuile d'un intent, prouve que
        la réponse est arrivée APRÈS la demande, puis retourne le compteur
        chargé : le dict de `Wait For Flp Tile Counter` complété de
        ``{refreshed_at, response_started_at, response_at, response_after_ms,
        response_status, body_check, service_path}`` (millisecondes de
        l'horloge du minutage des ressources de la page).

        La raison d'être : une tuile chargée au démarrage du launchpad garde sa
        valeur jusqu'à son prochain rafraîchissement (450 s pour « Approve
        Purchase Orders »), et `Wait For Flp Tile Counter` la rend aussitôt.
        Encadrer cette LECTURE par deux mesures d'un autre canal n'encadre
        donc pas la REQUÊTE qui a produit le chiffre ; encadrer CE keyword, si.

        Le rafraîchissement passe par le service ushell ``LaunchPage``
        (``refreshTile``), sur la tuile des groupes que désigne l'intent (même
        contrat que `Get Flp Tile Configuration`). Mesuré sur 1.71 : la tuile
        relance sa requête SANS repasser par la valeur d'attente ``...`` ; la
        preuve est donc la RÉPONSE, lue dans le minutage des ressources de la
        page : une requête du chemin du service PARTIE après le déclenchement
        (une requête du rafraîchissement périodique, lancée avant et revenue
        après, ne compte pas), mesurée sur la même horloge, et revenue en
        SUCCÈS (statut 200 : une réponse en erreur laisse la tuile sur son
        ANCIENNE valeur, qui passerait pour fraîche ; un statut que le
        navigateur n'expose pas est refusé, jamais supposé ; une première
        réponse en échec est refusée aussitôt, même si un nouvel essai
        suivrait) ; puis le compteur est relu deux fois de suite à l'identique
        après elle. Les réponses sont vues par un observateur posé AVANT la
        demande (le tampon du minutage perd ses entrées au-delà de 250) et
        retiré ensuite. ``body_check`` relie la valeur lue au corps de la
        réponse (``sapfx_common.flp_tiles.response_body_check``) : ``matched``
        (venue du réseau, corps de la longueur exacte de l'entier affiché),
        ``not_exposed`` (tailles cachées par une autre origine : non
        mesurable, dit comme tel) ; un corps servi par le cache est refusé, un
        corps d'une autre longueur fait attendre (la tuile n'a pas encore
        appliqué la réponse). Un lien de longueur, pas d'identité. Quand la
        tuile rendue déclare son instance (``debugInfo``, 1.71), elle doit être
        celle qu'on a rafraîchie.

        Aucune donnée n'est écrite : le shell réinterroge un service de
        lecture. Échoue, en le disant, sur une tuile statique (pas de
        ``service_url``), un shell sans ``refreshTile``, une tuile absente des
        groupes, une réponse qui n'arrive pas dans ``timeout``, et pour les
        mêmes raisons que `Wait For Flp Tile Counter`.

        Exemple :
        | ${tile}=    `Refresh Flp Tile Counter`    EPMPurchaseOrder-approve    timeout=60s
        | Should Be Equal As Integers    ${tile}[response_status]    200
        """
        budget = timestr_to_secs(timeout if timeout is not None else self.ui5_timeout)
        conf = self.get_flp_tile_configuration(
            intent, index=index, ignore_parameters=ignore_parameters)
        if not conf["service_path"]:
            raise AssertionError(
                "La tuile '%s' n'a pas de service (tuile statique) : il n'y a "
                "rien à rafraîchir." % conf["intent"])
        declenche = self._flp_result(self._evaluate(
            FLP_TILE_REFRESH_PROBE_JS,
            arg=json.dumps({"tile_instance_id": conf["tile_instance_id"]})),
            service="LaunchPage")
        if not isinstance(declenche, dict):
            raise AssertionError(
                "Le rafraîchissement de la tuile '%s' n'a rien rendu : aucun "
                "runtime sur la portée courante (`Get Ui5 Frame Stack`)."
                % conf["intent"])
        if declenche.get("__no_refresh"):
            raise AssertionError(
                "Le service LaunchPage de ce launchpad n'expose pas "
                "`refreshTile` : la fraîcheur du compteur ne peut pas être "
                "demandée.")
        if "__not_found" in declenche:
            raise AssertionError(
                "La tuile d'instance %s (intent '%s') a disparu des groupes "
                "entre la lecture de sa configuration et son rafraîchissement."
                % (conf["tile_instance_id"], conf["intent"]))
        depuis = declenche.get("triggered_at")
        if not isinstance(depuis, (int, float)):
            raise AssertionError(
                "Le rafraîchissement de la tuile '%s' n'a pas rendu l'instant de "
                "son déclenchement (%r) : la fraîcheur n'est pas mesurable."
                % (conf["intent"], depuis))
        etat = {}

        def _check():
            fraiches = flp_tiles.fresh_responses(self._evaluate(
                PAGE_RESOURCE_RESPONSES_PROBE_JS, arg=conf["service_path"]) or [],
                depuis)
            retenue, refus = flp_tiles.fresh_response_verdict(fraiches)
            if refus:
                etat["refus"] = refus
                return {"__refus": True}
            if retenue is None:
                etat["attente"] = "aucune réponse de %s depuis le déclenchement" % (
                    conf["service_path"])
                return None
            try:
                lu = self.get_flp_tile_counter(
                    intent, index=index, ignore_parameters=ignore_parameters)
            except AssertionError as err:
                etat["attente"] = str(err)
                return None
            precedent = etat.get("lu")
            etat["lu"], etat["reponse"] = lu, retenue
            if not lu["loaded"]:
                etat["attente"] = "compteur %r (%s)" % (lu["value"], lu["reason"])
                return None
            if precedent is None or precedent["value"] != lu["value"]:
                etat["attente"] = "compteur %r lu une fois après la réponse" % lu["value"]
                return None
            etat["corps"] = flp_tiles.response_body_check(
                retenue, lu["number"] if lu["number"] is not None else lu["value"])
            if etat["corps"] == "cached":
                etat["refus"] = ("la réponse retenue vient du cache du navigateur "
                                 "(aucun octet transféré) : le serveur n'a pas été réinterrogé")
                return {"__refus": True}
            if etat["corps"] == "mismatch":
                etat["attente"] = ("corps de %s octets, compteur %r : la tuile n'a pas "
                                   "appliqué la réponse" % (retenue["body"], lu["value"]))
                return None
            return lu

        try:
            result = poll_until(_check, budget, step=self.poll_interval)
        finally:
            try:
                self._evaluate(FLP_TILE_REFRESH_CLEANUP_JS)
            except Exception:      # noqa: BLE001 (nettoyage : jamais d'échec)
                pass
        if result and result.get("__refus"):
            raise AssertionError(
                "Le rafraîchissement de la tuile '%s' n'a pas produit de "
                "compteur frais : %s." % (conf["intent"], etat["refus"]))
        if not result:
            raise AssertionError(
                "La tuile '%s' n'a pas rendu de compteur frais %s s après son "
                "rafraîchissement : %s." % (conf["intent"], budget,
                                            etat.get("attente", "aucune lecture")))
        if result["chip_instance_id"] and \
                result["chip_instance_id"] != conf["tile_instance_id"]:
            raise AssertionError(
                "La tuile rendue lue (instance %s) n'est pas la tuile "
                "rafraîchie (instance %s)." % (result["chip_instance_id"],
                                              conf["tile_instance_id"]))
        result = dict(self._comparable_counter(result, accept_truncated))
        reponse = etat["reponse"]
        result.update({
            "refreshed_at": depuis,
            "response_started_at": reponse["start"],
            "response_at": reponse["end"],
            "response_after_ms": round(reponse["end"] - float(depuis), 1),
            "response_status": reponse["status"],
            "body_check": etat["corps"],
            "service_path": conf["service_path"],
        })
        return result
