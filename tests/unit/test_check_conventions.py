"""Tests du garde mécanique des conventions #1 (localisateurs bruts), #2
(``Sleep``) et #12 (JS inline / ``__import__`` dans la couche Robot) :
``scripts/check_conventions.py``.

Couvre la nuance propre à ce dépôt : les conventions #1 et #12 sont
bloquantes dans les suites GÉNÉRÉES (marqueur de provenance) et seulement
informatives dans les suites de validation de la bibliothèque, dont l'objet
est de piloter SAP par ses ids bruts ou de planter du JS d'épreuve ; la
convention #2 est bloquante partout ; la #12 est bloquante dans
``resources/`` sous réserve de l'allowlist à compte exact ``ALLOWED_12``.
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


class TestConventionDouze:
    """JS inline et ``__import__`` : la capacité appartient à la bibliothèque.

    L'allowlist ``ALLOWED_12`` est à COMPTE EXACT (modèle du garde du
    cadratin) : une occurrence de plus échoue, une de moins aussi (entrée
    périmée), et chaque entrée doit désigner un fichier RÉEL du dépôt.
    """

    @pytest.mark.parametrize("ligne", [
        "    ${x}=    Evaluate JavaScript    ${None}    () => 1\n",
        "    Wait For Function    () => true    timeout=5s\n",
        "    ${x}=    Browser.Evaluate JavaScript    ${None}    () => 1\n",
        "    ${h}=    Evaluate    __import__('json').dumps($d)\n",
    ])
    def test_js_inline_et_dunder_import_bloquent_dans_une_resource(
            self, tmp_path, ligne):
        repo = _repo(tmp_path)
        _resource(repo, "*** Keywords ***\nLire\n" + ligne)
        assert conv_mod.check(repo) == 1

    def test_modules_bloque_dans_une_suite_generee(self, tmp_path):
        repo = _repo(tmp_path)
        _suite(repo, "*** Test Cases ***\nCas\n"
                     "    ${h}=    Evaluate    urllib.parse.urlparse($u).netloc"
                     "    modules=urllib.parse\n", generated=True)
        assert conv_mod.check(repo) == 1

    def test_modules_reste_permis_dans_une_resource(self, tmp_path):
        """La décision DDIC ne proscrit ``modules=`` que dans les SUITES : la
        couche resources garde le droit d'importer un sous-module."""
        repo = _repo(tmp_path)
        _resource(repo, "*** Keywords ***\nDecoder\n"
                        "    ${v}=    Evaluate    urllib.parse.unquote($f)"
                        "    modules=urllib.parse\n")
        assert conv_mod.check(repo) == 0

    def test_js_inline_informatif_dans_une_suite_non_generee(self, tmp_path):
        """Les smokes de validation PLANTENT du JS d'épreuve à dessein
        (bundle périmé, CSP) : signalés, jamais bloquants hors --strict."""
        repo = _repo(tmp_path)
        _suite(repo, "*** Test Cases ***\nCas\n"
                     "    Evaluate JavaScript    ${None}    () => 1\n")
        assert conv_mod.check(repo) == 0
        assert conv_mod.check(repo, strict=True) == 1

    def test_allowlist_au_compte_exact(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path)
        _resource(repo, "*** Keywords ***\nMarquer\n"
                        "    Evaluate JavaScript    ${None}    () => 1\n"
                        "    Evaluate JavaScript    ${None}    () => 2\n")
        rel = "resources/page_objects/p.resource"
        monkeypatch.setattr(conv_mod, "ALLOWED_12", {rel: 2})
        assert conv_mod.check(repo) == 0
        # une occurrence de PLUS que le compte déclaré échoue...
        monkeypatch.setattr(conv_mod, "ALLOWED_12", {rel: 1})
        assert conv_mod.check(repo) == 1
        # ...et une de MOINS aussi : l'allowlist périmée doit se voir.
        monkeypatch.setattr(conv_mod, "ALLOWED_12", {rel: 3})
        assert conv_mod.check(repo) == 1

    def test_les_entrees_allowlist_designent_le_vrai_arbre(self):
        """Anti-entrée morte : chaque chemin d'ALLOWED_12 existe dans le dépôt
        et son compte RÉEL de sondes assumées vaut le compte déclaré."""
        racine = Path(__file__).resolve().parents[2]
        for rel, attendu in conv_mod.ALLOWED_12.items():
            fichier = racine / rel
            assert fichier.exists(), "entrée ALLOWED_12 morte : %s" % rel
            problemes = conv_mod.scan_file(fichier, forbid_locators=False)
            reel = sum(1 for p in problemes if p[2] == 12)
            assert reel == attendu, (
                "%s : %d sonde(s) réelle(s) pour %d déclarée(s)"
                % (rel, reel, attendu))


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
