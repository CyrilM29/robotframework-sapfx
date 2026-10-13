"""Mixin de cartographie du paysage par RFC : `Read Workload Statistics` et
`Read Sap Landscape` (backlog § 2.76, lot 2, 2026-10-12).

Le relevé côté SAP de la cartographie des interfaces, en lecture seule : il
assemble les lecteurs existants (destinations, profils partenaire, registre
Gateway) et lit ce qui manquait (trafic IDoc et jobs sur la fenêtre, appels
tRFC en échec, statistiques de la collecte de workload). L'assemblage et les
règles de classement sont dans ``sapfx_common.landscape_collect``, hors
système ; le modèle et ses verdicts dans ``sapfx_common.landscape``.

Typed.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from sapfx_common import gateway_log, landscape_collect
from sapfx_common.robot_args import as_optional_int

from ._rfc_impact import RfcImpactKeywords

#: États tRFC qui disent qu'un appel n'est PAS parti (SM58).
TRFC_ERROR_STATES = ("SYSFAIL", "CPICERR", "SYSLOAD")


class RfcLandscapeKeywords(RfcImpactKeywords):
    """Mixin de :class:`SapApiLibrary` : le relevé des interfaces d'un système."""

    def _window(self, days: Any) -> tuple[int, dt.date, dt.date]:
        given = as_optional_int(days, "days")
        span = 30 if given is None else given
        if span < 1:
            raise ValueError("days doit valoir au moins 1, reçu %d." % span)
        end = dt.date.today()
        return span, end - dt.timedelta(days=span), end

    def read_workload_statistics(self, alias: str = "default", days: Any = 30,
                                 component: str = "TOTAL") -> dict[str, Any]:
        """Lit les statistiques d'appels de la *collecte de workload* (celle
        de ST03N) sur les ``days`` derniers jours : appels RFC sortants par
        destination, appels RFC entrants, requêtes HTTP reçues par chemin.

        Rend ``{available, last_collection, days_read, totals, note}``.
        ``available`` est faux quand aucun jour de la fenêtre n'a été
        collecté, et c'est un état à part entière, jamais un zéro : le job du
        collecteur peut ne plus tourner (sur les deux images de démonstration
        du banc, il s'est arrêté le 2017-05-08, dernier agrégat quotidien du
        2017-05-05) ; ``last_collection``
        dit alors jusqu'où la source remonte et ``note`` le formule. Lecture
        seule, par ``SWNC_COLLECTOR_GET_AGGREGATES`` jour par jour, sur les
        seuls jours que l'index de la collecte (``SWNCMONIINDEX``) déclare.
        Un jour sans agrégat ``TOTAL`` (il n'est produit qu'une fois par jour,
        après le collecteur horaire) se lit sur ses composants d'instance,
        additionnés ; ``components`` dit ce qui a été lu.

        Exemple :
        | ${stats}=    `Read Workload Statistics`    days=30
        | Should Not Be Empty    ${stats}[note]
        """
        span, start, end = self._window(days)
        try:
            index = self.read_rfc_table("SWNCMONIINDEX", ["COMPONENT", "PERIODTYPE", "PERIODSTRT"],
                                        alias=alias, options=["PERIODTYPE = 'D'"])
        except Exception as exc:  # noqa: BLE001 - une source illisible est un état, pas une panne
            return {"available": False, "last_collection": None, "days_read": 0, "totals": {},
                    "note": "index de la collecte illisible : %s" % str(exc).splitlines()[0][:120]}
        last, reads = landscape_collect.plan_workload_reads(index, component, start, end)
        if not reads:
            result: dict[str, Any] = {"available": False, "last_collection": last, "days_read": 0,
                                      "totals": {}}
            result["note"] = landscape_collect.workload_note(result)
            return result
        system = str(self.get_rfc_connection_attributes(alias).get("sysId", "")).strip()
        rows = [self.call_rfc("SWNC_COLLECTOR_GET_AGGREGATES", alias=alias, COMPONENT=comp,
                              ASSIGNDSYS=system, PERIODTYPE="D", PERIODSTRT=day) for day, comp in reads]
        days_read = len({day for day, _ in reads})
        return {"available": True, "last_collection": last, "days_read": days_read,
                "components": sorted({comp for _, comp in reads}),
                "totals": landscape_collect.normalize_workload(rows),
                "note": "%d jour(s) collecté(s) sur %d" % (days_read, span)}

    def read_sap_landscape(self, alias: str = "default", days: Any = 30,
                           max_rows: Any = 50000) -> dict[str, Any]:
        """Relève les interfaces du système joint par ``alias`` et rend
        l'ENTRÉE de la cartographie : ``{target, window, nodes, interfaces,
        limits}``, à valider par ``build_landscape`` puis rendre par l'outil
        ``tools/landscape_map``.

        Lit, en lecture seule : l'identité (release, kernel, hôtes, système
        logique du mandant), les mandants, les destinations RFC classées, les
        profils partenaire IDoc et le trafic ``EDIDC`` des ``days`` derniers
        jours, le registre Gateway, les jobs de la fenêtre, les appels tRFC en
        échec, les statistiques de workload (`Read Workload Statistics`) et
        l'activation ICF des chemins HTTP servis (seconde source d'une
        interface HTTP). Un appelant RFC entrant qu'aucune destination ne
        déclare devient lui aussi une interface.
        Un trafic sans profil actuel reste une interface (l'écart que l'outil
        doit montrer), une destination vers le système lui-même est un
        bouclage, une destination de programme est comptée sans devenir un
        tiers. ``max_rows`` borne chaque lecture volumineuse ; une borne
        atteinte est annoncée dans les limites, jamais tue.

        Exemple :
        | ${survey}=    `Read Sap Landscape`    days=30
        | Should Be Equal    ${survey}[target][basis_release]    754
        """
        span, start, end = self._window(days)
        cap = as_optional_int(max_rows, "max_rows") or 0
        since = start.strftime("%Y%m%d")
        attrs = self.get_rfc_connection_attributes(alias)
        client = str(attrs.get("client", "")).strip()
        info = self.call_rfc("RFC_SYSTEM_INFO", alias=alias).get("RFCSI_EXPORT", {})
        basis = self.read_rfc_table("CVERS", ["RELEASE"], alias=alias, options=["COMPONENT = 'SAP_BASIS'"])
        clients = self.read_rfc_table("T000", ["MANDT", "MTEXT", "LOGSYS", "CCCATEGORY"], alias=alias)
        logsys = next((r["LOGSYS"].strip() for r in clients if r["MANDT"].strip() == client), "")
        identity = {"system": str(info.get("RFCSYSID", "")).strip(), "client": client,
                    "basis_release": basis[0]["RELEASE"].strip() if basis else "",
                    "kernel": str(info.get("RFCKERNRL", "")).strip(), "host": str(info.get("RFCHOST", "")).strip(),
                    "db_host": str(info.get("RFCDBHOST", "")).strip(), "logical_system": logsys}
        limits: list[str] = []

        def bounded(table: str, fields: list[str], options: list[str]) -> list[dict[str, str]]:
            rows = self.read_rfc_table(table, fields, alias=alias, options=options,
                                       rowcount=cap + 1 if cap else 0)
            if cap and len(rows) > cap:
                limits.append("%s : plafond de %d lignes atteint, volumes minorés." % (table, cap))
                return rows[:cap]
            return rows

        traffic: list[dict[str, Any]] | None
        try:
            edidc = bounded("EDIDC", ["DIRECT", "MESTYP", "SNDPRN", "RCVPRN"], ["CREDAT >= '%s'" % since])
            grouped: dict[tuple[str, ...], int] = {}
            for row in edidc:
                key = (row["DIRECT"].strip(), row["MESTYP"].strip(), row["SNDPRN"].strip(), row["RCVPRN"].strip())
                grouped[key] = grouped.get(key, 0) + 1
            traffic = [{"direction": k[0], "message_type": k[1], "sender": k[2], "receiver": k[3], "count": n}
                       for k, n in sorted(grouped.items())]
        except Exception:  # noqa: BLE001 - trafic illisible = volumes None, jamais zéro
            traffic = None
        jobs = bounded("TBTCO", ["JOBNAME"], ["SDLSTRTDT >= '%s'" % since])
        trfc = self.read_rfc_table("ARFCSSTATE", ["ARFCDEST", "ARFCSTATE"], alias=alias,
                                   options=[" OR ".join("ARFCSTATE = '%s'" % s for s in TRFC_ERROR_STATES)])
        workload = self.read_workload_statistics(alias=alias, days=span)
        icf: dict[str, bool] = {}
        served = sorted(((workload.get("totals") or {}).get("http_server") or {}).items(),
                        key=lambda kv: -kv[1])
        for path, _count in served[:5]:
            try:
                icf[path] = bool(self.get_icf_node_activation(path, alias=alias).get("active"))
            except Exception:  # noqa: BLE001 - activation illisible = source absente, jamais « actif »
                continue
        model = landscape_collect.assemble_sap_landscape(
            identity, clients, self.read_rfc_destination_inventory(alias=alias),
            self.get_idoc_partner_profiles("outbound", alias=alias),
            self.get_idoc_partner_profiles("inbound", alias=alias), traffic,
            self.read_rfc_table(gateway_log.REGISTRY_TABLE, gateway_log.REGISTRY_FIELDS, alias=alias),
            [{"JOBNAME": r["JOBNAME"].strip(), "runs": 1} for r in jobs],
            [{"destination": r["ARFCDEST"].strip(), "state": r["ARFCSTATE"].strip()} for r in trfc],
            workload, {"days": span, "measured_from": start.isoformat(), "measured_to": end.isoformat()},
            icf_activation=icf)
        model["limits"] = limits + model["limits"]
        return model
