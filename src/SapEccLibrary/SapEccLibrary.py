"""SapEccLibrary : un fork robuste de robotframework-sapguilibrary pour SAP ECC.

Hérite de tous les keywords de l'upstream ``SapGuiBase`` (vendored, Apache 2.0)
et ajoute :

* amorçage autonome de la connexion      -> ``keywords/_connection.py``
* synchronisation réelle / attentes intelligentes -> ``keywords/_waits.py``
* ergonomie de grille ALV (lecture par titre)     -> ``keywords/_grid.py``
* un override de `Run Transaction` indépendant de la locale (ci-dessous)
* des erreurs d'élément absent qui disent sur quel écran on se trouve
  (ci-dessous, `Element Should Be Present` et `Get Element Type`)

Il s'agit de la bibliothèque SAP GUI de *bas niveau*. Les keywords lisibles
métier pour les tests se trouvent dans ``resources/ecc_keywords.resource``
au-dessus de celle-ci.
"""
import os
import threading

from robot.api import logger
from robot.api.types import Secret
from robot.utils import timestr_to_secs

from sapfx_common.com_safety import ensure_com_initialized
from sapfx_common.secrets import reveal_secret
from sapfx_common.session_context import current_execution_namespace

from ._vendor.sapgui_base import SapGuiBase
from .keywords import (
    ConnectionKeywords,
    DdicKeywords,
    DiagnosticsKeywords,
    EmbeddedBrowserKeywords,
    GridKeywords,
    HealingKeywords,
    PerceptionKeywords,
    PointerKeywords,
    SemanticKeywords,
    SessionKeywords,
    WaitKeywords,
)


