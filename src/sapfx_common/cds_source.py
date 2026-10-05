"""Annotations d'EN-TÊTE d'une vue CDS ABAP, lues dans sa source DDL.

Logique pure derrière `Get Cds Header Annotations` (SapApiLibrary), née de la
revue indépendante de la fiche scénario 7 (2026-09-29). Le dictionnaire
(``DDHEADANNO``) porte le NOM de chaque annotation d'en-tête, mais sa colonne
``VALUE`` (1300 caractères) dépasse ce que ``RFC_READ_TABLE`` sait rendre :
une campagne qui ne lit que le dictionnaire par RFC constate qu'une
annotation EXISTE, jamais ce qu'elle VAUT, et
``@Analytics.dataExtraction.enabled: false`` y ressemble trait pour trait à
``true``. La source, elle, se lit par l'API des outils ABAP
(``/sap/bc/adt/ddic/ddl/sources/<nom>/source/main``, ``Accept: text/plain``,
mesuré sur A4H 1909).

Le résultat reprend la convention du dictionnaire, pour que les deux lectures
se confrontent sans traduction : clés en MAJUSCULES et pointées
(``ANALYTICS.DATACATEGORY``), valeurs en texte (``#DIMENSION``, ``true``,
``SEPM_IPO`` sans ses apostrophes). Formes lues, toutes relevées sur les
sources EPM du banc : annotation à plat (``@AbapCatalog.sqlViewName:
'SEPM_IPO'``), objet imbriqué (``@Analytics:{ dataCategory: #DIMENSION,
dataExtraction.enabled: true }``), sans espace après les deux-points,
commentaires ``//``, ``--`` et ``/* */`` (une annotation commentée n'existe
pas), tableau de valeurs.
"""
from __future__ import annotations

import re
from typing import Any, Union
from urllib.parse import quote

__all__ = ["DDL_SOURCE_PATH", "ddl_source_path", "strip_comments",
           "header_annotations"]

#: Chemin de la source d'une définition DDL dans l'API des outils ABAP.
DDL_SOURCE_PATH = "/sap/bc/adt/ddic/ddl/sources/%s/source/main"

_NOM = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
_DEFINE = re.compile(r"\bdefine\b", re.IGNORECASE)

Valeur = Union[str, list]


def ddl_source_path(name: Any) -> str:
    """Le chemin ADT de la source d'une vue CDS (nom en minuscules, encodé)."""
    nom = str(name or "").strip()
    if not nom:
        raise ValueError("Aucune vue CDS désignée.")
    return DDL_SOURCE_PATH % quote(nom.lower(), safe="")


def _fin_de_chaine(texte: str, debut: int) -> int:
    """Indice de l'apostrophe qui ferme la chaîne ouverte en ``debut``
    (``''`` est une apostrophe échappée) ; une chaîne jamais fermée LÈVE :
    lue jusqu'au bout, elle avalerait en silence tout ce qui la suit."""
    j = debut + 1
    while j < len(texte):
        if texte[j] == "'":
            if j + 1 < len(texte) and texte[j + 1] == "'":
                j += 2
                continue
            return j
        j += 1
    raise ValueError("Chaîne non fermée dans la source DDL à la position %d : %r"
                     % (debut, texte[debut:debut + 40]))


def _masquer_chaines(texte: str) -> str:
    """Le texte, chaînes remplacées par des blancs de même longueur : pour y
    chercher un mot-clé sans le trouver DANS une valeur."""
    out, i = [], 0
    while i < len(texte):
        if texte[i] == "'":
            fin = _fin_de_chaine(texte, i)
            out.append(" " * (fin + 1 - i))
            i = fin + 1
        else:
            out.append(texte[i])
            i += 1
    return "".join(out)


def strip_comments(source: Any) -> str:
    """La source sans ses commentaires (``//`` et ``--`` jusqu'à la fin de
    ligne, ``/* */``), chaînes entre apostrophes respectées : un ``//`` dans
    une valeur n'ouvre pas de commentaire. Une chaîne ou un commentaire de
    bloc jamais fermé LÈVE plutôt que d'avaler la suite du texte."""
    texte = str(source or "")
    out = []
    i, n = 0, len(texte)
    while i < n:
        c = texte[i]
        if c == "'":
            j = _fin_de_chaine(texte, i)
            out.append(texte[i:j + 1])
            i = j + 1
        elif texte.startswith(("//", "--"), i):
            fin = texte.find("\n", i)
            i = n if fin < 0 else fin
        elif texte.startswith("/*", i):
            fin = texte.find("*/", i + 2)
            if fin < 0:
                raise ValueError("Commentaire /* non fermé dans la source DDL à "
                                 "la position %d." % i)
            i = fin + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


