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
import contextlib
import os
import subprocess
import time

import pythoncom
import win32com.client
from pythoncom import com_error
from robot.api import logger
from robot.utils import timestr_to_secs

from sapfx_common.com_safety import ensure_com_initialized, is_dead_server_error
from sapfx_common.polling import poll_until, retry_call, retry_until

# Emplacements d'installation courants ; à remplacer via l'argument `path` ou la variable d'env SAPLOGON_PATH.
_DEFAULT_SAPLOGON_PATHS = (
    r"C:\Program Files\SAP\FrontEnd\SAPgui\saplogon.exe",        # SAP GUI 8.x (64-bit)
    r"C:\Program Files (x86)\SAP\FrontEnd\SAPGUI\saplogon.exe",  # SAP GUI 7.x (32-bit)
    r"C:\Program Files\SAP\FrontEnd\SAPGUI\saplogon.exe",
)


def _raise_unless_dead(error, what):
    """Ne laisse passer qu'une panne qui PROUVE que le serveur COM a disparu
    (``sapfx_common.com_safety.DEAD_SERVER_HRESULTS``) ; toute autre lève :
    un objet vivant mais illisible n'est jamais un objet absent."""
    if isinstance(error, com_error) and is_dead_server_error(error):
        return
    raise RuntimeError(
        "SAP GUI illisible (%s : %s) : impossible de conclure qu'aucune "
        "connexion n'est ouverte." % (what, error))


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
        result = super().connect_to_session(explicit_wait)
        # La base garde le DERNIER moteur trouvé dans la table des objets actifs,
        # y compris celui d'un Logon fermé juste avant (relevé 2026-10-01 : une
        # seconde ouverture dans le même process réutilisait ce moteur mort et
        # échouait en « serveur RPC non disponible »). Un moteur qui ne répond
        # pas est remplacé par un moteur VIVANT, ou la connexion échoue et
        # `Connect To Session With Retry` réessaie le temps que l'entrée morte
        # disparaisse.
        engine = getattr(self, "sapapp", None)
        if engine is not None and engine != -1 and not _engine_is_alive(engine):
            live = self._acquire_scripting_engine()
            if live is None:
                raise Warning(
                    "Could not connect to Session, is Sap Logon Pad open? (le "
                    "moteur de scripting trouvé ne répond plus : un Logon "
                    "fermé laisse un moment son entrée dans la table des objets actifs)")
            self.sapapp = live
        return result

    def _acquire_scripting_engine(self):
        """Le moteur de scripting SAP GUI acquis depuis la ROT pour le thread
        COURANT (``GetScriptingEngine`` du SAPGUI enregistré), ou ``None``.

        C'est la primitive du ré-attachement cross-thread du rail STA
        (``SapEccLibrary._touch_com_thread``) : un proxy COM STA ne se partage
        pas entre threads, mais chaque thread peut obtenir le SIEN par la ROT
        puis ``FindById(id de session)``. Même parcours que `Connect To
        Session` (code amont), sans toucher ``self.sapapp``."""
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

    def get_open_sap_gui_connections(self):
        """Les connexions SAP GUI ouvertes sur le poste, lues SANS capture
        d'écran et sans toucher l'état de la bibliothèque : une liste de dicts
        ``{index, description, connection_string, sessions}``, vide quand
        aucun SAP Logon ne répond (rien n'est ouvert).

        La sonde d'une PREUVE DE FERMETURE. La voie précédente rattachait
        l'index 0 par `Attach To Open Session` et attendait son échec : un
        échec qui passe par `Connect To Session` capture l'écran, donc chaque
        run VERT laissait une capture (relevé le 2026-10-01 sur les campagnes
        des scénarios 8 et 9). Une connexion dont la lecture rend une panne de
        DISPARITION (voir plus bas) est ignorée ; toute autre panne, y compris
        une entrée de la table des objets actifs illisible ou une connexion
        qui se ferme entre le comptage et la lecture avec une autre erreur,
        fait ÉCHOUER la sonde plutôt que de rendre une liste vide, qui
        conclurait « rien n'est ouvert » (`Sap Gui Should Have No Open
        Connection` réessaie alors jusqu'à son délai).

        Seules les pannes COM de DISPARITION valent « disparu » (serveur RPC
        indisponible : un SAP Logon fermé dont l'entrée traîne dans la table
        des objets actifs ; objet déconnecté ; objet non connecté ; serveur
        mort, l'appel exécuté ou non). Un moteur OCCUPÉ ou qui refuse l'accès
        est vivant : la sonde ÉCHOUE (revue indépendante du 2026-10-01, où un
        moteur occupé passait pour absent)."""
        found = []
        for engine_index, (engine, error) in enumerate(self._scripting_engine_candidates()):
            if engine is None:
                _raise_unless_dead(error, "moteur de scripting")
                continue
            try:
                connections = engine.Children
                count = connections.Count
            except (AttributeError, com_error) as exc:
                _raise_unless_dead(exc, "connexions du moteur")
                continue
            for index in range(count):
                try:
                    connection = connections.ElementAt(index)
                    record = {
                        "engine": engine_index,
                        "index": index,
                        "description": str(getattr(connection, "Description", "") or "").strip(),
                        # SAP GUI préfixe la chaîne d'une espace, et la
                        # description est VIDE pour une connexion ouverte par
                        # chaîne (mesuré) : les deux sont rendues.
                        "connection_string": str(getattr(connection, "ConnectionString", "") or "").strip(),
                        "sessions": int(connection.Children.Count),
                    }
                except (AttributeError, com_error) as exc:
                    _raise_unless_dead(exc, "connexion %d" % index)
                    continue   # connexion refermée pendant la lecture
                found.append(record)
        return found

    def sap_gui_should_have_no_open_connection(self, connection=None, timeout="5s"):
        """Vérifie qu'aucune connexion SAP GUI n'est restée ouverte (ou aucune
        dont la description ou la chaîne de connexion contient ``connection``,
        pour ne viser que la sienne quand un autre SAP GUI tourne sur le
        poste), en sondant jusqu'à ``timeout`` : un ``/nex`` met un instant à
        refermer la connexion. Échec qui nomme les connexions encore ouvertes ;
        aucune capture d'écran tant que rien ne reste ouvert. Le filtre
        ignore la casse. Un SAP GUI ILLISIBLE (moteur occupé, accès refusé)
        n'est jamais pris pour « fermé » : la sonde réessaie jusqu'au délai,
        puis échoue en nommant la panne. Rend la dernière lecture de `Get Open
        Sap Gui Connections`."""
        wanted = str(connection).strip().casefold() if connection not in (None, "") else ""
        state = {"open": [], "error": None}

        def closed():
            try:
                state["open"] = [
                    c for c in self.get_open_sap_gui_connections()
                    if not wanted or wanted in c["description"].casefold()
                    or wanted in c["connection_string"].casefold()]
            except RuntimeError as error:
                state["error"] = error
                return False
            state["error"] = None
            return not state["open"]

        if poll_until(closed, timestr_to_secs(timeout), self.poll_interval):
            return []
        if state["error"] is not None:
            raise AssertionError("Fermeture SAP GUI NON constatée après %s : %s"
                                 % (timeout, state["error"]))
        raise AssertionError(
            "Connexion(s) SAP GUI restée(s) ouverte(s)%s après %s : %s"
            % (" (filtre %r)" % wanted if wanted else "", timeout, state["open"]))

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
        # Processus enfant ordinaire (Windows ne le tue pas avec le parent) ;
        # close_fds évite seulement d'hériter nos descripteurs. `Close Sap
        # Logon` en teardown reste la voie nominale pour l'arrêter.
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
        # Le moteur obtenu auprès de ce Logon est mort avec lui : le garder
        # ferait réutiliser un proxy COM sans serveur à la prochaine ouverture.
        if proc is not None:
            self.sapapp = -1

    def connect_to_session_with_retry(self, retries=3, retry_interval="2s", explicit_wait=0):
        """Comme `Connect To Session` mais réessaie pendant que le Logon Pad
        finit de démarrer. Utile juste après `Open Sap Logon` sur les machines lentes."""
        attempts = int(retries)

        def log_failure(attempt, err):  # base raises Warning/ValueError when not ready
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
                pass    # connexion en cours d'amorçage : COM peut refuser l'accès, on re-sonde
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
        """Interroge `Connect To Session` jusqu'à ce que le moteur réponde ou que le délai expire.

        Les tentatives PRÉMATURÉES sont attendues pendant le démarrage du
        Logon Pad : elles sondent sans capture d'écran (le code amont en
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
