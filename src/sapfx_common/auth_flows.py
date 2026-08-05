"""Presets de connexion aux fournisseurs d'identité (IDP) : données pures.

Concept issu de l'analyse de playwright-praman (Apache-2.0, attribution dans
``NOTICE``), réimplémenté sur notre modèle : un launchpad Fiori d'entreprise
n'affiche presque jamais un formulaire SAP classique : il redirige vers un
IDP (SAP Identity Authentication / IAS, Azure AD/Entra, IDP maison). Chaque
IDP a un formulaire aux sélecteurs connus et un déroulé en UNE page
(utilisateur+mot de passe ensemble) ou en DEUX étapes (utilisateur → Suivant
→ mot de passe). Ici : les fiches de sélecteurs (:data:`IDP_PRESETS`) et leur
résolution défensive ; le pilotage réel (Browser library) vit dans le keyword
``Log In Via Identity Provider`` de ``SapFioriLibrary``.

Les presets sont un point de départ : tout sélecteur est surchargeable à
l'appel (IDP personnalisé = preset ``generic`` + les trois sélecteurs).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class IdpPreset:
    """Sélecteurs du formulaire de connexion d'un IDP."""
    name: str
    username_selector: str
    password_selector: str
    submit_selector: str
    description: str = ""


IDP_PRESETS: dict = {
    # SAP Identity Authentication Service (IAS) : le défaut BTP/Fiori cloud.
    "sap-ias": IdpPreset(
        "sap-ias",
        username_selector="#j_username",
        password_selector="#j_password",
        submit_selector="#logOnFormSubmit",
        description="SAP Identity Authentication Service (BTP default)"),
    # Azure AD / Microsoft Entra : déroulé en deux étapes.
    "azure-ad": IdpPreset(
        "azure-ad",
        username_selector="input[name=loginfmt]",
        password_selector="input[name=passwd]",
        submit_selector="input[type=submit]",
        description="Microsoft Entra ID (Azure AD) two-step sign-in"),
    # IDP quelconque : à compléter par les sélecteurs à l'appel.
    "generic": IdpPreset(
        "generic",
        username_selector="input[type=email], input[type=text]",
        password_selector="input[type=password]",
        submit_selector="button[type=submit], input[type=submit]",
        description="Generic form: override selectors per call"),
}


def resolve_preset(preset: str,
                   username_selector: Optional[str] = None,
                   password_selector: Optional[str] = None,
                   submit_selector: Optional[str] = None) -> IdpPreset:
    """La fiche effective : le preset nommé, surchargé champ par champ.

    Preset inconnu = erreur immédiate avec la liste des presets valides
    (jamais de repli silencieux vers ``generic``)."""
    key = str(preset).strip().lower()
    if key not in IDP_PRESETS:
        raise ValueError(
            "Preset IDP inconnu : %r. Presets valides : %s (tout sélecteur "
            "reste surchargeable à l'appel)."
            % (preset, ", ".join(sorted(IDP_PRESETS))))
    base = IDP_PRESETS[key]
    return IdpPreset(
        name=base.name,
        username_selector=username_selector or base.username_selector,
        password_selector=password_selector or base.password_selector,
        submit_selector=submit_selector or base.submit_selector,
        description=base.description)
