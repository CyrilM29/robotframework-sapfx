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

#: Marqueur de l'``URLError`` levée par le garde de redirection same-origin
#: (``_SameOriginRedirectHandler``) : une redirection vers un AUTRE hôte est
#: refusée pour ne jamais transporter l'authentification ailleurs. Sans ce
#: marqueur, la sonde arrive ici en ``http_status=None`` et se ferait classer
#: « système éteint », c'est-à-dire l'inverse de la vérité.
CROSS_ORIGIN_REDIRECT_MARKER = "Cross-origin API redirect blocked"

_ACTIVATION_REMEDIATION = (
    "Activer la Gateway : activité IMG /IWFND/IWF_ACTIVATE (SPRO, bouton "
    "« Activate » ; réglage inter-mandants), puis re-sonder. Procédure "
    "complète : docs/ecc-validation.md §11.7.")

_IDP_REMEDIATION = (
    "Ce canal est protégé par un fournisseur d'identité (SAP IAS, XSUAA sur "
    "BTP), pas par une authentification directe : un client HTTP ne franchit "
    "pas un déroulé interactif. Ouvrir la session en OAuth2 client "
    "credentials (token_url / client_id / client_secret d'une clé de service "
    "d'instance du sous-compte), et prévoir le périmètre (scope) associé, "
    "sans quoi le token est obtenu mais refusé par la route visée.")


def looks_like_html(body: str) -> bool:
    """Vrai quand le corps est une page HTML plutôt que des données.

    Le critère est STRUCTUREL et porte sur le DÉBUT du document : un
    catalogue OData répond du JSON (``{``) ou du XML (``<?xml`` puis
    ``<edmx:Edmx``), jamais un document ouvert par ``<!doctype``/``<html``.
    Chercher un mot comme « login » dépendrait de la langue du serveur
    (convention #3), et chercher ``<html`` n'importe où dans le corps
    prendrait pour du HTML un JSON qui CITE la balise dans un message.
    """
    head = (body or "").lstrip("﻿ \t\r\n").lower()
    return head.startswith("<!doctype") or head.startswith("<html")


def looks_like_json(body: str) -> bool:
    """Vrai quand le corps est un document JSON (objet ou tableau).

    Même critère STRUCTUREL et même portée que :func:`looks_like_html` : on
    regarde le DÉBUT du document, jamais un mot du contenu (convention #3).
    Distinguer un corps JSON d'un corps HTML est ce qui sépare « l'application
    a traité la requête et explique ce qui lui manque » de « une page de
    connexion a été servie à la place des données ».
    """
    head = (body or "").lstrip("﻿ \t\r\n")
    return head.startswith("{") or head.startswith("[")


#: En-tête posé par le routeur de plateforme Cloud Foundry quand AUCUNE
#: application n'est routée derrière le préfixe demandé. C'est le discriminant
#: STRUCTUREL des trois familles de 404 d'un site BTP (relevé live
#: 2026-08-26) : le corps porte le même sens en toutes lettres, mais un texte
#: ne s'asserte pas.
ROUTER_ERROR_HEADER = "x-cf-routererror"


def classify_http_response(http_status: Optional[int],
                           headers: Any = None,
                           body: str = "") -> str:
    """Range une réponse HTTP dans une famille de RECONNAISSANCE, par des
    critères purement structurels. Retourne l'une des chaînes :

    - ``unreachable`` : aucune réponse (``http_status`` vaut ``None``) ;
    - ``unknown_route`` : 404 portant l'en-tête du routeur de plateforme, donc
      le préfixe n'est routé vers AUCUNE application ;
    - ``missing_route`` : 404 SANS cet en-tête, donc une application a bien
      répondu et c'est cette route-là qui n'existe pas ;
    - ``forbidden`` : 403, la route existe et l'autorisation refuse ;
    - ``dialog`` : 4xx dont le corps est du JSON, l'application traite la
      requête et explique ce qui lui manque ;
    - ``login_page`` : 2xx dont le corps est du HTML, la réponse n'est PAS une
      donnée (le « vert et faux » des cibles derrière un fournisseur
      d'identité) ;
    - ``data`` : 2xx qui n'est pas du HTML ;
    - ``other`` : tout le reste (5xx, 3xx…).

    Les trois familles de 404 sont la leçon centrale d'une cible Cloud
    Foundry : sous un même statut, le corps désigne trois COUCHES distinctes.
    C'est pourquoi toute sonde s'accompagne d'un chemin volontairement absent
    sur le même hôte : sans ce témoin, on ne sait pas si un 404 qualifie la
    ressource ou l'hôte entier. ``headers`` accepte tout mapping ou itérable
    de noms (la casse est ignorée).
    """
    if http_status is None:
        return "unreachable"
    status = int(http_status)
    names = {str(name).lower() for name in (headers or ())}
    if status == 404:
        return "unknown_route" if ROUTER_ERROR_HEADER in names else "missing_route"
    if status == 403:
        return "forbidden"
    if 400 <= status < 500 and looks_like_json(body):
        return "dialog"
    if 200 <= status < 300:
        return "login_page" if looks_like_html(body) else "data"
    return "other"


