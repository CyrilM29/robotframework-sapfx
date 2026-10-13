"""Mixin d'analyse d'impact de changement par RFC : `Read Transport Request`,
`Get Object Usage` et `Get Change Impact` (backlog § 2.3, 2026-10-09).

Un MVP annoncé comme tel : un transport, ses objets, UN niveau
d'utilisation lu dans les tables de références du système, les transactions
des programmes qui les utilisent. Lecture seule (``RFC_READ_TABLE``). Le
croisement avec les suites de test est dans ``sapfx_common.change_impact``
(`Suites Impacted By Change`), hors système.

Typed.
"""
from __future__ import annotations

from typing import Any

from sapfx_common import change_impact
from sapfx_common.rfc_tables import abap_quote, in_list_clauses
from sapfx_common.robot_args import as_optional_int

from ._rfc_gateway import RfcGatewayKeywords

#: Valeurs d'une liste ``IN`` par appel : la clause se découpe en lignes de
#: 72 caractères, un appel en porte des dizaines sans peine.
IN_CHUNK = 40


class RfcImpactKeywords(RfcGatewayKeywords):
    """Mixin de :class:`SapApiLibrary` : d'un transport aux transactions
    qu'il touche."""

    # -- lectures bornées ---------------------------------------------------------------

    def _impact_rows(self, table: str, fields: str, alias: str, clauses: list[str],
                     cap: int = 0) -> tuple[list[dict[str, str]], bool]:
        """Lignes et complétude : avec un plafond, on lit une ligne de plus
        pour SAVOIR qu'il est atteint, jamais pour la rendre."""
        rows = self.read_rfc_table(table, fields, alias=alias, options=clauses,
                                   rowcount=cap + 1 if cap else 0)
        if cap and len(rows) > cap:
            return rows[:cap], False
        return rows, True

    def _impact_rows_in(self, table: str, fields: str, alias: str, field: str,
                        values: list[str], cap: int = 0) -> tuple[list[dict[str, str]], bool]:
        rows: list[dict[str, str]] = []
        complete = True
        for start in range(0, len(values), IN_CHUNK):
            clauses = in_list_clauses(field, values[start:start + IN_CHUNK])
            part, whole = self._impact_rows(table, fields, alias, clauses, cap)
            rows.extend(part)
            complete = complete and whole
        if cap and len(rows) > cap:
            return rows[:cap], False
        return rows, complete

    # -- keywords -----------------------------------------------------------------------

    def read_transport_request(self, request: str, alias: str = "default") -> dict[str, Any]:
        """Lit un transport (requête ou tâche) et les objets qu'il porte :
        ``{request, function, status, owner, date, text, parent, tasks,
        objects, skipped}``.

        Les objets d'une requête vivent sur ses TÂCHES jusqu'à sa libération :
        la requête et ses tâches (``E070-STRKORR``) sont lues ensemble, les
        objets dédoublonnés. Chaque objet porte son objet PRINCIPAL
        (``main_type``, ``main_name``) : une méthode (``LIMU METH``) relève de
        sa classe, un include de classe de son pool, une table de contenu
        (``TABU``) de sa table. Ce qui ne désigne rien d'exécutable
        (libération ``CORR``, note, documentation) va dans ``skipped``, nommé,
        jamais perdu. Un transport absent de ``E070`` échoue en le nommant.

        Exemple :
        | ${request}=    `Read Transport Request`    A4HK900053    alias=a4h
        | Should Be Equal    ${request}[function]    W
        | Should Be Equal    ${request}[objects][0][main_name]    TTZCU
        """
        number = str(request or "").strip().upper()
        if not number:
            raise ValueError("Read Transport Request : numéro de transport vide.")
        head, _ = self._impact_rows("E070", "TRKORR,TRFUNCTION,TRSTATUS,AS4USER,AS4DATE,"
                                    "STRKORR", alias, ["TRKORR = %s" % abap_quote(number)])
        if not head:
            raise AssertionError("Transport %s absent de E070 sur ce système (numéro, "
                                 "mandant de transport, système visé ?)." % number)
        tasks, _ = self._impact_rows("E070", "TRKORR", alias,
                                     ["STRKORR = %s" % abap_quote(number)])
        texts, _ = self._impact_rows("E07T", "AS4TEXT", alias,
                                     ["TRKORR = %s" % abap_quote(number)], cap=1)
        keys = [number] + sorted(t["TRKORR"] for t in tasks)
        rows, _ = self._impact_rows_in("E071", "PGMID,OBJECT,OBJ_NAME", alias, "TRKORR", keys)
        objects: list[dict[str, str]] = []
        skipped: list[dict[str, str]] = []
        seen: set[tuple[str, str, str]] = set()
        for row in rows:
            key = (row.get("PGMID", ""), row.get("OBJECT", ""), row.get("OBJ_NAME", ""))
            if key in seen:
                continue
            seen.add(key)
            main = change_impact.main_object(*key)
            entry = {"pgmid": key[0], "type": key[1], "name": key[2].strip()}
            if main is None:
                skipped.append(entry)
            else:
                objects.append({**entry, "main_type": main["type"], "main_name": main["name"]})
        first = head[0]
        return {
            "request": number, "function": first.get("TRFUNCTION", ""),
            "status": first.get("TRSTATUS", ""), "owner": first.get("AS4USER", ""),
            "date": first.get("AS4DATE", ""), "text": texts[0]["AS4TEXT"] if texts else "",
            "parent": first.get("STRKORR", ""), "tasks": keys[1:],
            "objects": objects, "skipped": skipped,
        }

    def get_object_usage(self, object_type: str, name: str, alias: str = "default",
                         max_rows: Any = 500) -> dict[str, Any]:
        """Qui utilise un objet, UN niveau : ``{object, strategy, programs,
        transactions, names, complete}``.

        Selon le type : une table, une vue ou un contenu de table (``TABL``,
        ``VIEW``, ``TABU``) par ``D010TAB`` ; une vue CDS ou son extension de
        métadonnées (``DDLS``, ``DDLX``) par ses vues SQL (``DDLDEPENDENCY``)
        puis ``D010TAB`` ; une classe, une interface, un type de table ou une
        définition de comportement (``CLAS``, ``INTF``, ``TTYP``, ``BDEF``) par
        ``WBCROSSGT`` ; un élément de données (``DTEL``) par les tables qui le
        portent (``DD03L``) et le code qui le prend pour type (``WBCROSSGT``) ;
        un domaine (``DOMA``) par ses éléments de données (``DD04L``) et les
        tables qui le portent ; un objet de verrouillage (``ENQU``) par ses
        modules ``ENQUEUE_`` et ``DEQUEUE_`` et leurs appelants ; une définition
        ou une liaison de service (``SRVD``, ``SRVB``) par l'autre et le nom du
        service (``SRVB_SERVICES``) ; un module fonction par ``CROSS``
        (appelants) et son groupe (``ENLFDIR``) ; un programme par lui-même et,
        s'il est un include, ses programmes principaux (``D010INC``). Puis les
        transactions de ces programmes (``TSTC``). ``names`` rend les noms
        qu'une suite peut écrire (l'objet, ses vues SQL, son groupe, les tables
        qui portent un élément de données ; pour un service, aussi sa forme
        d'URL OData, ``dmo/ui_travel_d_d_o4``).

        ``max_rows`` borne chaque lecture : un plafond atteint rend
        ``complete`` à faux, jamais une liste tronquée en silence (mesuré sur
        A4H : ``T000`` est lue par 2793 programmes). Les références sont
        STATIQUES : un accès par SQL dynamique ou un appel par nom calculé n'y
        figure pas. Un type sans famille de références (``IWSV``, ``IWMO``...)
        rend ``strategy`` vide et son seul nom (et sa forme d'URL pour un
        service Gateway).

        Exemple :
        | ${usage}=    `Get Object Usage`    TABL    TTZCU    alias=a4h
        | Should Be True    ${usage}[complete]
        | Should Contain    ${usage}[programs]    CL_SUID_TOOLS=================CP
        """
        kind = str(object_type or "").strip().upper()
        target = str(name or "").strip()
        if not kind or not target:
            raise ValueError("Get Object Usage : type et nom d'objet obligatoires.")
        cap = as_optional_int(max_rows, "max_rows") or 0
        strategy = change_impact.usage_strategy(kind)
        names: list[str] = [target]
        masters: list[str] = []
        transactions: list[str] = []
        complete = True

        def tables_users(tables: list[str]) -> None:
            nonlocal complete
            rows, whole = self._impact_rows_in("D010TAB", "MASTER", alias, "TABNAME",
                                               tables, cap)
            masters.extend(r["MASTER"] for r in rows)
            complete = complete and whole

        if strategy == "tables":
            tables_users([target])
        elif strategy == "cds":
            views, _ = self._impact_rows("DDLDEPENDENCY", "OBJECTNAME", alias, [
                "DDLNAME = %s" % abap_quote(target.upper()), "AND STATE = 'A'",
                "AND OBJECTTYPE = 'VIEW'"])
            names.extend(v["OBJECTNAME"] for v in views)
            tables_users(sorted({target.upper(), *(v["OBJECTNAME"] for v in views)}))
        elif strategy == "types":
            rows, whole = self._impact_rows("WBCROSSGT", "INCLUDE", alias, [
                "OTYPE = 'TY'", "AND NAME = %s" % abap_quote(target)], cap)
            complete = whole
            masters.extend(self._masters_of_includes(sorted({r["INCLUDE"] for r in rows}),
                                                     alias))
        elif strategy == "functions":
            groups, _ = self._impact_rows("ENLFDIR", "AREA", alias,
                                          ["FUNCNAME = %s" % abap_quote(target)])
            names.extend(g["AREA"] for g in groups)
            masters.extend(change_impact.function_group_master(g["AREA"]) for g in groups)
            rows, whole = self._impact_rows("CROSS", "INCLUDE", alias, [
                "TYPE = 'F'", "AND NAME = %s" % abap_quote(target)], cap)
            complete = whole
            masters.extend(self._masters_of_includes(sorted({r["INCLUDE"] for r in rows}),
                                                     alias))
        elif strategy == "data_element":
            tables, carried = self._impact_rows("DD03L", "TABNAME", alias, [
                "ROLLNAME = %s" % abap_quote(target), "AND AS4LOCAL = 'A'"], cap)
            names.extend(t["TABNAME"] for t in tables)
            rows, typed = self._impact_rows("WBCROSSGT", "INCLUDE", alias, [
                "OTYPE = 'TY'", "AND NAME = %s" % abap_quote(target)], cap)
            masters.extend(self._masters_of_includes(sorted({r["INCLUDE"] for r in rows}),
                                                     alias))
            complete = carried and typed
        elif strategy == "domain":
            elements, whole = self._impact_rows("DD04L", "ROLLNAME", alias, [
                "DOMNAME = %s" % abap_quote(target), "AND AS4LOCAL = 'A'"], cap)
            tables, carried = self._impact_rows("DD03L", "TABNAME", alias, [
                "DOMNAME = %s" % abap_quote(target), "AND AS4LOCAL = 'A'"], cap)
            names.extend([e["ROLLNAME"] for e in elements] + [t["TABNAME"] for t in tables])
            complete = whole and carried
        elif strategy == "lock_object":
            modules = ["ENQUEUE_" + target, "DEQUEUE_" + target]
            found, _ = self._impact_rows_in("ENLFDIR", "FUNCNAME", alias, "FUNCNAME", modules)
            names.extend(f["FUNCNAME"] for f in found)
            for module in modules:
                rows, whole = self._impact_rows("CROSS", "INCLUDE", alias, [
                    "TYPE = 'F'", "AND NAME = %s" % abap_quote(module)], cap)
                complete = complete and whole
                masters.extend(self._masters_of_includes(
                    sorted({r["INCLUDE"] for r in rows}), alias))
        elif strategy in ("service_definition", "service_binding"):
            key, other = (("SRVDNAME", "SRVB_NAME") if strategy == "service_definition"
                          else ("SRVB_NAME", "SRVDNAME"))
            rows, complete = self._impact_rows("SRVB_SERVICES", "%s,SERVICE_NAME" % other,
                                               alias, ["%s = %s" % (key, abap_quote(target)),
                                                       "AND VERSION = 'A'"], cap)
            names.extend(r[n] for r in rows for n in (other, "SERVICE_NAME"))
        elif strategy == "function_group":
            masters.append(change_impact.function_group_master(target))
        elif strategy == "programs":
            masters.extend(self._masters_of_includes([target], alias) or [target])
        elif strategy == "transactions":
            transactions.append(target)
        if kind in change_impact.SERVICES:      # le nom tel qu'une URL OData l'écrit
            names.extend(u for n in list(names) for u in change_impact.service_url_names(n))
        programs = sorted(set(masters))
        if programs:
            rows, whole = self._impact_rows_in("TSTC", "TCODE", alias, "PGMNA", programs, cap)
            transactions.extend(r["TCODE"] for r in rows)
            complete = complete and whole
        return {"object": {"type": kind, "name": target}, "strategy": strategy or "",
                "programs": programs, "transactions": sorted(set(transactions)),
                "names": sorted(set(names)), "complete": complete,
                "max_rows": cap}

    def _masters_of_includes(self, includes: list[str], alias: str) -> list[str]:
        """Programmes principaux d'includes : par le NOM pour un pool de
        classe, par ``D010INC`` pour les autres ; un include sans maître
        connu est rendu tel quel (un rapport est son propre maître). Un include
        technique caché (``~DMO/BP_TRAVEL_U===HP/``, définitions locales d'un
        pool) est écarté : aucune suite ne l'écrit, et son pool est rendu par
        ses autres includes."""
        masters: list[str] = []
        unknown: list[str] = []
        for include in (i for i in includes if not i.startswith("~")):
            master = change_impact.include_master(include)
            if master:
                masters.append(master)
            else:
                unknown.append(include)
        if unknown:
            rows, _ = self._impact_rows_in("D010INC", "MASTER,INCLUDE", alias, "INCLUDE",
                                           unknown)
            owned = {r["INCLUDE"] for r in rows}
            masters.extend(r["MASTER"] for r in rows)
            masters.extend(i for i in unknown if i not in owned)
        return masters

    def get_change_impact(self, request: str, alias: str = "default",
                          max_rows: Any = 500) -> dict[str, Any]:
        """L'impact d'un transport, assemblé : `Read Transport Request`, puis
        `Get Object Usage` sur chaque objet PRINCIPAL (une fois chacun), puis
        ``{request, objects, skipped, usages, programs, transactions, names,
        truncated, limits}`` (``sapfx_common.change_impact``). ``names`` est
        ce qu'on croise avec les suites (`Suites Impacted By Change`) ;
        ``truncated`` nomme les objets dont un plafond a été atteint ;
        ``limits`` dit ce que l'analyse ne voit pas. JSON-safe et
        déterministe (même transport, même système, même empreinte).

        Exemple :
        | ${impact}=    `Get Change Impact`    A4HK900053    alias=a4h
        | Should Contain    ${impact}[names]    TTZCU
        | Should Be Empty    ${impact}[truncated]
        """
        found = self.read_transport_request(request, alias)
        mains = sorted({(o["main_type"], o["main_name"]) for o in found["objects"]})
        usages = [self.get_object_usage(kind, name, alias, max_rows) for kind, name in mains]
        return change_impact.build_change_impact(found, usages)
