"""Mixin de la supervision de la Gateway SAP par RFC : `Read Gateway Error Log`,
`Get Gateway Error Log Entry`, `Wait For Gateway Error Log Entry`,
`Get Gateway Service Registration`, `Gateway Service Should Be Registered`
et `Get Icf Node Activation`.

Né du scénario 11 (2026-10-07, a4h, release 754) : la bibliothèque savait
dire si la Gateway répond (`Get Gateway Status`) et ce qu'un service déclare
(`Get Odata Metadata`), pas ce que la Gateway a ENREGISTRÉ (le registre
``/IWFND/I_MED_SRH`` que montre ``/IWFND/MAINT_SERVICE``) ni ce qu'elle a
JOURNALISÉ (le journal ``/IWFND/SU_ERRLOG`` que montre ``/IWFND/ERROR_LOG``).
Le journal regroupe les erreurs identiques : on y retrouve une requête par
son URI, jamais par un compte d'entrées. Logique pure dans
``sapfx_common.gateway_log``.

Typed.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from robot.utils import timestr_to_secs

from sapfx_common import gateway_log
from sapfx_common.rfc_reads import build_options

from ._rfc_users import RfcUserKeywords


class RfcGatewayKeywords(RfcUserKeywords):
    """Mixin de :class:`SapApiLibrary` : registre et journal de la Gateway."""

    def read_gateway_error_log(self, alias: str = "default", uri_contains: Optional[str] = None,
                               message_id: Optional[str] = None, user: Optional[str] = None,
                               since: Optional[str] = None,
                               transaction_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Lit le journal d'erreurs de la Gateway (``/IWFND/SU_ERRLOG``, celui
        de ``/IWFND/ERROR_LOG``) par RFC et rend ses entrées, triées par
        dernière activité : ``identity`` (``/IWFND/MED/170``), ``count``,
        ``first_seen``, ``last_seen`` (ISO, heure SYSTÈME), ``expiry``,
        ``request_uri``, ``service_name``, ``service_version``,
        ``logged_http_status``, ``transaction_id``, ``user``, ``client`` (le
        mandant qui a SERVI la requête HTTP), ``location``, ``opid``.

        Filtres facultatifs : ``uri_contains`` (fragment de l'URI, sans casse),
        ``message_id`` (identité ``CLASSE/NUMÉRO``), ``user``, ``since`` (ISO,
        heure SYSTÈME, comparé à la dernière activité ; filtré côté serveur :
        à poser dès qu'on connaît le début du run, le journal gardant 14 jours
        d'entrées de tous les acteurs), ``transaction_id`` (celui que rend
        `Get Odata Error` sur la réponse du client : le lien le plus fort entre
        ce que le client a reçu et ce que la Gateway a journalisé).

        Ce que le journal fait d'une erreur, mesuré sur la 754 : le même appel
        rejoué ne crée PAS d'entrée, il fait monter ``count`` de l'entrée
        existante et lui donne un nouvel ``opid``. Un nombre d'entrées avant et
        après ne prouve donc rien, et ``opid`` n'est pas une ancre : retrouver
        une requête par son URI (`Get Gateway Error Log Entry`). Un service
        inexistant est journalisé ``/IWFND/MED/170`` avec ``service_name``
        vide et ``logged_http_status`` à ``000``, alors que le client a reçu
        403 : le statut journalisé n'est pas celui du fil.

        Exemple :
        | ${entries}=    `Read Gateway Error Log`    alias=gw11    message_id=/IWFND/MED/170
        | Should Not Be Empty    ${entries}
        """
        options = build_options([("USERNAME", user.strip().upper() if user else None)])
        if since:
            # filtré CÔTÉ SERVEUR (borne numérique, sans joker) : le journal
            # garde 14 jours d'entrées de tous les acteurs du système
            options.append(("AND " if options else "") + "TIMESTAMP GE %s" % gateway_log.iso_to_sap_timestamp(since))
        rows = self.read_rfc_table(gateway_log.ERROR_LOG_TABLE, gateway_log.ERROR_LOG_FIELDS,
                                   alias=alias, options=options or None)
        entries = [gateway_log.normalize_error_entry(r) for r in rows]
        return gateway_log.select_entries(entries, uri_contains=uri_contains, identity=message_id,
                                          since=since, transaction_id=transaction_id)

    def get_gateway_error_log_entry(self, uri_contains: str, alias: str = "default",
                                    since: Optional[str] = None) -> dict[str, Any]:
        """L'entrée du journal d'erreurs Gateway d'UNE requête, retrouvée par
        un fragment de son URI : ``{"found": bool, ...}`` avec les champs de
        `Read Gateway Error Log` quand elle existe. Plusieurs entrées pour le
        fragment font échouer en les nommant : le fragment doit désigner une
        requête (un nom de service unique par run, par exemple).

        À lire AVANT et APRÈS l'appel qu'on observe : ``found`` faux puis
        ``count`` 1 = une entrée neuve ; ``count`` qui monte = le journal a
        regroupé la requête avec une précédente identique. ``since`` (ISO,
        heure système) borne la lecture côté serveur.

        Exemple :
        | ${entry}=    `Get Gateway Error Log Entry`    ZZ_SAPFX11_20261007165335    alias=gw11
        | Should Be Equal    ${entry}[identity]    /IWFND/MED/170
        """
        if not str(uri_contains or "").strip():
            raise ValueError("Get Gateway Error Log Entry : le fragment d'URI est vide, "
                             "il désignerait tout le journal.")
        entry = gateway_log.single_entry(
            self.read_gateway_error_log(alias=alias, uri_contains=uri_contains, since=since), uri_contains)
        return {"found": False, "uri_contains": uri_contains} if entry is None else {"found": True, **entry}

    def wait_for_gateway_error_log_entry(self, uri_contains: str, minimum_count: int = 1,
                                         timeout: str = "30s", poll: str = "1s",
                                         alias: str = "default", since: Optional[str] = None) -> dict[str, Any]:
        """Attend que l'entrée d'une requête apparaisse au journal d'erreurs
        Gateway avec un compteur d'au moins ``minimum_count``, et la rend.
        Délai dépassé = échec qui dit ce qui a été lu en dernier (absente, ou
        présente avec un compteur trop bas : la requête est peut-être
        regroupée sous une autre URI). ``since`` borne chaque lecture côté
        serveur.

        Exemple :
        | ${entry}=    `Wait For Gateway Error Log Entry`    ZZ_SAPFX11_20261007165335    alias=gw11    timeout=30s
        | Should Be Equal As Integers    ${entry}[count]    1
        """
        wanted = int(minimum_count)
        deadline = time.monotonic() + timestr_to_secs(timeout)
        step = timestr_to_secs(poll)
        while True:
            last = self.get_gateway_error_log_entry(uri_contains, alias=alias, since=since)
            if last["found"] and int(last["count"]) >= wanted:
                return last
            if time.monotonic() >= deadline:
                state = ("absente" if not last["found"]
                         else "présente avec un compteur de %s" % last["count"])
                raise AssertionError(
                    "Aucune entrée du journal d'erreurs Gateway pour %r avec un compteur d'au moins %d "
                    "après %s : dernière lecture, entrée %s." % (uri_contains, wanted, timeout, state))
            time.sleep(step)

    def get_gateway_service_registration(self, service_name: str, version: int = 1,
                                         namespace: str = "", alias: str = "default") -> dict[str, Any]:
        """L'enregistrement d'un service OData dans la Gateway (le registre
        ``/IWFND/I_MED_SRH`` que liste ``/IWFND/MAINT_SERVICE``) :
        ``{"service_name", "namespace", "version", "found", "active_version",
        "registrations"}``, chaque enregistrement portant son ``identifier``
        local (``ZSEPMRA_PROD_MAN_0001`` pour ``SEPMRA_PROD_MAN`` sur a4h : le
        préfixe est celui de l'enregistrement, pas le nom du service).

        C'est l'état DÉCLARÉ côté Gateway : ``active_version`` dit qu'une
        version active de l'enregistrement existe (champ clé de version, ``A``
        sur les 47 services d'a4h), JAMAIS que le service est servi. Ce que le
        service sert se mesure par le canal API (`Get Odata Metadata`) et par
        l'activation de son nœud ICF (`Get Icf Node Activation`). Un service
        absent rend ``found`` faux, jamais une erreur.

        Exemple :
        | ${reg}=    `Get Gateway Service Registration`    SEPMRA_PROD_MAN    alias=gw11
        | Should Be True    ${reg}[active_version]
        """
        name = str(service_name).strip().upper()
        if not name:
            raise ValueError("Get Gateway Service Registration : le nom de service est vide.")
        rows = self.read_rfc_table(gateway_log.REGISTRY_TABLE, gateway_log.REGISTRY_FIELDS, alias=alias,
                                   options=build_options([("SERVICE_NAME", name)]))
        return gateway_log.registration_verdict(rows, name, version=int(version), namespace=namespace)

    def gateway_service_should_be_registered(self, service_name: str, version: int = 1,
                                             namespace: str = "", alias: str = "default") -> dict[str, Any]:
        """Échoue sauf si le service est enregistré dans la Gateway à cette
        version, avec une version active de l'enregistrement ; rend
        l'enregistrement. L'échec dit lequel des deux manque. Ne prouve PAS
        que le service répond : le canal API le prouve.

        Exemple :
        | `Gateway Service Should Be Registered`    SEPMRA_PROD_MAN    alias=gw11
        """
        reg = self.get_gateway_service_registration(service_name, version=version, namespace=namespace,
                                                    alias=alias)
        if not reg["found"]:
            raise AssertionError(
                "Le service %s (version %d) n'est pas enregistré dans la Gateway (%s) : l'enregistrer "
                "par /IWFND/MAINT_SERVICE." % (reg["service_name"], reg["version"], gateway_log.REGISTRY_TABLE))
        if not reg["active_version"]:
            raise AssertionError(
                "Le service %s (version %d) est enregistré sans version active : %s."
                % (reg["service_name"], reg["version"],
                   ", ".join("%s=%s" % (r["identifier"], r["is_active_flag"]) for r in reg["registrations"])))
        return reg

    def get_icf_node_activation(self, path: str, host: str = "DEFAULT_HOST",
                                alias: str = "default") -> dict[str, Any]:
        """L'activation d'un nœud ICF désigné par son chemin (``/sap/opu/odata``)
        : ``{"path", "host", "found", "active", "inactive_ancestors",
        "node_guid", "missing"}``. Le chemin est remonté nœud par nœud dans
        ``ICFSERVICE`` (nom ET parent, un même nom étant porté par plusieurs
        nœuds), puis l'activation de CHAQUE nœud lue dans ``ICFSERVLOC``.
        ``active`` est celle de la FEUILLE ; ``inactive_ancestors`` nomme les
        nœuds du chemin qui sont inactifs (un ancêtre inactif coupe tout ce
        qui est dessous). Un chemin introuvable rend ``found`` faux et
        ``missing`` nomme le premier segment absent ; plusieurs lignes
        d'activation pour un même nœud font échouer en les nommant, jamais la
        première prise en silence.

        C'est le nœud qui porte le voyant ICF de ``/IWFND/MAINT_SERVICE`` : un
        service OData de la Gateway est servi sous le nœud ``ODATA``
        (``/sap/opu/odata``), pas sous un nœud à son nom. Que le service
        réponde se prouve par le canal API. ``host`` nomme l'hôte virtuel
        (jamais deviné d'après le chemin).

        Exemple :
        | ${node}=    `Get Icf Node Activation`    /sap/opu/odata    alias=gw11
        | Should Be True    ${node}[active]
        | Should Be Empty    ${node}[inactive_ancestors]
        """
        root, segments = gateway_log.split_icf_path(path, default_host=host)
        result: dict[str, Any] = {"path": "/" + "/".join(segments).lower(), "host": root, "found": False,
                                  "active": False, "inactive_ancestors": [], "node_guid": "", "missing": ""}
        # La racine d'un hôte virtuel a pour parent FFFF… (mesuré sur a4h).
        parent, node = "F" * 25, ""
        chain: list[tuple[str, str]] = []
        for position, segment in enumerate([root] + segments):
            if position:
                parent = node  # le parent d'un segment est le nœud du segment précédent
            rows = self.read_rfc_table("ICFSERVICE", ["ICF_NAME", "ICFPARGUID", "ICFNODGUID"], alias=alias,
                                       options=build_options([("ICF_NAME", segment), ("ICFPARGUID", parent)]))
            if not rows:
                result["missing"] = segment
                return result
            chain.append((segment, parent))
            node = str(rows[0]["ICFNODGUID"]).strip()
        states = []
        for name, par in chain:
            loc = self.read_rfc_table("ICFSERVLOC", ["ICF_NAME", "ICFPARGUID", "ICFACTIVE"], alias=alias,
                                      options=build_options([("ICF_NAME", name), ("ICFPARGUID", par)]))
            states.append((name, gateway_log.icf_activation(loc, name)))
        result.update(found=True, node_guid=node, active=states[-1][1],
                      inactive_ancestors=[n for n, active in states[:-1] if not active])
        return result
