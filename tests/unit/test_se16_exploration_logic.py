"""Tests hors-SAP de la logique non triviale des nouveaux mots-clés d'exploration
SE16 (``resources/ecc_keywords.resource`` : ``Try Open Table Selection Screen``,
``Count Entries On Current Selection Screen``, ``List Repository Tables``).
Convention #5 du CLAUDE.md.

Ces mots-clés sont pour l'essentiel un enchaînement de primitives SapEccLibrary
déjà testées ailleurs (Input Text, Send Vkey, Wait Until Busy Done, Get Screen
Signature, Read Full Grid...) ; un aller-retour est aussi validé bout-en-bout en
live par `tests/robot/ecc_exploration.robot`. Reconstruire ici une session SAP
GUI factice complète pour rejouer tout l'enchaînement n'apporterait rien de plus
que ces deux couvertures. En revanche, trois fragments contiennent de la VRAIE
logique conditionnelle : le repérage dynamique de la case à cocher, la
normalisation des séparateurs de milliers, et le garde-fou anti-troncature. On
les exécute ici via le VRAI moteur Robot (``robot.run`` sur un snippet
temporaire) plutôt que de les rejouer à la main en Python, pour reproduire
fidèlement l'échappement de backslash propre à Robot Framework, un piège qui a
déjà une fois changé le sens d'une regex en silence (voir
``test_count_parser_*`` ci-dessous, qui a détecté le bug avant ce correctif).

Le texte des expressions est EXTRAIT du fichier .resource réel (jamais recopié
à la main) pour qu'un futur changement de la logique soit automatiquement
exercé par ces tests plutôt que de dériver silencieusement.
"""
import os

import pytest

pytest.importorskip("robot", reason="robotframework requis pour ce test")
import robot as robot_pkg  # noqa: E402

_RESOURCE = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "resources", "ecc_keywords.resource"))


def _resource_text():
    with open(_RESOURCE, "r", encoding="utf-8") as fh:
        return fh.read()


def _extract_line(marker):
    """Retourne la ligne (dépouillée) du .resource contenant ``marker`` ; lève
    explicitement si absente, pour que ce test échoue bruyamment (plutôt que de
    passer silencieusement) si la logique visée a été renommée/déplacée."""
    for line in _resource_text().splitlines():
        if marker in line:
            return line.strip()
    raise AssertionError("Marker %r introuvable dans %s -- logique déplacée/renommée ?"
                         % (marker, _RESOURCE))


def _run_snippet(tmp_path, lines):
    """Exécute un Test Case Robot minimal (une liste de lignes de corps) et
    retourne le code retour (0 = tout est passé, y compris les Should Be Equal)."""
    body = "\n".join("    %s" % ln for ln in lines)
    suite = tmp_path / "snippet.robot"
    suite.write_text("*** Test Cases ***\nT\n%s\n" % body, encoding="utf-8")
    return robot_pkg.run(str(suite), outputdir=str(tmp_path), report=None,
                         log=None, output=None, console="NONE", exitonfailure=False)


# --- Try Open Table Selection Screen : une seule implémentation, dans la lib ---

def test_selection_screen_opening_is_delegated_to_the_library_keyword():
    """L'ouverture d'un écran de sélection SE16 (statut de type E, popup
    « choix des champs » des tables larges, dialogue de message de génération,
    attente de l'écran généré) a vécu en TROIS copies divergentes : cette
    resource, le mixin DDIC et la campagne autonome. Elle vit désormais dans
    l'unique keyword de bibliothèque `Reach Se16 Selection Screen`, couvert
    par tests/unit/test_ddic_keywords.py (case cochée avec un id RELATIF,
    dialogue absorbé, verdicts rejected/dialog/modal).

    Ce test garde le dédoublonnage : il échoue si une copie de la logique
    revient dans la resource (repérage de case à cocher par parsing de
    signature, ou absorption de modale à la main)."""
    text = _resource_text()
    assert "Reach Se16 Selection Screen" in text, (
        "Try Open Table Selection Screen doit déléguer au keyword de "
        "bibliothèque, pas réimplémenter l'ouverture d'écran de sélection.")
    for copy_marker in ("wnd[1]/usr/chk", "Select Checkbox"):
        assert copy_marker not in text, (
            "Une copie du pilotage de popup SE16 est revenue dans %s (%r) : "
            "la logique appartient à Reach Se16 Selection Screen."
            % (_RESOURCE, copy_marker))


# --- Count Entries On Current Selection Screen : séparateurs de milliers ------

def test_se16_screen_primitives_live_in_the_library():
    """Le comptage « Number of Entries » et le réglage d'affichage ALV sont
    des primitives d'ÉCRAN SE16 : promues dans la bibliothèque (mixin
    ``_se16.py``, convention #12), avec la normalisation locale-safe du
    compteur (``sapfx_common.robot_args.displayed_count``, leçon anti-regex
    comprise, couverte par ``test_robot_args.py``).

    Deux raisons de les avoir sorties de la resource, et ce test les garde :
    trois messages d'échec de la bibliothèque PRESCRIVENT « Use ALV Grid In
    Data Browser » à un utilisateur PyPI qui n'a pas ``resources/``, et le
    comptage se dupliquait déjà dans trois suites autonomes. Le test échoue
    si une copie inline revient ici."""
    text = _resource_text()
    for marker in ("isdigit", "tbar[1]/btn[31]", "txtG_DBCOUNT",
                   "radRSEUMOD-TBALV_GRID"):
        assert marker not in text, (
            "Une copie d'une primitive d'écran SE16 (%r) est revenue dans "
            "%s : elle appartient au mixin _se16.py de la bibliothèque."
            % (marker, _RESOURCE))


# --- List Repository Tables : garde-fou anti-troncature ------------------------

_GUARD_MARKER = "IF    len($rows) == int($max_hits)"


def _guard_snippet_lines(rows_len, max_hits, allow_truncation):
    if_line = _extract_line(_GUARD_MARKER)   # condition réelle, extraite du .resource
    return [
        "${rows}=    Evaluate    [1] * %s" % rows_len,
        "${max_hits}=    Set Variable    %s" % max_hits,
        "${allow_truncation}=    Set Variable    %s" % ("${True}" if allow_truncation else "${False}"),
        if_line,
        "    Fail    truncated",
        "END",
    ]


def test_truncation_guard_fails_when_rows_equal_max_hits(tmp_path):
    rc = _run_snippet(tmp_path, _guard_snippet_lines(rows_len=3, max_hits=3, allow_truncation=False))
    assert rc != 0    # le Fail doit bien se déclencher


def test_truncation_guard_passes_when_under_max_hits(tmp_path):
    rc = _run_snippet(tmp_path, _guard_snippet_lines(rows_len=2, max_hits=3, allow_truncation=False))
    assert rc == 0


def test_truncation_guard_suppressed_by_allow_truncation(tmp_path):
    rc = _run_snippet(tmp_path, _guard_snippet_lines(rows_len=3, max_hits=3, allow_truncation=True))
    assert rc == 0
