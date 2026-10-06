"""Mixin de la CRÉATION et de la manipulation d'IDocs par le canal RFC :
`Create Outbound Idoc`, `Describe Idoc Segment`, `Describe Idoc Type`,
`Set Idoc Status`, `Read Idoc Segments` et `Delete Idoc`.

Avant le scénario 8 (IDoc sortant sur A4H 1909, 2026-10-01), la bibliothèque
savait LIRE le statut d'un IDoc (`Get Idoc Status`) mais ni en créer ni en
expédier un : le test d'intégration asynchrone le plus classique de SAP
n'avait aucun point d'entrée. Ce mixin assemble ce que les modules ``EDI_*``
rendent possible à distance. L'expédition (le passage de 30 à 03) n'en fait
PAS partie : aucun module accessible à distance relevé ne remplace le moniteur
WE14 (rapport ``RSEOUT00``), geste d'écran qui reste dans la couche resources.

Logique pure dans ``sapfx_common.idoc`` et ``sapfx_common.idoc_status``.
Piège commun : les modules ``EDI_DOCUMENT_*`` sont ÉTATFULS (un document
ouvert vit dans le contexte de la connexion), donc toute la séquence part sur
UNE connexion, et un échec entre l'ouverture et la clôture remet le contexte
à zéro (sinon le document resterait verrouillé).

Typed.
"""
from __future__ import annotations

from typing import Any, Optional

from sapfx_common import idoc, idoc_profiles, idoc_status

from ._http import _as_bool
from ._rfc_idoc_profiles import RfcIdocProfileKeywords, abap_key


