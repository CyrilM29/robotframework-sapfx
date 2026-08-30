"""Déballage minimal des secrets Robot Framework aux frontières externes.

Aussi le PRÉDICAT de présence d'un secret (`Secret Is Provided`, atteint par
un keyword depuis les resources) : un identifiant fourni en type ``Secret``
refuse d'être MESURÉ (``Should Not Be Empty`` échoue dessus par « Could not
get length of '<secret>' »), donc une garde de préflight écrite naïvement
masque le prérequis manquant derrière une erreur de garde. La seule chose
observable sans déballer est qu'une valeur non fournie est restée la chaîne
vide du défaut : cinq copies de ce test vivaient dans la couche Robot,
promues ici (convention #12).
"""
from typing import Any

from robot.api.types import Secret


def reveal_secret(value: Any) -> Any:
    """Retourne la valeur encapsulée, ou la valeur d'origine si elle est publique."""
    return value.value if isinstance(value, Secret) else value


def secret_is_provided(value: Any) -> bool:
    """Un identifiant a-t-il été fourni, SANS jamais lire sa valeur ?

    ``True`` pour tout ``Secret`` (sa présence suffit, son contenu ne se
    mesure pas) et pour une chaîne non vide ; ``False`` pour la chaîne vide
    du défaut et pour ``None``. Le prédicat des gardes de préflight des
    quatre canaux (`Api Credentials Should Be Provided`, `Rfc Credentials
    Should Be Provided`, les gardes de cible des page objects)."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value)
    return True

