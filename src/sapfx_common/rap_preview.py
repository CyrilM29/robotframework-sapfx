"""Aperçu Fiori Elements d'un service RAP OData v4 (FEAP) : l'adresse. Logique pure.

Un binding RAP publié s'ouvre en application Fiori Elements (List Report puis
Object Page) sans aucune application déployée : le serveur ABAP la GÉNÈRE à
la volée, c'est le bouton « Preview » des outils de développement ABAP. Ce
chemin est le seul qui mène à l'interface d'un modèle de démonstration RAP
(`/DMO/...`) quand aucune tuile du launchpad ne l'expose, ce qui est le cas sur
les deux images trial du banc (relevé le 2026-09-24 : aucun intent « Travel »
parmi les 62 du launchpad de la 2023).

Le piège qui justifie ce module : le paramètre ``feapParams`` n'est PAS une
liste en clair. Lu dans la source du gestionnaire (`CL_ADT_ODATAV4_FEAP`,
méthode `GET_SERVICE_INFO`, ABAP Platform 2023) : chaque caractère est décalé
de +20 en point de code, et les champs sont séparés par ``##`` (adresse du
service, entity set principal, propriété de navigation, entity set
secondaire, nom du service, version, binding). Les formes « naturelles »
qu'on essaie d'abord échouent en 500 sur des messages qui n'orientent vers
rien (« Parameter UCCP has invalid value », « A row with the index 2 is not
in the table ») : mesuré, les deux sur la même cible.

Importé comme bibliothèque Robot (``Library    sapfx_common.rap_preview``) :
chaque fonction de ``__all__`` est un keyword, signatures JSON-safe.
"""
from __future__ import annotations

import urllib.parse
from typing import Any

__all__ = [
    "rap_service_url",
    "build_fe_preview_path",
    "decode_fe_preview_params",
]

FEAP_V4_PATH = "/sap/bc/adt/businessservices/odatav4/feap"
FIELD_SEPARATOR = "##"
CODE_POINT_SHIFT = 20
FIELD_NAMES = (
    "service_url",
    "primary_entity_set",
    "navigation_property",
    "secondary_entity_set",
    "service_name",
    "service_version",
    "service_binding",
)


def _text(value: Any, name: str, required: bool = True) -> str:
    text = "" if value is None else str(value).strip()
    if required and not text:
        raise ValueError(f"Argument '{name}' obligatoire pour l'aperçu Fiori Elements.")
    if FIELD_SEPARATOR in text:
        raise ValueError(
            f"Argument '{name}' contient '{FIELD_SEPARATOR}', le séparateur des champs "
            f"de feapParams : la valeur serait découpée côté serveur ({text!r}).")
    return text


def _split_repository_name(name: str) -> tuple[str, str]:
    """``/DMO/UI_TRAVEL_D_D_O4`` -> (``dmo``, ``ui_travel_d_d_o4``) ;
    un nom sans espace de noms relève de ``sap``."""
    if name.startswith("/"):
        parts = name.split("/")
        if len(parts) != 3 or not parts[1] or not parts[2]:
            raise ValueError(f"Nom d'objet à espace de noms mal formé : {name!r} "
                             "(attendu /NAMESPACE/NOM).")
        return parts[1].lower(), parts[2].lower()
    return "sap", name.lower()


def rap_service_url(binding: Any, service: Any, version: Any = "0001") -> str:
    """Adresse OData v4 d'un service RAP publié, dérivée de son binding.

    ``/sap/opu/odata4/<ns>/<binding>/srvd/<ns>/<service>/<version>/``, en
    minuscules. La forme à espace de noms (``/DMO/...`` -> ``dmo``) est
    MESURÉE (elle est celle que les outils ABAP annoncent pour
    ``/DMO/UI_TRAVEL_D_D_O4`` sur ABAP 2023) ; un nom sans espace de noms suit
    la convention ``sap`` de la plateforme, non relevée sur ce banc. En cas de
    doute, passer l'adresse annoncée par le système à
    `Build Fe Preview Path` (argument ``service_url``) plutôt que la dériver.
    """
    binding_ns, binding_name = _split_repository_name(_text(binding, "binding"))
    service_ns, service_name = _split_repository_name(_text(service, "service"))
    ver = _text(version, "version")
    return f"/sap/opu/odata4/{binding_ns}/{binding_name}/srvd/{service_ns}/{service_name}/{ver}/"


