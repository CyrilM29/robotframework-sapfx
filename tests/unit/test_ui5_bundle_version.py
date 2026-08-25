"""Tests hors navigateur du **bundle `__SAPFX` versionné** et du containment DOM.

Le comportement en page est prouvé par la suite hors ligne
`tests/robot/fiori_bundle_version_smoke.robot` (vrai navigateur : comptage des
incréments par requête, identité des enveloppes, survie de l'état à travers un
remplacement). Ici on verrouille ce qu'un test sans navigateur peut trancher :
la garde compare bien une VERSION, l'empreinte est stable et dérive du contenu,
et les hooks sont posés une fois sur un état porté par la fenêtre.
"""
import re

from SapFioriLibrary._ui5_js import BUNDLE, BUNDLE_VERSION, build_call, bundle_version
from SapFioriLibrary._ui5_runtime import build_control_selector, selector_to_json


def test_version_is_a_short_stable_fingerprint_of_the_content():
    assert re.fullmatch(r"[0-9a-f]{12}", BUNDLE_VERSION)
    assert bundle_version("meme texte") == bundle_version("meme texte")
    assert bundle_version("un texte") != bundle_version("un AUTRE texte")


def test_guard_compares_the_version_and_not_mere_presence():
    # La garde historique (`if (window.__SAPFX) return;`) gardait à vie le premier
    # bundle reçu : c'est exactement ce qu'on interdit ici.
    assert "if (window.__SAPFX && window.__SAPFX.__v === V) return;" in BUNDLE
    assert "if (window.__SAPFX) return;" not in BUNDLE
    # ...et le bundle installé s'annonce, sans quoi la garde n'aurait rien à lire.
    assert "window.__SAPFX = { __v: V," in BUNDLE
    assert ("const V = '%s';" % BUNDLE_VERSION) in BUNDLE
    # le marqueur de gabarit ne doit jamais atteindre la page
    assert "__SAPFX_BUNDLE_VERSION__" not in BUNDLE


def test_every_injected_call_carries_the_versioned_bundle():
    call = build_call("openPopups")
    assert BUNDLE_VERSION in call
    assert "window.__SAPFX.openPopups(arg)" in call


def test_hooks_are_installed_once_over_state_carried_by_the_window():
    # L'état vit sur la fenêtre : une réinstallation le RETROUVE au lieu de
    # repartir de zéro (sinon les requêtes en vol et les toasts déjà captés
    # seraient perdus).
    assert "window.__SAPFX_STATE ||" in BUNDLE
    assert "const NET = STATE.net;" in BUNDLE
    assert "const TOASTS = STATE.toasts;" in BUNDLE
    # Chaque enveloppe porte sa marque et n'est posée que si elle manque : sans
    # cela, chaque réinstallation empilerait une enveloppe, donc compterait
    # chaque requête une fois de plus.
    assert "if (!xhrSend.__sapfxHook)" in BUNDLE
    assert "if (window.fetch && !window.fetch.__sapfxHook)" in BUNDLE
    assert "xhrHook.__sapfxHook = true;" in BUNDLE
    assert "fetchHook.__sapfxHook = true;" in BUNDLE
    # Le hook de toasts se marque par son RÉCEPTACLE : un booléen laisserait un
    # hook d'une version antérieure remplir une liste orpheline.
    assert "MT.__sapfxToastSink === TOASTS" in BUNDLE
    assert "MT.__sapfxToastSink = TOASTS;" in BUNDLE


def test_runtime_probe_still_injects_nothing():
    # Une lecture d'état ne modifie pas la page : la sonde de runtime reste la
    # seule expression du module qui n'embarque pas le bundle (donc n'instrumente
    # ni fetch ni XHR).
    from SapFioriLibrary._ui5_js import UI5_RUNTIME_PROBE_JS
    assert "__SAPFX" not in UI5_RUNTIME_PROBE_JS
    assert BUNDLE_VERSION not in UI5_RUNTIME_PROBE_JS


def test_contained_in_is_a_selector_key_reaching_the_engine():
    sel = build_control_selector(controlType="sap.m.GenericTile",
                                 containedIn="__tile0")
    assert sel == {"controlType": "sap.m.GenericTile", "containedIn": "__tile0"}
    assert '"containedIn":"__tile0"' in selector_to_json(sel)


def test_contained_in_restricts_to_strict_dom_descendants():
    # Relation DOM, distincte de viewId (propriété/agrégation) : le conteneur est
    # cherché par id exact puis par suffixe, et il n'est pas son propre contenu.
    assert "function containerDom(wanted)" in BUNDLE
    assert "if (sel.containedIn) {" in BUNDLE
    assert "scope.contains(d)" in BUNDLE
    assert "d === scope" in BUNDLE
    # Conteneur introuvable ou non rendu : aucune correspondance, jamais un
    # périmètre élargi en silence.
    assert "scope = containerDom(sel.containedIn);\n      if (!scope) return [];" in BUNDLE
