"""Tests hors navigateur de `Wait For Ui5 Idle`, `Get Ui5 Messages` /
`Ui5 Should Have No Messages Of Type` et `Upload File Via Ui5` : la frontière
``_evaluate``/``_browser`` est stubbée ; le bundle JS est vérifié
textuellement (instrumentation réseau, hook toast, exports)."""
import pytest

from SapFioriLibrary import SapFioriLibrary
from SapFioriLibrary._ui5_js import BUNDLE


# --- le bundle embarque bien les nouvelles briques ---------------------------

def test_bundle_instrumente_reseau_toasts_et_exporte():
    assert "XMLHttpRequest.prototype.send" in BUNDLE
    assert "window.fetch" in BUNDLE
    assert "sapUiLocalBusyIndicator" in BUNDLE
    assert "sap/m/MessageToast" in BUNDLE
    assert "idleState: idleState" in BUNDLE
    assert "getMessages: getMessages" in BUNDLE


# --- Wait For Ui5 Idle -------------------------------------------------------

def _idle_lib(states):
    lib = SapFioriLibrary(ui5_timeout="2s", poll_interval="0.01s")
    queue = list(states)
    lib._evaluate = lambda js, arg=None: (queue.pop(0) if len(queue) > 1
                                          else queue[0])
    return lib


def test_wait_for_ui5_idle_attend_le_calme_reseau():
    lib = _idle_lib([
        {"pending": 2, "busy": False, "quiet_ms": 0},
        {"pending": 0, "busy": True, "quiet_ms": 0},
        {"pending": 0, "busy": False, "quiet_ms": 450},
    ])
    state = lib.wait_for_ui5_idle(settle="300 ms")
    assert state == {"pending": 0, "busy": False, "quiet_ms": 450}


def test_wait_for_ui5_idle_respecte_le_settle():
    # calme, mais pas encore ASSEZ longtemps : le keyword doit re-sonder
    lib = _idle_lib([
        {"pending": 0, "busy": False, "quiet_ms": 100},
        {"pending": 0, "busy": False, "quiet_ms": 500},
    ])
    assert lib.wait_for_ui5_idle(settle="300 ms")["quiet_ms"] == 500


def test_wait_for_ui5_idle_timeout_nomme_le_diagnostic():
    lib = _idle_lib([{"pending": 3, "busy": False, "quiet_ms": 0}])
    with pytest.raises(AssertionError) as err:
        lib.wait_for_ui5_idle(timeout="0.05s")
    message = str(err.value)
    assert "Log Fiori Diagnostics" in message and "'pending': 3" in message


