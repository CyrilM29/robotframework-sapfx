"""Mixin preuve de fermeture : quelles connexions SAP GUI restent ouvertes.

`Get Open Sap Gui Connections` lit les connexions dans le moteur de
scripting (énumération de la table des objets actifs, partagée avec
l'acquisition du moteur dans ``_connection.py``) sans toucher l'état de la
bibliothèque ni capturer l'écran ; `Sap Gui Should Have No Open Connection`
en fait la garde de fin de campagne. Extrait de ``_connection.py`` le
2026-10-06 (convention #13), quand les keywords de connexion repris de
robotframework-sapguilibrary l'ont rejoint.
"""
from pythoncom import com_error
from robot.utils import timestr_to_secs

from sapfx_common.com_safety import is_dead_server_error
from sapfx_common.polling import poll_until


def _raise_unless_dead(error, what):
    """Ne laisse passer qu'une panne qui PROUVE que le serveur COM a disparu
    (``sapfx_common.com_safety.DEAD_SERVER_HRESULTS``) ; toute autre lève :
    un objet vivant mais illisible n'est jamais un objet absent."""
    if isinstance(error, com_error) and is_dead_server_error(error):
        return
    raise RuntimeError(
        "SAP GUI illisible (%s : %s) : impossible de conclure qu'aucune "
        "connexion n'est ouverte." % (what, error))



class ConnectionProbeKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Lecture seule."""

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
        moteur occupé passait pour absent).

        Exemple :
        | ${connections}=    `Get Open Sap Gui Connections`
        | Should Contain    ${connections}[0][connection_string]    vhcala4hci
        """
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
        Sap Gui Connections`.

        Exemple :
        | `Run Transaction`    /nex
        | `Sap Gui Should Have No Open Connection`    vhcala4hci
        """
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
