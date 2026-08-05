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


def _extract_evaluate_expr(marker):
    line = _extract_line(marker)
    return line.split("Evaluate", 1)[1].strip()


def _robot_escaped(text):
    """Échappe une chaîne Python multi-lignes/tabulée pour une cellule Robot
    plain-text : ``\\n``/``\\t`` littéraux (reconvertis en vrais retours à la
    ligne/tabulations par l'échappement natif de Robot), et CHAQUE espace en
    ``\\ `` : une tabulation, ou juste deux espaces réels consécutifs, dans une
    cellule seraient lus comme un séparateur de colonnes et éclateraient la
    valeur en plusieurs arguments au lieu d'une seule chaîne."""
    return (text.replace("\\", "\\\\")
                .replace("\n", "\\n")
                .replace("\t", "\\t")
                .replace(" ", "\\ "))


def _run_snippet(tmp_path, lines):
    """Exécute un Test Case Robot minimal (une liste de lignes de corps) et
    retourne le code retour (0 = tout est passé, y compris les Should Be Equal)."""
    body = "\n".join("    %s" % ln for ln in lines)
    suite = tmp_path / "snippet.robot"
    suite.write_text("*** Test Cases ***\nT\n%s\n" % body, encoding="utf-8")
    return robot_pkg.run(str(suite), outputdir=str(tmp_path), report=None,
                         log=None, output=None, console="NONE", exitonfailure=False)


# --- Try Open Table Selection Screen : repérage dynamique de la case à cocher -

_CHECKBOX_MARKER = "l.startswith('* wnd[1]/usr/chk')"


def test_checkbox_picker_selects_first_popup_checkbox_in_signature_order(tmp_path):
    expr = _extract_evaluate_expr(_CHECKBOX_MARKER)
    # NB : pas de ligne d'en-tête "# screen ..." ici (non nécessaire à ce
    # fragment, qui ne regarde que les lignes "* wnd[1]/usr/chk...") : un "#" en
    # tout début de cellule Robot serait lu comme un commentaire et viderait
    # ${sig} silencieusement.
    sig = "\n".join([
        "  wnd[0]/usr/lbl1\tGuiLabel\tSome label",
        "* wnd[0]/usr/chkNOT_THE_POPUP\tGuiCheckBox\t",     # fenêtre 0 : ne doit pas matcher
        "  wnd[1]/usr/lbl2\tGuiLabel\tChoisissez les champs",
        "* wnd[1]/usr/chkRSDBFIELD-CHECK\tGuiCheckBox\t",
        "* wnd[1]/usr/chkRSDBFIELD-CHECK2\tGuiCheckBox\t",  # 2e case -> ignorée, on prend la 1re
        "  wnd[1]/tbar[0]/btn[0]\tGuiButton\tOK",
    ])
    rc = _run_snippet(tmp_path, [
        "${sig}=    Set Variable    %s" % _robot_escaped(sig),
        "${chk}=    Evaluate    %s" % expr,
        "Should Be Equal    ${chk}    wnd[1]/usr/chkRSDBFIELD-CHECK",
    ])
    assert rc == 0


def test_checkbox_picker_returns_empty_when_no_popup_checkbox(tmp_path):
    expr = _extract_evaluate_expr(_CHECKBOX_MARKER)
    sig = "  wnd[1]/usr/lbl\tGuiLabel\tNo checkbox here"
    rc = _run_snippet(tmp_path, [
        "${sig}=    Set Variable    %s" % _robot_escaped(sig),
        "${chk}=    Evaluate    %s" % expr,
        "Should Be Equal    ${chk}    ${EMPTY}",
    ])
    assert rc == 0


# --- Count Entries On Current Selection Screen : séparateurs de milliers ------

_COUNT_MARKER = "int(''.join(c for c in $raw if c.isdigit())"


@pytest.mark.parametrize("raw, expected", [
    ("1,234", 1234),    # séparateur virgule (profil US)
    ("1 234", 1234),    # séparateur espace (profil FR)
    ("1.234", 1234),    # séparateur point (profil DE)
    ("0", 0),
    ("", 0),            # table vide -> compteur vide
    ("42", 42),
])
def test_count_parser_strips_thousands_separators(tmp_path, raw, expected):
    expr = _extract_evaluate_expr(_COUNT_MARKER)
    rc = _run_snippet(tmp_path, [
        "${raw}=    Set Variable    %s" % (raw if raw else "${EMPTY}"),
        "${count}=    Evaluate    %s" % expr,
        "Should Be Equal As Integers    ${count}    %s" % expected,
    ])
    assert rc == 0


def test_count_parser_is_not_the_backslash_regex_that_silently_broke():
    # Non-régression explicite du bug détecté en construisant ce test : un motif
    # `\D`/`\d` écrit dans une cellule .resource traverse DEUX couches
    # d'échappement (parsing du fichier, puis Evaluate) qui rongent le backslash
    # et transforment silencieusement la regex en un motif sans rapport (`D` au
    # lieu de `\D`) : aucune erreur de syntaxe, juste un mauvais résultat.
    expr = _extract_evaluate_expr(_COUNT_MARKER)
    assert "\\" not in expr, (
        "L'expression de comptage réintroduit un backslash ; cf. le piège "
        "d'échappement Robot documenté dans ecc_keywords.resource avant de "
        "le retirer.")


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