class SapEccLibrary(ConnectionKeywords, WaitKeywords, GridKeywords,
                    PerceptionKeywords, DiagnosticsKeywords, HealingKeywords,
                    SemanticKeywords, EmbeddedBrowserKeywords, PointerKeywords,
                    SessionKeywords, DdicKeywords, SapGuiBase):
    """Bibliothèque Robot Framework pour automatiser le client bureau SAP GUI (ECC,
    backend S/4HANA GUI). Superset compatible de SapGuiLibrary.

    == Avant d'exécuter les tests ==
    Le scripting doit être activé côté serveur (transaction ``RZ11`` ->
    ``sapgui/user_scripting = TRUE``) et côté client (Options SAP GUI ->
    Accessibilité & Scripting). Démarrez ensuite le Logon Pad manuellement et
    appelez `Connect To Session`, ou laissez la bibliothèque le démarrer avec
    `Open Sap Logon`.

    == Localisateurs ==
    Les éléments sont adressés par leur identifiant SAP depuis la fenêtre, ex.
    ``wnd[0]/usr/txtRSYST-BNAME``. Capturez les identifiants avec l'outil Spy
    du projet (``tools/recorder``) ou l'enregistreur de scripts intégré au SAP GUI.

    En complément, les keywords `Find Element By Label`, `Fill Field By Label`,
    `Read Field By Label` et `Click Button By Label` acceptent des localisateurs
    **humains** (libellé visible, ``Gauche @ Haut``, ``N @ Libellé``/``Libellé
    @ N`` pour une grille, ``Ancre >> Reste`` pour une portée, ``= contenu`` ;
    voir `Find Element By Label`), résolus géométriquement sur l'écran réel ; et
    `Resolve Element With Healing` accepte une ancre ``label=`` de secours.

    == Contrôles navigateur embarqués ==
    Certains écrans embarquent un contrôle WebView2 (aide moderne, Business
    Client) : `Enable Embedded Browser Debugging` (à appeler avant `Open Sap
    Logon`) puis `Switch To Embedded Browser Page` le rendent pilotable par la
    bibliothèque Browser (``Library    Browser`` requise dans la suite).
    """

    __version__ = "0.6.7"
    ROBOT_LIBRARY_SCOPE = "SUITE"
    ROBOT_LIBRARY_DOC_FORMAT = "ROBOT"

    # Vrais préfixes de navigation de l'OK-code (nouvelle session/fenêtre/onglet).
    # Un tcode de namespace client/partenaire (ex. ``/BEV1/RCA01``, ``/SAPAPO/...``)
    # commence lui aussi par ``/`` mais n'EST PAS un préfixe de navigation.
    _NAV_PREFIXES = ("/n", "/o", "/i")

    # Alias de la session historique (hors registre) : voir keywords/_sessions.py.
    _DEFAULT_ALIAS = "default"

    def _context_state(self):
        namespace = current_execution_namespace()
        return self._state_by_namespace.setdefault(namespace, {})

    # -- registre de sessions par alias (multi-session : keywords/_sessions.py) --
    # ``sapapp`` (le moteur de scripting, un par process saplogon) reste PARTAGÉ
    # au niveau du namespace ; ``session``/``connection`` sont routés vers le
    # slot de l'alias ACTIF ; la compatibilité est totale : sans keyword de
    # registre, tout vit dans l'alias ``default`` comme avant.

    def _session_registry(self):
        return self._context_state().setdefault("sessions", {})

    def _active_alias(self):
        return self._context_state().get("active_alias", self._DEFAULT_ALIAS)

    def _set_active_alias(self, alias):
        self._context_state()["active_alias"] = alias

    def _active_slot(self):
        return self._session_registry().setdefault(self._active_alias(), {})

    def _touch_com_thread(self, slot):
        """Rail de sûreté **STA** : la session appartient au thread COM qui l'a
        bindée. Un accès depuis un AUTRE thread initialise COM défensivement
        (marshaling, le mode dont dépendent les state providers rf-mcp,
        validé live) et se journalise une fois ; ``SAPFX_STRICT_COM_THREAD=1``
        en fait une erreur actionnable, au lieu du ``RPC_E_WRONG_THREAD``
        cryptique de COM, ou pire d'un plantage différé."""
        ident = threading.get_ident()
        owner = slot.get("com_thread")
        if owner is None or owner == ident:
            return
        if os.environ.get("SAPFX_STRICT_COM_THREAD") == "1":
            raise RuntimeError(
                "SAP session '%s' is COM-bound to thread %s but accessed from "
                "thread %s, and SAPFX_STRICT_COM_THREAD=1 forbids cross-thread "
                "access. SAP GUI Scripting is STA COM: drive every keyword of "
                "a session from the thread that bound it: multiplex sessions "
                "with `Switch Sap Session`, never with threads."
                % (self._active_alias(), owner, ident))
        seen = slot.setdefault("threads_seen", set())
        if ident not in seen:
            seen.add(ident)
            ensure_com_initialized()
            logger.debug(
                "SAP session '%s': first access from thread %s (COM-bound on "
                "thread %s); COM initialised defensively for marshalled "
                "cross-thread access." % (self._active_alias(), ident, owner))

    @property
    def sapapp(self):
        return self._context_state().get("sapapp", -1)

    @sapapp.setter
    def sapapp(self, value):
        self._context_state()["sapapp"] = value

    @property
    def session(self):
        slot = self._active_slot()
        value = slot.get("session", -1)
        if value is not None and not isinstance(value, int):
            self._touch_com_thread(slot)
        return value

    @session.setter
    def session(self, value):
        slot = self._active_slot()
        slot["session"] = value
        if value is not None and not isinstance(value, int):
            # binde le thread COM propriétaire ; un re-bind volontaire (Connect
            # To Session depuis un autre thread) reprend la propriété.
            slot["com_thread"] = threading.get_ident()
            slot.pop("threads_seen", None)

    @property
    def connection(self):
        return self._active_slot().get("connection", -1)

    @connection.setter
    def connection(self, value):
        self._active_slot()["connection"] = value

    @property
    def _saplogon_proc(self):
        return self._context_state().get("saplogon_proc")

    @_saplogon_proc.setter
    def _saplogon_proc(self, value):
        self._context_state()["saplogon_proc"] = value

    @property
    def _last_screen_signature(self):
        return self._context_state().get("last_screen_signature")

    @_last_screen_signature.setter
    def _last_screen_signature(self, value):
        self._context_state()["last_screen_signature"] = value

    @property
    def _object_tree_unsupported(self):
        return self._context_state().get("object_tree_unsupported", False)

    @_object_tree_unsupported.setter
    def _object_tree_unsupported(self, value):
        self._context_state()["object_tree_unsupported"] = value

    def __init__(self, screenshots_on_error=True, screenshot_directory=None,
                 default_timeout="30s", poll_interval="0.1s"):
        """``default_timeout`` est la valeur de repli utilisée par chaque keyword
        ``Wait Until ...``. Accepte les chaînes de temps Robot (``30s``, ``500 ms``).

        ``poll_interval`` est le délai entre deux sondages de `Wait Until Busy
        Done` (l'attente la plus fréquemment invoquée, après quasi chaque
        action) : la valeur par défaut convient à une session locale, mais une
        connexion à un serveur SAP distant/plus lent peut bénéficier d'un
        intervalle plus large pour réduire le nombre d'accès COM inutiles."""
        self._state_by_namespace = {}
        SapGuiBase.__init__(self, screenshots_on_error, screenshot_directory)
        self.default_timeout = timestr_to_secs(default_timeout)
        self.poll_interval = timestr_to_secs(poll_interval)
        self._saplogon_proc = None

    @classmethod
    def _has_nav_prefix(cls, transaction):
        """Vrai si la chaîne commence par un préfixe de navigation OK-code (/n, /o, /i).

        ``transaction[:2]`` ne suffit pas : un tcode de namespace commençant par
        N, O ou I (``/IWFND/MAINT_SERVICE``, ``/IWBEP/...``) partage ses deux
        premiers caractères avec un préfixe. La forme du reste tranche : après un
        vrai préfixe ne peut venir qu'un tcode simple (sans ``/``) ou un tcode de
        namespace (commençant par ``/``, ex. ``/n/BEV1/RCA01``). Un reste
        contenant ``/`` sans commencer par ``/`` (``WFND/MAINT_SERVICE``) n'est
        pas un tcode valide : le ``/X`` initial appartenait à un namespace.
        """
        if transaction[:2].lower() not in cls._NAV_PREFIXES:
            return False
        rest = transaction[2:]
        return not rest or rest.startswith("/") or "/" not in rest

    def run_transaction(self, transaction, skip_if_error=False):
        """Exécute une transaction SAP et vérifie qu'elle s'est bien ouverte.

        Remplace le keyword upstream, qui détectait une transaction inconnue en
        comparant le *texte* de la barre de statut en néerlandais/anglais/allemand
        uniquement, fragile dans toute autre langue SAP. Ici, on compare la
        **transaction réellement active** (``session.Info.Transaction``) au code
        demandé : c'est totalement indépendant de la locale et robuste (validé en
        live, où une transaction inexistante renvoie un message de type ``S`` et non
        ``E`` : l'ancienne hypothèse « type ``E`` » était donc fausse).

        Préfixe automatiquement ``/n`` pour démarrer la transaction même depuis un
        autre écran, y compris pour un tcode de **namespace** (``/BEV1/RCA01``),
        dont le ``/`` initial fait partie du code et n'est pas un préfixe de
        navigation : seul un vrai préfixe déjà présent (``/n``, ``/o``, ``/i``)
        dispense d'en rajouter un, même quand le namespace commence par la même
        lettre qu'un préfixe (``/IWFND/MAINT_SERVICE``), voir `_has_nav_prefix`.
        Définissez ``skip_if_error=True`` pour journaliser au lieu d'échouer
        (étapes de navigation optionnelles).
        """
        already_prefixed = self._has_nav_prefix(transaction)
        okcode = transaction if already_prefixed else "/n" + transaction
        self.session.findById("wnd[0]/tbar[0]/okcd").text = okcode
        self.send_vkey(0)
        self.wait_until_busy_done()

        # Les OK-codes système (fermer session/fenêtre) ne démarrent pas de transaction.
        if transaction.lower() in ("/nex", "/n", "/i", "/o", "/nend"):
            return

        expected = transaction.upper()
        if already_prefixed and len(expected) > 2:
            expected = expected[2:]

        actual = self.session.Info.Transaction
        # Un tcode de namespace peut être rendu par ``Info.Transaction`` avec ou
        # sans son ``/`` initial : les deux côtés sont normalisés à l'identique
        # (aucun tcode valide ne se distingue d'un autre par ses ``/`` de tête).
        if actual.upper().lstrip("/") != expected.lstrip("/"):
            status = self.session.findById("wnd[0]/sbar")
            message = ("Transaction '%s' did not start (active='%s'). Status: %s"
                       % (transaction, actual, status.text))
            if skip_if_error:
                logger.warn(message)
                return
            self.take_screenshot()
            raise ValueError(message)

    def input_password(self, element_id, password: "str | Secret"):
        """Saisit un mot de passe dans le champ identifié, sans le journaliser.

        Remplace le keyword upstream pour accepter, en plus d'une chaîne, le
        type ``Secret`` de Robot Framework 7.4 ; créez la variable typée dès la
        ligne de commande (``-v "SAP_PASSWORD: Secret:<motdepasse>"``) : sa
        valeur est alors masquée partout, y compris en niveau de log TRACE. Le
        secret n'est déballé qu'ici, juste avant la frontière COM ; le
        comportement pour une chaîne ordinaire est inchangé.
        """
        return super().input_password(element_id, reveal_secret(password))

    def element_should_be_present(self, element_id, message=None):
        """Échoue si ``element_id`` est absent de l'écran courant.

        Comportement upstream inchangé : seul le message d'échec est
        enrichi de l'identité de l'écran réel (voir `_absence_message`).
        Un ``message`` explicite fourni par l'appelant est respecté tel
        quel : c'est sa phrase, pas la nôtre.
        """
        try:
            return super().element_should_be_present(element_id, message)
        except ValueError as absent:
            if message is not None:
                raise
            raise ValueError(self._absence_message(str(absent))) from absent

    def get_element_type(self, element_id):
        """Retourne le type SAP de ``element_id`` (``GuiButton``, ``GuiTab``...).

        Comportement upstream inchangé, message d'absence enrichi de
        l'écran courant. C'est le chemin par lequel passe `Click Element`,
        qui résout le type avant d'agir : sans cet enrichissement, un clic
        sur un écran inattendu ne rapporte que l'id manquant.
        """
        try:
            return super().get_element_type(element_id)
        except ValueError as absent:
            raise ValueError(self._absence_message(str(absent))) from absent

    def _absence_message(self, message):
        """Suffixe un message d'élément absent par l'IDENTITÉ de l'écran actif.

        « Cannot find element with id 'wnd[0]/tbar[1]/btn[31]' » ne
        distingue pas les trois causes possibles : localisateur périmé,
        élément pas encore matérialisé, ou écran qui n'est pas celui
        qu'on croit. La troisième est la plus fréquente en ECC (une
        transaction qui refuse une saisie reste sur l'écran précédent) et
        c'est la seule que l'id seul ne peut pas révéler. Une ligne
        ``# screen <Programme>/<Transaction>/<Numéro>`` tranche
        immédiatement, pour un humain comme pour un agent.

        Mesuré le 2026-08-17 : le même `Click Element` avait réussi
        vingt étapes plus tôt dans la session, puis échoué sur la table
        suivante ; sans l'écran, le diagnostic généré a conclu à un
        problème de synchronisation et a été rejeté par le juge.

        Best-effort, comme `_closest_matches_hint` : le calcul ne masque
        jamais l'erreur d'origine, et le mixin de perception peut être
        absent (usage isolé en tests unitaires).
        """
        header = getattr(self, "_screen_header", None)
        if header is None:
            return message
        try:
            return "%s\n%s" % (message, header())
        except Exception:                       # noqa: BLE001 (best-effort)
            return message

    def get_current_transaction(self):
        """Retourne le **code de la transaction active** (``session.Info.Transaction``),
        p.ex. ``SE16`` ou ``SESSION_MANAGER`` sur l'écran SAP Easy Access.
        Indépendant de la langue, idéal pour les assertions de navigation."""
        return self.session.Info.Transaction

    def get_status_message(self):
        """Retourne ``(message_type, text)`` de la barre de statut courante.

        ``message_type`` vaut ``S`` (succès), ``W`` (avertissement), ``E`` (erreur),
        ``I`` (info), ``A`` (abandon), ou ``""`` quand la barre est vide ; tous
        indépendants de la locale."""
        status = self.session.findById("wnd[0]/sbar")
        return status.messageType, status.text

    def status_message_should_be_success(self):
        """Échoue si la barre de statut n'affiche pas actuellement un message de succès (``S``)."""
        msg_type, text = self.get_status_message()
        if msg_type not in ("S", ""):
            self.take_screenshot()
            raise AssertionError(
                "Expected a success status message but got type '%s': %s"
                % (msg_type, text)
            )
