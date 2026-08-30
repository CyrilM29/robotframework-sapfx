"""Mixin RFC et BAPI (optionnel) : pyrfc si installe, erreur actionnable sinon.

`Open Rfc Connection` / `Call Rfc` (SAP NW RFC SDK requis, jamais de
dependance dure), la perception du canal (`Get Rfc Channel Status`,
`Get Rfc Connection Attributes`, `Read Rfc Table`), la classification de ses
refus par code technique (`Rfc Should Fail With Code`) ou par identifiant de
message (`Rfc Should Fail With Message Id`), le pattern **BAPI**
au-dessus (`Call Bapi` juge par TYPE de BAPIRET2, convention #3 ;
`Commit/Rollback Bapi Transaction` ferment la LUW), les jobs de fond
(`Wait For Background Job` : TBTCO via RFC_READ_TABLE, verdicts purs dans
``sapfx_common.rfc_tables`` ; `Find Background Job Cases` et
`Get Background Job Status Model` : la perception qui permet d'éprouver
l'attente sur les jobs que la cible porte déjà, sans en créer ni en annuler
aucun) et la **surface du canal** (`Write Rfc Surface Artifact` /
`Compare Rfc Surface Artifacts`, logique pure dans
``sapfx_common.rfc_surface``).

Extrait de ``SapApiLibrary.py`` (convention #13).
"""
from __future__ import annotations

import datetime
import json
import time
from typing import Any, Iterable, Mapping, Optional

from robot.api import logger
from robot.utils import timestr_to_secs

from sapfx_common import bapi_return, rfc_channel, rfc_surface, rfc_tables
from sapfx_common.polling import poll_until
from sapfx_common.secrets import reveal_secret

from ._core import _ApiCore
from ._http import _as_bool


