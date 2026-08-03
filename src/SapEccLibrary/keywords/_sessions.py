"""Registre de sessions SAP GUI nommées — multi-session par alias, en sécurité.

L'API SAP GUI Scripting est nativement multi-session : un moteur de scripting
(``sapapp``) porte N connexions (systèmes/utilisateurs différents), chacune
jusqu'à 6 sessions/fenêtres (limite serveur ``rdisp/max_alt_modes``). La
bibliothèque n'en exposait qu'UNE (``self.session``). Ce mixin ajoute un
**registre par alias** — le pattern `Open Api Session` du canal API, et
`New Context`/`Switch` de la bibliothèque Browser::

    Open Sap Session      erp_qa    connection_string=/H/hosta/S/3200
    Create Gui Session    verif                 # 2e fenêtre, même connexion, sans re-login
    Switch Sap Session    erp_qa
    ...
    Close All Sap Sessions                      # Suite Teardown

Les deux cas « deux sessions live » sont couverts :

* **même connexion** (poser un verrou dans l'une, vérifier dans l'autre) :
  `Create Gui Session` — l'équivalent scripté de ``/o``, AUCUN nouveau login,
  donc jamais de popup multi-logon ;
* **deux systèmes/utilisateurs** : `Open Sap Session` avec sa propre chaîne de
  connexion et, optionnellement, ses identifiants.

Rails de sûreté (le « en sécurité » du multi-session) :

* **Affinité de thread (COM STA)** : les objets SAP GUI appartiennent au thread
  qui les a créés. Le registre mémorise ce thread ; un accès depuis un autre
  thread initialise COM défensivement (marshaling — le mode dont dépendent les
  state providers rf-mcp), et ``SAPFX_STRICT_COM_THREAD=1`` transforme ce cas
  en erreur actionnable. Le multi-session est un **multiplexage** (une session
  active à la fois, bascule explicite) — jamais du parallélisme de threads.
* **Identifiants** : ``password`` accepte le type ``Secret`` de Robot
  Framework 7.4 et n'est jamais journalisé.
* **Teardown isolé** : `Close Sap Session` ne ferme QUE la session visée ; les
  autres alias et le Logon Pad partagé restent debout. La connexion n'est
  fermée que si plus aucun alias ne la référence.
"""
from typing import TYPE_CHECKING, Any

from robot.api import logger
from robot.api.types import Secret
from robot.utils import timestr_to_secs

from sapfx_common.polling import poll_until
from sapfx_common.secrets import reveal_secret