def test_wait_for_ui5_idle_tolere_les_erreurs_js_transitoires():
    lib = SapFioriLibrary(ui5_timeout="2s", poll_interval="0.01s")
    calls = {"n": 0}

    def evaluate(js, arg=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("navigation en cours")
        return {"pending": 0, "busy": False, "quiet_ms": 999}

    lib._evaluate = evaluate
    assert lib.wait_for_ui5_idle()["quiet_ms"] == 999


# --- Get Ui5 Messages --------------------------------------------------------

_MESSAGES = {
    "messages": [
        {"type": "Error", "message": "Champ obligatoire", "target": "/x",
         "description": ""},
        {"type": "Success", "message": "Créé", "target": "", "description": ""},
    ],
    "toasts": [{"text": "Sauvegardé", "time": 1}],
}


def test_get_ui5_messages_json_safe_et_toasts_optionnels():
    lib = SapFioriLibrary()
    lib._evaluate = lambda js, arg=None: dict(_MESSAGES,
                                              toasts=list(_MESSAGES["toasts"]))
    result = lib.get_ui5_messages()
    assert [m["type"] for m in result["messages"]] == ["Error", "Success"]
    assert result["toasts"][0]["text"] == "Sauvegardé"
    sans_toasts = lib.get_ui5_messages(include_toasts=False)
    assert "toasts" not in sans_toasts


def test_get_ui5_messages_sans_runtime_nomme_la_sonde():
    lib = SapFioriLibrary()
    lib._evaluate = lambda js, arg=None: None
    with pytest.raises(AssertionError) as err:
        lib.get_ui5_messages()
    message = str(err.value)
    assert "Ui5 Runtime Is Present" in message
    assert "Get Page Composition" in message


# --- Ui5 Runtime Is Present : la sonde qui n'injecte rien --------------------

def test_la_sonde_de_runtime_repond_par_un_booleen():
    lib = SapFioriLibrary()
    lib._evaluate = lambda js, arg=None: True
    assert lib.ui5_runtime_is_present() is True
    lib._evaluate = lambda js, arg=None: False
    assert lib.ui5_runtime_is_present() is False


def test_la_sonde_de_runtime_n_echoue_jamais():
    """C'est une SONDE : une page injoignable (navigation en cours, pas de page
    du tout) répond « pas de runtime », elle ne lève pas. Sans cela, elle ne
    pourrait pas servir à décider si l'on ose appeler un keyword UI5."""
    lib = SapFioriLibrary()

    def boom(js, arg=None):
        raise RuntimeError("aucune page ouverte")

    lib._evaluate = boom
    assert lib.ui5_runtime_is_present() is False


def test_l_etat_agrege_tient_en_un_appel_et_sonde_avant_de_lire():
    """L'état du canal web est assemblé côté bibliothèque : un consommateur
    (le state provider rf-mcp) paierait sinon un aller-retour de contexte
    Robot Framework PAR section, ce qui domine largement le coût du JS.

    L'ordre est la moitié du contrat : le runtime est sondé AVANT la lecture
    des messages, qui l'exige et installe le bundle."""
    lib = SapFioriLibrary()
    lib._ui5_frame = "iframe#app"
    vus = []

    def evaluate(js, arg=None):
        vus.append("probe" if BUNDLE not in js else "bundle")
        return True if BUNDLE not in js else dict(_MESSAGES)

    lib._evaluate = evaluate
    state = lib.get_ui5_application_state()
    assert state["frame_stack"] == ["iframe#app"]
    assert state["ui5_runtime"] is True
    assert state["messages"]["messages"][0]["type"] == "Error"
    assert vus == ["probe", "bundle"]


def test_l_etat_agrege_ne_lit_pas_les_messages_hors_runtime_ui5():
    lib = SapFioriLibrary()
    vus = []

    def evaluate(js, arg=None):
        vus.append("probe" if BUNDLE not in js else "bundle")
        return False

    lib._evaluate = evaluate
    state = lib.get_ui5_application_state()
    assert state == {"frame_stack": [], "ui5_runtime": False}
    # rien d'autre n'a été évalué : pas d'échec inutile, pas d'injection
    assert vus == ["probe"]


def test_l_etat_agrege_consigne_une_lecture_de_messages_en_echec():
    lib = SapFioriLibrary()

    def evaluate(js, arg=None):
        if BUNDLE not in js:
            return True
        raise RuntimeError("Pas de page ouverte")

    lib._evaluate = evaluate
    state = lib.get_ui5_application_state()
    assert state["ui5_runtime"] is True
    assert "messages" not in state
    assert "Pas de page ouverte" in state["messages_error"]


def test_la_sonde_de_runtime_n_injecte_pas_le_bundle():
    """La propriété qui justifie son existence : toute autre expression web du
    dépôt (ré)installe ``__SAPFX``, donc instrumente ``fetch`` et
    ``XMLHttpRequest`` dans l'application sous test. Une simple lecture d'état
    (celle que sert le state provider rf-mcp après chaque étape) ne doit rien
    modifier."""
    from SapFioriLibrary._ui5_js import GET_MESSAGES_JS, UI5_RUNTIME_PROBE_JS

    assert BUNDLE not in UI5_RUNTIME_PROBE_JS
    assert "window.__SAPFX" not in UI5_RUNTIME_PROBE_JS
    assert BUNDLE in GET_MESSAGES_JS          # contre-épreuve
    # Playwright ne lance pas un littéral de fonction qui commence par un blanc.
    assert UI5_RUNTIME_PROBE_JS.startswith("(")
    # Même logique que `isUI5()` du bundle : classe Element par AMD, sinon Core.
    for marqueur in ("sap/ui/core/Element", "getElementById", "registry",
                     "getCore", "byId"):
        assert marqueur in UI5_RUNTIME_PROBE_JS, marqueur


def test_ui5_should_have_no_messages_of_type():
    lib = SapFioriLibrary()
    lib._evaluate = lambda js, arg=None: dict(_MESSAGES)
    with pytest.raises(AssertionError) as err:
        lib.ui5_should_have_no_messages_of_type("Error")
    assert "Champ obligatoire" in str(err.value)
    # les Success ne bloquent pas la vérification des Warning
    lib.ui5_should_have_no_messages_of_type("Warning")


# --- Upload File Via Ui5 -----------------------------------------------------

class _FakeBrowser:
    def __init__(self):
        self.uploads = []

    def upload_file_by_selector(self, selector, path):
        self.uploads.append((selector, path))


def test_upload_file_via_ui5_vise_l_input_interne():
    lib = SapFioriLibrary(ui5_timeout="1s", poll_interval="0.01s")
    browser = _FakeBrowser()
    lib._browser = lambda: browser
    lib._resolve = lambda js, arg, description, timeout=None: ["upl-1"]
    lib.upload_file_via_ui5("C:/tmp/doc.pdf", controlType="FileUploader")
    assert browser.uploads == [
        ('css=[id="upl-1"] input[type="file"]', "C:/tmp/doc.pdf")]


def test_upload_file_via_ui5_prefixe_la_frame_ciblee():
    lib = SapFioriLibrary(ui5_timeout="1s", poll_interval="0.01s")
    browser = _FakeBrowser()
    lib._browser = lambda: browser
    lib._resolve = lambda js, arg, description, timeout=None: ["upl-1"]
    lib.set_ui5_frame('iframe[id*="application"]')
    lib.upload_file_via_ui5("f.txt", controlType="FileUploader")
    assert browser.uploads[0][0].startswith('iframe[id*="application"] >>> ')


def test_upload_file_via_ui5_echec_actionnable_sans_controle():
    lib = SapFioriLibrary(ui5_timeout="0.05s", poll_interval="0.01s")
    lib._browser = lambda: _FakeBrowser()
    lib._resolve = lambda js, arg, description, timeout=None: []
    lib._relaxed_hint = lambda parts: ""
    with pytest.raises(AssertionError, match="No UI5 control matched"):
        lib.upload_file_via_ui5("f.txt", controlType="FileUploader")
