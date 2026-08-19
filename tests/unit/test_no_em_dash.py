"""Tests du garde anti-tiret cadratin (``scripts/check_no_em_dash.py``).

Le garde rend mécanique une règle jusque-là seulement énoncée : pas de « — »
dans la rédaction du dépôt. On teste la logique pure sur un arbre jetable, puis
on vérifie que le VRAI dépôt passe le garde : c'est ce dernier test qui empêche
la règle de se dégrader silencieusement au fil des commits.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

import check_no_em_dash as guard  # noqa: E402

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _write(tmp_path, rel, text):
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_find_occurrences_donne_ligne_et_extrait():
    text = "ligne propre\nun terme — son explication\n"
    found = guard.find_occurrences(text)
    assert len(found) == 1
    lineno, excerpt = found[0]
    assert lineno == 2
    assert "son explication" in excerpt


def test_find_occurrences_compte_plusieurs_cadratins_sur_une_ligne():
    # L'incise « — x — » en porte deux : les compter séparément, sinon une
    # incise fermée passerait pour une seule violation.
    assert len(guard.find_occurrences("a — b — c")) == 2


def test_find_occurrences_ignore_demi_cadratin_et_trait_d_union():
    # Le demi-cadratin (intervalles : « 0.31–0.35 ») et le trait d'union sont
    # d'autres signes : les confondre rendrait le garde inutilisable.
    assert guard.find_occurrences("plage 0.31–0.35, mot-composé") == []


@pytest.mark.parametrize("rel, scanned", [
    ("docs/architecture.md", True),
    ("src/SapEccLibrary/keywords/_waits.py", True),
    ("src/SapEccLibrary/_vendor/sapgui_base.py", False),  # convention #4
    ("results/output.xml", False),
    ("assets/logo.png", False),
    ("docs/media/demo.mp4", False),
])
def test_perimetre_du_garde(rel, scanned):
    assert guard.is_scanned(rel) is scanned


def test_check_signale_un_cadratin_et_nomme_le_fichier(tmp_path):
    _write(tmp_path, "docs/x.md", "titre — sous-titre\n")
    problems = guard.check(tmp_path, [str(tmp_path / "docs" / "x.md")])
    assert len(problems) == 1
    assert "docs/x.md:1" in problems[0]


def test_check_est_muet_sur_un_texte_conforme(tmp_path):
    _write(tmp_path, "docs/x.md", "titre : sous-titre, et une incise (ainsi).\n")
    assert guard.check(tmp_path, [str(tmp_path / "docs" / "x.md")]) == []


def test_check_ignore_le_code_vendorise(tmp_path):
    # Le vendor est upstream verbatim : le garde ne doit jamais pousser à
    # l'éditer, sinon il entre en conflit avec la convention #4.
    rel = "src/SapEccLibrary/_vendor/sapgui_base.py"
    _write(tmp_path, rel, "# amont — verbatim\n")
    assert guard.check(tmp_path, [str(tmp_path / rel)]) == []


def test_un_repertoire_cible_est_developpe_recursivement(tmp_path):
    # Régression : un répertoire en argument était accepté puis ignoré en
    # silence (``read_text`` lève dessus, erreur avalée comme celle d'un
    # binaire), et le garde répondait « OK (ciblé) » sans avoir rien lu.
    _write(tmp_path, "docs/sous/x.md", "titre — sous-titre\n")
    problems = guard.check(tmp_path, [str(tmp_path / "docs")])
    assert len(problems) == 1
    assert "docs/sous/x.md:1" in problems[0]


def test_un_repertoire_cible_respecte_les_exemptions(tmp_path):
    _write(tmp_path, "src/SapEccLibrary/_vendor/x.py", "# amont — verbatim\n")
    _write(tmp_path, "results/run.md", "rapport — de run\n")
    assert guard.check(tmp_path, [str(tmp_path)]) == []


def test_une_cible_hors_depot_est_ignoree(tmp_path):
    # Le hook voit passer les fichiers d'autres arbres (base mémoire privée) :
    # ils ont leurs propres règles.
    autre = tmp_path.parent / (tmp_path.name + "_ailleurs")
    autre.mkdir()
    (autre / "x.md").write_text("titre — sous-titre\n", encoding="utf-8")
    assert guard.check(tmp_path, [str(autre / "x.md")]) == []


def test_le_depot_reel_passe_le_garde():
    """Le test qui tient la règle dans la durée : l'arbre suivi est conforme."""
    problems = guard.check(_ROOT)
    assert problems == [], "tirets cadratins introduits :\n" + "\n".join(problems)


def test_le_garde_s_execute_en_ligne_de_commande():
    # Le hook post-édition et la CI l'appellent en sous-processus : vérifier le
    # code de sortie, pas seulement l'API Python.
    result = subprocess.run(
        [sys.executable, os.path.join(_ROOT, "scripts", "check_no_em_dash.py")],
        cwd=_ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace")
    assert result.returncode == 0, result.stdout + result.stderr