class _Lecteur:
    def __init__(self, texte: str) -> None:
        self.t, self.i = texte, 0

    def blancs(self) -> None:
        while self.i < len(self.t) and self.t[self.i].isspace():
            self.i += 1

    def car(self) -> str:
        self.blancs()
        return self.t[self.i] if self.i < len(self.t) else ""

    def nom(self) -> str:
        self.blancs()
        m = _NOM.match(self.t, self.i)
        if not m:
            raise ValueError("Nom d'annotation attendu à la position %d : %r"
                             % (self.i, self.t[self.i:self.i + 30]))
        self.i = m.end()
        return m.group(0)

    def valeur(self) -> Union[Valeur, dict]:
        c = self.car()
        if c == "{":
            self.i += 1
            objet: dict = {}
            while self.car() not in ("}", ""):
                cle = self.nom()
                if cle in objet:
                    raise ValueError("Clé %s en double dans un objet d'annotation." % cle)
                if self.car() != ":":
                    objet[cle] = "true"
                else:
                    self.i += 1
                    objet[cle] = self.valeur()
                if self.car() == ",":
                    self.i += 1
            if not self.car():
                raise ValueError("Objet d'annotation non fermé (« } » manquant).")
            self.i += 1
            return objet
        if c == "[":
            self.i += 1
            liste: list = []
            while self.car() not in ("]", ""):
                liste.append(self.valeur())
                if self.car() == ",":
                    self.i += 1
            if not self.car():
                raise ValueError("Tableau d'annotation non fermé (« ] » manquant).")
            self.i += 1
            return liste
        if c == "'":
            fin = _fin_de_chaine(self.t, self.i)
            valeur = self.t[self.i + 1:fin].replace("''", "'")
            self.i = fin + 1
            return valeur
        m = re.compile(r"[^\s,}\]@]+").match(self.t, self.i)
        if not m:
            raise ValueError("Valeur d'annotation attendue à la position %d : %r"
                             % (self.i, self.t[self.i:self.i + 30]))
        self.i = m.end()
        return m.group(0)


def _poser(out: dict[str, Valeur], cle: str, valeur: Valeur) -> None:
    """Une annotation déjà lue n'est jamais écrasée en silence : à plat puis
    imbriquée (``@A.b: false`` et ``@A: { b: true }``), la dernière lue
    l'emporterait sans que rien ne le dise (revue n°3 du 2026-09-29)."""
    if cle in out:
        raise ValueError("Annotation %s en double dans l'en-tête DDL (%r puis %r)."
                         % (cle, out[cle], valeur))
    out[cle] = valeur


def _aplatir(prefixe: str, valeur: Any, out: dict[str, Valeur]) -> None:
    if isinstance(valeur, dict):
        for cle, sous in valeur.items():
            _aplatir("%s.%s" % (prefixe, cle.upper()), sous, out)
    elif isinstance(valeur, list):
        if all(not isinstance(v, (dict, list)) for v in valeur):
            _poser(out, prefixe, [str(v) for v in valeur])
        else:
            for rang, sous in enumerate(valeur, start=1):
                _aplatir("%s[%d]" % (prefixe, rang), sous, out)
    else:
        _poser(out, prefixe, str(valeur))


def header_annotations(source: Any) -> dict[str, Valeur]:
    """Les annotations d'EN-TÊTE d'une source DDL (tout ce qui précède le mot
    ``define``), aplaties : ``{"ANALYTICS.DATACATEGORY": "#DIMENSION",
    "ANALYTICS.DATAEXTRACTION.ENABLED": "true", "ABAPCATALOG.SQLVIEWNAME":
    "SEPM_IPO", ...}``. Une annotation sans valeur vaut ``"true"`` ; un
    tableau de valeurs simples rend une liste.

    Refuse une source sans ``define`` (ce n'est pas une définition DDL : page
    de connexion, erreur) et une annotation illisible, en nommant la position,
    plutôt que de rendre un dictionnaire partiel qui passerait pour complet.
    """
    texte = strip_comments(source)
    # `define` cherché HORS des chaînes : un libellé « Define purchase
    # orders » couperait sinon l'en-tête en silence.
    fin = _DEFINE.search(_masquer_chaines(texte))
    if not fin:
        raise ValueError("Source DDL sans « define » : ce n'est pas la "
                         "définition d'une vue CDS (%r)." % texte[:80])
    lecteur = _Lecteur(texte[:fin.start()])
    out: dict[str, Valeur] = {}
    while True:
        c = lecteur.car()
        if not c:
            return out
        if c != "@":
            raise ValueError("Texte inattendu dans l'en-tête DDL à la position "
                             "%d : %r" % (lecteur.i, lecteur.t[lecteur.i:lecteur.i + 30]))
        lecteur.i += 1
        nom = lecteur.nom().upper()
        if lecteur.car() == ":":
            lecteur.i += 1
            _aplatir(nom, lecteur.valeur(), out)
        else:
            _poser(out, nom, "true")
