"""Tests du garde mécanique des conventions #1 (localisateurs bruts) et #2
(``Sleep``) : ``scripts/check_conventions.py``.

Couvre la nuance propre à ce dépôt : la convention #1 est bloquante dans les
suites GÉNÉRÉES (marqueur de provenance) et seulement informative dans les
suites de validation de la bibliothèque, dont l'objet est de piloter SAP par
ses ids bruts ; la convention #2 est bloquante partout.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_conventions.py"
_spec = importlib.util.spec_from_file_location("check_conventions", _SCRIPT)
conv_mod = importlib.util.module_from_spec(_spec)
sys.modules["check_conventions"] = conv_mod
_spec.loader.exec_module(conv_mod)

_STAMP = "...                 Spec: specs/plan.md (sha256:0123456789ab, 2026-07-24)\n"


def _repo(tmp_path):
    (tmp_path / "tests" / "robot").mkdir(parents=True)
    (tmp_path / "resources" / "page_objects").mkdir(parents=True)
    return tmp_path


def _suite(repo, body, generated=False, name="s.robot"):
    header = "*** Settings ***\nDocumentation     Suite de test.\n"
    if generated:
        header += _STAMP
    path = repo / "tests" / "robot" / name
    path.write_text(header + "\n" + body, encoding="utf-8")
    return path


def _resource(repo, body):
    path = repo / "resources" / "page_objects" / "p.resource"
    path.write_text(body, encoding="utf-8")
    return path


class TestConventionUnSuitesGenerees:
    """Suite générée = tests métier : la convention #1 est bloquante."""

    @pytest.mark.parametrize("cellule", [
        "wnd[0]/usr/ctxtRF02K-KUNNR",
        "wnd[1]/tbar[0]/btn[0]",
        "wnd[0]/usr/cntlGRID1/shellcont/shell",
        "/app/con[0]/ses[0]/wnd[0]/usr/txtX",
        "css=#login",
        "xpath=//input[1]",
        "//div[@id='x']",
        "controlType=sap.m.Button",
        "bindingPath=/Flights('X')",
    ])
    def test_localisateur_brut_bloque(self, tmp_path, cellule):
        repo = _repo(tmp_path)
        _suite(repo, "*** Test Cases ***\nCas\n    Input Text    %s    v\n"
               % cellule, generated=True)
        assert conv_mod.check(repo) == 1

    def test_suite_generee_propre_passe(self, tmp_path):
        repo = _repo(tmp_path)
        _suite(repo, "*** Test Cases ***\nCas\n"
                     "    Open SAP And Log In\n"
                     "    Consulter Les Liaisons SPFLI\n"
                     "    Wait Until Busy Done\n", generated=True)
        assert conv_mod.check(repo) == 0


class TestConventionUnSuitesNonGenerees:
    """Validation de la bibliothèque : ids bruts assumés, non bloquants."""

    def test_ids_bruts_non_bloquants(self, tmp_path):
        repo = _repo(tmp_path)
        _suite(repo, "*** Test Cases ***\nCas\n"
                     "    Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    SFLIGHT\n")
        assert conv_mod.check(repo) == 0

    def test_mais_bloquants_en_strict(self, tmp_path):
        repo = _repo(tmp_path)
        _suite(repo, "*** Test Cases ***\nCas\n"
                     "    Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    SFLIGHT\n")
        assert conv_mod.check(repo, strict=True) == 1

    def test_le_marqueur_de_provenance_est_bien_detecte(self, tmp_path):
        repo = _repo(tmp_path)
        brut = _suite(repo, "*** Test Cases ***\nCas\n    No Operation\n",
                      name="brut.robot")
        genere = _suite(repo, "*** Test Cases ***\nCas\n    No Operation\n",
                        generated=True, name="genere.robot")
        assert conv_mod.is_generated_suite(brut) is False
        assert conv_mod.is_generated_suite(genere) is True


class TestConventionDeux:
    """Le Sleep est bloquant partout : généré ou pas, test ou resource."""

    def test_sleep_dans_suite_generee(self, tmp_path):
        repo = _repo(tmp_path)
        _suite(repo, "*** Test Cases ***\nCas\n    Sleep    2s\n",
               generated=True)
        assert conv_mod.check(repo) == 1

    def test_sleep_dans_suite_non_generee(self, tmp_path):
        repo = _repo(tmp_path)
        _suite(repo, "*** Test Cases ***\nCas\n    Sleep    2s\n")
        assert conv_mod.check(repo) == 1

    def test_sleep_qualifie_dans_une_resource(self, tmp_path):
        repo = _repo(tmp_path)
        _resource(repo, "*** Keywords ***\nAttendre\n    BuiltIn.Sleep    1s\n")
        assert conv_mod.check(repo) == 1

    def test_attentes_reelles_autorisees(self, tmp_path):
        repo = _repo(tmp_path)
        _resource(repo, "*** Keywords ***\nAttendre\n"
                        "    Wait Until Busy Done\n"
                        "    Wait Until Element Present    ${LOC}    timeout=10\n")
        assert conv_mod.check(repo) == 0


class TestPerimetreEtBruit:
    def test_locators_autorises_dans_les_resources(self, tmp_path):
        repo = _repo(tmp_path)
        _resource(repo, "*** Variables ***\n"
                        "${CHAMP_TABLE}    wnd[0]/usr/ctxtDATABROWSE-TABLENAME\n")
        assert conv_mod.check(repo) == 0

    def test_documentation_et_commentaires_ignores(self, tmp_path):
        repo = _repo(tmp_path)
        _suite(repo, "*** Test Cases ***\nCas\n"
                     "    [Documentation]    Résout wnd[0]/usr/ctxtX en interne.\n"
                     "    ...                et css=#autre pour Fiori.\n"
                     "    # wnd[0]/tbar[0]/okcd en commentaire\n"
                     "    No Operation\n", generated=True)
        assert conv_mod.check(repo) == 0

    def test_url_et_arguments_nommes_non_confondus(self, tmp_path):
        repo = _repo(tmp_path)
        _suite(repo, "*** Test Cases ***\nCas\n"
                     "    Open Fiori App    https://exemple.test/flp\n"
                     "    Wait Until Element Present    ${LOC}    timeout=10\n",
               generated=True)
        assert conv_mod.check(repo) == 0

    def test_cible_explicite(self, tmp_path):
        repo = _repo(tmp_path)
        suite = _suite(repo, "*** Test Cases ***\nCas\n    Sleep    1s\n")
        assert conv_mod.check(repo, [str(suite.relative_to(repo))]) == 1

    def test_workspace_vide_passe(self, tmp_path):
        assert conv_mod.check(_repo(tmp_path)) == 0
