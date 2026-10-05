"""Mixin des lectures de PREUVES d'exploitation par le canal RFC.

La famille que `Read Rfc Table` débloque (backlog 2.2, ouverte le
2026-08-29) : `Read Change Documents` (CDHDR/CDPOS, l'assertion d'audit
qu'aucun OSS SAP ne propose), `Get Idoc Status` (EDIDC/EDIDS),
`Read Application Log` (BALHDR, comptes par sévérité) et `Get Job Log`
(chaîne XBP). Logique pure dans ``sapfx_common.rfc_reads``.

Caveat commun, à écrire une fois : ``RFC_READ_TABLE`` n'est pas officiellement
libéré par SAP, sa ligne est bornée à 512 octets, et l'autorisation ``S_RFC``
est souvent restreinte en production ; le repli est toujours l'écran (SE16,
SLG1, WE02, SM37), que ce dépôt sait déjà piloter.

Extrait de ``_rfc.py`` avant d'y entrer (convention #13).
"""
from __future__ import annotations

from typing import Any, Optional

from sapfx_common import idoc_status, rfc_reads
from sapfx_common.robot_args import as_name_list

from ._http import _as_bool
from ._xbp import XbpSessionMixin


class RfcReadKeywords(XbpSessionMixin):
    """Mixin de :class:`SapApiLibrary` : les lectures de preuves du canal RFC."""

    def read_change_documents(self, object_class: str,
                              object_id: Optional[str] = None,
                              alias: str = "default",
                              username: Optional[str] = None,
                              date_from: Optional[str] = None,
                              tcode: Optional[str] = None,
                              include_items: Any = True,
                              rowcount: int = 0) -> list[dict[str, Any]]:
        """Lit les **documents de modification** (CDHDR, postes CDPOS) d'une
        classe d'objet : l'assertion d'audit « la modification a bien été
        journalisée », sans écran. Retourne une liste d'en-têtes JSON-safe
        (``OBJECTCLAS``, ``OBJECTID``, ``CHANGENR``, ``USERNAME``, ``UDATE``,
        ``UTIME``, ``TCODE``, ``CHANGE_IND``), chacun portant ses postes sous
        ``items`` (``TABNAME``, ``FNAME``, ``CHNGIND``, ``VALUE_NEW``,
        ``VALUE_OLD``) quand ``include_items`` est vrai.

        ``object_class`` est la classe de documents (``IDENTITY``,
        ``ADRESSE``, ``MATERIAL``…), ``object_id``/``username``/``tcode``
        restreignent, ``date_from`` (``YYYYMMDD`` ou ``YYYY-MM-DD``) borne
        dans le temps, ``rowcount`` plafonne les EN-TÊTES lus.

        Piège encodé, payé live (A4H, 2026-08-29) : une projection CDPOS
        portant ``VALUE_NEW`` ET ``VALUE_OLD`` (254 caractères chacun) dépasse
        le tampon de 512 octets de ``RFC_READ_TABLE`` et sort en
        ``DATA_BUFFER_EXCEEDED`` (AD/E/559), code qui ne nomme pas la cause.
        Les postes sont donc lus en DEUX projections fusionnées sur la clé
        (``sapfx_common.rfc_reads.merge_change_items``). NB : sur un ECC
        classique pré-S/4, CDPOS vit dans le cluster CDCLS et n'est pas
        lisible par ``RFC_READ_TABLE`` ; sur S/4 (mesuré : release 754) les
        deux tables sont transparentes."""
        options = rfc_reads.build_options([
            ("OBJECTCLAS", str(object_class).strip()),
            ("OBJECTID", object_id), ("USERNAME", username),
            ("TCODE", tcode)])
        if date_from is not None:
            rfc_reads.append_clause(options, "UDATE GE '%s'"
                                    % rfc_reads.normalize_date(date_from, "date_from"))
        headers = self.read_rfc_table(
            "CDHDR", ["OBJECTCLAS", "OBJECTID", "CHANGENR", "USERNAME",
                      "UDATE", "UTIME", "TCODE", "CHANGE_IND"],
            alias=alias, options=options, rowcount=int(rowcount))
        if not _as_bool(include_items) or not headers:
            return rfc_reads.attach_change_items(headers, [])
        item_options = rfc_reads.build_options([
            ("OBJECTCLAS", str(object_class).strip()),
            ("OBJECTID", object_id)])
        key_fields = ["CHANGENR", "TABNAME", "TABKEY", "FNAME", "CHNGIND"]
        new_rows = self.read_rfc_table("CDPOS", key_fields + ["VALUE_NEW"],
                                       alias=alias, options=item_options)
        old_rows = self.read_rfc_table("CDPOS", key_fields + ["VALUE_OLD"],
                                       alias=alias, options=item_options)
        items = rfc_reads.merge_change_items(new_rows, old_rows)
        return rfc_reads.attach_change_items(headers, items)

    def filter_change_documents(self, documents: Any, since: Any = None,
                                tcode: Any = None, change_ind: Any = None,
                                table: Any = None, key_suffix: Any = None,
                                fields: Any = None, indicator: Any = None,
                                all_fields: Any = False) -> list[dict[str, Any]]:
        """Filtre des documents rendus par `Read Change Documents`, HORS
        ligne : le constat d'audit « un document POSTÉRIEUR à ``since``
        journalise tel poste », sans ``Evaluate`` dans la suite.

        En-tête : ``since`` (numéro de document, comparaison numérique),
        ``tcode``, ``change_ind``. Postes : ``table``, ``key_suffix`` (la clé
        CDPOS commence par le mandant, d'où un SUFFIXE), ``fields`` (liste ou
        chaîne à virgules), ``indicator`` (``I``/``U``/``E``/``D``) ;
        ``all_fields=True`` exige que TOUS les ``fields`` soient journalisés
        (le retrait d'une ligne porte ``VALID_FROM`` ET ``VALID_TO`` en
        ``E``). Rend la liste des documents retenus. Aussi
        `Latest Change Number`, le point de départ d'un tel constat. ::

            ${depuis}=    Latest Change Number    ${documents}
            ...    (le geste)
            ${docs}=    Read Change Documents    BUPA_BUP    object_id=${numero}
            ${ajout}=    Filter Change Documents    ${docs}    since=${depuis}
            ...    table=BUT100    key_suffix=${numero}BUP002    fields=KEY    indicator=I
            Length Should Be    ${ajout}    1"""
        return rfc_reads.select_change_documents(
            documents, since=since, tcode=tcode, change_ind=change_ind,
            table=table, key_suffix=key_suffix,
            fields=as_name_list(fields, "fields"), indicator=indicator,
            all_fields=_as_bool(all_fields))

    def latest_change_number(self, documents: Any) -> int:
        """Le plus grand numéro parmi des documents de `Read Change
        Documents`, 0 s'il n'y en a aucun. Hors ligne."""
        return rfc_reads.latest_change_number(documents)

    def get_idoc_status(self, alias: str = "default",
                        docnum: Optional[str] = None,
                        message_type: Optional[str] = None,
                        idoc_type: Optional[str] = None,
                        direction: Optional[str] = None,
                        date_from: Optional[str] = None,
                        include_history: Any = False,
                        rowcount: int = 0) -> dict[str, Any]:
        """Lit le **statut des IDocs** (EDIDC) et le juge par CODE : le test
        d'intégration classique (« l'IDoc est parti / a été intégré »), sans
        écran WE02. Retourne ``{"idocs": [...], "counts": {...}}`` : chaque
        IDoc porte ``DOCNUM``, ``STATUS``, sa ``category`` (``success`` /
        ``error`` / ``in_progress`` / ``unmapped``), ``DIRECT``, ``MESTYP``,
        ``IDOCTP``, partenaires et horodatage ; ``counts`` compte par
        catégorie, toutes présentes même à zéro.

        Le barème est un ensemble EXPLICITE de statuts standard
        (``sapfx_common.rfc_reads.IDOC_STATUS_CATEGORIES``) : un statut hors
        barème est ``unmapped`` et n'est JAMAIS un succès, le même repli sûr
        que l'attente des jobs de fond. On juge le code numérique, jamais le
        texte localisé de TEDS1 (convention n°3).

        ``message_type``/``idoc_type``/``direction`` (``1`` sortant, ``2``
        entrant)/``date_from``/``docnum`` restreignent ; ``include_history``
        accroche à chaque IDoc son historique EDIDS sous ``history`` (une
        clause ``OR`` par numéro trouvé) ; chaque enregistrement porte le
        statut, l'origine, le message par IDENTIFIANT, ses paramètres, le TID
        qui relie un sortant à son entrant et l'utilisateur. NB : les images
        du banc ne portent aucun IDoc à la livraison ; le barème est verrouillé
        hors SAP et éprouvé live depuis la fiche scénario 8 (2026-10-01), qui
        a mesuré 01, 30, 03 sur un sortant et 50, 64, 62, 53, 51, 56 sur un
        entrant."""
        options = rfc_reads.build_options([
            ("DOCNUM", docnum), ("MESTYP", message_type),
            ("IDOCTP", idoc_type), ("DIRECT", direction)])
        if date_from is not None:
            rfc_reads.append_clause(options, "CREDAT GE '%s'"
                                    % rfc_reads.normalize_date(date_from, "date_from"))
        rows = self.read_rfc_table(
            "EDIDC", ["DOCNUM", "STATUS", "DIRECT", "MESTYP", "IDOCTP",
                      "SNDPRN", "RCVPRN", "CREDAT", "CRETIM"],
            alias=alias, options=options, rowcount=int(rowcount))
        idocs: list[dict[str, Any]] = []
        for row in rows:
            idoc: dict[str, Any] = dict(row)
            idoc["category"] = rfc_reads.classify_idoc_status(row.get("STATUS", ""))
            idocs.append(idoc)
        if _as_bool(include_history) and idocs:
            history_options: list[str] = []
            for idoc in idocs:
                clause = "DOCNUM EQ '%s'" % str(idoc["DOCNUM"]).strip()
                history_options.append(
                    clause if not history_options else "OR " + clause)
            history = self.read_rfc_table(
                "EDIDS", list(idoc_status.HISTORY_FIELDS),
                alias=alias, options=history_options)
            by_docnum: dict[str, list[dict[str, str]]] = {}
            for entry in history:
                by_docnum.setdefault(str(entry.get("DOCNUM", "")), []).append(entry)
            for idoc in idocs:
                idoc["history"] = by_docnum.get(str(idoc["DOCNUM"]), [])
        return {"idocs": idocs,
                "counts": rfc_reads.summarize_idoc_statuses(rows)}

    def read_application_log(self, log_object: Optional[str] = None,
                             subobject: Optional[str] = None,
                             external_number: Optional[str] = None,
                             alias: str = "default",
                             user: Optional[str] = None,
                             date_from: Optional[str] = None,
                             with_problems_only: Any = False,
                             rowcount: int = 0) -> dict[str, Any]:
        """Lit les **journaux applicatifs** (BALHDR, transaction SLG1 sans
        écran) : ce qu'écrivent les traitements. Retourne ``{"headers":
        [...], "totals": {...}}`` : chaque en-tête porte l'objet, le
        sous-objet, le numéro externe, l'auteur, l'horodatage, le programme
        et ses COMPTES de messages par sévérité (``total``, ``abort``,
        ``error``, ``warning``, ``info``, ``success``, convertis en entiers
        depuis les NUMC ``"000004"``) ; ``totals`` agrège.

        L'assertion est locale-safe par construction : on juge des COMPTES
        par type de message, jamais des textes (convention n°3). Les textes
        eux-mêmes vivent dans BALDAT sous forme compressée, illisible par
        ``RFC_READ_TABLE`` : ce keyword dit COMBIEN et de quelle sévérité,
        l'écran SLG1 reste la loupe pour lire le détail d'un journal désigné
        par son ``LOGNUMBER``.

        ``with_problems_only`` ne rapporte que les journaux portant au moins
        une erreur ou un abandon ; ``date_from`` borne dans le temps,
        ``rowcount`` plafonne."""
        options = rfc_reads.build_options([
            ("OBJECT", log_object), ("SUBOBJECT", subobject),
            ("EXTNUMBER", external_number), ("ALUSER", user)])
        if date_from is not None:
            rfc_reads.append_clause(options, "ALDATE GE '%s'"
                                    % rfc_reads.normalize_date(date_from, "date_from"))
        if _as_bool(with_problems_only):
            rfc_reads.append_clause(options,
                                    "( MSG_CNT_E GT 0 OR MSG_CNT_A GT 0 )")
        rows = self.read_rfc_table(
            "BALHDR", ["LOGNUMBER", "OBJECT", "SUBOBJECT", "EXTNUMBER",
                       "ALDATE", "ALTIME", "ALUSER", "ALPROG", "MSG_CNT_AL",
                       "MSG_CNT_A", "MSG_CNT_E", "MSG_CNT_W", "MSG_CNT_I",
                       "MSG_CNT_S"],
            alias=alias, options=options, rowcount=int(rowcount))
        headers = [rfc_reads.normalize_log_header(row) for row in rows]
        return {"headers": headers,
                "totals": rfc_reads.summarize_log_headers(headers)}

    def get_job_log(self, jobname: str, jobcount: str,
                    alias: str = "default",
                    external_user: Optional[str] = None) -> list[dict[str, str]]:
        """Lit le **journal d'un job de fond** (le complément de `Wait For
        Background Job`, qui n'a que le statut TBTCO) : lignes JSON-safe
        avec identifiant de message (``MSGID``/``MSGNO``, le critère stable),
        horodatage et texte pour le lecteur.

        Passe par la chaîne **XBP**, l'interface officielle des ordonnanceurs
        externes : ``BAPI_XMI_LOGON`` (interface ``XBP`` 3.0) puis
        ``BAPI_XBP_JOB_JOBLOG_READ`` (table ``JOB_PROTOCOL``), chaque étape
        jugée par TYPE de BAPIRET2, et ``BAPI_XMI_LOGOFF`` TOUJOURS exécuté
        (une session XMI orpheline reste ouverte côté serveur, même hygiène
        que les connexions). Depuis le 2026-10-01 la session XBP est PARTAGÉE
        (``_xbp.py``) : une session déjà ouverte sur la connexion
        (``XM/E/022`` au logon) est réutilisée au lieu de faire échouer la
        lecture, et seule une session ouverte ici est refermée. Pourquoi pas
        ``BP_JOBLOG_READ`` : mesuré live (A4H, 2026-08-29), ce module sort en
        ``CALL_FUNCTION_NOT_REMOTE``, il n'est pas appelable à distance.

        ``external_user`` est le nom d'utilisateur externe annoncé à XBP
        (défaut : l'utilisateur de la connexion RFC). ``jobcount`` désigne le
        RUN exact ; il se lit dans TBTCO (`Read Rfc Table`) ou dans
        `Find Background Job Cases`."""
        external_user = self._xbp_external_user(alias, external_user)
        with self._xbp_session(alias):
            result = self.call_bapi(
                "BAPI_XBP_JOB_JOBLOG_READ", alias=alias,
                JOBNAME=str(jobname), JOBCOUNT=str(jobcount),
                EXTERNAL_USER_NAME=str(external_user))
        return rfc_reads.normalize_job_log_lines(result.get("JOB_PROTOCOL", []))