class RfcIdocKeywords(RfcIdocProfileKeywords):
    """Mixin de :class:`SapApiLibrary` : créer, décrire, lire, supprimer un IDoc."""

    def create_outbound_idoc(self, message_type: str, idoc_type: str,
                             receiver_port: str, receiver_partner: str,
                             segments: Any, receiver_partner_type: str = "LS",
                             sender_partner: Optional[str] = None,
                             sender_port: Optional[str] = None,
                             ready_for_dispatch: Any = True,
                             alias: str = "default") -> dict[str, Any]:
        """Crée un IDoc SORTANT et rend ``{"docnum", "status", "message_type",
        "idoc_type", "segment_count", "created_date", "created_time"}``.

        ``segments`` : liste imbriquée ``[{"segment": "E1SCU_CHG", "fields":
        {"CUSTOMERNUMBER": "00004691"}, "children": [...]}]`` (ou ``"data"``
        pour une donnée brute) ; liste, JSON ou littéral Python. Le découpage
        de chaque segment est LU dans le dictionnaire, et l'arbre est
        confronté à la syntaxe du type AVANT toute écriture : segment
        étranger, mauvais parent, trop d'occurrences, segment obligatoire
        absent, champ inconnu ou valeur trop longue échouent en nommant la
        cause.

        ``docnum`` est le numéro que rend la CLÔTURE, jamais l'identifiant
        provisoire de l'ouverture (mesuré : ils diffèrent, 0004 contre 0007).
        Avec ``ready_for_dispatch`` (défaut), l'IDoc est posé au statut 30
        (prêt à l'expédition) après avoir vérifié qu'un profil sortant existe
        pour (destinataire, type de message) : sans profil, le refus tombe
        AVANT l'écriture plutôt qu'un statut d'erreur découvert plus tard.
        L'expédition (30 vers 03) reste le geste du moniteur WE14.

        ``sender_partner`` par défaut : le système logique du mandant ;
        ``sender_port`` : ``SAP`` + identifiant système. ``REFINT`` et
        ``ARCKEY`` n'existent pas ici (le module les refuse) : un marqueur
        d'exécution se met dans la donnée d'un segment.

        Exemple :
        | &{fields}=    Create Dictionary    TLINE=Hello from an example
        | &{segment}=    Create Dictionary    segment=E1TXTRW    fields=${fields}
        | @{segments}=    Create List    ${segment}
        | ${idoc}=    `Create Outbound Idoc`    TXTRAW    TXTRAW01    A000000001    A4HCLNT001
        | ...    ${segments}    receiver_partner_type=LS    alias=a4h
        | Log    ${idoc}[docnum]
        """
        specs = idoc.parse_segments(segments)
        attributes = self.get_rfc_connection_attributes(alias)
        client = attributes.get("client", "")
        syntax = self._idoc_syntax(idoc_type, alias)
        layouts = {name: self._segment_layout(name, alias)
                   for name in idoc.collect_segment_names(specs)}
        rows = idoc.flatten_segments(specs, layouts, syntax)
        if sender_partner is None:
            sender_partner = idoc.resolve_logical_system(
                self.read_rfc_table("T000", ["MANDT", "LOGSYS"], alias=alias), client)
        if sender_port is None:
            sender_port = idoc.default_sender_port(attributes.get("sysId", ""))
        dispatch = _as_bool(ready_for_dispatch)
        profile = self._outbound_profile_for(
            client, receiver_partner, receiver_partner_type, message_type,
            alias, required=dispatch)
        control = idoc.control_record(
            client, message_type, idoc_type, receiver_port, receiver_partner,
            sender_partner, sender_port, receiver_partner_type,
            output_mode=str((profile or {}).get("OUTMOD") or "2"))
        closed = self._write_idoc(control, rows, alias)
        created = closed["IDOC_CONTROL"]
        docnum = idoc.normalize_docnum(created["DOCNUM"])
        self.commit_bapi_transaction(alias)
        if int(closed.get("SYNTAX_RETURN") or 0) != 0:
            raise AssertionError(
                "L'IDoc %s a été créé mais le contrôle de syntaxe de la "
                "clôture a échoué (SYNTAX_RETURN=%s) : il est resté au statut "
                "d'erreur. Le retirer par Delete Idoc."
                % (docnum, closed.get("SYNTAX_RETURN")))
        status = "01"
        if dispatch:
            try:
                status = self.set_idoc_status(docnum, "30", alias=alias)["status"]
            except Exception as err:
                raise AssertionError(
                    "L'IDoc %s a été créé (statut 01) mais la pose du statut 30 "
                    "a échoué : %s. Le reprendre par Set Idoc Status ou le "
                    "retirer par Delete Idoc." % (docnum, err)) from err
        return {"docnum": docnum, "status": status,
                "message_type": control["MESTYP"], "idoc_type": control["IDOCTP"],
                "segment_count": len(rows),
                "created_date": str(created.get("CREDAT", "")).strip(),
                "created_time": str(created.get("CRETIM", "")).strip()}

    def describe_idoc_segment(self, segment: str,
                              alias: str = "default") -> dict[str, Any]:
        """Le découpage d'un segment lu dans le dictionnaire :
        ``{"segment", "length", "fields": [{"name", "offset", "length",
        "type"}]}``, offsets en caractères. C'est la source de vérité de
        `Create Outbound Idoc` : un découpage recopié de mémoire écrit la
        valeur dans le champ voisin sans la moindre erreur.

        Exemple :
        | ${segment}=    `Describe Idoc Segment`    E1TXTRW    alias=a4h
        | Should Be Equal As Integers    ${segment}[length]    72
        """
        name = str(segment).strip().upper()
        layout = self._segment_layout(name, alias)
        return {"segment": name, "length": idoc.layout_length(layout), "fields": layout}

    def describe_idoc_type(self, idoc_type: str,
                           alias: str = "default") -> list[dict[str, Any]]:
        """L'arbre de segments d'un type d'IDoc (``EDI_IDOC_SYNTAX_GET``) :
        ``[{"segment", "parent", "min", "max", "mandatory", "level"}]``.

        Exemple :
        | ${syntax}=    `Describe Idoc Type`    TXTRAW01    alias=a4h
        | Should Be Equal    ${syntax}[0][segment]    E1TXTRW
        """
        return self._idoc_syntax(idoc_type, alias)

    def set_idoc_status(self, docnum: Any, status: Any, alias: str = "default",
                        repid: str = "SAPFX") -> dict[str, Any]:
        """Pose un statut sur un IDoc (``EDI_DOCUMENT_OPEN_FOR_PROCESS``,
        ``EDI_DOCUMENT_STATUS_SET``, ``EDI_DOCUMENT_CLOSE_PROCESS``, commit) et
        rend ``{"docnum", "status_before", "status"}``. La date et l'heure de
        l'enregistrement sont celles du SERVEUR (lues sur le contrôle de
        l'IDoc), jamais celles du poste.

        REFUSE tout statut de catégorie succès (03, 12, 16, 41, 53) : un test
        qui poserait lui-même son succès ne prouverait rien. Les statuts qui
        se posent sont ceux du pipeline, en pratique 30 (prêt à
        l'expédition).

        Exemple :
        | ${result}=    `Set Idoc Status`    ${idoc}[docnum]    02    alias=a4h
        """
        code = idoc_status.refuse_success_status(status)
        number = idoc.normalize_docnum(docnum)
        opened = False
        try:
            try:
                control = self.call_rfc("EDI_DOCUMENT_OPEN_FOR_PROCESS", alias=alias,
                                        DOCUMENT_NUMBER=number)["IDOC_CONTROL"]
            except Exception as err:
                raise AssertionError(_open_failure(number, abap_key(err))) from err
            opened = True
            before = str(control.get("STATUS", "")).strip()
            record = {"DOCNUM": number, "STATUS": code, "REPID": str(repid)[:30],
                      "LOGDAT": control.get("UPDDAT") or control.get("CREDAT", ""),
                      "LOGTIM": control.get("UPDTIM") or control.get("CRETIM", "")}
            self.call_rfc("EDI_DOCUMENT_STATUS_SET", alias=alias,
                          DOCUMENT_NUMBER=number, IDOC_STATUS=record)
            self.call_rfc("EDI_DOCUMENT_CLOSE_PROCESS", alias=alias,
                          DOCUMENT_NUMBER=number)
            opened = False
        except BaseException:
            if opened:
                self._reset_rfc_context(alias)
            raise
        self.commit_bapi_transaction(alias)
        return {"docnum": number, "status_before": before, "status": code}

    def read_idoc_segments(self, docnum: Any, alias: str = "default",
                           decode: Any = False) -> list[dict[str, Any]]:
        """Lit les segments d'un IDoc (``EDI_DOCUMENT_OPEN_FOR_READ``,
        ``EDI_SEGMENTS_GET_ALL``, ``EDI_DOCUMENT_CLOSE_READ``, toujours
        refermé, même sur échec) : ``[{"segment", "segnum", "parent", "level",
        "data"}]``, ``data`` sans les blancs de fin. Avec ``decode``, chaque
        segment porte en plus ``fields`` (champ par champ, découpage du
        dictionnaire). ``EDID4`` n'est pas lisible par ``Read Rfc Table`` (un
        champ de 1000 caractères), d'où ce chemin.

        Exemple :
        | ${segments}=    `Read Idoc Segments`    6    alias=a4h    decode=True
        | Should Be Equal    ${segments}[0][segment]    E1SCU_CHG
        """
        number = idoc.normalize_docnum(docnum)
        try:
            self.call_rfc("EDI_DOCUMENT_OPEN_FOR_READ", alias=alias,
                          DOCUMENT_NUMBER=number)
        except Exception as err:
            raise AssertionError(_open_failure(number, abap_key(err))) from err
        try:
            try:
                containers = self.call_rfc("EDI_SEGMENTS_GET_ALL", alias=alias,
                                           DOCUMENT_NUMBER=number)["IDOC_CONTAINERS"]
            except Exception as err:
                if abap_key(err) != "END_OF_DOCUMENT":
                    raise
                containers = []
        finally:
            try:
                self.call_rfc("EDI_DOCUMENT_CLOSE_READ", alias=alias,
                              DOCUMENT_NUMBER=number)
            except Exception:
                self._reset_rfc_context(alias)
        segments: list[dict[str, Any]] = []
        layouts: dict[str, Any] = {}
        for row in containers:
            name = str(row.get("SEGNAM", "")).strip()
            entry: dict[str, Any] = {
                "segment": name, "segnum": str(row.get("SEGNUM", "")).strip(),
                "parent": str(row.get("PSGNUM", "")).strip(),
                "level": str(row.get("HLEVEL", "")).strip(),
                "data": str(row.get("SDATA", "")).rstrip()}
            if _as_bool(decode):
                if name not in layouts:
                    layouts[name] = self._segment_layout(name, alias)
                entry["fields"] = idoc.decode_sdata(layouts[name], row.get("SDATA", ""))
            segments.append(entry)
        return segments

    def delete_idoc(self, docnum: Any, allowed_message_types: Any,
                    alias: str = "default") -> dict[str, Any]:
        """Supprime un IDoc (``EDI_DOCUMENT_DELETE`` puis commit) et rend
        ``{"docnum", "deleted", ...}``. ``allowed_message_types`` est
        OBLIGATOIRE (liste blanche, une liste vide refuse tout) : un IDoc d'un
        autre type de message est refusé en nommant les deux. Idempotent : un
        IDoc déjà absent rend ``{"deleted": False}``. Mesuré sur A4H :
        les statuts 03, 51, 56 et 62 se suppriment sans exception.

        Exemple :
        | ${deletion}=    `Delete Idoc`    ${idoc}[docnum]    allowed_message_types=TXTRAW    alias=a4h
        """
        number = idoc.normalize_docnum(docnum)
        rows = self.read_rfc_table(
            "EDIDC", ["DOCNUM", "STATUS", "DIRECT", "MESTYP"], alias=alias,
            options=["DOCNUM EQ '%s'" % number])
        if not rows:
            return {"docnum": number, "deleted": False, "reason": "absent"}
        message_type = idoc_profiles.require_in_list(rows[0].get("MESTYP", ""),
                                                       allowed_message_types)
        try:
            self.call_rfc("EDI_DOCUMENT_DELETE", alias=alias, DOCUMENT_NUMBER=number)
        except Exception as err:
            raise AssertionError(
                "L'IDoc %s (statut %s) n'a pas pu être supprimé : %s."
                % (number, rows[0].get("STATUS", "?"),
                   abap_key(err) or str(err))) from err
        self.commit_bapi_transaction(alias)
        return {"docnum": number, "deleted": True, "message_type": message_type,
                "status_before": str(rows[0].get("STATUS", "")).strip(),
                "direction": str(rows[0].get("DIRECT", "")).strip()}

    # --- internes ---------------------------------------------------------

    def _idoc_syntax(self, idoc_type: str, alias: str) -> list[dict[str, Any]]:
        try:
            result = self.call_rfc("EDI_IDOC_SYNTAX_GET", alias=alias,
                                   PI_IDOCTYP=str(idoc_type).strip().upper())
        except Exception as err:
            if abap_key(err) == "SYNTAX_NOT_FOUND":
                raise AssertionError(
                    "Le type d'IDoc %s n'existe pas sur la cible (WE30)." % idoc_type) from err
            raise
        return idoc.syntax_tree(result["PT_SYNTAX_TABLE"])

    def _segment_layout(self, segment: str, alias: str) -> list[dict[str, Any]]:
        try:
            result = self.call_rfc("DDIF_FIELDINFO_GET", alias=alias, TABNAME=segment)
        except Exception as err:
            if abap_key(err) == "NOT_FOUND":
                raise AssertionError(
                    "Le segment %s n'existe pas dans le dictionnaire de la "
                    "cible (WE31)." % segment) from err
            raise
        return idoc.segment_layout(result["DFIES_TAB"])

    def _outbound_profile_for(self, client: str, partner: str, partner_type: str,
                              message_type: str, alias: str,
                              required: bool) -> Optional[dict[str, Any]]:
        """Le profil sortant de (partenaire, type de message), ou ``None``. Si
        ``required``, son absence est un refus AVANT toute écriture."""
        key = idoc_profiles.outbound_key(client, partner, partner_type, message_type)
        profile = self._read_profile("EDI_AGREE_OUT_MESSTYPE_READ", "REC_EDK13",
                                     "REC_EDD13", key, alias)
        if profile is None and required:
            raise AssertionError(
                "Aucun profil sortant pour %s/%s et le type de message %s : "
                "l'IDoc ne pourrait pas être expédié. Le provisionner par "
                "Ensure Idoc Outbound Profile, ou créer l'IDoc avec "
                "ready_for_dispatch=${False}."
                % (str(partner).strip(), str(partner_type).strip(),
                   str(message_type).strip()))
        return profile

    def _write_idoc(self, control: dict[str, str], rows: list[dict[str, str]],
                    alias: str) -> dict[str, Any]:
        """Ouvre, remplit et clôt le document sur UNE connexion. Un échec
        après l'ouverture remet le contexte à zéro : rien n'est écrit tant que
        la clôture n'a pas eu lieu."""
        opened = False
        try:
            identifier = self.call_rfc("EDI_DOCUMENT_OPEN_FOR_CREATE", alias=alias,
                                       IDOC_CONTROL=control)["IDENTIFIER"]
            opened = True
            for row in rows:
                try:
                    self.call_rfc("EDI_SEGMENT_ADD_NEXT", alias=alias,
                                  IDENTIFIER=identifier,
                                  IDOC_CONTAINER=dict(row, DOCNUM=identifier))
                except Exception as err:
                    raise AssertionError(
                        "Le segment %s (n° %s) est refusé par EDI_SEGMENT_ADD_NEXT "
                        "(%s) ; rien n'est écrit." % (
                            row["SEGNAM"], row["SEGNUM"], abap_key(err) or err)) from err
            closed = self.call_rfc("EDI_DOCUMENT_CLOSE_CREATE", alias=alias,
                                   IDENTIFIER=identifier)
            opened = False
            return dict(closed)
        except BaseException:
            if opened:
                self._reset_rfc_context(alias)
            raise

    def _reset_rfc_context(self, alias: str) -> None:
        """Remet à zéro le contexte de la connexion (un document ouvert reste
        sinon verrouillé) ; sans effet si la connexion est déjà partie."""
        connection = self._rfc_connections().get(alias)
        reset = getattr(connection, "reset_server_context", None)
        if reset is not None:
            try:
                reset()
            except Exception:
                pass


def _open_failure(docnum: str, key: str) -> str:
    causes = {
        "DOCUMENT_NOT_EXIST": "l'IDoc n'existe pas",
        "DOCUMENT_FOREIGN_LOCK": "l'IDoc est verrouillé par un autre utilisateur",
        "DOCUMENT_IS_ALREADY_OPEN": "l'IDoc est déjà ouvert sur cette connexion",
        "DOCUMENT_NUMBER_INVALID": "le numéro est invalide"}
    return "L'IDoc %s ne s'ouvre pas : %s (%s)." % (
        docnum, causes.get(key, "cause non documentée"), key or "erreur inconnue")
