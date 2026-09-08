"""Perception ECC : signature, carte @N, fenetres, GetObjectTree, screenshots. Doublures dans _perception_fixtures (convention #13)."""
from SapEccLibrary import SapEccLibrary
from pythoncom import com_error
import pytest

from _perception_fixtures import (  # noqa: F401
    FakeChildren,
    FakeNode,
    FakeSession,
    ObjectTreeSession,
    ScreenshotWindow,
    StaleChildrenNode,
    _PNG_BYTES,
    _TREE_JSON,
    _ecc_lib,
    _ecc_lib_actionable,
    _lib_with_session,
    _lib_with_windows,
)



def test_screen_signature_entete_porte_l_identite_d_ecran():
    sig = _ecc_lib().get_screen_signature()
    assert sig.splitlines()[0] == "# screen SAPLSMTR_NAVIGATION/SESSION_MANAGER/100"


def test_screen_signature_ids_relatifs_a_la_session():
    sig = _ecc_lib().get_screen_signature()
    # préfixe /app/con[0]/ses[0]/ retiré -> id collable dans un test
    assert "wnd[0]/usr/txtRSYST-BNAME" in sig
    assert "/app/con[0]" not in sig


def test_screen_signature_marque_les_champs_editables():
    lines = _ecc_lib().get_screen_signature().splitlines()
    field = next(line for line in lines if "txtRSYST-BNAME" in line)
    button = next(line for line in lines if "btn[0]" in line)
    assert field.startswith("* ")       # GuiTextField -> éditable
    assert button.startswith("  ")       # GuiButton -> non éditable


def test_screen_signature_defensif_si_pas_de_fenetre():
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession(None)
    sig = lib.get_screen_signature()
    assert sig.startswith("# screen")    # entête seule, pas d'exception


def test_screen_signature_defensif_si_children_leve_com_error():
    # un enfant dont .Children est périmé ne doit pas faire planter tout le
    # parcours : on garde sa propre ligne et on arrête simplement sa descente.
    stale = StaleChildrenNode("/app/con[0]/ses[0]/wnd[0]/usr/subScreen", "GuiContainerShell")
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP Easy Access", [stale])
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession(win)
    sig = lib.get_screen_signature()
    assert "usr/subScreen" in sig
    assert sig.startswith("# screen")


def test_get_screen_map_numerote_les_cibles_actionnables():
    lib = _ecc_lib_actionable()
    lines = lib.get_screen_map().splitlines()
    assert lines[0].startswith("# screen ")
    assert lines[1].startswith("@1\t")
    assert "txtRSYST-BNAME" in lines[1]      # champ saisissable = 1re cible
    assert lines[2].startswith("@2\t")
    assert "btn[0]" in lines[2]              # bouton = 2e cible
    assert len(lines) == 3                    # la fenêtre elle-même n'est pas une cible


def test_resolve_screen_ref_retourne_l_id_et_accepte_le_prefixe_arobase():
    lib = _ecc_lib_actionable()
    lib.get_screen_map()
    assert lib.resolve_screen_ref("1") == "wnd[0]/usr/txtRSYST-BNAME"
    assert lib.resolve_screen_ref("@2") == "wnd[0]/tbar[0]/btn[0]"


def test_resolve_screen_ref_sans_perception_erreur_actionnable():
    lib = _ecc_lib_actionable()
    with pytest.raises(AssertionError, match="Get Screen Map"):
        lib.resolve_screen_ref("1")


def test_resolve_screen_ref_inconnue_liste_la_plage_disponible():
    lib = _ecc_lib_actionable()
    lib.get_screen_map()
    with pytest.raises(AssertionError, match=r"@1\.\.@2"):
        lib.resolve_screen_ref("7")


def test_resolve_screen_ref_refuse_un_ecran_qui_a_change():
    lib = _ecc_lib_actionable()
    lib.get_screen_map()
    lib.session.Info.Transaction = "SE16"     # navigation depuis la perception
    with pytest.raises(AssertionError, match="re-percevoir"):
        lib.resolve_screen_ref("1")


def test_resolve_screen_ref_refuse_un_element_disparu():
    lib = _ecc_lib_actionable()
    lib.get_screen_map()
    lib.session.found_ids = set()             # même écran, cible retirée
    with pytest.raises(AssertionError, match="n'existe plus"):
        lib.resolve_screen_ref("1")


def test_click_et_fill_screen_ref_deleguent_aux_keywords_deterministes():
    lib = _ecc_lib_actionable()
    lib.get_screen_map()
    calls = []
    lib.click_element = lambda eid: calls.append(("click", eid))
    lib.input_text = lambda eid, value: calls.append(("fill", eid, value))
    assert lib.click_screen_ref("@2") == "wnd[0]/tbar[0]/btn[0]"
    assert lib.fill_screen_ref("1", "T000") == "wnd[0]/usr/txtRSYST-BNAME"
    assert calls == [("click", "wnd[0]/tbar[0]/btn[0]"),
                     ("fill", "wnd[0]/usr/txtRSYST-BNAME", "T000")]


def test_get_open_windows_liste_la_pile_et_marque_le_modal():
    main = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP Easy Access")
    popup = FakeNode("/app/con[0]/ses[0]/wnd[1]", "GuiModalWindow",
                     "Cannot start transaction ")
    windows = _lib_with_windows(FakeChildren([main, popup])).get_open_windows()
    assert windows == [
        {"id": "wnd[0]", "type": "GuiMainWindow",
         "title": "SAP Easy Access", "modal": False},
        {"id": "wnd[1]", "type": "GuiModalWindow",
         "title": "Cannot start transaction", "modal": True},
    ]


