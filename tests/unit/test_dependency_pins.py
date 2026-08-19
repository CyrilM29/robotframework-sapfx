# -*- coding: utf-8 -*-
"""Garde de cohérence des DÉPENDANCES entre les fichiers qui les déclarent.

Pendant du garde de versions (``test_version_consistency.py``), pour l'autre
moitié du packaging. Quatre faits vivaient à plusieurs endroits, sans rien pour
les comparer, et la revue packaging du 2026-08-19 les a trouvés tous les quatre
au bord de la dérive :

1. **le plancher ``robotframework-sapfx`` du wheel des plugins rf-mcp** était
   écrit à la main (``>=0.6.6``) et hors de tout garde. Les cartes de keywords
   des plugins sont versionnées en lock-step avec la bibliothèque (la dérive
   0.5.6 -> 0.6.1 que ``check_guidance_sync.py`` a dû rattraper) : un plancher
   figé laisserait pip apparier un plugin 0.6.7 avec une bibliothèque 0.6.6, le
   sens dangereux. On garde ``>=`` (une post-release ``0.6.6.post1`` de la
   bibliothèque doit rester installable, cf. le workflow pypi-publish) mais le
   plancher doit valoir la version courante ;
2. **le pin ``pywin32``**, que la convention #6 du CLAUDE.md désigne comme la
   première source de casse COM, vit dans trois fichiers. C'était le pin qui
   méritait le moins une divergence muette ;
3. **la borne de ``robotframework-browser``**, dont la justification est longue
   et précise (chemins internes de Browser visés par SapFioriLibrary) : elle ne
   protège que si les trois fichiers la portent ;
4. **les copies de ``LICENSE``/``NOTICE``** dans ``integrations/robotmcp/``,
   nécessaires pour que le wheel des plugins embarque sa licence (le glob de
   setuptools cherche dans le dossier du projet). Une copie qui dérive de
   l'original est un piège : ici elle est vérifiée octet à octet.
"""
import os
import re
import sys

import pytest

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))

#: Fichiers qui déclarent des dépendances d'environnement (hors pyproject).
_REQ_FILES = (
    "requirements.txt",
    os.path.join("packaging", "requirements-deploy.txt"),
    os.path.join("packaging", "constraints-deploy.txt"),
)


def _read(rel):
    with open(os.path.join(_ROOT, rel), encoding="utf-8") as handle:
        return handle.read()


def _requirement(text, package):
    """La ligne de contrainte de ``package``, marqueur compris, ou ``None``.

    Lecture ligne à ligne, commentaires ignorés : les fichiers de requirements
    du dépôt sont largement commentés, et un pin CITÉ dans un commentaire n'est
    pas un pin appliqué.
    """
    motif = re.compile(r"^%s\s*([<>=!~].*)$" % re.escape(package),
                       re.IGNORECASE)
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = motif.match(line)
        if match:
            return match.group(1).strip()
    return None


def _project_version():
    from _common import read_project_version  # noqa: PLC0415 (outillage dépôt)
    return read_project_version(_read("pyproject.toml"))


# --- 1. plancher du wheel des plugins rf-mcp ------------------------------------

def test_le_plugin_rfmcp_exige_la_bibliotheque_de_la_version_courante():
    version = _project_version()
    text = _read(os.path.join("integrations", "robotmcp", "pyproject.toml"))
    match = re.search(r'"robotframework-sapfx>=([^"]+)"', text)
    assert match, ("integrations/robotmcp/pyproject.toml ne déclare plus sa "
                   "dépendance à robotframework-sapfx : les plugins importent "
                   "sapfx_common au niveau module, la dépendance est réelle")
    assert match.group(1) == version, (
        "le plancher robotframework-sapfx>=%s du wheel des plugins ne suit pas "
        "la version courante (%s) : pip pourrait apparier un plugin neuf avec "
        "une bibliothèque ancienne, alors que leurs cartes de keywords sont "
        "versionnées en lock-step" % (match.group(1), version))


# --- 2. pin pywin32 (convention #6) ---------------------------------------------

def test_le_pin_pywin32_est_le_meme_partout():
    pins = {rel: _requirement(_read(rel), "pywin32") for rel in _REQ_FILES}
    absents = [rel for rel, pin in pins.items() if pin is None]
    assert not absents, ("pywin32 n'est plus épinglé dans : %s (convention #6 : "
                         "pin EXACT, #1 source de casse COM)"
                         % ", ".join(sorted(absents)))
    distincts = sorted(set(pins.values()))
    assert len(distincts) == 1, (
        "pins pywin32 divergents : "
        + ", ".join("%s -> %s" % (rel, pin) for rel, pin in sorted(pins.items())))
    assert distincts[0].startswith("=="), (
        "le pin pywin32 doit être EXACT (convention #6), lu : %s" % distincts[0])


