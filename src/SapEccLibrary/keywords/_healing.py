"""Mixin d'auto-réparation de localisateurs SAP GUI.

Un id SAP GUI hiérarchique casse typiquement par renumérotation de sous-écrans
(``subSUB0:SAPLMEGUI:0013`` -> ``:0015`` selon customizing/variante/release)
alors que le champ visé, lui, est toujours là. Ces keywords scorent les
contrôles réellement présents (parcours de la fenêtre active) contre l'id
attendu — segment terminal (nom du champ dynpro) lourdement pondéré, chemin en
LCS, type — et :

* `Resolve Element With Healing` **répare** au-dessus d'un seuil, avec un
  warning journalisé (jamais silencieux : le test passe, la dérive est visible
  et le localisateur à corriger est dans le log) ;
* `Get Closest Element Ids` alimente des messages d'erreur **auto-corrigibles**
  (un agent rf-mcp — ou un humain — lit les candidats scorés directement dans
  l'erreur au lieu de repartir d'une perception complète).

Le scoring pur vit dans ``sapfx_common.healing`` (partagé, typé, testé).
"""
from robot.api import logger

from sapfx_common.healing import closest_gui_ids, format_suggestions
from sapfx_common.healing_telemetry import record_healing
from sapfx_common.semantic import resolve_semantic


class HealingKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose ``self.session`` connectée."""

    def get_closest_element_ids(self, element_id, limit=5):
        """Retourne les ids de la fenêtre active les plus proches de
        ``element_id`` : liste de paires ``[id, score]``, score décroissant.

        Sert aux messages d'erreur enrichis et au diagnostic d'un localisateur
        périmé (« qu'est-ce qui y ressemble sur l'écran réel ? »). Lecture seule."""
        scored = closest_gui_ids(element_id, self._present_ids(), limit=int(limit))
        return [[sc.candidate, round(sc.score, 3)] for sc in scored]

    def resolve_element_with_healing(self, element_id, threshold=0.6, limit=5,
                                     label=None):
        """Résout ``element_id`` en id réellement présent, en le réparant si besoin.

        1. Si l'id existe tel quel -> le retourne (chemin nominal, coût quasi nul).
        2. Sinon, score tous les contrôles de la fenêtre active ; si le meilleur
           atteint ``threshold`` -> le retourne avec un WARNING journalisé
           (« localisateur réparé : ancien -> nouveau, score »), pour que la
           dérive soit corrigée dans ``resources/`` à la prochaine maintenance.
           La réparation est aussi consignée dans le journal JSONL cumulatif si
           ``SAPFX_HEALING_LOG`` est défini (``sapfx_common.healing_telemetry``).
        3. Si ``label`` est fourni et que le score ne suffit pas : tentative par
           **ancre de libellé** (``sapfx_common.semantic``, grammaire de `Find
           Element By Label`) — un libellé visible survit aux renumérotations
           d'écran qui pulvérisent les ids. La réparation n'est adoptée que si
           le libellé désigne UN SEUL élément (jamais de premier-match
           silencieux) ; journalisée en WARNING + télémétrie ``engine=label``.
        4. Sinon -> échec avec les ``limit`` candidats les plus proches DANS le
           message (erreur auto-corrigible : un agent peut choisir et réessayer).

        Retourne toujours une **chaîne** (jamais l'objet COM — sûr à travers la
        frontière rf-mcp). Usage type::

            ${id}=    Resolve Element With Healing    wnd[0]/usr/ctxtMEPO_TOPLINE-BSART    label=Doc. type
            Input Text    ${id}    NB
        """
        if self._find(element_id, raise_on_missing=False) is not None:
            return element_id
        threshold = float(threshold)
        elements = self._screen_elements()
        scored = closest_gui_ids(element_id,
                                 [(el.id, el.type) for el in elements],
                                 limit=int(limit))
        if scored and scored[0].score >= threshold:
            healed = scored[0]
            logger.warn(
                "Localisateur réparé (score %d%%) : '%s' est absent, '%s' retenu. "
                "Mettre à jour le localisateur dans resources/."
                % (round(healed.score * 100), element_id, healed.candidate))
            record_healing("ecc", original=element_id, healed=healed.candidate,
                           score=healed.score)
            return healed.candidate
        if label:
            matches = resolve_semantic(elements, label)
            if len(matches) == 1:
                healed_id = matches[0].element.id
                logger.warn(
                    "Localisateur réparé par ancre de libellé '%s' (via %s) : "
                    "'%s' est absent, '%s' retenu. Mettre à jour le localisateur "
                    "dans resources/." % (label, matches[0].via, element_id, healed_id))
                record_healing("ecc", original=element_id, healed=healed_id,
                               engine="label")
                return healed_id
        self.take_screenshot()
        suggestions = format_suggestions(scored)
        raise AssertionError(
            "Element '%s' introuvable et aucun candidat au-dessus du seuil %s.%s"
            % (element_id, threshold,
               ("\nCandidats les plus proches :\n%s" % suggestions) if suggestions else ""))

    # -- helpers (méthodes internes) ------------------------------------------

    def _present_ids(self):
        """Paires ``(id relatif, type)`` de tous les contrôles de la fenêtre
        active — la population de candidats du scoring. Passe par
        ``_screen_elements`` (mixin de perception) : chemin rapide
        ``GetObjectTree`` quand disponible, marche COM sinon. Défensif : une
        fenêtre indisponible donne une liste vide (échec propre en aval)."""
        return [(el.id, el.type) for el in self._screen_elements()]
