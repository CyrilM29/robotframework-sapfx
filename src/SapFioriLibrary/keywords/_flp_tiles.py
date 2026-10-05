"""Mixin tuiles du launchpad : compteur affiché et configuration d'une tuile.

`Get Flp Tile Counter`, `Wait For Flp Tile Counter`, `Refresh Flp Tile
Counter` et `Get Flp Tile Configuration`, nés de la fiche scénario 7
(2026-09-29) : confronter le chiffre d'une tuile dynamique à un agrégat lu par
un autre canal. Jusque-là le compteur se lisait par une sonde JavaScript
inline dans un page object, et la configuration d'une tuile (le service
qu'elle interroge) par un double décodage JSON d'une réponse OData, deux
capacités génériques qui n'avaient rien à faire dans la couche métier
(convention #12). Le rafraîchissement est né de la revue indépendante du même
jour : une tuile chargée au démarrage du launchpad garde sa valeur jusqu'à
son prochain rafraîchissement (450 s pour celle du scénario), donc encadrer
sa LECTURE par deux mesures d'un autre canal n'encadre pas sa REQUÊTE.

Les lectures sont PURES, sans injection du bundle ; seul `Refresh Flp Tile
Counter` agit, en demandant au shell de réinterroger le service de la tuile
(aucune donnée n'est écrite). Les sondes vivent dans ``_flp_js``, la logique
(intent à paramètres, symboles numériques, verdict du compteur, fraîcheur,
configuration) dans ``sapfx_common.flp_tiles``. Extrait au format des autres
mixins (convention #13).
"""

import json

from robot.utils import is_truthy, timestr_to_secs

from sapfx_common import flp_tiles
from sapfx_common.polling import poll_until

from .._flp_js import (
    FLP_TILE_CONFIGURATION_PROBE_JS,
    FLP_TILE_COUNTERS_PROBE_JS,
    FLP_TILE_REFRESH_CLEANUP_JS,
    FLP_TILE_REFRESH_PROBE_JS,
    PAGE_NUMBER_SAMPLE_PROBE_JS,
    PAGE_RESOURCE_RESPONSES_PROBE_JS,
)


