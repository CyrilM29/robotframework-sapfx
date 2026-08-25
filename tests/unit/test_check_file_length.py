"""Le garde de la convention #13 (``scripts/check_file_length.py``) MORD.

Trois propriétés, dont deux contre-épreuves (un garde qui ne peut pas échouer
ne protège rien, leçon des gardes refaits en 0.6.7) :

* l'arbre réel est conforme : aucun fichier de code suivi au-delà de
  500 lignes hors allowlist : c'est la preuve d'apurement de la dette du
  2026-08-25 ;
* contre-épreuve : un fichier synthétique de 501 lignes est refusé, avec le
  message qui nomme la couture (jamais « couper à la ligne 500 ») ;
* le périmètre est celui de la règle : un artefact GÉNÉRÉ (le recorder web
  émis par ``regen_recorder``) et un fichier non-code sont ignorés, et une
  entrée d'allowlist au compte périmé échoue (l'exemption est bornée).
"""
import importlib.util
import os

import pytest

_SCRIPT = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "check_file_length.py"))


def _load():
    spec = importlib.util.spec_from_file_location("check_file_length", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load()


def test_l_arbre_reel_est_conforme():
    # La preuve mécanique de l'apurement : la dette des 23 fichiers du
    # 2026-08-25 est soldée, et aucun nouveau fichier ne l'a rejointe.
    # Le périmètre se lit par `git ls-files`, donc il n'existe pas hors d'un
    # dépôt : l'arbre exporté vers le dépôt public est validé AVANT d'être
    # poussé, et il est alors un simple dossier. On saute plutôt que de
    # passer à vide, ce que l'assertion suivante interdit précisément.
    if not os.path.isdir(os.path.join(guard._ROOT, ".git")):
        pytest.skip("hors d'un dépôt git : le périmètre se lit par git ls-files")
    rels = [p for p in guard.tracked_files(guard._ROOT) if guard.is_scanned(p)]
    assert rels, "le périmètre ne peut pas être vide"
    assert guard.check(guard._ROOT, rels) == []


def test_l_allowlist_est_vide_ou_bornee():
    # État visé : plus aucune dette. Si une entrée revient un jour, elle doit
    # porter un compte et une raison (le modèle du garde du cadratin).
    for rel, (count, reason) in guard.ALLOWED.items():
        assert isinstance(count, int) and count > guard.MAX_LINES
        assert reason.strip()
        assert (guard._ROOT / rel).exists(), f"exemption morte : {rel}"


def test_contre_epreuve_un_fichier_trop_long_est_refuse(tmp_path):
    long_file = tmp_path / "gros.py"
    long_file.write_text("x = 1\n" * (guard.MAX_LINES + 1), encoding="utf-8")
    problems = guard.check(tmp_path, ["gros.py"])
    assert len(problems) == 1
    assert "501 lignes" in problems[0]
    assert "couture" in problems[0]          # le message nomme le remède
    assert "convention #13" in problems[0]


def test_contre_epreuve_un_compte_d_allowlist_perime_echoue(tmp_path, monkeypatch):
    long_file = tmp_path / "dette.py"
    long_file.write_text("x = 1\n" * 600, encoding="utf-8")
    monkeypatch.setattr(guard, "ALLOWED",
                        {"dette.py": (700, "dette déclarée pour le test")})
    problems = guard.check(tmp_path, ["dette.py"])
    assert len(problems) == 1
    assert "l'allowlist en épingle 700" in problems[0]
    # au compte exact, l'exemption joue : aucune violation
    monkeypatch.setattr(guard, "ALLOWED",
                        {"dette.py": (600, "dette déclarée pour le test")})
    assert guard.check(tmp_path, ["dette.py"]) == []


def test_le_perimetre_suit_la_regle():
    # Générés : la limite s'applique au générateur, pas à l'artefact.
    assert not guard.is_scanned("tools/recorder_web/recorder_snippet.js")
    assert not guard.is_scanned("tools/recorder_web/extension/recorder.js")
    # Hors périmètre par nature : vendorisé, comms, non-code.
    assert not guard.is_scanned("src/SapEccLibrary/_vendor/sapgui_base.py")
    assert not guard.is_scanned("comms/deck/build_deck_fr.py")
    assert not guard.is_scanned("docs/architecture.md")
    assert not guard.is_scanned("resources/page_objects/abap_flp.resource")
    assert not guard.is_scanned("tests/robot/ecc_smoke.robot")
    # Dans le périmètre : le code, y compris les gabarits JS injectés.
    assert guard.is_scanned("src/SapFioriLibrary/_ui5_bundle_core.js.tpl")
    assert guard.is_scanned("tools/recorder/sapgui_recorder.py")
    assert guard.is_scanned("packaging/install.ps1")
