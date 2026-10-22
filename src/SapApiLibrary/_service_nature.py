"""Mixin de la *nature d'un service OData* : RAP natif, Gateway ABAP, CAP.

Né de la fiche scénario 15 (2026-10-13, ABAP Platform 2023, release 758). Le
nom d'un service ne dit pas qui l'a construit : ce mixin lit son
``$metadata`` (canal HTTP) et, en OData v2 où aucun marqueur du document ne
prouve un binding RAP, le registre des bindings de service (canal RFC,
``SRVB_BIND_TYPE`` et ``SRVB_SERVICES``, lecture seule). La règle de
classement vit dans ``sapfx_common.odata_service_nature`` ; ce module n'en
fait que les E/S.

Un service dont le ``$metadata`` ne se lit pas (statut d'erreur, page de
connexion) ÉCHOUE en nommant le statut : il ne reçoit jamais de nature (sur
la cible, 27 des 58 services du catalogue v2 répondent 404 ou 500).

Ajouté à côté de ``_discovery.py`` plutôt que dedans (convention #13 : une
capacité nouvelle va dans son propre module).
"""
from __future__ import annotations

from typing import Any, Literal

from sapfx_common import odata_error
from sapfx_common.argument_types import ODataServicePathInput
from sapfx_common import odata_service_nature as nature_logic
from sapfx_common.rfc_tables import abap_quote

from ._tls_posture import TlsPostureKeywords

_ERROR_STATUSES = tuple(range(400, 600))