class FlpTileKeywords:
    """Mixin composé dans :class:`SapFioriLibrary` (voir ce module). Suppose
    ``self._evaluate``, ``self._flp_result``, ``self.ui5_timeout`` et
    ``self.poll_interval`` disponibles par composition."""

    def _rendered_tiles(self):
        tiles = self._evaluate(FLP_TILE_COUNTERS_PROBE_JS)
        if tiles is None:
            raise AssertionError(
                "Aucun runtime UI5 sur la portée courante : aucune tuile ne "
                "peut être lue. Vérifier la portée de frame (`Get Ui5 Frame "
                "Stack`) : les tuiles vivent dans le shell, pas dans "
                "l'application.")
        return list(tiles)

    def _page_number_symbols(self):
        try:
            sample = self._evaluate(PAGE_NUMBER_SAMPLE_PROBE_JS)
        except Exception:      # noqa: BLE001 (sonde : symboles inconnus)
            sample = ""
        return flp_tiles.number_symbols(sample)

    @staticmethod
    def _pick_tile(matches, seen, intent, index, what):
        if not matches:
            raise AssertionError(
                "Aucune %s d'intent '%s' sur la portée courante. Vues : %s. "
                "Une application du catalogue n'est pas forcément sur "
                "l'accueil de l'utilisateur (vérifier `List Flp Groups`)."
                % (what, flp_tiles.normalize_intent(intent),
                   flp_tiles.describe_tile_candidates(seen)))
        if index is None or str(index).strip() == "":
            if len(matches) > 1:
                raise AssertionError(
                    "%d %ss portent l'intent '%s' (la même application "
                    "épinglée dans plusieurs groupes) : %s. Passer `index=` "
                    "pour en désigner une." % (
                        len(matches), what, flp_tiles.normalize_intent(intent),
                        flp_tiles.describe_tile_candidates(matches)))
            return matches[0]
        position = int(index)
        if not 0 <= position < len(matches):
            raise AssertionError(
                "index=%d hors des %d %s(s) d'intent '%s'."
                % (position, len(matches), what,
                   flp_tiles.normalize_intent(intent)))
        return matches[position]

    def get_flp_tile_counter(self, intent, index=None, ignore_parameters=False):
        """Lit le **compteur affiché** par la tuile d'un intent, avec son
        verdict : un dict JSON-safe ``{intent, intent_parameters, tile_id,
        intent_source, chip_id, chip_instance_id, value, scale, rendered,
        loaded, number, truncated, reason, group_symbol, decimal_symbol}``.

        La tuile se désigne par son intent (``SemanticObject-action``), jamais
        par son titre (traduit) ni par son identifiant (généré, ``__tile7``).
        L'intent se lit dans la propriété ``target`` de la tuile (SAPUI5 1.71)
        ou, quand elle est vide (1.120), dans l'ancre HTML de la tuile ;
        ``intent_source`` dit laquelle a servi. Les PARAMÈTRES de l'intent
        comptent : ``X-y`` ne désigne pas la tuile ``X-y?p=1``, qui ouvre la
        même application sur un autre jeu de données ; ``ignore_parameters=True``
        ne compare que l'objet et l'action. ``chip_id`` et
        ``chip_instance_id`` viennent de la propriété ``debugInfo`` de la tuile
        quand elle existe (1.71), vides sinon : ils relient la tuile RENDUE à
        la configuration de `Get Flp Tile Configuration`.

        ``value`` est la propriété du ``sap.m.NumericContent`` rendu DANS la
        tuile, ``rendered`` le texte qu'il affiche. ``number`` n'est rempli que
        pour un entier lu sans ambiguïté avec les symboles EFFECTIFS de la page
        (``1.950`` vaut 1950 quand la page groupe par des points) ; ``loaded``
        est faux tant que la valeur est la valeur d'attente ``...``, le SEUL
        témoin fiable : la tuile et son contenu se déclarent ``Loaded`` avant
        que la requête ne revienne (mesuré). ``truncated`` signale un rendu qui
        n'est pas la valeur (la tuile coupe à cinq caractères : ``10.000``
        affiché ``10.00``).

        Une lecture, pas une attente : pour un compteur chargé, voir `Wait For
        Flp Tile Counter`. Échoue si aucune tuile ne porte l'intent (en listant
        celles vues), si plusieurs le portent sans ``index=``, ou si la tuile
        n'a pas de contenu numérique (tuile statique). ::

            ${tuile}=    Get Flp Tile Counter    EPMPurchaseOrder-approve
            Log    ${tuile}[value] (chargé : ${tuile}[loaded])
        """
        seen = self._rendered_tiles()
        tile = self._pick_tile(
            flp_tiles.select_tiles(seen, intent, is_truthy(ignore_parameters)),
            seen, intent, index, "tuile rendue")
        contents = tile.get("contents") or []
        if not contents:
            raise AssertionError(
                "La tuile '%s' (%s) n'a aucun contenu numérique : c'est une "
                "tuile statique, elle n'affiche pas de compteur."
                % (flp_tiles.normalize_intent(intent), tile.get("tile_id")))
        if len(contents) > 1:
            raise AssertionError(
                "La tuile '%s' (%s) porte %d contenus numériques : lequel est "
                "« le » compteur n'est pas décidable ici. Valeurs : %s."
                % (flp_tiles.normalize_intent(intent), tile.get("tile_id"),
                   len(contents), [c.get("value") for c in contents]))
        content = contents[0]
        symbols = self._page_number_symbols()
        verdict = flp_tiles.tile_counter_verdict(
            content.get("value"), content.get("scale"),
            content.get("rendered"), symbols)
        base, parametres = flp_tiles.split_intent(tile.get("intent"))
        debug = flp_tiles.parse_debug_info(tile.get("debug"))
        result = {
            "intent": base,
            "intent_parameters": parametres,
            "tile_id": str(tile.get("tile_id") or ""),
            "intent_source": "target" if tile.get("target") else "href",
            "chip_id": debug.get("chip_id", ""),
            "chip_instance_id": debug.get("chip_instance_id", ""),
            "value": str(content.get("value") or ""),
            "scale": str(content.get("scale") or ""),
            "rendered": str(content.get("rendered") or "").strip(),
            "group_symbol": symbols.get("group", ""),
            "decimal_symbol": symbols.get("decimal", ""),
        }
        result.update(verdict)
        return result

    @staticmethod
    def _comparable_counter(result, accept_truncated):
        """Refuse aussitôt un compteur chargé qui n'est pas un entier
        comparable (état stable : attendre n'y changerait rien)."""
        if result["number"] is None:
            raise AssertionError(
                "Le compteur de la tuile '%s' est chargé mais n'est pas un "
                "entier comparable : %s." % (result["intent"], result["reason"]))
        if result["truncated"] and not is_truthy(accept_truncated):
            raise AssertionError(
                "Le compteur de la tuile '%s' est tronqué à l'affichage : %s. "
                "La propriété porte %s ; passer `accept_truncated=True` pour "
                "comparer la propriété malgré tout."
                % (result["intent"], result["reason"], result["number"]))
        return result

    def wait_for_flp_tile_counter(self, intent, timeout=None,
                                  accept_truncated=False, index=None,
                                  ignore_parameters=False):
        """Attend que la tuile d'un intent affiche un compteur **chargé et
        entier**, et retourne le même dict que `Get Flp Tile Counter`, dont
        ``number`` (un entier) est la valeur à comparer.

        L'attente porte sur la VALEUR, parce que rien d'autre ne témoigne du
        chargement : la tuile et son contenu se déclarent ``Loaded`` pendant
        qu'ils affichent encore ``...``, et `Wait For Ui5 Idle` ne voit pas la
        requête de la tuile (mesuré sur 1.71). Attente active bornée par
        ``timeout`` (défaut : ``ui5_timeout``), jamais une pause fixe ; une
        tuile pas encore rendue est attendue elle aussi.

        Échoue, en nommant l'intent et la dernière valeur vue :

        * à l'expiration, si la valeur est restée ``...`` : la requête n'est
          pas revenue, ou le service de la tuile ne rend pas un nombre (la
          tuile ``Repository-manage`` des launchpads du banc y reste pour
          toujours) ;
        * aussitôt, si le compteur chargé n'est pas un entier lisible (facteur
          d'échelle ``K``/``M``, décimale, forme inconnue) : une approximation
          ne se compare pas ;
        * aussitôt, si le rendu est tronqué, sauf ``accept_truncated=True`` :
          l'utilisateur ne voit alors pas le nombre que la propriété porte.

        Ne compare rien : la comparaison, et son message qui nomme les deux
        nombres, reviennent à l'appelant. Ne rafraîchit rien non plus : une
        tuile déjà chargée rend aussitôt sa valeur, qui peut dater du
        chargement du launchpad ; pour une valeur dont la requête est
        POSTÉRIEURE à un instant donné, voir `Refresh Flp Tile Counter`. ::

            ${tuile}=    Wait For Flp Tile Counter    EPMPurchaseOrder-approve    timeout=30s
            Should Be Equal As Integers    ${tuile}[number]    ${attendu}
            ...    msg=Tuile ${tuile}[number], vue CDS ${attendu}
        """
        budget = timestr_to_secs(timeout if timeout is not None else self.ui5_timeout)
        last = {}

        def _check():
            try:
                result = self.get_flp_tile_counter(
                    intent, index=index, ignore_parameters=ignore_parameters)
            except AssertionError as err:
                last["error"] = str(err)
                return None
            last["result"] = result
            last.pop("error", None)
            return result if result["loaded"] else None

        result = poll_until(_check, budget, step=self.poll_interval)
        if not result:
            vu = last.get("result")
            if vu is None:
                raise AssertionError(
                    "Tuile '%s' introuvable après %s s : %s"
                    % (flp_tiles.normalize_intent(intent), budget,
                       last.get("error", "aucune lecture")))
            raise AssertionError(
                "Le compteur de la tuile '%s' n'est pas chargé après %s s : "
                "dernière valeur %r (%s)."
                % (vu["intent"], budget, vu["value"], vu["reason"]))
        return self._comparable_counter(result, accept_truncated)

    def page_number_symbols_should_match_decimal_notation(self, decimal_format_key):
        """Les symboles numériques EFFECTIFS de la page (groupement et
        décimale, déduits d'un nombre que la page formate) sont ceux qu'impose
        la notation décimale SAP de l'utilisateur (``USR01-DCPFM`` : vide →
        ``1.234.567,89``, ``X`` → ``1,234,567.89``, ``Y`` → ``1 234 567,89``).
        Retourne les symboles lus.

        Le contrôle CROISÉ de la conversion d'un compteur de tuile : `Get Flp
        Tile Counter` lit un nombre avec les symboles de la page, ce qui est
        juste tant que la page formate selon l'utilisateur ; une page qui
        formaterait selon la langue du navigateur lirait ``1,950`` là où
        l'utilisateur voit ``1.950``. La notation se lit par un autre canal
        (RFC sur ``USR01``) et se passe telle quelle, clé vide comprise. ::

            ${dcpfm}=    Lire La Notation Decimale De L Utilisateur
            Page Number Symbols Should Match Decimal Notation    ${dcpfm}

        Échoue en nommant les deux jeux de symboles, ou si la page n'a pas pu
        formater son échantillon (runtime absent)."""
        attendus = flp_tiles.symbols_for_decimal_notation(decimal_format_key)
        lus = self._page_number_symbols()
        if not lus:
            raise AssertionError(
                "La page n'a pas formaté son échantillon numérique : aucun "
                "runtime UI5 sur la portée courante, ou formateur absent.")
        if lus != attendus:
            raise AssertionError(
                "La page groupe par %r et sépare les décimales par %r ; la "
                "notation décimale %r de l'utilisateur impose %r et %r."
                % (lus["group"], lus["decimal"], decimal_format_key,
                   attendus["group"], attendus["decimal"]))
        return lus

    def get_flp_tile_configuration(self, intent, index=None,
                                   ignore_parameters=False):
        """Retourne la **configuration** d'une tuile des groupes de
        l'utilisateur, désignée par son intent : un dict JSON-safe
        ``{intent, intent_parameters, title, group_id, tile_instance_id,
        chip_id, base_chip_id, service_url, service_path, service_query,
        service_refresh_interval, display_number_unit, configuration}``, où
        ``configuration`` est le paramètre ``tileConfiguration`` DÉCODÉ en
        entier.

        C'est ce qui relie une tuile au service qu'elle interroge : sur une
        tuile dynamique, ``service_url`` est l'adresse dont la réponse devient
        le compteur (``/sap/opu/odata/SAP/SEPMRA_PO_APV/PurchaseOrders/$count``
        pour « Approve Purchase Orders »), séparée en ``service_path`` et
        ``service_query`` : une adresse qui porte un ``$filter`` ne compte
        pas la même chose que son chemin nu, et un contrôle par sous-chaîne
        ne le verrait pas. ``service_refresh_interval`` est le
        rafraîchissement en secondes. Une tuile statique rend une
        ``service_url`` vide. Les paramètres d'intent comptent comme pour
        `Get Flp Tile Counter` (``ignore_parameters`` pour s'en affranchir).

        Lu par le service ushell ``LaunchPage`` (lecture pure, sans
        injection), parce que ``getTileTarget`` y rend une cible VIDE sur
        l'adaptateur ABAP (mesuré sur 1.71 et 1.120) : l'intent vient de
        ``navigation_target_url`` de la configuration. Échoue si aucune tuile
        des groupes ne porte l'intent (en listant celles vues), ou si
        plusieurs le portent sans ``index=``. `List Flp Catalogs` dit ce que
        l'utilisateur a le DROIT d'ouvrir ; ce keyword-ci, ce que ses groupes
        portent. ::

            ${conf}=    Get Flp Tile Configuration    EPMPurchaseOrder-approve
            Should End With    ${conf}[service_url]    /$count
        """
        raw = self._flp_result(self._evaluate(FLP_TILE_CONFIGURATION_PROBE_JS),
                               service="LaunchPage")
        seen = []
        for entry in raw or []:
            conf = flp_tiles.decode_tile_configuration(entry.get("configuration"))
            cible = conf.get("navigation_target_url") or ""
            if not cible and conf.get("navigation_semantic_object"):
                cible = "#%s-%s" % (conf.get("navigation_semantic_object"),
                                    conf.get("navigation_semantic_action") or "")
                if conf.get("navigation_semantic_parameters"):
                    cible += "?" + str(conf.get("navigation_semantic_parameters"))
            chemin, requete = flp_tiles.split_service_url(conf.get("service_url"))
            seen.append({
                "intent": cible,
                "title": str(entry.get("title") or ""),
                "group_id": str(entry.get("group_id") or ""),
                "tile_instance_id": str(entry.get("tile_instance_id") or ""),
                "chip_id": str(entry.get("chip_id") or ""),
                "base_chip_id": str(entry.get("base_chip_id") or ""),
                "service_url": str(conf.get("service_url") or ""),
                "service_path": chemin,
                "service_query": requete,
                "service_refresh_interval": conf.get("service_refresh_interval"),
                "display_number_unit": str(conf.get("display_number_unit") or ""),
                "configuration": conf,
            })
        choisie = dict(self._pick_tile(
            flp_tiles.select_tiles(seen, intent, is_truthy(ignore_parameters)),
            seen, intent, index, "tuile des groupes"))
        choisie["intent"], choisie["intent_parameters"] = \
            flp_tiles.split_intent(choisie["intent"])
        return choisie

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
        mêmes raisons que `Wait For Flp Tile Counter`. ::

            ${avant}=    Compter Par Le Canal RFC
            ${tuile}=    Refresh Flp Tile Counter    EPMPurchaseOrder-approve    timeout=60s
            ${apres}=    Compter Par Le Canal RFC
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