class RfcKeywords(_ApiCore):
    """Mixin de :class:`SapApiLibrary` : le canal RFC/BAPI optionnel."""

    #: Les appels dont un refus peut être ATTENDU par `Rfc Should Fail With
    #: Code` : la cible est nommée par le keyword qui la porte, et résolue
    #: dans la bibliothèque elle-même (aucune indirection par le runner, donc
    #: un mot de passe de type `Secret` traverse intact).
    _EXPECTABLE_CALLS = {
        "open rfc connection": "open_rfc_connection",
        "call rfc": "call_rfc",
        "read rfc table": "read_rfc_table",
        "call bapi": "call_bapi",
        "wait for background job": "wait_for_background_job",
    }

    def get_rfc_channel_status(self) -> dict[str, Any]:
        """État du canal RFC sur ce poste, **sans jamais échouer** : le
        préflight à poser avant d'ouvrir quoi que ce soit, et le pendant RFC de
        `Gateway Should Be Active`.

        Retourne ``{"available": bool, "reason", "version", "detail",
        "remediation"}``. ``reason`` distingue les deux absences qui n'ont pas
        le même remède : ``module_absent`` (le binding `pyrfc` n'est pas
        installé, souvent parce que l'interpréteur dépasse 3.12) et
        ``runtime_absent`` (le binding est là, la bibliothèque native NW RFC
        manque). Une suite RFC s'en sert pour se SAUTER proprement là où le
        canal n'existe pas, au lieu de rougir là où rien n'est cassé."""
        try:
            import pyrfc
        except Exception as err:   # ImportError, mais aussi OSError Windows
            return rfc_channel.unavailable_status(err)
        # Un import qui réussit ne suffit PAS : le __init__ de pyrfc 3.3.1
        # avale l'échec de chargement du runtime natif et rend un module sans
        # Connection (mesuré en CI le 2026-08-29). Le verdict lit le module.
        return rfc_channel.binding_status(pyrfc)

    def rfc_channel_should_be_available(self) -> dict[str, Any]:
        """Échoue si le canal RFC n'est pas utilisable sur ce poste, en nommant
        la cause ET son remède. Variante assertive de `Get Rfc Channel
        Status` : à poser quand l'absence du canal EST une anomalie (sinon,
        lire le statut et sauter)."""
        status = self.get_rfc_channel_status()
        if not status["available"]:
            raise AssertionError(
                "Canal RFC indisponible (%s) : %s %s"
                % (status["reason"], status["detail"], status["remediation"]))
        return status

    def open_rfc_connection(self, alias: str = "default", **params: Any) -> str:
        """Ouvre une connexion RFC via `pyrfc` (``ashost=``, ``sysnr=``,
        ``client=``, ``user=``, ``passwd=``...). Échec explicite avec la marche
        à suivre si `pyrfc`/le SDK NW RFC ne sont pas installés : le RFC reste
        **optionnel**, rien d'autre dans la bibliothèque n'en dépend."""
        pyrfc = self._require_pyrfc()
        self._rfc_connections()[alias] = pyrfc.Connection(
            **{name: reveal_secret(value) for name, value in params.items()})
        return alias

    def _require_pyrfc(self) -> Any:
        """Le module `pyrfc` UTILISABLE, ou une erreur actionnable qui nomme la
        cause et son remède. Le même verdict que `Get Rfc Channel Status` :
        un import qui réussit ne suffit pas (binding importable mais vide de
        ``Connection`` = runtime natif absent, voir
        ``rfc_channel.binding_status``)."""
        try:
            import pyrfc
        except Exception as err:
            status = rfc_channel.unavailable_status(err)
        else:
            status = rfc_channel.binding_status(pyrfc)
            if status["available"]:
                return pyrfc
        raise RuntimeError(
            "Le canal RFC a besoin de pyrfc et du runtime NW RFC (%s : %s). "
            "%s Les keywords OData, eux, fonctionnent sans."
            % (status["reason"], status["detail"], status["remediation"]))

    def get_rfc_connection_attributes(self, alias: str = "default") -> dict[str, Any]:
        """Les attributs de la connexion RFC ``alias``, tels que le canal les
        rend : ``sysId``, ``client``, ``user``, ``partnerRel`` (release du
        système joint), ``kernelRel``, ``sysNumber``, ``language``…

        C'est la **perception d'identité** du canal sans écran : un canal
        ouvert ne dit pas encore vers QUOI. Une campagne qui ne prouve pas
        l'identité de sa cible peut être verte contre le mauvais système, ce
        que ce dépôt a déjà vécu côté web avec un nom d'hôte partagé. Les
        valeurs sont converties en chaînes (retour JSON-safe, servable à un
        agent)."""
        connection = self._require_rfc_connection(alias, "Get Rfc Connection Attributes")
        attributes = connection.get_connection_attributes()
        return {str(name): str(value) for name, value in dict(attributes).items()}

    def read_rfc_table(self, table: str, fields: Any, alias: str = "default",
                       options: Any = None, rowcount: int = 0,
                       delimiter: str = "|") -> list[dict[str, str]]:
        """Lit une table par ``RFC_READ_TABLE`` et rend une liste de dicts
        ``{champ: valeur}`` : le miroir sans écran de `Read Grid` (ECC) et de
        `Read Business Entities` (OData).

        ``fields`` : liste, ou chaîne séparée par des virgules. La lecture est
        toujours PROJETÉE (on ne rapatrie que les champs utiles) et bornée par
        ``rowcount`` (0 = tout). ``options`` : une clause de sélection ou une
        liste de clauses, chacune limitée à 72 caractères par le module ABAP,
        limite vérifiée AVANT tout appel réseau (au-delà, découper en clauses
        ``AND``).

        Piège de diagnostic du canal, mesuré : un nom de champ inexistant sort
        en ``TABLE_WITHOUT_DATA``, un code qui accuse la TABLE d'être vide
        alors qu'elle est pleine et que le fautif est le champ. Vérifier
        l'orthographe des champs avant de conclure à une absence de données."""
        params = rfc_tables.read_table_params(
            table, rfc_tables.as_field_list(fields),
            rfc_tables.as_clause_list(options),
            delimiter=delimiter, rowcount=int(rowcount))
        result = self.call_rfc("RFC_READ_TABLE", alias=alias, **params)
        return rfc_tables.parse_read_table(result, delimiter=delimiter)

    def rfc_should_fail_with_code(self, expected_code: str, keyword: str,
                                  *args: Any, **params: Any) -> dict[str, Any]:
        """Vérifie qu'un appel RFC échoue avec le **code technique** attendu
        (``TABLE_NOT_AVAILABLE``, ``FU_NOT_FOUND``, ``RFC_LOGON_FAILURE``…), et
        retourne la fiche du refus.

        C'est la convention n°3 appliquée au canal RFC : le code est stable
        d'un système et d'une langue à l'autre, le message ne l'est pas. Un
        `Run Keyword And Expect Error` ne peut pas rendre ce service, il ne
        voit que le texte.

        ``keyword`` nomme l'appel attendu en échec parmi ceux de cette
        bibliothèque : `Open Rfc Connection`, `Call Rfc`, `Read Rfc Table`,
        `Call Bapi`, `Wait For Background Job`. Les arguments qui suivent sont
        ceux de ce keyword, transmis intacts : un mot de passe de type `Secret`
        reste un `Secret`, et rien n'est journalisé.

        Deux échecs distincts, à dessein : l'appel a réussi (le refus attendu
        ne se produit plus), ou il a échoué avec un AUTRE code (les deux codes
        sont nommés). Un refus sans code technique, comme les gardes propres à
        la bibliothèque, n'est jamais confondu avec un refus du serveur."""
        expected = str(expected_code).strip()
        subject, error = self._provoke_rfc_failure(keyword, expected, args, params)
        if rfc_channel.rfc_error_code(error).upper() != expected.upper():
            raise AssertionError(
                rfc_channel.format_code_mismatch(subject, expected, error))
        return rfc_channel.describe_rfc_error(error)

    def rfc_should_fail_with_message_id(self, expected_message_id: str,
                                        keyword: str, *args: Any,
                                        **params: Any) -> dict[str, Any]:
        """Vérifie qu'un appel RFC échoue avec l'**identifiant de message**
        attendu (``DA/E/131``, ``AD/E/718``, ``FL/E/046``…), et retourne la
        fiche du refus.

        Complément FIN de `Rfc Should Fail With Code`, et tout aussi
        indépendant de la langue : le code technique est stable mais grossier,
        alors que la classe, le type et le numéro du message ABAP désignent le
        refus exact. Les asserter ensemble caractérise un refus sans jamais
        toucher à son libellé (convention n°3).

        Mêmes arguments que `Rfc Should Fail With Code` : ``keyword`` nomme
        l'appel attendu en échec, les arguments qui suivent sont les siens et
        traversent intacts. Un refus qui ne porte AUCUN identifiant de message
        (refus du runtime client, garde de la bibliothèque) échoue en le
        disant, plutôt que de se comparer à du vide."""
        expected = str(expected_message_id).strip()
        subject, error = self._provoke_rfc_failure(keyword, expected, args, params)
        described = rfc_channel.describe_rfc_error(error)
        if described["message_id"].upper() != expected.upper():
            raise AssertionError(
                rfc_channel.format_message_id_mismatch(subject, expected, error))
        return described

    def _provoke_rfc_failure(self, keyword: str, expected: str,
                             args: tuple[Any, ...],
                             params: dict[str, Any]) -> tuple[str, BaseException]:
        """Provoque l'appel ``keyword`` en ATTENDANT son échec, et rend
        ``(sujet, exception)``. Le socle commun des deux oracles de refus
        (`Rfc Should Fail With Code` et `Rfc Should Fail With Message Id`) :
        résolution de la cible, exécution, et le cas de l'appel qui RÉUSSIT là
        où un refus était attendu, qui mérite son propre message parce qu'un
        oracle vert parce que rien n'a échoué ne prouve rien."""
        target = self._EXPECTABLE_CALLS.get(
            " ".join(str(keyword).replace("_", " ").lower().split()))
        if target is None:
            raise ValueError(
                "Un oracle de refus RFC ne sait pas provoquer '%s'. Appels "
                "attendus en échec : %s." % (keyword, ", ".join(
                    sorted(name.title() for name in self._EXPECTABLE_CALLS))))
        subject = "L'appel « %s »" % str(keyword).strip()
        try:
            result = getattr(self, target)(*args, **params)
        except Exception as err:   # noqa: BLE001 : c'est le refus attendu
            return subject, err
        if target == "open_rfc_connection":
            # Une ouverture qui réussit là où un refus était attendu laisserait
            # une session utilisateur ouverte côté serveur : la refermer AVANT
            # de rapporter l'échec.
            self.close_rfc_connection(str(result))
        raise AssertionError(rfc_channel.format_missing_failure(subject, expected))

    def _require_rfc_connection(self, alias: str, keyword: str) -> Any:
        """La connexion RFC ``alias``, ou une erreur qui nomme le keyword
        d'ouverture (le refus le plus fréquent du canal : un alias jamais
        ouvert, ou déjà fermé par un teardown)."""
        connection = self._rfc_connections().get(alias)
        if connection is None:
            raise RuntimeError(
                "Aucune connexion RFC '%s' : appeler Open Rfc Connection "
                "d'abord (%s)." % (alias, keyword))
        return connection

    def call_rfc(self, function_name: str, alias: str = "default",
                 **params: Any) -> Any:
        """Appelle le module fonction ``function_name`` sur la connexion RFC
        ``alias`` (ouverte par `Open Rfc Connection`) et retourne le résultat
        (dict pyrfc).

        Deux règles de la frontière Robot vers ABAP, la première tenue ici, la
        seconde à la charge de l'appelant : les structures et les tables sont
        ramenées à des types nus (un dictionnaire construit dans une suite est
        un ``DotDict``, que `pyrfc` refuse pour un paramètre de structure) ;
        en revanche un paramètre NUMÉRIQUE doit être passé comme un vrai
        nombre (``${3}``, pas ``3``), car deviner le type d'après la forme de
        la chaîne corromprait les champs caractère numériques, où ``'0400'``
        est un numéro de liaison et non l'entier 400."""
        connection = self._require_rfc_connection(alias, "Call Rfc")
        return connection.call(
            function_name, **rfc_channel.plain_rfc_parameters(params))

    def call_bapi(self, function_name: str, alias: str = "default",
                  return_key: str = "RETURN", **params: Any) -> Any:
        """Appelle une **BAPI** et vérifie sa table ``RETURN`` (BAPIRET2) :
        un message de type ``E``/``A``/``X`` = échec listant les messages
        bloquants (décision par TYPE, jamais par texte localisé : convention
        n°3) et rappelant `Rollback Bapi Transaction`. Sinon retourne le
        résultat complet (dict pyrfc). Le pattern SAP de préparation de
        données robuste : `Call Bapi` puis `Commit Bapi Transaction`."""
        result = self.call_rfc(function_name, alias=alias, **params)
        messages = bapi_return.iter_bapi_messages(result, return_key)
        failing = bapi_return.failing_messages(messages)
        if failing:
            raise AssertionError(
                bapi_return.format_bapi_failure(function_name, failing))
        return result

    def commit_bapi_transaction(self, alias: str = "default",
                                wait: bool = True) -> Any:
        """``BAPI_TRANSACTION_COMMIT`` sur la connexion RFC ``alias`` :
        rend durables les écritures des BAPIs précédentes. ``wait=True``
        (défaut) attend la fin de la mise à jour (``WAIT='X'``) : le réglage
        sûr pour enchaîner une vérification. La table RETURN est vérifiée
        comme dans `Call Bapi`."""
        params = {"WAIT": "X"} if _as_bool(wait) else {}
        return self.call_bapi("BAPI_TRANSACTION_COMMIT", alias=alias, **params)

    def rollback_bapi_transaction(self, alias: str = "default") -> Any:
        """``BAPI_TRANSACTION_ROLLBACK`` sur la connexion RFC ``alias`` :
        annule la LUW en cours (le réflexe après un `Call Bapi` en échec, et
        un teardown sûr des préparations de données interrompues)."""
        return self.call_rfc("BAPI_TRANSACTION_ROLLBACK", alias=alias)

    def wait_for_background_job(self, jobname: str, alias: str = "default",
                                timeout: str = "10m", poll: str = "5s",
                                jobcount: Optional[str] = None) -> dict[str, Any]:
        """Attend la fin d'un **job de fond** (facturation, IDoc, génération
        de données…) en lisant la table ``TBTCO`` via ``RFC_READ_TABLE``
        (remote-enabled partout, aucun écran occupé). Succès quand plus aucun
        run du job n'est dans le pipeline (P/S/Y/R) et qu'au moins un est
        ``F`` (fini) : retourne ``{"state": "done", "statuses",
        "waited_seconds"}``. Un run annulé (``A``) = échec immédiat ; timeout
        = échec actionnable (statuts vus, suggestion ``jobcount=`` si
        plusieurs runs portent ce nom, journal SM37). Nécessite une connexion
        `Open Rfc Connection` sur ``alias``."""
        if self._rfc_connections().get(alias) is None:
            raise RuntimeError(
                "Aucune connexion RFC '%s' : appeler Open Rfc Connection "
                "d'abord (Wait For Background Job lit TBTCO via "
                "RFC_READ_TABLE)." % alias)
        secs = timestr_to_secs(timeout)
        step = timestr_to_secs(poll)
        options = ["JOBNAME EQ %s" % rfc_tables.abap_quote(jobname)]
        if jobcount:
            options.append("AND JOBCOUNT EQ %s" % rfc_tables.abap_quote(jobcount))
        params = rfc_tables.read_table_params("TBTCO", ["STATUS"], options)
        started = time.monotonic()
        state: dict[str, Any] = {
            "verdict": {"state": "missing", "detail": "aucune sonde encore"},
            "counts": {}, "error": None}

        def probe() -> bool:
            try:
                result = self.call_rfc("RFC_READ_TABLE", alias=alias, **params)
            except Exception as err:
                state["error"] = str(err)
                return False
            rows = rfc_tables.parse_read_table(result)
            counts = rfc_tables.summarize_job_statuses(rows)
            state["verdict"] = rfc_tables.job_wait_verdict(counts)
            state["counts"] = counts
            state["error"] = None
            return state["verdict"]["state"] in ("done", "aborted")

        poll_until(probe, secs, max(0.1, step))
        verdict = state["verdict"]
        waited = round(time.monotonic() - started, 2)
        if verdict["state"] == "done":
            return {"state": "done", "statuses": state["counts"],
                    "waited_seconds": waited}
        if verdict["state"] == "aborted":
            raise AssertionError(
                "Le job de fond '%s' a été annulé (statut A). %s Journal "
                "détaillé : SM37." % (jobname, verdict["detail"]))
        raise AssertionError(
            "Le job de fond '%s' n'a pas fini après %s : %s%s Préciser "
            "jobcount= si plusieurs runs portent ce nom ; journal : SM37."
            % (jobname, timeout, verdict["detail"],
               " Dernière erreur RFC : %s." % state["error"]
               if state["error"] else ""))

    def get_background_job_status_model(self) -> dict[str, Any]:
        """Ce que cette bibliothèque **cartographie** des statuts de job de
        fond : ``{"labels": {"F": "finished", "A": "cancelled"…}, "pending":
        ["P", "S", "Y", "R"]}``, c'est-à-dire exactement ce qui fonde le
        verdict de `Wait For Background Job`.

        Sert à lire un décompte de statuts sans deviner, et surtout à établir
        qu'un statut rencontré n'est PAS cartographié ici. Le domaine
        ``BTCSTATUS`` est un ``CHAR1`` sans liste de valeurs dans le
        dictionnaire : ce que cette table ne contient pas ne s'invente pas, et
        l'attente le traite en continuant d'attendre plutôt qu'en concluant au
        succès."""
        return {"labels": dict(rfc_tables.JOB_STATUS_LABELS),
                "pending": list(rfc_tables.PENDING_JOB_STATUSES)}

    def find_background_job_cases(self, alias: str = "default",
                                  rowcount: int = 0) -> dict[str, Any]:
        """Lit le journal des jobs (``TBTCO``) et le rend comme un **catalogue
        de cas d'attente** : quels jobs de CETTE cible produiraient chacune des
        issues de `Wait For Background Job`.

        Retourne ``{"rows", "statuses", "jobs", "cases"}`` : le nombre de runs
        lus, le décompte global par statut, le décompte par job, et les jobs
        classés par cas (``done``, ``aborted``, ``aborted_with_finished``,
        ``pipeline``, ``unmapped``).

        La perception qui manquait à l'attente : elle permet d'éprouver toutes
        ses issues en **lecture seule**, sur les jobs d'exploitation que le
        système porte déjà, sans créer ni annuler quoi que ce soit, et sans
        graver dans une suite des noms de jobs qui sont ceux d'une image donnée.

        ``rowcount`` borne la lecture, et vaut 0 (tout le journal) à dessein :
        un plafond ne tronque pas seulement le résultat, il **fausse la
        classification**. Mesuré sur une cible réelle, les 200 premières lignes
        d'un journal qui en portait 4719 étaient toutes ``F`` et faisaient
        conclure que le système ne portait que des jobs terminés."""
        rows = self.read_rfc_table("TBTCO", ["JOBNAME", "STATUS"], alias=alias,
                                   rowcount=int(rowcount))
        grouped = rfc_tables.group_job_statuses(rows)
        return {"rows": len(rows),
                "statuses": rfc_tables.summarize_job_statuses(rows),
                "jobs": grouped,
                "cases": rfc_tables.job_wait_cases(grouped)}

    def write_rfc_surface_artifact(
            self, path: str, target_id: str, identity: Mapping[str, Any],
            measures: Mapping[str, Any],
            components: Optional[Iterable[Mapping[str, Any]]] = None
    ) -> dict[str, Any]:
        """Écrit l'artefact déterministe de la **surface du canal RFC** d'une
        cible et retourne sa preuve : ``{path, sha256, summary}``.

        La surface d'un canal, ce sont ses décomptes (modules ouverts à
        distance, interfaces métier publiées, objets du modèle de
        programmation, volumétries des jeux de démonstration) plus l'inventaire
        des composants logiciels installés. La question « quels modules ici et
        pas là-bas » ne se répond pas par une note dans un document : elle se
        répond par un artefact produit sur chaque cible et comparé par
        `Compare Rfc Surface Artifacts`.

        ``identity`` porte l'identité de la cible (``system_id``, ``client``,
        ``release``, ``kernel``, ``database``, ``operating_system``,
        ``host``), et elle n'est pas décorative : sans elle, comparer deux
        artefacts revient à comparer deux inconnues. Le hash EXCLUT
        l'horodatage, donc deux exécutions sur la même cible lisant les mêmes
        chiffres produisent le même hash. Une mesure non entière, un périmètre
        vide ou un composant sans nom sont refusés à l'écriture plutôt que
        comparés plus tard. Hors ligne : n'ouvre aucune connexion."""
        observed = datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds")
        surface = rfc_surface.build_surface(
            target_id, identity, measures, observed, components=components)
        digest = rfc_surface.comparison_hash(surface)
        with open(str(path), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(rfc_surface.surface_json(surface))
        logger.info("Surface RFC écrite dans %s (sha256 %s)." % (path, digest))
        return {"path": str(path), "sha256": digest,
                "summary": surface["summary"]}

    def read_rfc_surface_artifact(self, path: str) -> dict[str, Any]:
        """Relit un artefact écrit par `Write Rfc Surface Artifact` et le rend
        tel quel (dict JSON-safe : identité, périmètre, mesures, composants).

        Le symétrique de l'écriture, pour qu'une suite n'ait jamais à ouvrir le
        fichier elle-même : les primitives de cette bibliothèque s'atteignent
        par un keyword, jamais par un import improvisé dans un test. Hors
        ligne : ne joint aucune cible."""
        with open(str(path), encoding="utf-8") as handle:
            return dict(json.load(handle))

    def compare_rfc_surface_artifacts(self, path_a: str,
                                      path_b: str) -> dict[str, Any]:
        """Compare deux artefacts écrits par `Write Rfc Surface Artifact`.

        Charge les deux fichiers, journalise le rapport Markdown et retourne
        la comparaison JSON-safe : différences d'identité, écarts de mesure, et
        les composants logiciels rendus dans les trois catégories utiles
        (communs, propres à la première cible, propres à la seconde), avec les
        changements de release des communs.

        Le périmètre est une PORTE : deux artefacts dont les ensembles de
        mesures diffèrent sont marqués non comparables et seules les mesures
        communes sont chiffrées, parce qu'une mesure absente d'un côté ne vaut
        pas zéro. Hors ligne : aucune cible n'est jointe, la comparaison se
        fait sur les fichiers."""
        with open(str(path_a), encoding="utf-8") as handle:
            surface_a = json.load(handle)
        with open(str(path_b), encoding="utf-8") as handle:
            surface_b = json.load(handle)
        try:
            comparison = rfc_surface.compare_surfaces(surface_a, surface_b)
        except ValueError as error:
            raise AssertionError(
                "Compare Rfc Surface Artifacts : %s" % error) from error
        logger.info(rfc_surface.render_surface_report(comparison))
        return comparison

    def close_rfc_connection(self, alias: str = "default") -> None:
        """Ferme la connexion RFC ``alias`` (silencieux si absente)."""
        connection = self._rfc_connections().pop(alias, None)
        if connection is not None:
            connection.close()