def test_le_pin_pywin32_respecte_le_plancher_du_paquet():
    """Le paquet garde un plancher (``>=305``) : une *bibliothèque* ne doit pas
    épingler ses consommateurs. Le pin exact, lui, vit dans les fichiers
    d'environnement, et il ne peut pas passer SOUS ce plancher."""
    plancher = _requirement(_read("pyproject.toml").replace('"', ""), "pywin32")
    assert plancher and plancher.startswith(">="), plancher
    plancher_num = int(re.search(r"(\d+)", plancher).group(1))
    pin = _requirement(_read("requirements.txt"), "pywin32")
    pin_num = int(re.search(r"(\d+)", pin).group(1))
    assert pin_num >= plancher_num, (
        "requirements.txt épingle pywin32 %s, sous le plancher %s déclaré par "
        "pyproject.toml" % (pin, plancher))


# --- 3. borne de robotframework-browser -----------------------------------------

def test_la_borne_browser_est_la_meme_dans_les_trois_declarations():
    """La borne haute ``<21`` protège d'une majeure qui DÉPLACERAIT
    ``Browser.utils.data_types`` sans casser à l'import (le repli repasserait
    l'état en chaîne : le KeyError attrapé live sur le smoke hybride). Elle ne
    vaut que si les trois déclarations la portent."""
    extra = re.search(r'web = \["robotframework-browser([^"]+)"\]',
                      _read("pyproject.toml"))
    assert extra, "l'extra `web` ne déclare plus robotframework-browser"
    bornes = {"pyproject.toml [web]": extra.group(1).strip()}
    for rel in ("requirements.txt",
                os.path.join("packaging", "requirements-deploy.txt")):
        bornes[rel] = _requirement(_read(rel), "robotframework-browser")
    assert len(set(bornes.values())) == 1, (
        "bornes robotframework-browser divergentes : "
        + ", ".join("%s -> %s" % (k, v) for k, v in sorted(bornes.items())))
    assert "<" in extra.group(1), (
        "la borne HAUTE de robotframework-browser a disparu : une majeure "
        "réintroduirait en silence le bug d'état passé en chaîne")


# --- 4. copies de licence du wheel des plugins ----------------------------------

@pytest.mark.parametrize("nom", ["LICENSE", "NOTICE"])
def test_les_licences_du_wheel_plugins_sont_des_copies_fideles(nom):
    """``setuptools`` cherche les fichiers de licence dans le dossier du PROJET :
    sans ces copies, le wheel ``sap_robotmcp`` se déclarait Apache-2.0 sans en
    embarquer une ligne (constaté sur le wheel du pack 0.6.6), alors que
    l'article 4 de la licence impose de joindre la copie ET le NOTICE."""
    copie = os.path.join(_ROOT, "integrations", "robotmcp", nom)
    remede = ("remettre les deux fichiers en phase : "
              "`cp %s integrations/robotmcp/%s` (depuis la racine du dépôt)"
              % (nom, nom))
    assert os.path.isfile(copie), (
        "integrations/robotmcp/%s manquant : le wheel des plugins repartirait "
        "sans licence. %s" % (nom, remede))
    with open(os.path.join(_ROOT, nom), "rb") as handle:
        origine = handle.read()
    with open(copie, "rb") as handle:
        assert handle.read() == origine, (
            "integrations/robotmcp/%s a dérivé de la copie de référence à la "
            "racine : les deux distributions doivent porter le MÊME texte. %s"
            % (nom, remede))


@pytest.mark.skipif(
    not os.path.exists(os.path.join(_ROOT, "scripts", "export_public_tree.py")),
    reason="script d'export absent (arbre public exporté) : il est exclu de "
           "l'export par construction, donc ce garde ne peut tourner que dans "
           "le dépôt qui le porte. Même skip que test_export_public_tree.py.")
def test_les_copies_de_licence_sont_connues_du_scan_anti_fuite():
    """Dupliquer un fichier de licence duplique son obligation d'allowlist.

    Les copies portent la mention d'auteur de l'original, que le scan
    anti-fuite de l'export public traite comme un motif interdit et n'autorise
    que par chemin EXACT. Une copie inconnue de `LICENSE_COPIES` ne se voit
    donc que le jour de la release, quand l'export (manuel, une fois par
    version) s'arrête sur une fuite qui n'en est pas une."""
    sys.path.insert(0, os.path.join(_ROOT, "scripts"))
    try:
        import export_public_tree as export
    finally:
        sys.path.pop(0)
    for rel in sorted(export.LICENSE_COPIES):
        chemin = os.path.join(_ROOT, *rel.split("/"))
        assert os.path.isfile(chemin), "copie de licence déclarée absente : %s" % rel
        with open(chemin, "rb") as handle:
            fuites = export.scan_bytes(rel, handle.read(), export.FORBIDDEN)
        assert fuites == [], (
            "l'export public refuserait %s : %s. Ajouter le chemin à "
            "LICENSE_COPIES dans scripts/export_public_tree.py." % (rel, fuites))