def classify_gateway_probe(http_status: Optional[int], body: str = "",
                           error: Optional[str] = None) -> dict[str, Any]:
    """Classe le résultat d'une sonde HTTP du catalogue Gateway en dict
    JSON-safe ``{"status", "http_status", "detail", "remediation"}``.

    ``http_status=None`` + ``error`` = échec de connexion (système éteint,
    port fermé), SAUF si l'erreur porte ``CROSS_ORIGIN_REDIRECT_MARKER``, qui
    dénonce une redirection vers un fournisseur d'identité. ``body`` est
    l'extrait de la réponse, utilisé pour reconnaître le marqueur
    ``/IWFND/CM_COS/003`` d'une Gateway désactivée, et pour distinguer des
    DONNÉES d'une page HTML de connexion servie en HTTP 200.
    """
    if http_status is None:
        if CROSS_ORIGIN_REDIRECT_MARKER in (error or ""):
            return {
                "status": "identity_provider_redirect",
                "http_status": None,
                "detail": ("La sonde a été redirigée hors de l'hôte de base et "
                           "la redirection a été refusée pour ne pas y "
                           "transporter l'authentification : %s"
                           % (error or "")),
                "remediation": _IDP_REMEDIATION,
            }
        return {
            "status": "unreachable",
            "http_status": None,
            "detail": "Connexion impossible : %s" % (error or "raison inconnue"),
            "remediation": ("Système démarré ? (A4H : docker start, attendre la "
                            "fin du boot ABAP) ; vérifier base_url, port et "
                            "verify_tls."),
        }
    if 300 <= http_status < 400:
        return {
            "status": "identity_provider_redirect",
            "http_status": http_status,
            "detail": ("Le serveur redirige (HTTP %d) au lieu de servir le "
                       "catalogue : authentification déléguée." % http_status),
            "remediation": _IDP_REMEDIATION,
        }
    if 200 <= http_status < 300:
        if looks_like_html(body):
            return {
                "status": "login_page",
                "http_status": http_status,
                "detail": ("HTTP %d, mais le corps est une page HTML et non des "
                           "données : c'est une page d'amorçage de connexion, "
                           "pas un catalogue. Relevé live sur un site SAP Build "
                           "Work Zone (2026-08-26), où AUCUNE route ne renvoie "
                           "de défi d'authentification." % http_status),
                "remediation": ("Ne pas conclure au succès sur ce 200 : le "
                                "canal n'a reçu aucune donnée. " + _IDP_REMEDIATION),
            }
        return {"status": "ok", "http_status": http_status,
                "detail": "Catalogue Gateway joignable.", "remediation": None}
    if http_status == 401:
        return {
            "status": "auth_failed",
            "http_status": http_status,
            "detail": "Authentification refusée (HTTP 401).",
            "remediation": ("Vérifier les identifiants de Open Api Session : "
                            "sur ABAP, user/password/sap_client (mandant "
                            "licencié ? sur A4H sans licence, seul SAP*/000 "
                            "passe) ; sur BTP ou S/4 Cloud, la validité du "
                            "client OAuth2 et de son périmètre."),
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