class SessionKeywords:
    """Mixin ajouté à :class:`SapEccLibrary` (registre multi-session par alias)."""

    if TYPE_CHECKING:
        # Contrat attendu du composite (SapEccLibrary) : le registre d'alias vit
        # à côté des propriétés ``session``/``connection`` dans SapEccLibrary.py,
        # les keywords d'amorçage viennent de ConnectionKeywords/SapGuiBase.
        # Déclaré ici pour mypy seulement (mixin en duck-typing, convention du dépôt).
        _DEFAULT_ALIAS: str
        default_timeout: float
        session: Any
        connection: Any
        def _session_registry(self) -> dict: ...
        def _active_alias(self) -> str: ...
        def _set_active_alias(self, alias: str) -> None: ...
        def open_connection_by_string(self, connection_string: str) -> None: ...
        def open_connection(self, connection_name: str) -> None: ...
        def send_vkey(self, vkey_id: Any, window: int = 0) -> None: ...
        def wait_until_busy_done(self, timeout: Any = None) -> None: ...
        def take_screenshot(self, screenshot_name: str = "sap-screenshot") -> None: ...

    def open_sap_session(self, alias, connection_string=None, connection_name=None,
                         user=None, password: "str | Secret | None" = None,
                         client=None, language=None):
        """Ouvre une **nouvelle connexion SAP** enregistrée sous ``alias`` et
        l'active. Le moteur de scripting doit déjà être joignable (`Connect To
        Session` / `Open Sap Logon` une fois par process — le Logon Pad est
        PARTAGÉ par toutes les sessions).

        Exactement une des deux formes : ``connection_string=/H/hôte/S/32NN``
        (système sans entrée Logon préenregistrée — image Docker, serveur
        local) ou ``connection_name=`` (description d'une entrée SAP Logon).

        ``user=`` (avec ``password=``, ``client=``, ``language=`` optionnels)
        déroule aussi l'écran de connexion SAP standard (champs ``RSYST-*``).
        ``password`` accepte le type ``Secret`` de Robot Framework 7.4 —
        créez la variable typée dès la ligne de commande
        (``-v "SAP_PASSWORD: Secret:<motdepasse>"``) : la valeur est alors
        masquée partout, même en TRACE ; ce keyword ne la journalise jamais,
        y compris pour une chaîne ordinaire. Un login qui ne se
        termine pas (mauvais identifiants, popup multi-logon ``wnd[1]``, mot
        de passe expiré) échoue en le nommant. Pour une 2e session du MÊME
        utilisateur, préférer `Create Gui Session` — aucun re-login, donc
        aucun popup multi-logon. ::

            Open Sap Session    erp_qa    connection_string=/H/vhcala4hci/S/3200
            ...    user=DEVELOPER    password=${SAP_PASSWORD}    client=001
        """
        alias = self._validate_session_alias(alias)
        registry = self._session_registry()
        if self._slot_bound(registry.get(alias)):
            raise ValueError(
                "SAP session alias '%s' is already connected. Close it first "
                "(Close Sap Session) or pick another alias." % alias)
        if bool(connection_string) == bool(connection_name):
            raise ValueError(
                "Provide exactly one of connection_string= (/H/host/S/32NN) or "
                "connection_name= (a SAP Logon entry description).")
        previous = self._active_alias()
        self._set_active_alias(alias)
        try:
            if connection_string:
                self.open_connection_by_string(connection_string)
            else:
                self.open_connection(connection_name)
            if user is not None:
                self._log_in_on_active_session(user, password, client, language)
        except Exception:
            # rollback : jamais d'alias fantôme ni de bascule silencieuse.
            registry.pop(alias, None)
            self._set_active_alias(previous)
            raise
        logger.info("SAP session '%s' opened and active." % alias)
        return alias

    def create_gui_session(self, alias, timeout=None):
        """Ouvre une **2e fenêtre/session** sur la connexion ACTIVE (même
        système, même utilisateur — l'équivalent scripté de ``/o``) et
        l'enregistre sous ``alias``, qui devient la session active.

        AUCUN nouveau login : pas de popup multi-logon — c'est la voie
        recommandée pour le scénario « poser une donnée dans une session,
        la vérifier dans l'autre ». La création étant asynchrone, on attend
        (jusqu'à ``timeout``, défaut ``default_timeout``) que la nouvelle
        session apparaisse sur la connexion. Un refus dans les délais nomme
        la limite serveur probable (``rdisp/max_alt_modes``, 6 max)."""
        alias = self._validate_session_alias(alias)
        registry = self._session_registry()
        if self._slot_bound(registry.get(alias)):
            raise ValueError(
                "SAP session alias '%s' is already connected. Close it first "
                "(Close Sap Session) or pick another alias." % alias)
        connection = self.connection
        base_session = self.session
        if self._is_unbound(connection) or self._is_unbound(base_session):
            raise AssertionError(
                "No active SAP connection/session to branch from — open one "
                "first (Open Connection / Open Sap Session).")
        before = int(connection.Children.Count)
        base_session.createSession()
        budget = timestr_to_secs(timeout) if timeout is not None else self.default_timeout

        def new_session():
            try:
                count = int(connection.Children.Count)
                if count > before:
                    return connection.Children(count - 1)
            except Exception:
                pass
            return None

        created = poll_until(new_session, budget, step=0.5)
        if not created:
            raise AssertionError(
                "createSession() produced no new session within %ss — the "
                "per-connection session limit may be reached (server parameter "
                "rdisp/max_alt_modes, 6 max), or the server refuses new modes."
                % budget)
        registry[alias] = {"connection": connection}
        self._set_active_alias(alias)
        self.session = created       # via le setter : binde aussi le thread COM propriétaire
        logger.info("SAP session '%s' created on the active connection." % alias)
        return alias

    def switch_sap_session(self, alias):
        """Bascule la **session active** vers ``alias`` : tous les keywords
        suivants (saisie, transaction, perception…) s'exécutent dessus. Le
        multi-session est un multiplexage — une session active à la fois,
        bascule explicite ; jamais deux threads sur deux sessions. Un alias
        inconnu échoue en listant les alias connectés."""
        alias = self._validate_session_alias(alias)
        registry = self._session_registry()
        if not self._slot_bound(registry.get(alias)):
            known = sorted(a for a in registry if self._slot_bound(registry[a]))
            raise ValueError(
                "Unknown SAP session alias '%s'. Connected aliases: %s. Open "
                "one with Open Sap Session / Create Gui Session."
                % (alias, ", ".join(known) or "<none>"))
        self._set_active_alias(alias)
        logger.info("Active SAP session: '%s'." % alias)
        return alias

    def get_active_sap_session(self):
        """Retourne l'**alias** de la session active (``default`` pour la
        session historique hors registre). JSON-safe."""
        return self._active_alias()

    def list_sap_sessions(self):
        """Retourne la liste des sessions du registre — une entrée par alias :
        ``alias``, ``active``, ``connected`` et, best-effort, ``system`` /
        ``client`` / ``user`` / ``transaction`` (depuis ``session.Info``).

        Uniquement des chaînes/booléens — jamais d'objet COM (contrainte
        rf-mcp : un objet COM ne doit JAMAIS traverser la frontière MCP)."""
        entries = []
        for alias in sorted(self._session_registry()):
            slot = self._session_registry()[alias]
            entry = {"alias": alias,
                     "active": alias == self._active_alias(),
                     "connected": self._slot_bound(slot)}
            if entry["connected"]:
                try:
                    info = slot["session"].Info
                    entry["system"] = str(info.SystemName)
                    entry["client"] = str(info.Client)
                    entry["user"] = str(info.User)
                    entry["transaction"] = str(info.Transaction)
                except Exception:
                    pass    # session morte / Info partiel : l'inventaire reste best-effort
            entries.append(entry)
        return entries

    def close_sap_session(self, alias=None):
        """Ferme la session ``alias`` (défaut : l'active) — et SEULEMENT
        elle : teardown isolé, les autres alias et le Logon Pad restent
        debout. La connexion sous-jacente n'est fermée que si plus aucun
        alias ne la référence. La fermeture COM est best-effort (une session
        déjà morte ne fait pas échouer le teardown) ; l'alias actif bascule
        sur un alias restant. Retourne ``True`` si la fermeture COM a abouti."""
        registry = self._session_registry()
        alias = self._validate_session_alias(alias) if alias else self._active_alias()
        if not self._slot_bound(registry.get(alias)):
            known = sorted(a for a in registry if self._slot_bound(registry[a]))
            raise ValueError(
                "Unknown or unbound SAP session alias '%s'. Connected aliases: "
                "%s." % (alias, ", ".join(known) or "<none>"))
        slot = registry.pop(alias)
        session, connection = slot.get("session"), slot.get("connection")
        closed = False
        try:
            connection.CloseSession(session.Id)
            closed = True
        except Exception as err:
            shared = any(s.get("connection") is connection for s in registry.values())
            if shared:
                # ne JAMAIS fermer une connexion encore utilisée par un autre alias.
                logger.warn("Could not close SAP session '%s' cleanly: %s" % (alias, err))
            else:
                try:
                    connection.CloseConnection()
                    closed = True
                except Exception as err2:
                    logger.warn("Could not close SAP session '%s' cleanly: %s / %s"
                                % (alias, err, err2))
        if alias == self._active_alias():
            remaining = sorted(a for a in registry if self._slot_bound(registry[a]))
            self._set_active_alias(remaining[0] if remaining else self._DEFAULT_ALIAS)
        return closed

    def close_all_sap_sessions(self):
        """Ferme toutes les sessions du registre (best-effort, chacune
        isolément — une session morte n'empêche pas de fermer les autres) et
        revient sur l'alias ``default``. Le keyword de Suite Teardown du
        multi-session. Retourne la liste des alias effectivement fermés."""
        registry = self._session_registry()
        closed = []
        for alias in sorted(list(registry)):
            if not self._slot_bound(registry.get(alias)):
                registry.pop(alias, None)
                continue
            try:
                if self.close_sap_session(alias):
                    closed.append(alias)
            except Exception as err:
                logger.warn("Close All Sap Sessions: '%s' -> %s" % (alias, err))
                registry.pop(alias, None)
        self._set_active_alias(self._DEFAULT_ALIAS)
        return closed

    # -- helpers (méthodes internes) ------------------------------------------

    @staticmethod
    def _validate_session_alias(alias):
        alias = str(alias).strip()
        if not alias:
            raise ValueError("SAP session alias must be a non-empty string.")
        return alias

    @staticmethod
    def _is_unbound(value):
        """Vrai pour les sentinelles « pas de session » (``-1`` upstream, None)."""
        return value is None or isinstance(value, int)

    @classmethod
    def _slot_bound(cls, slot):
        return bool(slot) and not cls._is_unbound(slot.get("session"))

    def _log_in_on_active_session(self, user, password, client, language):
        """Déroule l'écran de login SAP standard (champs ``RSYST-*``) sur la
        session active. Le mot de passe (``Secret`` accepté) n'est jamais
        journalisé. Vérifie best-effort que le login a abouti
        (``Info.User`` non vide) — un échec nomme les causes probables."""
        session = self.session
        if client:
            session.findById("wnd[0]/usr/txtRSYST-MANDT").text = str(client)
        session.findById("wnd[0]/usr/txtRSYST-BNAME").text = str(user)
        if password is not None:
            session.findById("wnd[0]/usr/pwdRSYST-BCODE").text = reveal_secret(password)
        if language:
            session.findById("wnd[0]/usr/txtRSYST-LANGU").text = str(language)
        self.send_vkey(0)
        self.wait_until_busy_done()
        try:
            logged_user = str(self.session.Info.User)
        except Exception:
            return    # session simulée / Info partiel : la vérification reste best-effort
        if not logged_user:
            self.take_screenshot()
            raise AssertionError(
                "Login as '%s' did not complete (Info.User still empty) — wrong "
                "credentials, a pending dialog (multiple-logon popup wnd[1], "
                "expired password), or a locked user. For a second session of "
                "the SAME user, use Create Gui Session instead (no re-login, "
                "no multi-logon popup)." % user)
