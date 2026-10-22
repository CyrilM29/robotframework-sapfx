"""``sapfx_common`` : la logique pure partagée par les trois bibliothèques, et des keywords à importer module par module.

Le paquet a deux usages. D'abord la logique pure que ``SapEccLibrary``,
``SapFioriLibrary`` et ``SapApiLibrary`` partagent : aucune dépendance COM ni
navigateur, des fonctions qui se testent hors SAP (sondage borné, scoring de
réparation, contrats d'extraction, verdicts). Ensuite, une vingtaine de ses
modules s'importent comme *bibliothèques Robot Framework* : c'est par eux que
les ressources métier atteignent cette logique par un keyword, sans
``Evaluate`` ni ``__import__`` dans une suite.

Le paquet part sur PyPI avec les trois bibliothèques, dans la même
distribution ``robotframework-sapfx`` : ``pip install robotframework-sapfx``
installe tous les modules documentés ici. Écrire du Parquet demande en plus
l'extra facultatif ``parquet`` ; sans lui, `Parquet Channel Status` le dit et
nomme le remède.

= Importer un module =

Chaque module est une bibliothèque à lui seul. L'étiquette d'un keyword sur
cette page est le nom à écrire après ``Library`` :

| Library    sapfx_common.table_extract
| Library    sapfx_common.table_csv

Une bibliothèque faite d'un module est globale (une seule instance pour toute
l'exécution) et n'expose que les fonctions listées dans son ``__all__`` : un
assistant interne ou une fonction importée d'ailleurs n'y devient jamais un
keyword. Ces keywords ne pilotent aucun écran : ils prennent et rendent des
valeurs simples (chaînes, listes, dictionnaires), donc ils s'enchaînent
derrière n'importe quel canal.

= Les modules =
"""
from importlib.util import find_spec as _find_spec

__version__ = "0.8.6"

#: Les modules du paquet qu'une suite importe comme bibliothèques Robot
#: (``Library    sapfx_common.table_csv``). Une seule liste, que lisent la page
#: Libdoc (``scripts/build_common_libdoc.py``) et les plugins rf-mcp qui
#: déclarent ces modules au serveur : un module ajouté ici entre dans les deux.
#: Dans le dépôt privé, ``sapfx_common._extension`` y ajoute les modules de
#: l'atelier, absents de la distribution publique.
ROBOT_LIBRARY_MODULES: tuple[str, ...] = (
    "sapfx_common.alv_cells",
    "sapfx_common.artifacts",
    "sapfx_common.auth_flows",
    "sapfx_common.cross_channel",
    "sapfx_common.gateway_log",
    "sapfx_common.parameter_origin",
    "sapfx_common.rap_preview",
    "sapfx_common.rfc_tables",
    "sapfx_common.robot_args",
    "sapfx_common.secrets",
    "sapfx_common.security_baseline",
    "sapfx_common.security_inventory",
    "sapfx_common.table_csv",
    "sapfx_common.table_extract",
    "sapfx_common.table_json",
    "sapfx_common.table_parquet",
    "sapfx_common.table_svg",
    "sapfx_common.table_xlsx",
    "sapfx_common.user_formats",
    "sapfx_common.vocabulary",
    "sapfx_common.webgui_selection",
    "sapfx_common.write_simulation",
)

if _find_spec("sapfx_common._extension") is not None:
    from ._extension import ROBOT_LIBRARY_MODULES as _EXTENSION_MODULES

    ROBOT_LIBRARY_MODULES = tuple(sorted(ROBOT_LIBRARY_MODULES + _EXTENSION_MODULES))
