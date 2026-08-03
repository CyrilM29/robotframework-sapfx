"""Keywords d'attente et de synchronisation.

L'upstream `SapGuiBase` ne propose qu'un `time.sleep(explicit_wait)` *fixe* après
chaque keyword. C'est fragile : soit on perd du temps (attente trop longue), soit
les tests sont instables (attente trop courte). Ce mixin ajoute une vraie
synchronisation basée sur deux propriétés de la SAP GUI Scripting API :

* `session.Busy` vaut ``True`` pendant qu'un aller-retour serveur est en cours.
* `session.findById(id, False)` retourne ``None`` (au lieu de lever une exception)
  quand le second argument est ``False`` — idéal pour sonder l'existence d'un élément.

Ces keywords sont la méthode recommandée pour attendre ; réservez `Set Explicit Wait`
aux démos et au débogage. Les boucles de sondage/relance elles-mêmes vivent dans
``sapfx_common.polling`` (partagées avec le canal Fiori).
"""
from robot.utils import secs_to_timestr, timestr_to_secs

from sapfx_common.polling import poll_until, retry_call


class WaitKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose que ``self.session`` est une
    GuiSession connectée (définie par `Connect To Session`) et que
    ``self.default_timeout``/``self.poll_interval`` (secondes, float) existent."""

    def wait_until_busy_done(self, timeout=None):
        """Bloque jusqu'à ce que le serveur SAP ait fini de traiter la requête en cours.

        Sonde ``session.Busy`` jusqu'à ce qu'il soit ``False`` ou que ``timeout``
        soit écoulé. ``timeout`` accepte les chaînes de temps Robot (``30s``,
        ``500 ms``) ; utilise ``default_timeout`` de la bibliothèque par défaut.

        À appeler après toute action déclenchant un aller-retour serveur (Entrée,
        Sauvegarde, ouverture d'une transaction) avant de faire des assertions sur
        l'écran résultant.
        """
        def idle():
            try:
                return not self.session.Busy
            except Exception:  # session momentanément indisponible pendant l'aller-retour
                return False

        if not poll_until(idle, self._timeout_secs(timeout), step=self.poll_interval):
            self.take_screenshot()
            raise AssertionError(
                "SAP session was still busy after %s seconds." % self._timeout_secs(timeout)
            )

    def wait_until_element_present(self, element_id, timeout=None, interval="0.2s"):
        """Attend que ``element_id`` existe sur l'écran courant.

        Retourne l'élément résolu (objet COM) pour permettre l'enchaînement. Lève
        une exception après ``timeout`` si l'élément n'apparaît pas.

        ATTENTION sous rf-mcp (exécution hors thread principal) : ne faites jamais
        *retourner* cet objet COM par un keyword appelé depuis l'agent (RPC_E_WRONG_
        THREAD à la sérialisation). En fin de lot piloté par rf-mcp, préférez
        `Element Should Be Present` (qui n'a pas de valeur de retour) comme dernière
        étape ; les runs Robot classiques ne sont pas concernés.
        """
        element = poll_until(
            lambda: self._find(element_id, raise_on_missing=False),
            self._timeout_secs(timeout), step=timestr_to_secs(interval))
        if element is None:
            self.take_screenshot()
            raise AssertionError(
                "Element '%s' did not appear within %s seconds.%s"
                % (element_id, self._timeout_secs(timeout),
                   self._closest_matches_hint(element_id))
            )
        return element

    def wait_until_element_value_is(self, element_id, expected, timeout=None, interval="0.2s"):
        """Attend que la valeur retournée par `Get Value` pour ``element_id`` soit
        égale à ``expected``. Utile pour les panneaux de statut mis à jour après
        une sauvegarde."""
        state = {"last": None}

        def value_matches():
            element = self._find(element_id, raise_on_missing=False)
            if element is None:
                return False
            state["last"] = self.get_value(element_id)
            return state["last"] == expected

        if not poll_until(value_matches, self._timeout_secs(timeout),
                          step=timestr_to_secs(interval)):
            self.take_screenshot()
            raise AssertionError(
                "Element '%s' value was '%s', expected '%s' after %s seconds."
                % (element_id, state["last"], expected, self._timeout_secs(timeout))
            )

    def click_element_with_retry(self, element_id, retries=3, interval="0.3s"):
        """Clique sur ``element_id`` en retentant les échecs transitoires.

        Sur SAP GUI, un clic peut échouer ponctuellement parce que l'élément n'est
        pas encore (re)matérialisé après un aller-retour, ou que le pont COM est
        momentanément indisponible. On vérifie la présence puis on clique, jusqu'à
        ``retries`` fois espacées de ``interval`` ; la dernière erreur est relevée si
        tous les essais échouent. Préférer ce keyword à un `Click Element` nu sur les
        écrans qui se redessinent (ALV, dialogues asynchrones)."""
        def attempt():
            element = self._find(element_id, raise_on_missing=False)
            if element is None:
                raise LookupError("element '%s' is not present" % element_id)
            self.click_element(element_id)

        try:
            retry_call(attempt, attempts=retries, interval=timestr_to_secs(interval))
        except Exception as last:
            self.take_screenshot()
            raise AssertionError(
                "Could not click '%s' after %s attempts. Last error: %s"
                % (element_id, retries, last)
            )

    def set_default_timeout(self, timeout):
        """Change le ``default_timeout`` de la bibliothèque et retourne l'ancienne valeur.

        ``default_timeout`` est le repli utilisé par chaque keyword ``Wait
        Until ...`` (et par les attentes de connexion) quand aucun ``timeout``
        explicite n'est passé — fixé à l'import de la bibliothèque, ajustable
        ici en cours de suite. Accepte les chaînes de temps Robot (``30s``,
        ``2 min``). L'ancienne valeur est retournée dans le même format,
        prête à être restaurée en teardown :

        | ${old}= | Set Default Timeout | 2 min |
        | ... étapes lentes (génération de données de démo) ... | |
        | Set Default Timeout | ${old} | |

        Portée : l'instance de bibliothèque (scope ``SUITE``) — le réglage ne
        déborde jamais sur la suite suivante.
        """
        previous = secs_to_timestr(self.default_timeout)
        self.default_timeout = timestr_to_secs(timeout)
        return previous

    def set_poll_interval(self, interval):
        """Change le ``poll_interval`` de la bibliothèque et retourne l'ancienne valeur.

        ``poll_interval`` est le délai entre deux sondages de `Wait Until Busy
        Done` (l'attente invoquée après quasi chaque action) : élargissez-le en
        cours de suite pour une connexion à un serveur distant/lent (moins
        d'accès COM), resserrez-le pour une session locale réactive. Accepte
        les chaînes de temps Robot (``0.5s``, ``250 ms``) ; retourne l'ancienne
        valeur dans le même format, restaurable comme pour `Set Default
        Timeout`. Portée : l'instance de bibliothèque (scope ``SUITE``).
        """
        previous = secs_to_timestr(self.poll_interval)
        self.poll_interval = timestr_to_secs(interval)
        return previous

    # -- helpers (méthodes internes) ------------------------------------------

    def _find(self, element_id, raise_on_missing=True):
        """`findById` sous la forme silencieuse (second argument ``False``) pour que
        le sondage ne lève pas d'exception. Retourne ``None`` si absent et que
        ``raise_on_missing`` est False."""
        try:
            element = self.session.findById(element_id, False)
        except Exception:
            element = None
        if element is None and raise_on_missing:
            self.take_screenshot()
            raise ValueError("Cannot find element with id '%s'." % element_id)
        return element

    def _timeout_secs(self, timeout):
        return self.default_timeout if timeout is None else timestr_to_secs(timeout)

    def _closest_matches_hint(self, element_id):
        """Suffixe de message d'erreur listant les ids présents les plus proches
        (erreur auto-corrigible : un agent — ou un humain — corrige le
        localisateur sans repasser par une perception complète). Best-effort :
        ne masque jamais l'erreur d'origine si le calcul échoue, et vide si le
        mixin healing n'est pas composé (usage isolé du mixin en tests)."""
        get_closest = getattr(self, "get_closest_element_ids", None)
        if get_closest is None:
            return ""
        try:
            scored = get_closest(element_id, limit=5)
        except Exception:
            return ""
        lines = ["  - %s  (similarité %d%%)" % (cid, round(score * 100))
                 for cid, score in scored if score >= 0.05]
        if not lines:
            return ""
        return "\nClosest ids on the current screen:\n%s" % "\n".join(lines)
