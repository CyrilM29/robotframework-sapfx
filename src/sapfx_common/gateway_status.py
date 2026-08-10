"""Préflight du canal API : classification d'une sonde de la Gateway OData.

Le pendant API des préflights GUI (``Get Scripting Status``, ``Get List
Rendering Status``) : une requête sur le catalogue de services suffit à
diagnostiquer l'état de la Gateway, et chaque état porte sa remédiation
NOMMÉE. Le cas fondateur, vécu sur A4H (2026-08) : conteneur re-créé ->
Gateway désactivée -> tout appel OData répond HTTP 500 avec le message
``/IWFND/CM_COS/003`` ; la réparation est l'activité IMG
``/IWFND/IWF_ACTIVATE`` (procédure : docs/ecc-validation.md §11.7).

Logique pure : les E/S HTTP restent dans ``SapApiLibrary``.
"""
from __future__ import annotations

from typing import Any, Optional

#: Chemin standard du catalogue de services de la Gateway embarquée.
CATALOG_SERVICE_PATH = "/sap/opu/odata/iwfnd/catalogservice;v=2/ServiceCollection"

#: Marqueur du « Gateway non activée » dans le corps d'un HTTP 500.
GATEWAY_INACTIVE_MARKER = "/IWFND/CM_COS/003"

_ACTIVATION_REMEDIATION = (
    "Activer la Gateway : activité IMG /IWFND/IWF_ACTIVATE (SPRO, bouton "
    "« Activate » ; réglage inter-mandants), puis re-sonder. Procédure "
    "complète : docs/ecc-validation.md §11.7.")


def classify_gateway_probe(http_status: Optional[int], body: str = "",
                           error: Optional[str] = None) -> dict[str, Any]:
    """Classe le résultat d'une sonde HTTP du catalogue Gateway en dict
    JSON-safe ``{"status", "http_status", "detail", "remediation"}``.

    ``http_status=None`` + ``error`` = échec de connexion (système éteint,
    port fermé). ``body`` est l'extrait de la réponse, utilisé pour
    reconnaître le marqueur ``/IWFND/CM_COS/003`` d'une Gateway désactivée.
    """
    if http_status is None:
        return {
            "status": "unreachable",
            "http_status": None,
            "detail": "Connexion impossible : %s" % (error or "raison inconnue"),
            "remediation": ("Système démarré ? (A4H : docker start, attendre la "
                            "fin du boot ABAP) ; vérifier base_url, port et "
                            "verify_tls."),
        }
    if 200 <= http_status < 300:
        return {"status": "ok", "http_status": http_status,
                "detail": "Catalogue Gateway joignable.", "remediation": None}
    if http_status == 401:
        return {
            "status": "auth_failed",
            "http_status": http_status,
            "detail": "Authentification refusée (HTTP 401).",
            "remediation": ("Vérifier user/password/sap_client de "
                            "Open Api Session (mandant licencié ? sur A4H sans "
                            "licence, seul SAP*/000 passe)."),
        }
    if http_status == 403:
        return {
            "status": "forbidden",
            "http_status": http_status,
            "detail": "Accès interdit (HTTP 403) : service ICF ou autorisation.",
            "remediation": ("Service ICF du catalogue actif ? Autorisation "
                            "S_SERVICE de l'utilisateur ? (SICF, SU53 après "
                            "l'appel)."),
        }
    if http_status == 404:
        return {
            "status": "catalog_not_found",
            "http_status": http_status,
            "detail": "Catalogue introuvable (HTTP 404).",
            "remediation": ("Vérifier le chemin du catalogue (composant Gateway "
                            "présent sur ce système ?) : %s" % CATALOG_SERVICE_PATH),
        }
    if http_status >= 500 and GATEWAY_INACTIVE_MARKER in (body or ""):
        return {
            "status": "gateway_inactive",
            "http_status": http_status,
            "detail": ("La Gateway OData n'est pas activée sur ce système "
                       "(message %s)." % GATEWAY_INACTIVE_MARKER),
            "remediation": _ACTIVATION_REMEDIATION,
        }
    if http_status >= 500:
        return {
            "status": "server_error",
            "http_status": http_status,
            "detail": "Erreur serveur (HTTP %d) : %s" % (http_status, (body or "")[:200]),
            "remediation": ("Lire le début de la réponse ci-dessus ; si le "
                            "message cite /IWFND/, vérifier l'activation de la "
                            "Gateway et des services (/IWFND/MAINT_SERVICE)."),
        }
    return {
        "status": "unexpected",
        "http_status": http_status,
        "detail": "Réponse inattendue (HTTP %d) : %s" % (http_status, (body or "")[:200]),
        "remediation": None,
    }


def format_gateway_failure(classification: dict[str, Any]) -> str:
    """Message d'échec auto-corrigible d'un préflight Gateway : l'état, le
    détail, puis la remédiation nommée (politique maison des erreurs)."""
    parts = ["Gateway OData non opérationnelle (état : %s). %s"
             % (classification.get("status"), classification.get("detail"))]
    remediation = classification.get("remediation")
    if remediation:
        parts.append(remediation)
    return "\n".join(parts)
