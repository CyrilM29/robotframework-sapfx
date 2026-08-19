"""Tests off-SAP du pont contexte-RF (``sap_robotmcp._rf_context``) : le contrat
texte historique et le canal ``allow_structured`` des keywords d'état
(convention #5 du CLAUDE.md). Le vrai gestionnaire de contexte rf-mcp est
doublé : aucune session SAP/Robot réelle.
"""
import pytest

robotmcp = pytest.importorskip("robotmcp", reason="rf-mcp non installé")

import robotmcp.components.execution.rf_native_context_manager as rf_ctx_mod  # noqa: E402

from sap_robotmcp._rf_context import run_keyword_in_context  # noqa: E402


class _FakeSession:
    session_id = "session-1"
    variables = {}


class _FakeManager:
    def __init__(self, result):
        self._result = result

    def execute_keyword_with_context(self, **kwargs):
        return self._result


def _patch_manager(monkeypatch, result):
    monkeypatch.setattr(rf_ctx_mod, "get_rf_native_context_manager",
                        lambda: _FakeManager(result))


def test_text_contract_returns_the_output_string(monkeypatch):
    _patch_manager(monkeypatch, {"success": True, "output": "# screen X"})
    assert run_keyword_in_context(_FakeSession(), "Get Screen Signature") == "# screen X"


def test_text_contract_rejects_a_structured_value(monkeypatch):
    _patch_manager(monkeypatch, {"success": True, "result": {"a": 1}, "output": None})
    with pytest.raises(RuntimeError, match="sortie vide"):
        run_keyword_in_context(_FakeSession(), "Get Screen Signature")


def test_structured_contract_returns_the_result_value(monkeypatch):
    windows = [{"id": "wnd[0]", "modal": False}]
    _patch_manager(monkeypatch, {"success": True, "result": windows})
    out = run_keyword_in_context(_FakeSession(), "Get Open Windows",
                                 allow_structured=True)
    assert out == windows


def test_structured_contract_accepts_an_empty_list_as_a_real_value(monkeypatch):
    # [] est une VRAIE réponse (aucune fenêtre lisible), pas une sortie vide.
    _patch_manager(monkeypatch, {"success": True, "result": []})
    out = run_keyword_in_context(_FakeSession(), "Get Open Windows",
                                 allow_structured=True)
    assert out == []


def test_structured_contract_falls_back_to_the_text_output(monkeypatch):
    # Réponse SANS clé ``result`` (forme défensive / rf-mcp ancien) : la sortie
    # texte fait alors foi.
    _patch_manager(monkeypatch, {"success": True, "output": "SE16"})
    out = run_keyword_in_context(_FakeSession(), "Get Current Transaction",
                                 allow_structured=True)
    assert out == "SE16"


def test_structured_contract_flags_a_truly_empty_return(monkeypatch):
    """Forme RÉELLE d'un keyword qui ne retourne rien : rf-mcp met ``result``
    à ``None`` et écrit la chaîne "OK" dans ``output`` (deux sites de retour de
    son rf_native_context_manager).

    Le garde doit voir un retour vide, PAS servir "OK" : une section d'état
    indisponible arrivait sinon à l'agent sous la forme d'un franc « OK »,
    indistinguable d'une vraie valeur."""
    _patch_manager(monkeypatch, {"success": True, "result": None, "output": "OK"})
    with pytest.raises(RuntimeError, match="sortie vide"):
        run_keyword_in_context(_FakeSession(), "Get Open Windows",
                               allow_structured=True)


def test_la_sentinelle_ok_ne_passe_pas_pour_une_valeur(monkeypatch):
    # Même sans clé ``result`` (repli), la sentinelle "OK" reste un retour vide.
    _patch_manager(monkeypatch, {"success": True, "output": "OK"})
    with pytest.raises(RuntimeError, match="sortie vide"):
        run_keyword_in_context(_FakeSession(), "Get Open Windows",
                               allow_structured=True)


def test_un_keyword_qui_retourne_vraiment_ok_est_servi(monkeypatch):
    # Contre-épreuve : "OK" RETOURNÉ par le keyword arrive dans ``result``, et
    # la sentinelle ne doit pas l'effacer.
    _patch_manager(monkeypatch, {"success": True, "result": "OK", "output": "OK"})
    assert run_keyword_in_context(_FakeSession(), "Get Status Message",
                                  allow_structured=True) == "OK"


def test_le_contrat_texte_refuse_aussi_la_sentinelle(monkeypatch):
    _patch_manager(monkeypatch, {"success": True, "result": None, "output": "OK"})
    with pytest.raises(RuntimeError, match="sortie vide"):
        run_keyword_in_context(_FakeSession(), "Get Screen Signature")


def test_le_saut_com_est_saute_sur_un_canal_sans_com(monkeypatch):
    """Les canaux Fiori (CDP) et API (HTTP) n'ont aucun objet COM : y appeler
    ``CoInitialize`` fait entrer durablement en appartement STA chaque worker
    frais du pool de threads, sans jamais de ``CoUninitialize``, pour rien."""
    import sap_robotmcp._rf_context as module

    appels = []
    monkeypatch.setattr(module, "ensure_com_initialized",
                        lambda: appels.append("com"))
    _patch_manager(monkeypatch, {"success": True, "result": "SE16"})
    run_keyword_in_context(_FakeSession(), "Get Current Transaction",
                           allow_structured=True)
    assert appels == ["com"]
    run_keyword_in_context(_FakeSession(), "Get Ui5 Frame Stack",
                           allow_structured=True, needs_com=False)
    assert appels == ["com"]


def test_rf_failure_surfaces_the_real_reason(monkeypatch):
    _patch_manager(monkeypatch, {"success": False, "error": "pas de session SAP"})
    with pytest.raises(RuntimeError, match="pas de session SAP"):
        run_keyword_in_context(_FakeSession(), "Get Open Windows",
                               allow_structured=True)
