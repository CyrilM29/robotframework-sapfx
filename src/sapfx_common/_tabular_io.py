"""L'écriture d'un fichier de restitution, et son seul mode d'échec courant.

Privé, partagé par les trois formats (:mod:`sapfx_common.table_svg`,
:mod:`table_xlsx`, :mod:`table_csv`).

Sous Windows, un classeur ou un CSV ouvert dans un tableur est VERROUILLÉ :
la ré-écriture part alors en ``PermissionError: [Errno 13] Permission denied``,
message qui désigne le fichier et rien d'autre. Lu dans un journal de test, il
se comprend comme un problème de droits, et c'est la mauvaise piste : le
fichier appartient à celui qui l'écrit, il est simplement ouvert à côté.

Le cas est arrivé en montant l'extraction de RSPARAM le 2026-09-15, le
classeur produit au run précédent étant resté affiché. La même campagne
rejouée par un opérateur qui garde son extraction ouverte le rencontrera, donc
l'échec nomme la cause et le remède.
"""
from __future__ import annotations

import os
from typing import Union

__all__ = ["write_bytes", "write_text", "prepare_target",
           "locked_target"]


def prepare_target(path: str) -> str:
    """Le chemin absolu de la cible, son dossier créé au besoin."""
    cible = os.path.abspath(str(path))
    dossier = os.path.dirname(cible)
    if dossier:
        os.makedirs(dossier, exist_ok=True)
    return cible


def locked_target(cible: str, cause: PermissionError) -> PermissionError:
    """L'erreur commune aux cinq formats quand la cible est verrouillée."""
    return PermissionError(
        "Écriture refusée sur %s. Cause la plus fréquente sous Windows : le "
        "fichier est OUVERT dans un tableur ou une visionneuse, qui le "
        "verrouille (il ne s'agit pas d'un problème de droits). Le refermer, "
        "ou écrire sous un autre nom. Détail : %s" % (cible, cause))


def write_bytes(path: str, contenu: bytes) -> str:
    """Écrit des octets, en nommant le verrouillage s'il y en a un."""
    cible = prepare_target(path)
    try:
        with open(cible, "wb") as flux:
            flux.write(contenu)
    except PermissionError as cause:
        raise locked_target(cible, cause) from None
    return cible


def write_text(path: str, contenu: str, encoding: str = "utf-8",
               newline: Union[str, None] = "\n") -> str:
    """Écrit du texte, en nommant le verrouillage s'il y en a un.

    ``newline`` est explicite parce que les trois formats n'ont pas la même
    règle : LF pour un artefact que l'on compare, CRLF pour un CSV qui suit la
    RFC 4180.
    """
    cible = prepare_target(path)
    try:
        with open(cible, "w", encoding=encoding, newline=newline) as flux:
            flux.write(contenu)
    except PermissionError as cause:
        raise locked_target(cible, cause) from None
    return cible
