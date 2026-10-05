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

import base64
from dataclasses import dataclass
from typing import Any, Optional


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


def basic_auth_header(user: Any, password: Any) -> str:
    """L'en-tête ``Authorization`` d'une authentification HTTP de base.

    Du savoir de PROTOCOLE, donc de la bibliothèque et non d'une couche
    Robot : l'encodage est normalisé (RFC 7617, ``user:password`` en base64
    sur un flux UTF-8), et le mot de passe traverse ici la frontière d'un
    `Secret` RF 7.4 comme partout ailleurs.

    Il existe parce qu'un formulaire de connexion n'est pas toujours
    atteignable. Mesuré le 2026-09-15 sur un système ABAP du banc : le
    WebGUI y rend TOUS les champs de son formulaire à 0x0 sans parent de mise
    en page, en HTTP comme en HTTPS (14 champs, 0 visible), donc hors
    d'atteinte de n'importe quel moteur, là où le système voisin en rend 5
    visibles. La même adresse répond parfaitement à une authentification
    d'en-tête. Sans cette voie, un test conclurait « cible injoignable » sur
    un système disponible. La CAUSE du formulaire muet n'est pas établie :
    l'avertissement « pas de bascule HTTPS » avait paru l'expliquer, une
    seconde mesure l'a trouvé aussi sur le système qui fonctionne.

    NB de frontière : la bibliothèque Browser n'accepte un dictionnaire
    d'identifiants que par sa syntaxe ``$variable``, qui ne résout PAS une
    variable créée dans un keyword utilisateur (vérifié). L'en-tête, lui,
    passe partout.

    Un utilisateur contenant ``:`` est refusé : la RFC ne permet pas de le
    représenter, et un identifiant tronqué en silence enverrait chercher un
    problème de droits.
    """
    from sapfx_common.secrets import reveal_secret

    nom = "" if user is None else str(user)
    if ":" in nom:
        raise ValueError(
            "Un identifiant d'authentification HTTP de base ne peut pas "
            "contenir « : » (reçu %r) : le séparateur est ce caractère, donc "
            "la valeur serait tronquée en silence." % nom)
    secret = reveal_secret(password)
    brut = "%s:%s" % (nom, "" if secret is None else str(secret))
    # UTF-8 SANS condition, et c'est un choix. L'encodage historique des
    # navigateurs essaie latin-1 d'abord : le même mot de passe part alors
    # encodé de deux façons selon qu'il tient ou non dans latin-1, ce qui
    # rend l'échec dépendant du contenu du secret, donc invisible en test et
    # capricieux en production. La RFC 7617 recommande UTF-8, et pour un mot
    # de passe ASCII (le cas courant) les deux encodages coïncident.
    return "Basic " + base64.b64encode(brut.encode("utf-8")).decode("ascii")