def test_get_open_windows_defensif_sans_session_lisible():
    class BrokenSession:
        @property
        def Children(self):
            raise com_error("session fermée")

    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = BrokenSession()
    # Depuis le 2026-09-07 : une session illisible ÉCHOUE en nommant la cause,
    # elle ne rend plus une liste vide (qu'un agent lirait « aucune fenêtre »).
    from SapEccLibrary.keywords._perception import ScreenUnreadableError
    with pytest.raises(ScreenUnreadableError, match="illisible"):
        lib.get_open_windows()


def test_get_open_windows_ignore_une_fenetre_illisible():
    class BrokenChildren(FakeChildren):
        def ElementAt(self, index):
            if index == 1:
                raise com_error("fenêtre disposée")
            return super().ElementAt(index)

    main = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "OK")
    ghost = FakeNode("/app/con[0]/ses[0]/wnd[9]", "GuiModalWindow", "?")
    windows = _lib_with_windows(BrokenChildren([main, ghost])).get_open_windows()
    assert [w["id"] for w in windows] == ["wnd[0]"]


def test_screen_signature_utilise_getobjecttree_quand_disponible():
    # la fenêtre COM n'a AUCUN enfant : si txtFAST-PATH apparaît, il vient
    # nécessairement du JSON GetObjectTree, pas de la marche COM.
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP", [])
    lib = _lib_with_session(ObjectTreeSession(win, _TREE_JSON))
    sig = lib.get_screen_signature()
    assert "wnd[0]/usr/txtFAST-PATH" in sig
    assert "/app/con[0]" not in sig          # ids relativisés aussi sur ce chemin
    field = next(line for line in sig.splitlines() if "txtFAST-PATH" in line)
    assert field.startswith("* ")            # GuiTextField -> éditable, comme avant


def test_screen_signature_format_identique_sur_les_deux_chemins():
    # même écran perçu via GetObjectTree et via la marche COM -> même signature
    txt = FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtFAST-PATH", "GuiTextField", "42")
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP", [txt])
    par_marche = _lib_with_session(FakeSession(win)).get_screen_signature()
    par_arbre = _lib_with_session(ObjectTreeSession(
        FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP", []),
        _TREE_JSON)).get_screen_signature()
    assert par_arbre == par_marche


def test_attributeerror_marque_l_api_absente_et_ne_retente_pas():
    txt = FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtA", "GuiTextField", "x")
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP", [txt])
    session = ObjectTreeSession(win, AttributeError("GetObjectTree absent"))
    lib = _lib_with_session(session)
    assert "txtA" in lib.get_screen_signature()   # repli marche COM
    lib.get_screen_signature()
    assert session.object_tree_calls == 1          # pas de nouvel essai


def test_com_error_replie_ponctuellement_mais_retente_au_prochain_appel():
    txt = FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtA", "GuiTextField", "x")
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP", [txt])
    session = ObjectTreeSession(win, com_error("transitoire"))
    lib = _lib_with_session(session)
    assert "txtA" in lib.get_screen_signature()
    lib.get_screen_signature()
    assert session.object_tree_calls == 2          # retenté : l'erreur était transitoire


def test_json_invalide_ou_vide_replie_sur_la_marche():
    txt = FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtA", "GuiTextField", "x")
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP", [txt])
    assert "txtA" in _lib_with_session(
        ObjectTreeSession(win, "pas du json {")).get_screen_signature()
    assert "txtA" in _lib_with_session(
        ObjectTreeSession(win, '{"children": []}')).get_screen_signature()


def test_include_geometry_ajoute_une_4e_colonne_optionnelle():
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP", [])
    lib = _lib_with_session(ObjectTreeSession(win, _TREE_JSON))
    avec = lib.get_screen_signature(include_geometry=True)
    field = next(line for line in avec.splitlines() if "txtFAST-PATH" in line)
    assert field.endswith("\t@10,20 110x22")
    # par défaut : format 3 colonnes inchangé (contrat du filtrage rf-mcp)
    sans = lib.get_screen_signature()
    assert "@10,20" not in sans


def test_get_screenshot_as_base64_retourne_les_octets_du_buffer():
    import base64
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession(ScreenshotWindow(_PNG_BYTES))
    b64 = lib.get_screenshot_as_base64()
    assert base64.b64decode(b64) == _PNG_BYTES


def test_get_screenshot_accepte_un_safearray_de_tuples_d_entiers():
    import base64
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession(ScreenshotWindow(tuple(_PNG_BYTES)))
    assert base64.b64decode(lib.get_screenshot_as_base64()) == _PNG_BYTES


def test_get_screenshot_echoue_clairement_si_l_api_est_absente():
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession(FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow"))
    with pytest.raises(AssertionError, match="HardCopyToMemory"):
        lib.get_screenshot_as_base64()


def test_log_screenshot_incruste_un_data_uri_du_mime_reel(monkeypatch):
    from SapEccLibrary.keywords import _perception
    logged = []
    monkeypatch.setattr(_perception.logger, "info",
                        lambda msg, **kw: logged.append((msg, kw)), raising=False)
    lib = SapEccLibrary(screenshots_on_error=False)
    # buffer JPEG alors que png était demandé : le MIME incrusté suit les magic bytes
    lib.session = FakeSession(ScreenshotWindow(b"\xff\xd8\xff" + b"jpeg-payload"))
    assert lib.log_screenshot("après validation") == "image/jpeg"
    message, kwargs = logged[0]
    assert "data:image/jpeg;base64," in message
    assert "après validation" in message
    assert kwargs.get("html") is True
