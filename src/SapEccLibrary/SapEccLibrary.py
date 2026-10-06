"""SapEccLibrary : bibliothèque Robot Framework pour SAP GUI (ECC, backend S/4HANA).

Compatible avec robotframework-sapguilibrary 1.2.1 : ses 37 keywords gardent
leur nom et leur signature (``tests/unit/test_upstream_compatibility.py``).
Son code, d'abord vendorisé tel quel, a été absorbé et réécrit le 2026-10-06
(Apache License 2.0, attribution dans NOTICE et en tête de chaque module
dérivé) : connexion (``keywords/_connection.py``), éléments
(``keywords/_elements.py``), saisies (``keywords/_inputs.py``),
vérifications de valeur (``keywords/_value_checks.py``), cellules de grille
(``keywords/_grid_cells.py``), capture sur erreur
(``keywords/_screenshots.py``) et pause explicite (``keywords/_waits.py``).

Ce module compose les mixins et porte `Run Transaction`, indépendant de la
locale. Il s'agit de la bibliothèque de *bas niveau* qui pilote SAP GUI ; les
keywords lisibles métier pour les tests se trouvent dans
``resources/ecc_keywords.resource`` au-dessus de celle-ci.
"""
import os
import threading

from robot.api import logger
from robot.utils import timestr_to_secs

from sapfx_common.com_safety import ensure_com_initialized, is_disconnected_error
from sapfx_common.session_context import current_execution_namespace

from .keywords import (
    AbapListKeywords,
    ComboBoxKeywords,
    ConnectionKeywords,
    ConnectionProbeKeywords,
    DdicKeywords,
    DiagnosticsKeywords,
    ElementKeywords,
    EmbeddedBrowserKeywords,
    GridActionKeywords,
    GridCellKeywords,
    GridKeywords,
    HealingKeywords,
    InputKeywords,
    MenuKeywords,
    PerceptionKeywords,
    PointerKeywords,
    ScreenshotKeywords,
    Se16Keywords,
    SemanticKeywords,
    SessionKeywords,
    StatusBarKeywords,
    SystemIdentityKeywords,
    TableControlKeywords,
    TabStripKeywords,
    ToolbarKeywords,
    TreeKeywords,
    ValueCheckKeywords,
    VisualKeywords,
    WaitKeywords,
    WatchKeywords,
    WindowKeywords,
)
from .keywords._screenshots import SapWindowScreenshot