def _encode(plain: str) -> str:
    return "".join(chr(ord(char) + CODE_POINT_SHIFT) for char in plain)


def build_fe_preview_path(binding: Any, service: Any, entity_set: Any,
                          version: Any = "0001", service_url: Any = "",
                          navigation_property: Any = "",
                          secondary_entity_set: Any = "",
                          client: Any = "", language: Any = "") -> str:
    """Chemin de l'aperçu Fiori Elements d'un entity set racine d'un service RAP v4.

    À concaténer à l'adresse HTTPS du serveur ABAP puis à ouvrir dans le
    navigateur (la page demande l'authentification du système). Exemple :

    | ${path}= | Build Fe Preview Path | /DMO/UI_TRAVEL_D_D_O4 | /DMO/UI_TRAVEL_D_D | Travel | client=001 |
    | Go To | https://localhost:50101${path} |

    ``service_url`` vide : dérivée par `Rap Service Url`. ``client`` et
    ``language`` ajoutent ``sap-client`` / ``sap-ui-language`` (vides =
    absents : la langue par défaut de l'utilisateur s'applique). Le serveur
    n'ouvre l'aperçu que d'un binding PUBLIÉ ; un binding inconnu rend une
    erreur serveur, pas une page vide.
    """
    binding_text = _text(binding, "binding")
    service_text = _text(service, "service")
    version_text = _text(version, "version")
    url = _text(service_url, "service_url", required=False) or rap_service_url(
        binding_text, service_text, version_text)
    fields = [
        url,
        _text(entity_set, "entity_set"),
        _text(navigation_property, "navigation_property", required=False),
        _text(secondary_entity_set, "secondary_entity_set", required=False),
        service_text,
        version_text,
        binding_text,
    ]
    query = [("feapParams", _encode(FIELD_SEPARATOR.join(fields)))]
    language_text = _text(language, "language", required=False)
    client_text = _text(client, "client", required=False)
    if language_text:
        query.append(("sap-ui-language", language_text))
    if client_text:
        query.append(("sap-client", client_text))
    return FEAP_V4_PATH + "?" + urllib.parse.urlencode(query, quote_via=urllib.parse.quote)


def decode_fe_preview_params(value: Any) -> dict[str, str]:
    """L'inverse de l'encodage : ``feapParams`` (encodé URL ou non) -> champs nommés.

    Sert au diagnostic d'une adresse d'aperçu relevée ailleurs (un lien copié
    depuis les outils ABAP) ; accepte aussi un chemin complet ``...?feapParams=...``.
    """
    text = "" if value is None else str(value)
    if "feapParams=" in text:
        query = urllib.parse.urlsplit(text).query or text.split("?", 1)[-1]
        found = urllib.parse.parse_qs(query, keep_blank_values=True).get("feapParams")
        if not found:
            raise ValueError(f"Aucun paramètre feapParams lisible dans {text!r}.")
        text = found[0]
    elif "%" in text:
        text = urllib.parse.unquote(text)
    plain = "".join(chr(ord(char) - CODE_POINT_SHIFT) for char in text)
    parts = plain.split(FIELD_SEPARATOR)
    if len(parts) < 2:
        raise ValueError("feapParams ne porte pas au moins l'adresse du service et "
                         "l'entity set principal : ce n'est pas un paramètre d'aperçu v4.")
    if len(parts) > len(FIELD_NAMES):
        raise ValueError(f"feapParams porte {len(parts)} champs pour {len(FIELD_NAMES)} "
                         "connus : format d'une autre release, à relire dans la source "
                         "du gestionnaire avant de l'interpréter.")
    parts += [""] * (len(FIELD_NAMES) - len(parts))
    return dict(zip(FIELD_NAMES, parts, strict=True))
