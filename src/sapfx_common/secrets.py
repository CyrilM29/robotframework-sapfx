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

from sapfx_common import __version__ as _package_version
from robot.api.deco import keyword

#: Version de ce module quand Robot l'importe comme bibliothèque (Libdoc, journal) :
#: celle du paquet, jamais une seconde valeur à aligner à chaque release.
ROBOT_LIBRARY_VERSION = _package_version

#: Seules les fonctions décorées par ``@keyword`` deviennent des keywords :
#: Robot lit aussi ``__all__``, mais le chargeur de rf-mcp ne lit que ce
#: drapeau, et sans lui y publiait les fonctions importées d'ailleurs.
ROBOT_AUTO_KEYWORDS = False

#: Les keywords que ``Library    sapfx_common.secrets`` expose, et eux seuls.
#: ``reveal_secret`` en est EXCLU à dessein : comme keyword, il rendrait la
#: valeur claire d'un ``Secret`` dans une variable Robot, donc dans le journal.
#: La fonction reste à la disposition du code Python des bibliothèques, qui ne
#: déballe qu'à la frontière externe (COM, HTTP, RFC).
__all__ = ["secret_is_provided"]


def reveal_secret(value: Any) -> Any:
    """Retourne la valeur encapsulée, ou la valeur d'origine si elle est publique."""
    return value.value if isinstance(value, Secret) else value


@keyword
def secret_is_provided(value: Any) -> bool:
    """Un identifiant a-t-il été fourni, SANS jamais lire sa valeur ?

    ``True`` pour tout ``Secret`` (sa présence suffit, son contenu ne se
    mesure pas) et pour une chaîne non vide ; ``False`` pour la chaîne vide
    du défaut et pour ``None``. Le prédicat des gardes de préflight des
    quatre canaux (`Api Credentials Should Be Provided`, `Rfc Credentials
    Should Be Provided`, les gardes de cible des page objects).

    Exemple :
    | ${provided}=    `Secret Is Provided`    ${password}
    | Should Be True    ${provided}
    | ${missing}=    `Secret Is Provided`    ${EMPTY}
    | Should Not Be True    ${missing}
    """
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value)
    return True

