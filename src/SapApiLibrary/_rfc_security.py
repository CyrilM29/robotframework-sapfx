"""Mixin des lectures de **posture de sécurité** par le canal RFC.

Ce que ces keywords ajoutent au canal : la configuration de sécurité d'un
système ABAP se lit par des paramètres de profil (``login/*``, ``gw/*``,
``rsau/*``, ``auth/*``) et par quelques tables d'administration, et aucun des
deux ne se laisse lire naïvement.

Le piège central, mesuré le 2026-08-29 sur les deux releases du poste :
``TH_GET_PARAMETER`` ne refuse PAS un paramètre inconnu. Il répond ``RC = 4``
et une chaîne vide, indiscernable d'un paramètre légitimement vide. Une
campagne qui lit la valeur sans regarder le code de retour est donc verte sur
un nom mal orthographié, et pire, elle affirme une absence de durcissement
qu'elle n'a jamais mesurée. `Read Profile Parameters` juge sur le code de
retour et rend ``unknown``, jamais une valeur vide ; `Profile Parameters
Should Be Defined` en fait une garde à poser en tête de campagne.

Logique pure (classification, verdicts, artefact, sentinelle) dans
``sapfx_common.security_baseline``, importable comme bibliothèque Robot par la
couche resources, sur le patron de ``sapfx_common.cross_channel``.

Ajouté à côté de `_rfc_reads.py` plutôt que dedans (convention #13).
"""
from __future__ import annotations

import datetime
import json
import os
from typing import Any, Iterable, Mapping, Optional

from robot.api import logger

from sapfx_common import (
    rfc_tables,
    robot_args,
    security_baseline,
    security_inventory,
)

from ._http import _as_bool
from ._rfc_reads import RfcReadKeywords

#: Les comptes livrés par SAP dont l'état est un contrôle de sécurité en soi.
#: Universels (ils ne dépendent d'aucun site), donc un défaut de bibliothèque
#: et non du vocabulaire d'un projet ; surchargeable par l'appelant.
STANDARD_USERS = ("SAP*", "DDIC", "EARLYWATCH", "TMSADM", "SAPCPIC",
                  "SAPSUPPORT")


