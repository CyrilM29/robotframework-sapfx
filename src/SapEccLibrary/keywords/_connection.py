"""Keywords d'amorçage de la connexion.

L'upstream `SapGuiBase.connect_to_session` suppose que le SAP Logon Pad est *déjà
en cours d'exécution* (l'utilisateur est censé le démarrer lui-même via la bibliothèque
Process ou AutoIt). Ce mixin supprime cette étape manuelle : il peut lancer
``saplogon.exe`` lui-même, attendre que le moteur de scripting soit disponible,
puis se connecter, permettant un amorçage de test entièrement autonome.

Rien ici ne communique avec un serveur réel tant que `Open Connection` /
`Connect To Session` (hérités de la base) ne sont pas appelés, ce qui rend la
logique de lancement testable unitairement en simulant ``subprocess`` et la
recherche dans la table des objets en cours d'exécution.
"""
import os
import subprocess
import time

from pythoncom import com_error
from robot.api import logger
from robot.utils import timestr_to_secs

from sapfx_common.com_safety import ensure_com_initialized
from sapfx_common.polling import poll_until, retry_call, retry_until

# Emplacements d'installation courants ; à remplacer via l'argument `path` ou la variable d'env SAPLOGON_PATH.
_DEFAULT_SAPLOGON_PATHS = (
    r"C:\Program Files\SAP\FrontEnd\SAPgui\saplogon.exe",        # SAP GUI 8.x (64-bit)
    r"C:\Program Files (x86)\SAP\FrontEnd\SAPGUI\saplogon.exe",  # SAP GUI 7.x (32-bit)
    r"C:\Program Files\SAP\FrontEnd\SAPGUI\saplogon.exe",
)


class ConnectionKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`."""

    def connect_to_session(self, explicit_wait=0):
        """Comme `Connect To Session` de la base, mais initialise d'abord COM sur le
        thread courant.

        L'API SAP GUI Scripting est COM (STA). En exécution Robot classique, le thread
        principal a déjà COM initialisé ; mais sous un orchestrateur qui exécute les
        keywords hors du thread principal (p.ex. le serveur rf-mcp), ce thread doit
        appeler ``CoInitialize`` avant tout accès COM, sinon l'acquisition du moteur
        de scripting lève ``CoInitialize n'a pas été appelé``. Voir
        ``sapfx_common.com_safety.ensure_com_initialized`` (partagé avec le state
        provider rf-mcp, qui a le même besoin sur son propre thread)."""
        ensure_com_initialized()
        return super().connect_to_session(explicit_wait)

    def attach_to_open_session(self, connection_index=0, session_index=0):
        """Rattache la bibliothèque à une session SAP GUI **déjà ouverte**,
        sans Logon Pad à lancer ni login à rejouer : le prérequis exact d'un
        replay d'enregistrement du recorder bureau (dont les suites générées
        utilisent ce keyword en Suite Setup).

        `Connect To Session` seul n'obtient que le MOTEUR de scripting
        (``sapapp``) ; la session, elle, n'est posée que par
        `Connect To Existing Connection`, qui exige le libellé exact de la
        connexion. Ce keyword complète la chaîne par **index** (défaut : la
        première connexion, sa première session : la seule situation d'un
        poste de replay typique), avec des erreurs actionnables si rien n'est
        ouvert."""
        self.connect_to_session()
        try:
            connections = self.sapapp.Children
            count = connections.Count
        except (AttributeError, com_error) as exc:
            raise RuntimeError(
                "Impossible de lister les connexions SAP GUI (%s) : "
                "SAP Logon est-il ouvert ?" % exc)
        index = int(connection_index)
        if count <= index:
            raise RuntimeError(
                "Aucune connexion SAP GUI ouverte à l'index %d (%d ouverte(s)) : "
                "ouvrez une session et connectez-vous avant le replay." % (index, count))
        sess_index = int(session_index)
        try:
            self.connection = connections(index)
            if self.connection.Children.Count <= sess_index:
                raise RuntimeError(
                    "La connexion %d n'a pas de session à l'index %d : "
                    "terminez le login avant le replay." % (index, sess_index))
            self.session = self.connection.Children(sess_index)
        except com_error as exc:
            # connexion/session refermée entre le comptage et l'accès (course)
            raise RuntimeError(
                "La connexion ou la session visée s'est refermée pendant le "
                "rattachement (%s) : relancez le replay avec SAP GUI ouvert." % exc)

    def open_sap_logon(self, path=None, timeout="30s"):
        """Lance le SAP Logon Pad et attend que son moteur de scripting soit
        accessible, puis connecte cette bibliothèque à celui-ci.

        ``path`` utilise par défaut la variable d'environnement ``SAPLOGON_PATH``,
        puis les emplacements d'installation standard. Lève une exception si
        l'exécutable est introuvable ou si le moteur n'apparaît pas dans le
        délai ``timeout``.

        Après ce keyword, vous pouvez appeler `Open Connection`/`Connect To Session`
        normalement. À associer avec `Close Sap Logon` dans une Suite Teardown.
        """
        exe = self._resolve_saplogon_path(path)
        logger.info("Launching SAP Logon Pad: %s" % exe)
        # DETACHED pour que le pad continue de fonctionner indépendamment du processus de test.
        self._saplogon_proc = subprocess.Popen([exe], close_fds=True)
        self._wait_for_scripting_engine(timeout)

    def close_sap_logon(self):
        """Arrête le SAP Logon Pad démarré par `Open Sap Logon`.

        Ne fait rien si cette bibliothèque ne l'a pas démarré (ex. il était déjà ouvert).
        """
        proc = getattr(self, "_saplogon_proc", None)
        if proc is not None and proc.poll() is None:
            logger.info("Terminating SAP Logon Pad (pid %s)." % proc.pid)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warn("SAP Logon Pad (pid %s) did not exit within 5s of terminate()."
                           % proc.pid)
        self._saplogon_proc = None

    def connect_to_session_with_retry(self, retries=3, retry_interval="2s", explicit_wait=0):
        """Comme `Connect To Session` mais réessaie pendant que le Logon Pad
        finit de démarrer. Utile juste après `Open Sap Logon` sur les machines lentes."""
        attempts = int(retries)

        def log_failure(attempt, err):  # base raises Warning/ValueError when not ready
            logger.info("connect_to_session attempt %s/%s failed: %s"
                        % (attempt, attempts, err))

        try:
            retry_call(lambda: self.connect_to_session(explicit_wait),
                       attempts=attempts, interval=timestr_to_secs(retry_interval),
                       on_error=log_failure)
        except Exception as last_error:
            raise AssertionError(
                "Could not connect to a SAP session after %s attempts. Last error: %s"
                % (attempts, last_error)
            )

    def open_connection_by_string(self, connection_string, explicit_wait="0"):
        """Ouvre une connexion par **chaîne de connexion** (ex. ``/H/host/S/3200``).

        Contrairement à `Open Connection`, qui attend la *description* d'une entrée
        enregistrée dans le SAP Logon, ce keyword utilise
        ``OpenConnectionByConnectionString``, indispensable pour les systèmes sans
        entrée préenregistrée (image Docker, serveur local) où l'on se connecte
        directement à un serveur d'applications (``/H/<hôte>/S/<port dispatcher>``,
        le port étant ``32<n° instance>``, p.ex. ``3200`` pour l'instance ``00``).

        La session étant créée de façon asynchrone, on attend qu'elle apparaisse
        (jusqu'à ``default_timeout``) avant de rendre la main.
        """
        if not hasattr(self.sapapp, "OpenConnectionByConnectionString"):
            self.take_screenshot()
            raise Warning("Not connected to the scripting engine; call `Connect To "
                          "Session` / `Open Sap Logon` first.")
        try:
            self.connection = self.sapapp.OpenConnectionByConnectionString(
                connection_string, True)
        except Exception as err:
            self.take_screenshot()
            raise ValueError("Cannot open connection '%s': %s" % (connection_string, err))

        def session_ready():
            try:
                if self.connection.Children.Count > 0:
                    self.session = self.connection.Children(0)
                    return True
            except Exception:
                pass
            return False

        # self.default_timeout est déjà en secondes (converti une fois dans
        # SapEccLibrary.__init__) ; pas besoin de re-passer par timestr_to_secs ici.
        if poll_until(session_ready, self.default_timeout, step=0.5):
            time.sleep(timestr_to_secs(explicit_wait))
            return
        self.take_screenshot()
        raise AssertionError(
            "Connection '%s' opened but no session appeared within %s. Is the SAP "
            "system reachable and accepting dialog logons?"
            % (connection_string, self.default_timeout))

    # -- helpers (méthodes internes) ------------------------------------------

    def _resolve_saplogon_path(self, path):
        candidates = []
        if path:
            candidates.append(path)
        env_path = os.environ.get("SAPLOGON_PATH")
        if env_path:
            candidates.append(env_path)
        candidates.extend(_DEFAULT_SAPLOGON_PATHS)
        for candidate in candidates:
            if candidate and os.path.isfile(candidate):
                return candidate
        raise ValueError(
            "Could not locate saplogon.exe. Pass `path=` or set SAPLOGON_PATH. "
            "Tried: %s" % ", ".join(c for c in candidates if c)
        )

    def _wait_for_scripting_engine(self, timeout):
        """Interroge `Connect To Session` jusqu'à ce que le moteur réponde ou que le délai expire."""
        try:
            retry_until(lambda: self.connect_to_session(),
                        timestr_to_secs(timeout), step=0.5)
        except Exception as last_error:
            raise AssertionError(
                "SAP scripting engine did not become available within %s. Last error: %s"
                % (timeout, last_error)
            )
