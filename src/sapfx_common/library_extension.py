"""Extensions locales d'une bibliothèque SAPFX : des keywords ajoutés hors distribution publique.

Une bibliothèque (``SapEccLibrary``, ``SapFioriLibrary``, ``SapApiLibrary``)
compose ses keywords par des mixins. Un module ``<paquet>._extension``, quand il
existe, déclare des mixins de plus (``MIXINS``) et, s'il le faut, des
convertisseurs d'arguments (``CONVERTERS``) : la classe que Robot Framework
importe les porte alors en plus des siens. Sans ce module, la bibliothèque est
exactement celle qui est publiée.

Deux règles tenues ici, au moment de la composition :

- un mixin d'extension n'écrase jamais un attribut de la bibliothèque (keyword
  ou aide interne) : un homonyme fait échouer l'import en le nommant, parce
  qu'une extension qui remplacerait un keyword public changerait en silence le
  comportement d'une suite écrite contre la version publiée ;
- l'extension s'ajoute DEVANT la bibliothèque dans l'ordre de résolution, sans
  rien réordonner de ses propres mixins.
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect
from typing import Any

__all__ = ["extend_library", "extension_mixins", "homonyms"]


def _underlying(value: Any) -> Any:
    """La fonction derrière un ``staticmethod`` ou un ``classmethod``."""
    return getattr(value, "__func__", value)


def extension_mixins(package: str) -> tuple[type, ...]:
    """Les mixins déclarés par ``<package>._extension``, ou un tuple vide."""
    name = package + "._extension"
    if importlib.util.find_spec(name) is None:
        return ()
    return tuple(importlib.import_module(name).MIXINS)


def homonyms(cls: type, mixins: tuple[type, ...]) -> list[str]:
    """Les attributs qu'un mixin d'extension définit ET que ``cls`` porte déjà.

    Un même objet partagé (une fonction aide importée des deux côtés) n'est
    pas un homonyme : seul compte un attribut qui changerait de valeur.
    """
    clashes = []
    for mixin in mixins:
        for attr, value in vars(mixin).items():
            if attr.startswith("__") and attr.endswith("__"):
                continue
            try:
                existing = inspect.getattr_static(cls, attr)
            except AttributeError:
                continue
            if _underlying(existing) is not _underlying(value):
                clashes.append(f"{mixin.__name__}.{attr}")
    return sorted(clashes)


def extend_library(cls: type, package: str) -> type:
    """Rend ``cls`` augmentée des mixins d'extension de ``package``, ou ``cls``.

    La classe rendue garde le nom, le module et la documentation de ``cls`` :
    Libdoc et Robot Framework la voient comme la même bibliothèque.
    """
    mixins = extension_mixins(package)
    if not mixins:
        return cls
    clashes = homonyms(cls, mixins)
    if clashes:
        raise TypeError(
            "Extension de %s refusée : ces attributs existent déjà dans la "
            "bibliothèque et seraient remplacés : %s. Renommer l'attribut de "
            "l'extension." % (cls.__name__, ", ".join(clashes)))
    namespace: dict[str, Any] = {
        "__doc__": cls.__doc__,
        "__module__": cls.__module__,
        "__qualname__": cls.__qualname__,
    }
    extension = importlib.import_module(package + "._extension")
    converters = getattr(extension, "CONVERTERS", None)
    if converters:
        namespace["ROBOT_LIBRARY_CONVERTERS"] = {
            **getattr(cls, "ROBOT_LIBRARY_CONVERTERS", {}), **converters}
    return type(cls.__name__, (*mixins, cls), namespace)
