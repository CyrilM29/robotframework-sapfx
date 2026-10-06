"""Keywords d'amorçage de la connexion.

`Connect To Session`, `Connect To Existing Connection` et `Open Connection`
dérivent de robotframework-sapguilibrary 1.2.1 (Copyright Frank van der
Kuur, Apache License 2.0, voir NOTICE), absorbée et réécrite pour SAPFX le
2026-10-06, noms et signatures inchangés
(``tests/unit/test_upstream_compatibility.py``). Ce qui a changé :

* `Connect To Session` ne retient qu'un moteur de scripting qui RÉPOND : un
  Logon fermé laisse un moment son entrée dans la table des objets actifs,
  et l'amont gardait ce moteur mort ;
* `Connect To Existing Connection` cherche la connexion parmi TOUTES les
  connexions ouvertes (l'amont ne regardait que la première) ;
* `Open Connection` attend que la session existe avant de rendre la main.

L'amont supposait aussi le SAP Logon Pad *déjà en cours d'exécution* : ce
mixin peut lancer ``saplogon.exe`` lui-même (`Open Sap Logon`), attendre que
le moteur de scripting soit disponible, puis se connecter, pour un amorçage
de test entièrement autonome.

Rien ici ne communique avec un serveur réel tant qu'une connexion n'est pas
ouverte, ce qui rend la logique de lancement testable unitairement en
simulant ``subprocess`` et la recherche dans la table des objets actifs.
"""
import contextlib
import os
import subprocess
import time

import pythoncom
import win32com.client
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


def _engine_is_alive(engine):
    """Vrai si le moteur de scripting répond encore. Un Logon fermé laisse un
    moment son entrée dans la table des objets actifs : l'objet obtenu se
    construit sans erreur et ne lève (« le serveur RPC n'est pas disponible »)
    qu'au premier usage."""
    try:
        return engine.Children.Count >= 0
    except (AttributeError, com_error):
        return False


class ConnectionKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`."""

    def connect_to_session(self, explicit_wait=0):
        """Se connecte au moteur de scripting du SAP Logon Pad en cours
        d'exécution (sans ouvrir de connexion ni de session) et fixe la pause
        de `Set Explicit Wait` (``0`` par défaut, une durée Robot sinon).
        Échoue si aucun SAP Logon ne répond.

        Seul un moteur qui RÉPOND est retenu : un Logon fermé laisse un moment
        son entrée dans la table des objets actifs, et réutiliser son moteur
        faisait échouer l'ouverture suivante en « serveur RPC non disponible »
        (relevé le 2026-10-01). COM est initialisé sur le thread courant
        d'abord : un orchestrateur qui exécute les keywords hors du thread
        principal (le serveur rf-mcp) l'exige.

        Exemple :
        | `Connect To Session`
        | `Open Connection By String`    /H/vhcala4hci/S/3200
        | `Element Should Be Present`    wnd[0]/usr/pwdRSYST-BCODE
        """
        ensure_com_initialized()
        engine = self._acquire_scripting_engine()
        if engine is None:
            self.take_screenshot()
            raise Warning("Could not connect to Session, is Sap Logon Pad open?")
        self.sapapp = engine
        self.set_explicit_wait(explicit_wait)
        self._explicit_pause()

    def connect_to_existing_connection(self, connection_name):
        """Rattache la bibliothèque à une connexion DÉJÀ ouverte, désignée par
        sa description dans SAP Logon (le nom de l'entrée, ex. ``A4H``), et à
        sa première session. Toutes les connexions ouvertes sont examinées ;
        aucune ne porte ce nom = échec listant celles qui existent. Une
        connexion ouverte par chaîne n'a pas de description : `Attach To Open
        Session` la rattache par index.

        Exemple :
        | `Connect To Session`
        | `Connect To Existing Connection`    A4H
        | ${transaction}=    `Get Current Transaction`
        | Should Be Equal    ${transaction}    SESSION_MANAGER
        """
        connections = self._engine_connections()
        wanted = str(connection_name).strip()
        names = []
        for index in range(connections.Count):
            connection = connections.ElementAt(index)
            description = str(getattr(connection, "Description", "") or "").strip()
            names.append(description or "(sans description)")
            if description == wanted:
                self.connection = connection
                self._bind_first_session(wanted)
                self._explicit_pause()
                return
        self.take_screenshot()
        raise ValueError("No existing connection for '%s' found. Connexions ouvertes : %s"
                         % (connection_name, ", ".join(names) or "aucune"))

    def open_connection(self, connection_name):
        """Ouvre la connexion enregistrée dans SAP Logon sous ``connection_name``
        (la description COMPLÈTE de l'entrée, crochets compris) et attend que
        sa session existe (jusqu'à ``default_timeout``). Pour un serveur sans
        entrée enregistrée : `Open Connection By String`.

        Exemple :
        | `Connect To Session`
        | `Open Connection`    A4H
        | `Element Should Be Present`    wnd[0]/usr/txtRSYST-BNAME
        """
        if not hasattr(self.sapapp, "OpenConnection"):
            self.take_screenshot()
            raise Warning("Cannot find an open Sap Login Pad, is Sap Logon Pad open?")
        try:
            self.connection = self.sapapp.OpenConnection(connection_name, True)
        except com_error:
            self.take_screenshot()
            raise ValueError("Cannot open connection '%s', please check connection name."
                             % connection_name) from None
        self._wait_for_first_session(connection_name)
        self._explicit_pause()

    def _acquire_scripting_engine(self):
        """Le moteur de scripting SAP GUI acquis depuis la ROT pour le thread
        COURANT (``GetScriptingEngine`` du SAPGUI enregistré), ou ``None``.

        C'est la primitive du ré-attachement cross-thread du rail STA
        (``SapEccLibrary._touch_com_thread``) : un proxy COM STA ne se partage
        pas entre threads, mais chaque thread peut obtenir le SIEN par la ROT
        puis ``FindById(id de session)``. Même parcours que `Connect To
        Session`, sans toucher ``self.sapapp``."""
        engine = None
        for candidate, _error in self._scripting_engine_candidates():
            if candidate is not None and _engine_is_alive(candidate):
                engine = candidate
        return engine

    def _scripting_engine_candidates(self):
        """Les moteurs de scripting des SAPGUI enregistrés dans la table des
        objets actifs, pour le thread courant : une liste de couples
        ``(moteur, erreur)`` dont l'un vaut ``None``. Une entrée SAPGUI dont le
        moteur ne s'obtient pas garde son ERREUR au lieu de disparaître :
        l'acquisition l'ignore, la sonde de fermeture décide si elle prouve une
        absence (serveur disparu) ou une panne (serveur vivant illisible)."""
        ensure_com_initialized()
        try:
            rot = pythoncom.GetRunningObjectTable()
            enum = rot.EnumRunning()
        except (AttributeError, com_error) as exc:
            return [(None, exc)]
        found = []
        while True:
            try:
                monikers = enum.Next()
            except (AttributeError, com_error) as exc:
                # Les entrées suivantes ne seront pas lues : une entrée SAPGUI
                # vivante pourrait en faire partie, donc l'erreur est GARDÉE
                # (contre-revue indépendante du 2026-10-01).
                found.append((None, exc))
                break
            if not monikers:
                break
            try:
                name = monikers[0].GetDisplayName(pythoncom.CreateBindCtx(0), None)
            except (AttributeError, com_error) as exc:
                # Nom illisible : rien ne dit que ce n'est pas un SAPGUI.
                found.append((None, exc))
                continue
            if not name.endswith("SAPGUI"):
                continue
            try:
                obj = rot.GetObject(monikers[0])
                sapgui = win32com.client.Dispatch(
                    obj.QueryInterface(pythoncom.IID_IDispatch))
                found.append((sapgui.GetScriptingEngine, None))
            except (AttributeError, com_error) as exc:
                found.append((None, exc))
        return found

    def attach_to_open_session(self, connection_index=0, session_index=0):
        """Rattache la bibliothèque à une session SAP GUI *déjà ouverte*,
        sans Logon Pad à lancer ni login à rejouer : le prérequis exact d'un
        replay d'enregistrement du recorder bureau (dont les suites générées
        utilisent ce keyword en Suite Setup).

        `Connect To Session` seul n'obtient que le MOTEUR de scripting
        (``sapapp``) ; la session, elle, n'est posée que par
        `Connect To Existing Connection`, qui exige le libellé exact de la
        connexion (vide pour une connexion ouverte par chaîne). Ce keyword complète la chaîne par *index* (défaut : la
        première connexion, sa première session : la seule situation d'un
        poste de replay typique), avec des erreurs actionnables si rien n'est
        ouvert.

        Exemple :
        | `Attach To Open Session`    0    0
        | ${transaction}=    `Get Current Transaction`
        | Should Be Equal    ${transaction}    SESSION_MANAGER
        """
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

        Exemple :
        | `Open Sap Logon`
        | `Connect To Session With Retry`
        | `Open Connection By String`    /H/vhcala4hci/S/3200
        | `Element Should Be Present`    wnd[0]/usr/txtRSYST-BNAME
        """
        exe = self._resolve_saplogon_path(path)
        logger.info("Launching SAP Logon Pad: %s" % exe)
        # Processus enfant ordinaire (Windows ne le tue pas avec le parent) ;
        # close_fds évite seulement d'hériter nos descripteurs. `Close Sap
        # Logon` en teardown reste la voie nominale pour l'arrêter.
        self._saplogon_proc = subprocess.Popen([exe], close_fds=True)
        self._wait_for_scripting_engine(timeout)

    def close_sap_logon(self):
        """Arrête le SAP Logon Pad démarré par `Open Sap Logon`.

        Ne fait rien si cette bibliothèque ne l'a pas démarré (ex. il était déjà ouvert).

        Exemple :
        | `Close Sap Logon`
        | `Sap Gui Should Have No Open Connection`    vhcala4hci
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
        # Le moteur obtenu auprès de ce Logon est mort avec lui : le garder
        # ferait réutiliser un proxy COM sans serveur à la prochaine ouverture.
        if proc is not None:
            self.sapapp = -1

    def connect_to_session_with_retry(self, retries=3, retry_interval="2s", explicit_wait=0):
        """Comme `Connect To Session` mais réessaie pendant que le Logon Pad
        finit de démarrer. Utile juste après `Open Sap Logon` sur les machines lentes.

        Exemple :
        | `Open Sap Logon`
        | `Connect To Session With Retry`    retries=5    retry_interval=1s
        | `Open Connection By String`    /H/vhcala4hci/S/3200
        | ${screen}=    `Get Current Screen`
        | Should Be Equal    ${screen}[program]    SAPMSYST
        """
        attempts = int(retries)

        def log_failure(attempt, err):  # Warning/ValueError tant que le Logon démarre
            logger.info("connect_to_session attempt %s/%s failed: %s"
                        % (attempt, attempts, err))

        try:
            with self._probing_without_screenshots():
                retry_call(lambda: self.connect_to_session(explicit_wait),
                           attempts=attempts, interval=timestr_to_secs(retry_interval),
                           on_error=log_failure)
        except Exception as last_error:
            self.take_screenshot()
            raise AssertionError(
                "Could not connect to a SAP session after %s attempts. Last error: %s"
                % (attempts, last_error)
            )

    def open_connection_by_string(self, connection_string, explicit_wait="0"):
        """Ouvre une connexion par *chaîne de connexion* (ex. ``/H/host/S/3200``).

        Contrairement à `Open Connection`, qui attend la *description* d'une entrée
        enregistrée dans le SAP Logon, ce keyword utilise
        ``OpenConnectionByConnectionString``, indispensable pour les systèmes sans
        entrée préenregistrée (image Docker, serveur local) où l'on se connecte
        directement à un serveur d'applications (``/H/<hôte>/S/<port dispatcher>``,
        le port étant ``32<n° instance>``, p.ex. ``3200`` pour l'instance ``00``).

        La session étant créée de façon asynchrone, on attend qu'elle apparaisse
        (jusqu'à ``default_timeout``) avant de rendre la main.

        Exemple :
        | `Open Connection By String`    /H/vhcala4hci/S/3200
        | ${screen}=    `Get Current Screen`
        | Should Be Equal    ${screen}[program]    SAPMSYST
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

        self._wait_for_first_session(connection_string)
        time.sleep(timestr_to_secs(explicit_wait))

    # -- helpers (méthodes internes) ------------------------------------------

    def _engine_connections(self):
        """Les connexions du moteur de scripting (collection COM), ou un
        ``Warning`` si `Connect To Session` n'a pas été appelé."""
        try:
            return self.sapapp.Children
        except (AttributeError, com_error):
            self.take_screenshot()
            raise Warning("Not connected to the scripting engine; call `Connect To "
                          "Session` / `Open Sap Logon` first.") from None

    def _bind_first_session(self, label):
        """Pose la première session de la connexion courante, ou échoue en
        disant que la connexion n'en a aucune (login pas encore terminé)."""
        try:
            if self.connection.Children.Count > 0:
                self.session = self.connection.Children(0)
                return
        except com_error:
            pass
        self.take_screenshot()
        raise ValueError("La connexion '%s' n'a aucune session ouverte." % label)

    def _wait_for_first_session(self, label):
        """Attend (jusqu'à ``default_timeout``) que la connexion qui vient
        d'être ouverte porte une session, puis la pose. La session est créée
        de façon asynchrone : COM peut refuser l'accès pendant l'amorçage."""
        def session_ready():
            try:
                if self.connection.Children.Count > 0:
                    self.session = self.connection.Children(0)
                    return True
            except Exception:
                pass    # connexion en cours d'amorçage : on re-sonde
            return False

        # self.default_timeout est déjà en secondes (converti une fois dans
        # SapEccLibrary.__init__).
        if poll_until(session_ready, self.default_timeout, step=0.5):
            return
        self.take_screenshot()
        raise AssertionError(
            "Connection '%s' opened but no session appeared within %s. Is the SAP "
            "system reachable and accepting dialog logons?"
            % (label, self.default_timeout))


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
        """Interroge `Connect To Session` jusqu'à ce que le moteur réponde ou que le délai expire.

        Les tentatives PRÉMATURÉES sont attendues pendant le démarrage du
        Logon Pad : elles sondent sans capture d'écran (l'ancienne voie en
        prenait une à chaque tentative, soit 9 captures par démarrage réussi,
        relevé le 2026-09-28), et une seule capture est prise si l'attente
        échoue vraiment."""
        try:
            with self._probing_without_screenshots():
                retry_until(lambda: self.connect_to_session(),
                            timestr_to_secs(timeout), step=0.5)
        except Exception as last_error:
            self.take_screenshot()
            raise AssertionError(
                "SAP scripting engine did not become available within %s. Last error: %s"
                % (timeout, last_error)
            )

    @contextlib.contextmanager
    def _probing_without_screenshots(self):
        """Coupe la capture d'écran « sur erreur » le temps d'une SONDE dont
        les échecs sont attendus, puis rétablit le réglage de l'utilisateur."""
        previous = getattr(self, "take_screenshots", False)
        self.take_screenshots = False
        try:
            yield
        finally:
            self.take_screenshots = previous