class ServiceNatureKeywords(TlsPostureKeywords):
    """Mixin de :class:`SapApiLibrary` : nature d'un service OData."""

    def get_odata_service_nature(self, service_path: ODataServicePathInput, alias: str = "default",
                                 binding: Any = None) -> dict[str, Any]:
        """Lit le ``$metadata`` du service (en XML) et rend sa nature, prouvée
        par des marqueurs lus et jamais par son nom : ``{nature, odata_version,
        schema_namespace, repository, draft_flavour, evidence,
        ambiguous_markers, missing_proof, conflicts, candidates,
        service_path}``.

        ``nature`` vaut ``rap_draft`` (binding RAP avec brouillon), ``rap``
        (binding RAP sans brouillon), ``abap_bopf_draft`` (service Gateway à
        brouillon BOPF, SEGW), ``abap_gateway`` (service Gateway ABAP sans RAP
        ni brouillon), ``cap`` ou ``unknown``. En OData v4, l'espace de noms
        du schéma porte le dépôt (``srvd`` = binding RAP, ``default`` =
        service codé) ; la saveur du brouillon se lit dans ``DraftRoot``. En
        OData v2, passer ``binding=`` (le dict de `Get Service Binding`) : sans
        lui, le service reste ``unknown`` avec ses ``candidates`` (seul un
        brouillon BOPF, de signature propre, s'en passe).
        ``IsActiveEntity`` ou ``DraftRoot`` seuls ne prouvent rien, ils sont
        rendus dans ``ambiguous_markers``.

        Un ``$metadata`` illisible (statut d'erreur, document qui n'en est pas
        un) fait échouer en nommant le statut et le code d'erreur OData.

        Exemple :
        | ${nature}=    `Get Odata Service Nature`
        | ...    /sap/opu/odata4/dmo/ui_supplement_04/srvd/dmo/ui_supplement/0001    alias=rap15
        | Should Be Equal    ${nature}[nature]    rap_draft
        | ${binding}=    `Get Service Binding`    /DMO/UI_TRAVEL_D_D_O2    alias=rap15rfc
        | ${v2}=    `Get Odata Service Nature`    /sap/opu/odata/dmo/UI_TRAVEL_D_D_O2
        | ...    alias=rap15    binding=${binding}
        | Should Be Equal    ${v2}[nature]    rap_draft
        """
        key = service_path.rstrip("/")
        status, headers, body = self._request(
            alias, "GET", key + "/$metadata", None,
            headers={"Accept": "application/xml"},
            allowed_errors=_ERROR_STATUSES)
        text = body.decode("utf-8-sig", errors="replace")
        if status >= 400:
            try:
                error = odata_error.parse_odata_error({"status": status, "body": text})
                detail = "%s %s" % (error.get("code", ""), error.get("message", ""))
            except AssertionError:
                detail = text[:160]
            raise AssertionError(
                "Le $metadata de '%s' ne se lit pas (statut %d : %s) : aucune "
                "nature n'est rendue pour un service illisible."
                % (service_path, status, detail.strip()))
        try:
            verdict = nature_logic.classify_service_nature(
                text, headers=headers, binding=binding)
        except ValueError as err:
            raise AssertionError("%s (service '%s', statut %d)."
                                 % (err, service_path, status)) from None
        verdict["service_path"] = key
        return verdict

    def odata_service_nature_should_be(self, service_path: ODataServicePathInput,
                                       expected: Literal["rap_draft", "rap", "abap_bopf_draft",
                                                         "abap_gateway", "cap", "unknown"],
                                       alias: str = "default",
                                       binding: Any = None) -> dict[str, Any]:
        """Échoue si la nature lue par `Get Odata Service Nature` n'est pas
        ``expected``, en nommant les marqueurs, ce qui manque et ce qui se
        contredit. Rend le verdict lu.

        Exemple :
        | `Odata Service Nature Should Be`    /sap/opu/odata/sap/SEPMRA_PROD_MAN
        | ...    abap_bopf_draft    alias=rap15
        """
        if expected not in nature_logic.NATURES:
            raise ValueError("Nature attendue inconnue %r : valeurs admises %s."
                             % (expected, ", ".join(nature_logic.NATURES)))
        verdict = self.get_odata_service_nature(service_path, alias=alias,
                                                binding=binding)
        if verdict["nature"] != expected:
            raise AssertionError(
                "Service '%s' : nature %s attendue, %s lue. Marqueurs : %s ; "
                "preuve manquante : %s ; contradictions : %s ; candidats : %s."
                % (service_path, expected, verdict["nature"],
                   "; ".join(verdict["evidence"]) or "aucun",
                   "; ".join(verdict["missing_proof"]) or "aucune",
                   "; ".join(verdict["conflicts"]) or "aucune",
                   ", ".join(verdict["candidates"]) or "aucun"))
        return verdict

    def get_service_binding(self, binding: str, alias: str = "default"
                            ) -> dict[str, Any]:
        """Lit au registre des bindings de service, par RFC et en lecture
        seule (``SRVB_BIND_TYPE`` et ``SRVB_SERVICES``, version active), le
        binding ``binding`` : un nom (``/DMO/UI_TRAVEL_D_D_O2``) ou une adresse
        OData dont il se déduit (forme mesurée sur ``/DMO/``). Rend ``{found,
        binding, bind_type, odata_version, category, services}``, ``category``
        valant ``ui`` ou ``web_api`` ; un binding absent du registre rend
        ``found`` faux, sans échouer.

        Exemple :
        | ${binding}=    `Get Service Binding`    /DMO/UI_TRAVEL_D_D_O2    alias=rap15rfc
        | Should Be True    ${binding}[found]
        | Should Be Equal    ${binding}[odata_version]    V2
        """
        name = binding.strip()
        if "/opu/" in name.lower():
            name = nature_logic.binding_name_from_path(name)
        name = name.upper()
        clauses = ["SRVB_NAME = %s" % abap_quote(name), "AND VERSION = 'A'"]
        rows = self.read_rfc_table(
            "SRVB_BIND_TYPE",
            "SRVB_NAME,BIND_TYPE,BIND_TYPE_VERSION,BIND_TYPE_CATEGORY",
            alias=alias, options=clauses)
        services: list[dict[str, str]] = []
        if rows:
            services = self.read_rfc_table(
                "SRVB_SERVICES", "SRVB_NAME,SERVICE_NAME,SERVICE_VERSION,SRVDNAME",
                alias=alias, options=clauses)
        return nature_logic.describe_binding(rows, services, name)

    def get_service_binding_name(self, service_path: str) -> str:
        """Nom du binding de service déduit d'une adresse OData SAP, sans
        aucun appel : v4 ``/sap/opu/odata4/<ns>/<binding>/srvd/...``, v2
        ``/sap/opu/odata/<ns>/<binding>`` (``sap`` = sans préfixe). Forme
        mesurée sur les bindings ``/DMO/`` seulement ; une autre forme
        d'adresse fait échouer.

        Exemple :
        | ${name}=    `Get Service Binding Name`
        | ...    /sap/opu/odata4/dmo/ui_supplement_04/srvd/dmo/ui_supplement/0001
        | Should Be Equal    ${name}    /DMO/UI_SUPPLEMENT_04
        """
        try:
            return nature_logic.binding_name_from_path(service_path)
        except ValueError as err:
            raise AssertionError(str(err)) from None
