"""Thème UI5 réellement APPLIQUÉ à un document, logique pure de `Get Ui5 Theme`.

Deux témoins coexistent dans une page UI5 et aucun ne suffit seul :

* la classe technique ``sapUiTheme-<clé>`` de ``<html>`` : locale-safe, mais
  elle peut précéder les styles (Demo Kit OpenUI5, mesuré le 2026-11-16 : la
  classe et l'adresse des feuilles basculent ensemble, les nouvelles feuilles
  se chargent jusqu'à une seconde et demie plus tard) et elle peut garder un
  reliquat (launchpad SAPUI5 1.120.15 d'ABAP Platform 2023, mesuré le même
  jour : ``sapUiTheme-sap_belize`` reste à côté de ``sapUiTheme-sap_horizon``
  alors que seul Horizon est chargé et affiché) ;
* les feuilles de thème, une par bibliothèque (``<link
  id="sap-ui-theme-<bibliothèque>">``, ``…/themes/<clé>/library.css``) : ce
  qu'elles ont CHARGÉ est ce que l'écran affiche.

La règle : le thème appliqué est celui des feuilles actives quand toutes sont
chargées et nomment le même thème ; une feuille encore en attente, ou des
feuilles de deux thèmes, rendent une valeur VIDE (échange en cours, jamais le
premier venu) ; sans aucune feuille de thème, repli sur la classe, elle aussi
vide quand plusieurs thèmes y figurent. Un appelant qui asserte attend donc la
valeur voulue, il ne lit jamais une seule fois.

« Chargée » se lit sur ``link.sheet`` : UI5 1.152 ne pose aucun attribut de
fin de chargement sur ses liens, et sous Chromium une feuille en ÉCHEC (404)
porte elle aussi un ``sheet`` (mesuré le 2026-11-16 sur le Demo Kit : événement
``error``, ``sheet`` présent), donc une bibliothèque sans feuille de thème ne
bloque pas la lecture : seule une attente réelle la rend vide.

Deux limites, dites : une feuille en échec est tenue pour chargée et son adresse
nomme le thème demandé, donc ``applied`` peut annoncer un thème qu'une
bibliothèque n'a pas (comme le faisait la lecture par la classe) ; et une
bibliothèque qui retomberait sur un thème de repli rendrait ``applied`` vide en
permanence (une attente échoue alors, jamais en silence).
"""

from __future__ import annotations

import re
from typing import Any

# Préfixe de la classe technique que le runtime UI5 pose sur ``<html>``.
THEME_CLASS_PREFIX = "sapUiTheme-"

# Segment ``/themes/<clé>/`` d'une adresse de feuille. Une racine de thème du
# référentiel ABAP porte DEUX segments (``/sap/public/bc/themes/~client-001/
# ~cache-…/UI5/sap/m/themes/<clé>/library.css``) : la clé est la DERNIÈRE.
_THEME_SEGMENT_RE = re.compile(r"/themes/([^/?#]+)/")


def applied_theme(class_attribute: str | None) -> str:
    """Thème porté par la classe ``sapUiTheme-<clé>`` de ``<html>``.

    Vide sans classe de thème (fenêtre transitoire mesurée sur le Demo Kit le
    2026-08-30) et vide quand plusieurs classes de thème coexistent (reliquat
    d'amorçage du launchpad 1.120) : aucune ne prouve alors rien.
    """
    themes = {token[len(THEME_CLASS_PREFIX):] for token in str(class_attribute or "").split()
              if token.startswith(THEME_CLASS_PREFIX) and len(token) > len(THEME_CLASS_PREFIX)}
    return themes.pop() if len(themes) == 1 else ""


def sheet_theme(href: str | None) -> str:
    """Clé de thème d'une adresse de feuille : le DERNIER segment ``/themes/<clé>/``.

    Vide quand l'adresse n'en porte aucun.
    """
    segments = _THEME_SEGMENT_RE.findall(str(href or ""))
    return segments[-1] if segments else ""


def _sheet(entry: Any) -> tuple[str, bool]:
    """``(adresse, chargée)`` d'une entrée de sonde : un dict ``{href, loaded}``
    (la sonde actuelle) ou une adresse seule, tenue pour chargée."""
    if isinstance(entry, dict):
        return str(entry.get("href") or ""), bool(entry.get("loaded", True))
    return str(entry or ""), True


def applied_theme_from(class_attribute: str | None, sheets: Any) -> str:
    """Thème APPLIQUÉ : feuilles chargées d'abord, classe de ``<html>`` en repli.

    ``sheets`` est la liste des feuilles de thème ACTIVES lue par la sonde
    (``{href, loaded}`` chacune). Une feuille en attente ou des feuilles de
    plusieurs thèmes rendent une valeur vide ; sans feuille de thème, la classe
    décide (`applied_theme`).
    """
    lues = [_sheet(entry) for entry in (sheets or [])]
    lues = [(sheet_theme(href), charge) for href, charge in lues if href]
    lues = [(theme, charge) for theme, charge in lues if theme]
    if not lues:
        return applied_theme(class_attribute)
    if not all(charge for _, charge in lues):
        return ""
    themes = {theme for theme, _ in lues}
    return themes.pop() if len(themes) == 1 else ""