class RfcSecurityKeywords(RfcReadKeywords):
    """Mixin de :class:`SapApiLibrary` : la posture de sécurité par RFC."""

    def read_profile_parameters(self, parameters: Any,
                                alias: str = "default") -> list[dict[str, Any]]:
        """Lit un **lot de paramètres de profil** et rend une fiche par
        paramètre : ``{"name", "status", "value"}``.

        ``status`` vaut ``defined`` (le paramètre a une valeur effective, et
        ``value`` porte la chaîne rendue) ou ``unknown`` (aucune valeur
        effective, et ``value`` vaut ``None``). C'est toute la valeur du
        keyword : le module ABAP sous-jacent rend ``RC = 4`` avec une chaîne
        VIDE, si bien qu'une lecture directe confond « paramètre absent » et
        « paramètre à zéro ». Mesuré live sur les deux releases du poste le
        2026-08-29, et c'est le genre d'erreur qui rend une campagne de
        sécurité verte pour de mauvaises raisons.

        ``unknown`` couvre deux cas que ce canal ne sépare pas : le paramètre
        est inconnu de la release, ou il est connu du noyau et non positionné.
        La table dictionnaire qui trancherait est vide sur les deux releases
        mesurées, donc le keyword ne prétend pas choisir.

        ``parameters`` accepte une liste, une chaîne à virgules ou une
        liste-littérale sérialisée (la frontière rf-mcp passe tout en chaîne).
        L'ordre demandé est préservé, ce dont dépendent les comparaisons de
        deux relevés, et la **casse l'est aussi**, ce qui n'est pas un détail :
        le module est SENSIBLE À LA CASSE, ``LOGIN/MIN_PASSWORD_LNG`` rend
        ``RC = 4`` et une chaîne vide là où ``login/min_password_lng`` rend la
        valeur. Une normalisation en majuscules, réflexe courant côté ABAP et
        que ``sapfx_common.rfc_tables.as_field_list`` applique délibérément aux
        noms de champs, ferait donc remonter TOUS les paramètres comme non
        positionnés, avec un code de retour plausible et sans le moindre
        message. D'où le passage par ``robot_args.as_name_list``, qui préserve
        la casse, et jamais par son voisin qui la capitalise.

        Deux bornes du module, relevées sur la même passe et sans conséquence
        pratique : ``PARAMETER_NAME`` est déclaré sur 120 caractères, donc un
        nom plus long est tronqué en silence, et le bourrage d'espaces à droite
        est neutralisé. Rien ne plante, ni sur un nom vide ni sur 500
        caractères.

        La lecture est un aller-retour RFC par paramètre : le module standard
        n'expose pas de lecture en lot. Sur une trentaine de contrôles le coût
        reste négligeable devant l'ouverture de session.
        """
        names = robot_args.as_name_list(parameters)
        if not names:
            raise ValueError(
                "Read Profile Parameters : aucun paramètre demandé. Passer une "
                "liste, une chaîne à virgules ou une liste-littérale.")
        readings = []
        for name in names:
            result = self.call_rfc("TH_GET_PARAMETER", alias=alias,
                                   PARAMETER_NAME=name)
            readings.append(security_baseline.classify_parameter(
                name, result.get("RC"), result.get("PARAMETER_VALUE")))
        return readings

    def profile_parameters_should_be_defined(self, parameters: Any,
                                             alias: str = "default"
                                             ) -> list[dict[str, Any]]:
        """Vérifie que TOUS les paramètres demandés ont une valeur effective
        sur la cible, et rend leurs fiches.

        La garde à poser en tête d'une campagne de sécurité, avant tout
        jugement de conformité : elle sépare « le système n'est pas durci » de
        « mon contrôle vise un paramètre qui n'a pas de valeur ici ». Les deux
        se ressemblent dans un rapport et ne se corrigent pas au même endroit.

        L'échec nomme les paramètres en cause et rappelle les trois causes
        réelles, dont aucune n'est un défaut de durcissement."""
        readings = self.read_profile_parameters(parameters, alias=alias)
        unknown = [r["name"] for r in readings if r["status"] != "defined"]
        if unknown:
            raise AssertionError(
                f"{len(unknown)} paramètre(s) de profil sans valeur effective "
                f"sur cette cible : {', '.join(unknown)}.\n"
                f"Trois causes, aucune n'étant un défaut de durcissement : le "
                f"nom est mal orthographié, sa CASSE est fausse (le module est "
                f"sensible à la casse, LOGIN/... ne vaut pas login/...), ou le "
                f"paramètre est inconnu de cette release. Le module rend RC=4 "
                f"et une chaîne VIDE dans tous les cas, donc une lecture non "
                f"gardée les prendrait pour une valeur nulle.")
        return readings

    def read_standard_users_status(self, alias: str = "default",
                                   users: Any = None,
                                   client: Optional[str] = None
                                   ) -> list[dict[str, Any]]:
        """Lit l'état des **comptes standards livrés par SAP** dans le mandant
        de connexion, et rend une fiche par compte trouvé.

        Chaque fiche porte ``{"user", "present", "uflag", "locked", "reasons",
        "user_type", "user_group", "last_logon"}``, le verrouillage étant
        décodé du masque ``UFLAG`` (un compte verrouillé par l'administration
        ET par des échecs de connexion porte les deux causes, ce qu'une table
        de correspondance plate manquerait).

        ``users`` surcharge la liste par défaut (``SAP*``, ``DDIC``,
        ``EARLYWATCH``, ``TMSADM``, ``SAPCPIC``, ``SAPSUPPORT``). Les comptes
        ABSENTS du mandant sont rendus avec ``present=False`` plutôt que
        silencieusement omis : sur un contrôle de sécurité, « le compte n'existe
        pas ici » est une réponse, et la confondre avec « non mesuré » ferait
        disparaître le contrôle du rapport.

        ``client`` ne CHANGE pas le mandant lu (``RFC_READ_TABLE`` lit celui de
        la connexion) : il est seulement reporté dans les fiches, pour qu'un
        artefact dise de quel mandant il parle. Lire un autre mandant demande
        une autre connexion.

        La clause de sélection est DÉCOUPÉE par
        ``rfc_tables.in_list_clauses`` : le module ABAP borne chaque ligne de
        ``OPTIONS`` à 72 caractères, or la liste par défaut en occupe déjà 69 et
        un septième compte la ferait dépasser. Comme c'est le keyword qui
        compose la clause et non l'appelant, ce dernier ne pourrait pas la
        découper lui-même, et une liste surchargée d'un nom de trop échouerait
        sur une clause qu'il n'a jamais écrite.
        """
        wanted = [str(u).strip() for u in
                  (robot_args.as_name_list(users) if users else STANDARD_USERS)]
        rows = self.read_rfc_table(
            "USR02", ["BNAME", "UFLAG", "CLASS", "USTYP", "TRDAT"],
            alias=alias,
            options=rfc_tables.in_list_clauses("BNAME", wanted))
        found = {str(row.get("BNAME", "")).strip(): row for row in rows}
        fiches = []
        for user in wanted:
            row = found.get(user)
            if row is None:
                fiches.append({"user": user, "present": False, "uflag": None,
                               "locked": None, "reasons": [],
                               "user_type": None, "user_group": None,
                               "last_logon": None, "client": client})
                continue
            lock = security_baseline.classify_user_lock(row.get("UFLAG"))
            fiches.append({
                "user": user,
                "present": True,
                "uflag": lock["uflag"],
                "locked": lock["locked"],
                "reasons": lock["reasons"],
                "user_type": str(row.get("USTYP", "")).strip(),
                "user_group": str(row.get("CLASS", "")).strip(),
                "last_logon": str(row.get("TRDAT", "")).strip(),
                "client": client,
            })
        return fiches

    def get_audit_configuration(self, alias: str = "default") -> dict[str, Any]:
        """Lit la configuration du **journal d'audit de sécurité** et rend son
        verdict : ``{"enabled", "slots_declared", "slots_active", "filtering",
        "verdict", "version", "file_status"}``.

        Le keyword existe parce que le paramètre ne suffit pas. ``rsau/enable``
        vaut 1 sur les deux releases du banc, et une campagne qui s'arrête là
        conclut « audit actif » ; le relevé complet dit que 10 slots de
        filtrage sont DÉCLARÉS et qu'aucun n'est actif. Le journal est donc
        armé au niveau du noyau sans rien filtrer, ce qui est le faux positif
        de conformité le plus coûteux du domaine : le contrôle passe, et
        l'enregistrement qu'on croit avoir n'existe pas.

        Le verdict vaut ``disabled``, ``armed_without_filter`` ou
        ``filtering``. Des slots illisibles ne comptent jamais comme actifs :
        sur un contrôle d'audit, le repli sûr est de ne pas inventer une
        couverture.

        NB de lecture, relevé sur les deux cibles : le module ancien rend une
        date corrompue (année ``0126``) là où l'API moderne rend la bonne.
        Le keyword lit l'ancien, qui est le seul à porter le détail des slots,
        mais n'expose PAS sa date, précisément pour qu'aucune assertion ne
        s'appuie dessus."""
        config = self.call_rfc("RSAU_GET_AUDIT_CONFIG", alias=alias)
        return security_inventory.classify_audit_configuration(config)

    def read_rfc_destination_inventory(self, alias: str = "default",
                                       types: Any = None) -> list[dict[str, Any]]:
        """Inventorie les **destinations RFC** et classe chacune : où elle
        pointe, et si elle conserve un logon ou un mot de passe.

        Rend une fiche par destination (``destination``, ``type``,
        ``stored_logon``, ``stored_password``, plus la cible quand elle est
        déclarée). ``types`` restreint aux types voulus (``3`` pour les
        destinations ABAP, ``H``/``G`` pour HTTP), en liste ou en chaîne à
        virgules.

        Ce que le keyword apporte sur une simple lecture de table : les
        informations de logon ne sont pas dans une colonne, elles sont enfouies
        dans un agrégat de marqueurs mono-lettres. Une destination qui stocke
        un logon vers un autre système est un chemin d'élévation, et c'est
        exactement ce qu'un audit cherche à inventorier.

        Il ne lit JAMAIS un secret : il constate qu'une destination en
        conserve un. La valeur reste chiffrée et ce canal ne l'expose pas. Les
        marqueurs dont la signification n'est pas établie sont ignorés plutôt
        que devinés, une interprétation approximative valant moins que rien
        dans un rapport de sécurité, puisqu'elle serait lue comme un fait."""
        rows = self.read_rfc_table(
            "RFCDES", ["RFCDEST", "RFCTYPE", "RFCOPTIONS"], alias=alias)
        wanted = {str(t).strip() for t in robot_args.as_name_list(types)} \
            if types else None
        fiches = []
        for row in rows:
            kind = str(row.get("RFCTYPE", "")).strip()
            if wanted is not None and kind not in wanted:
                continue
            fiches.append(security_inventory.classify_rfc_destination(
                row.get("RFCDEST", ""), kind, row.get("RFCOPTIONS", "")))
        return fiches

    def build_security_posture(self, identity: Mapping[str, Any],
                               readings: Iterable[Mapping[str, Any]],
                               controls: Iterable[Mapping[str, Any]],
                               observations: Optional[Mapping[str, Any]] = None
                               ) -> dict[str, Any]:
        """Assemble l'artefact déterministe d'une posture : identité de la
        cible, mesures, verdicts et résumé, plus un hash calculé **hors
        horodatage**.

        ``identity`` doit porter ce qui PROUVE la cible. Sur un poste qui
        héberge deux conteneurs SAP, l'identifiant système et le nom d'hôte
        applicatif ne le font pas (les deux annoncent la même chose) et
        l'adresse IP est volatile : les ancres sont la release et le kernel.
        Hors ligne : n'ouvre aucune connexion, tout vient des lectures déjà
        faites."""
        return security_baseline.posture_artifact(
            identity, readings, controls_verdicts(controls, readings),
            observations=observations,
            generated_at=datetime.datetime.now(
                datetime.timezone.utc).isoformat(timespec="seconds"))

    def write_security_posture(self, path: str,
                               artifact: Mapping[str, Any]) -> dict[str, Any]:
        """Écrit un artefact de posture en JSON trié déterministe et retourne
        ``{path, sha256}``.

        Deux exécutions aux mêmes mesures sur la même cible écrivent le même
        contenu au hash près de l'horodatage, donc un artefact committé sert de
        référence de dérive."""
        payload = dict(artifact)
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                          indent=2) + "\n"
        directory = os.path.dirname(str(path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(str(path), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(blob)
        digest = str(payload.get("hash", ""))
        logger.info("Posture de sécurité écrite dans %s (hash %s)."
                    % (path, digest))
        return {"path": str(path), "sha256": digest}

    def read_security_posture(self, path: str) -> dict[str, Any]:
        """Relit un artefact écrit par `Write Security Posture` et le rend tel
        quel, pour qu'une suite n'ouvre jamais le fichier elle-même.

        Lu en ``utf-8-sig`` et non en ``utf-8``, à dessein : une référence
        committée est un fichier que des humains éditent, et sous Windows un
        éditeur ou un script PowerShell y laisse volontiers une marque d'ordre
        d'octets. Avec un décodage strict, la sentinelle échouait alors sur
        ``Unexpected UTF-8 BOM`` au lieu de comparer, c'est-à-dire qu'elle
        rougissait pour une raison sans rapport avec la sécurité du système,
        exactement là où elle doit être lisible. Constaté le 2026-08-29 en
        éprouvant la détection de dérive."""
        with open(str(path), encoding="utf-8-sig") as handle:
            return dict(json.load(handle))

    def security_posture_should_not_have_drifted(
            self, reference_path: str, readings: Iterable[Mapping[str, Any]],
            identity: Optional[Mapping[str, Any]] = None,
            fail_on_drift: Any = True) -> dict[str, Any]:
        """Compare la posture mesurée à la **référence committée** de la cible,
        et rend le verdict de dérive.

        Sémantique **snapshot**, celle de la sentinelle d'écran du dépôt :
        au premier passage la référence n'existe pas, elle est ÉCRITE et
        l'appel réussit avec un WARNING nommant le fichier à committer ;
        ensuite, tout écart est rapporté paramètre par paramètre.

        C'est ce qui rend une campagne de sécurité rejouable au lieu d'être un
        audit à verdict permanent. Juger « ce système est-il durci » rend une
        suite rouge à vie sur un bac à sable, donc désactivée ; juger « sa
        configuration a-t-elle bougé depuis la référence » a une réponse
        binaire, et c'est la dérive non annoncée qui est l'incident.

        ``fail_on_drift`` (vrai par défaut) décide si une dérive fait échouer
        ou se contente d'un rapport. Le verdict retourné est JSON-safe."""
        measured = [dict(r) for r in readings]
        reference_path = os.path.normpath(str(reference_path))
        exists = os.path.exists(str(reference_path))
        if not exists:
            artifact = security_baseline.posture_artifact(
                identity or {"note": "référence initiale"}, measured, [])
            self.write_security_posture(reference_path, artifact)
            logger.warn(
                "Aucune référence de posture : %s vient d'être ÉCRITE à partir "
                "de ce passage. La relire, la committer, et c'est elle qui "
                "servira de comparaison ensuite." % reference_path)
            return {"first_visit": True, "drifted": False,
                    "reference": str(reference_path), "changed": [],
                    "appeared": [], "disappeared": [],
                    "unchanged": len(measured)}

        reference = self.read_security_posture(reference_path)
        verdict = security_baseline.compare_posture(
            measured, reference.get("readings", []))
        verdict["first_visit"] = False
        verdict["reference"] = str(reference_path)
        if verdict["drifted"] and _as_bool(fail_on_drift):
            lines = [f"- {c['name']} : {c['before']['status']}"
                     f" {c['before']['value']!r} -> {c['after']['status']}"
                     f" {c['after']['value']!r}" for c in verdict["changed"]]
            for name in verdict["appeared"]:
                lines.append(f"- {name} : apparu (absent de la référence)")
            for name in verdict["disappeared"]:
                lines.append(f"- {name} : disparu du relevé")
            raise AssertionError(
                "La configuration de sécurité a DÉRIVÉ depuis la référence "
                f"{reference_path} :\n" + "\n".join(lines) +
                "\n\nSi la dérive est voulue, relire la référence et la "
                "re-committer ; sinon, c'est un changement de configuration "
                "non annoncé sur la cible.")
        return verdict


def controls_verdicts(controls: Iterable[Mapping[str, Any]],
                      readings: Iterable[Mapping[str, Any]]
                      ) -> list[dict[str, Any]]:
    """Raccourci interne vers la logique pure : confronte contrôles et mesures."""
    return security_baseline.evaluate_controls(controls, readings)