class SapEccLibrary(ConnectionKeywords, ConnectionProbeKeywords, WaitKeywords,
                    GridActionKeywords, GridKeywords, AbapListKeywords,
                    TableControlKeywords, TreeKeywords, ComboBoxKeywords,
                    MenuKeywords, WindowKeywords, SystemIdentityKeywords,
                    StatusBarKeywords, TabStripKeywords, ToolbarKeywords,
                    PerceptionKeywords, ScreenshotKeywords, VisualKeywords,
                    WatchKeywords, DiagnosticsKeywords, HealingKeywords,
                    SemanticKeywords, EmbeddedBrowserKeywords, PointerKeywords,
                    SessionKeywords, DdicKeywords, Se16Keywords,
                    GridCellKeywords, ElementKeywords, InputKeywords,
                    ValueCheckKeywords):
    """Bibliothèque Robot Framework pour automatiser le client bureau SAP GUI (ECC,
    backend S/4HANA GUI).

    Remplace robotframework-sapguilibrary sans changer une suite : ses 37
    keywords gardent leur nom et leur signature, leur code a été absorbé et
    réécrit (les écritures sont relues, une vérification ne modifie rien, la
    capture sur erreur photographie la fenêtre SAP et non l'écran entier ;
    licence Apache 2.0, voir NOTICE).

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
    *humains* (libellé visible, ``Gauche @ Haut``, ``N @ Libellé`` / ``Libellé
    @ N`` pour une grille, ``Ancre >> Reste`` pour une portée, ``= contenu`` ;
    voir `Find Element By Label`), résolus géométriquement sur l'écran réel ; et
    `Resolve Element With Healing` accepte une ancre ``label=`` de secours.

    == Contrôles navigateur embarqués ==
    Certains écrans embarquent un contrôle WebView2 (aide moderne, Business
    Client) : `Enable Embedded Browser Debugging` (à appeler avant `Open Sap
    Logon`) puis `Switch To Embedded Browser Page` le rendent pilotable par la
    bibliothèque Browser (``Library    Browser`` requise dans la suite).
    """

    __version__ = "0.8.4"
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
        """Rail de sûreté *STA* : la session appartient au thread COM qui l'a
        bindée, et un proxy COM STA utilisé depuis un AUTRE thread lève
        ``RPC_E_WRONG_THREAD`` (ou une ``AttributeError`` de proxy pywin32),
        que les couches défensives transformaient en perceptions VIDES en PASS
        (relevé live sous rf-mcp le 2026-09-07). Depuis cette date, un accès
        depuis un thread étranger *ré-attache* la session sur ce thread :
        moteur de scripting ré-acquis via la ROT puis ``FindById`` de l'id de
        session mémorisé au bind (``/app/con[0]/ses[0]``), proxy mis en cache
        par thread (vérifié live : la transaction se lit depuis le second
        thread là où l'accès direct échoue). Retourne le proxy à utiliser, ou
        ``None`` pour garder l'objet du slot (thread propriétaire, ou
        ré-attachement impossible : l'ancien ``CoInitialize`` défensif reste,
        et l'appel échouera en nommant la cause). ``SAPFX_STRICT_COM_THREAD=1``
        refuse tout accès cross-thread par une erreur actionnable."""
        ident = threading.get_ident()
        owner = slot.get("com_thread")
        if owner is None or owner == ident:
            return None
        if os.environ.get("SAPFX_STRICT_COM_THREAD") == "1":
            raise RuntimeError(
                "SAP session '%s' is COM-bound to thread %s but accessed from "
                "thread %s, and SAPFX_STRICT_COM_THREAD=1 forbids cross-thread "
                "access. SAP GUI Scripting is STA COM: drive every keyword of "
                "a session from the thread that bound it: multiplex sessions "
                "with `Switch Sap Session`, never with threads."
                % (self._active_alias(), owner, ident))
        proxies = slot.setdefault("thread_proxies", {})
        if ident in proxies:
            return proxies[ident]
        seen = slot.setdefault("threads_seen", set())
        first_time = ident not in seen
        seen.add(ident)
        ensure_com_initialized()
        proxy = self._reattach_on_this_thread(slot)
        if proxy is not None:
            proxies[ident] = proxy
            logger.debug(
                "SAP session '%s': re-attached on thread %s (COM-bound on "
                "thread %s) via the scripting engine and %r."
                % (self._active_alias(), ident, owner, slot.get("session_id")))
            return proxy
        if first_time:
            logger.warn(
                "SAP session '%s': accessed from thread %s (COM-bound on thread "
                "%s) and NOT re-attachable (no session id or scripting engine "
                "unreachable): COM initialised defensively, the next access "
                "may fail naming the cross-thread cause."
                % (self._active_alias(), ident, owner))
        return None

    def _reattach_on_this_thread(self, slot):
        """Proxy de la session pour le thread COURANT : moteur ré-acquis via
        la ROT (`_acquire_scripting_engine`, mixin connexion) puis
        ``FindById(session_id)``. ``None`` si l'un des deux manque ou échoue :
        jamais une exception depuis un accesseur de propriété."""
        session_id = slot.get("session_id")
        acquire = getattr(self, "_acquire_scripting_engine", None)
        if not session_id or acquire is None:
            return None
        try:
            engine = acquire()
            if engine is None:
                return None
            return engine.FindById(session_id)
        except Exception:                       # noqa: BLE001 (best-effort)
            return None

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
            proxy = self._touch_com_thread(slot)
            if proxy is not None:
                return proxy
        return value

    @session.setter
    def session(self, value):
        slot = self._active_slot()
        slot["session"] = value
        slot.pop("thread_proxies", None)
        if value is not None and not isinstance(value, int):
            # binde le thread COM propriétaire ; un re-bind volontaire (Connect
            # To Session depuis un autre thread) reprend la propriété. L'id de
            # session (``/app/con[0]/ses[0]``) est mémorisé pour le
            # ré-attachement depuis un autre thread ; illisible -> None.
            slot["com_thread"] = threading.get_ident()
            slot.pop("threads_seen", None)
            try:
                slot["session_id"] = str(value.Id or "") or None
            except Exception:                   # noqa: BLE001 (doublure/panne)
                slot["session_id"] = None

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
        """``screenshots_on_error`` active la capture de la fenêtre SAP quand un
        keyword échoue (voir `Take Screenshot`), écrite dans
        ``screenshot_directory`` (créé au besoin ; à défaut, le dossier de
        sortie de Robot).

        ``default_timeout`` est la valeur de repli utilisée par chaque keyword
        ``Wait Until ...``. Accepte les chaînes de temps Robot (``30s``, ``500 ms``).

        ``poll_interval`` est le délai entre deux sondages de `Wait Until Busy
        Done` (l'attente la plus fréquemment invoquée, après quasi chaque
        action) : la valeur par défaut convient à une session locale, mais une
        connexion à un serveur SAP distant/plus lent peut bénéficier d'un
        intervalle plus large pour réduire le nombre d'accès COM inutiles."""
        self._state_by_namespace = {}
        self.explicit_wait = 0.0
        self.sapapp = -1
        self.session = -1
        self.connection = -1
        self.take_screenshots = screenshots_on_error
        self.screenshot = SapWindowScreenshot(self._active_window_for_capture,
                                              screenshot_directory)
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

        Le keyword de robotframework-sapguilibrary détectait une transaction
        inconnue en comparant le *texte* de la barre de statut en
        néerlandais/anglais/allemand uniquement, fragile dans toute autre
        langue SAP. Ici, on compare la
        *transaction réellement active* (``session.Info.Transaction``) au code
        demandé : c'est totalement indépendant de la locale et robuste (validé en
        live, où une transaction inexistante renvoie un message de type ``S`` et non
        ``E`` : l'ancienne hypothèse « type ``E`` » était donc fausse).

        Préfixe automatiquement ``/n`` pour démarrer la transaction même depuis un
        autre écran, y compris pour un tcode de *namespace* (``/BEV1/RCA01``),
        dont le ``/`` initial fait partie du code et n'est pas un préfixe de
        navigation : seul un vrai préfixe déjà présent (``/n``, ``/o``, ``/i``)
        dispense d'en rajouter un, même quand le namespace commence par la même
        lettre qu'un préfixe (``/IWFND/MAINT_SERVICE``), voir `_has_nav_prefix`.
        Définissez ``skip_if_error=True`` pour journaliser au lieu d'échouer
        (étapes de navigation optionnelles).

        Exemple :
        | `Run Transaction`    SE16
        | ${transaction}=    `Get Current Transaction`
        | Should Be Equal    ${transaction}    SE16
        """
        already_prefixed = self._has_nav_prefix(transaction)
        okcode = transaction if already_prefixed else "/n" + transaction
        self.session.findById("wnd[0]/tbar[0]/okcd").text = okcode
        closing = transaction.lower() in ("/nex", "/nend")
        try:
            self.send_vkey(0)
            if closing:
                self._wait_until_closed_or_idle()
            else:
                self.wait_until_busy_done()
        except Exception as exc:
            # /nex et /nend FERMENT la session : la trouver déconnectée, ou
            # absente du moteur, est leur succès (mesuré 2026-09-28 : 30 s
            # d'attente puis une capture ; 2026-10-06 : depuis l'écran de
            # connexion, la session morte ne répond pas RPC_E_DISCONNECTED).
            if closing and (is_disconnected_error(exc) or self._session_is_gone()):
                return
            raise

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

    def get_current_transaction(self):
        """Retourne le *code de la transaction active* (``session.Info.Transaction``),
        p.ex. ``SE16`` ou ``SESSION_MANAGER`` sur l'écran SAP Easy Access.
        Indépendant de la langue, idéal pour les assertions de navigation.

        Exemple :
        | ${transaction}=    `Get Current Transaction`
        | Should Be Equal    ${transaction}    SE16
        """
        return self.session.Info.Transaction

    def get_status_message(self):
        """Retourne ``(message_type, text)`` de la barre de statut courante.

        ``message_type`` vaut ``S`` (succès), ``W`` (avertissement), ``E`` (erreur),
        ``I`` (info), ``A`` (abandon), ou ``""`` quand la barre est vide ; tous
        indépendants de la locale.

        Exemple :
        | ${type}    ${text}=    `Get Status Message`
        | Should Be Equal    ${type}    E
        """
        status = self.session.findById("wnd[0]/sbar")
        return status.messageType, status.text

    def status_message_should_be_success(self):
        """Échoue si la barre de statut n'affiche pas actuellement un message de succès (``S``).

        Exemple :
        | `Run Transaction`    SE38
        | `Input Text`    wnd[0]/usr/ctxtRS38M-PROGRAMM    RSPARAM
        | `Send Vkey`    26
        | `Status Message Should Be Success`
        """
        msg_type, text = self.get_status_message()
        if msg_type not in ("S", ""):
            self.take_screenshot()
            raise AssertionError(
                "Expected a success status message but got type '%s': %s"
                % (msg_type, text)
            )
