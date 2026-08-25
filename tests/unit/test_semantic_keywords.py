"""Localisateurs humains : describe_element, keywords By Label, healing par ancre, perception semantique. Doublures dans _semantic_fixtures."""
import pytest

from _semantic_fixtures import (  # noqa: F401
    LOGIN,
    SCOPE_FAR,
    SELECTION_ROW,
    _NoFindSession,
    _el,
    _lib,
)



def test_describe_element_prefere_le_libelle_ancre_pour_un_champ():
    from sapfx_common.semantic import describe_element
    assert describe_element(LOGIN, "wnd[0]/usr/txtRSYST-MANDT") == "Client"


def test_describe_element_texte_propre_pour_un_bouton_tooltip_sinon():
    from sapfx_common.semantic import describe_element
    assert describe_element(LOGIN, "wnd[0]/tbar[0]/btn[0]") == "Enter"
    assert describe_element(LOGIN, "wnd[0]/tbar[1]/btn[8]") == "Exécuter (F8)"


def test_describe_element_ne_se_sert_jamais_de_la_valeur_d_un_champ_modifiable():
    # le texte de txtAMOUNT ("42,00") est sa VALEUR : jamais un localisateur.
    from sapfx_common.semantic import describe_element
    assert describe_element(LOGIN, "wnd[0]/usr/txtAMOUNT") == "Amount"


def test_describe_element_retourne_none_si_aucun_libelle_ne_re_resout_unique():
    from sapfx_common.semantic import describe_element
    deux = LOGIN + [
        _el("wnd[0]/usr/lblAmount2", "GuiLabel", "Amount", box=(300, 80, 60, 20)),
        _el("wnd[0]/usr/txtAMOUNT2", "GuiTextField", "", changeable=True,
            box=(370, 80, 60, 20)),
    ]
    # "Amount" est ambigu (2 éléments) : la vérification aller-retour échoue
    assert describe_element(deux, "wnd[0]/usr/txtAMOUNT") is None


def test_describe_element_inconnu_ou_sans_ancrage_donne_none():
    from sapfx_common.semantic import describe_element
    assert describe_element(LOGIN, "wnd[0]/usr/txtINCONNU") is None
    sans_geo = [_el("wnd[0]/usr/txtX", "GuiTextField", "val", changeable=True)]
    assert describe_element(sans_geo, "wnd[0]/usr/txtX") is None


def test_find_element_by_label_retourne_l_id_en_chaine():
    eid = _lib().find_element_by_label("User")
    assert eid == "wnd[0]/usr/txtRSYST-BNAME"
    assert isinstance(eid, str)


def test_fill_field_by_label_delegue_a_input_text():
    lib = _lib()
    calls = []
    lib.input_text = lambda eid, value: calls.append((eid, value))
    assert lib.fill_field_by_label("Client", "100") == "wnd[0]/usr/txtRSYST-MANDT"
    assert calls == [("wnd[0]/usr/txtRSYST-MANDT", "100")]


def test_fill_field_by_label_via_grille_ecrit_dans_le_champ_modifiable():
    # Reproduit le scénario live SE16/T000 : `MTEXT @ 2` doit saisir la borne
    # HIGH, jamais le séparateur « to » en lecture seule (crash COM sinon).
    lib = _lib(SELECTION_ROW)
    calls = []
    lib.input_text = lambda eid, value: calls.append((eid, value))
    assert lib.fill_field_by_label("MTEXT @ 2", "ZLIVE") == "wnd[0]/usr/txtI1-HIGH"
    assert calls == [("wnd[0]/usr/txtI1-HIGH", "ZLIVE")]


def test_click_button_by_label_delegue_a_click_element():
    lib = _lib()
    calls = []
    lib.click_element = lambda eid: calls.append(eid)
    assert lib.click_button_by_label("Exécuter") == "wnd[0]/tbar[1]/btn[8]"
    assert calls == ["wnd[0]/tbar[1]/btn[8]"]


def test_read_field_by_label_relit_la_valeur_via_get_value():
    lib = _lib()
    lib.get_value = lambda eid: "VALEUR-FRAICHE"
    assert lib.read_field_by_label("Client") == "VALEUR-FRAICHE"


def test_read_field_by_label_via_grille_compte_les_memes_positions_que_fill():
    # Cascade « modifiables d'abord » : `MTEXT @ 2` lit la borne HIGH (comme
    # Find/Fill), jamais le séparateur « to » en lecture seule.
    lib = _lib(SELECTION_ROW)
    lus = []
    lib.get_value = lambda eid: lus.append(eid) or "ZLIVE"
    assert lib.read_field_by_label("MTEXT @ 2") == "ZLIVE"
    assert lus == ["wnd[0]/usr/txtI1-HIGH"]


def test_read_field_by_label_replie_sur_la_lecture_seule_d_un_affichage():
    # Dynpro d'AFFICHAGE : aucune cible modifiable, la cascade replie sur le
    # champ en lecture seule (la façon dont un dynpro montre ses valeurs).
    affichage = [
        _el("wnd[0]/usr/lblClient", "GuiLabel", "Client", box=(10, 20, 80, 20)),
        _el("wnd[0]/usr/txtT000-MANDT", "GuiTextField", "001",
            box=(100, 20, 60, 20)),
    ]
    lib = _lib(affichage)
    lib.get_value = lambda eid: "001"
    assert lib.read_field_by_label("Client") == "001"


def test_read_field_by_label_ambiguite_de_la_passe_modifiable_remontee():
    # Deux champs modifiables ancrés au même libellé (droite + dessous) : la
    # cascade ne replie PAS sur la lecture seule : l'ambiguïté est remontée.
    ambigu = [
        _el("wnd[0]/usr/lblDouble", "GuiLabel", "Double", box=(10, 20, 60, 20)),
        _el("wnd[0]/usr/txtDROITE", "GuiTextField", "", changeable=True,
            box=(80, 20, 60, 20)),
        _el("wnd[0]/usr/txtDESSOUS", "GuiTextField", "", changeable=True,
            box=(10, 45, 60, 20)),
    ]
    with pytest.raises(AssertionError) as err:
        _lib(ambigu).read_field_by_label("Double")
    assert "ambigu" in str(err.value)


def test_scope_radius_expose_sur_les_keywords_et_diagnostic_dans_l_erreur():
    lib = _lib(SCOPE_FAR)
    # hors rayon par défaut : l'échec diagnostique la portée (rayon + remède)
    with pytest.raises(AssertionError) as err:
        lib.find_element_by_label("Zone >> Currency")
    assert "Portée '>>'" in str(err.value)
    assert "scope_radius" in str(err.value)
    # le rayon passé en argument Robot (chaîne) élargit le voisinage
    assert lib.find_element_by_label("Zone >> Currency", scope_radius="300") \
        == "wnd[0]/usr/txtFAR"


def test_echec_sans_match_liste_les_libelles_visibles():
    with pytest.raises(AssertionError) as err:
        _lib().find_element_by_label("Inexistant")
    assert "Libellés visibles" in str(err.value)
    assert "Client" in str(err.value)


def test_echec_ambigu_liste_les_candidats():
    deux = LOGIN + [
        _el("wnd[0]/usr/lblAmount2", "GuiLabel", "Amount", box=(300, 80, 60, 20)),
        _el("wnd[0]/usr/txtAMOUNT2", "GuiTextField", "", changeable=True,
            box=(370, 80, 60, 20)),
    ]
    with pytest.raises(AssertionError) as err:
        _lib(deux).find_element_by_label("Amount")
    assert "ambigu" in str(err.value)
    assert "txtAMOUNT" in str(err.value) and "txtAMOUNT2" in str(err.value)


def test_echec_sans_geometrie_l_explique():
    sans_geo = [_el("wnd[0]/tbar[0]/btn[0]", "GuiButton", "Enter")]
    with pytest.raises(AssertionError) as err:
        _lib(sans_geo).find_element_by_label("Client")
    assert "géométrie" in str(err.value)


def test_control_types_accepte_une_chaine_robot():
    assert _lib().find_element_by_label("Enter", control_types="GuiButton, GuiTab") \
        == "wnd[0]/tbar[0]/btn[0]"


def test_healing_repare_par_ancre_de_libelle_quand_le_score_ne_suffit_pas():
    lib = _lib()
    lib.session = _NoFindSession()
    healed = lib.resolve_element_with_healing(
        "wnd[0]/usr/ctxtZZ-TOTALEMENT-DIFFERENT", label="User")
    assert healed == "wnd[0]/usr/txtRSYST-BNAME"


def test_healing_refuse_une_ancre_de_libelle_ambigue():
    deux = LOGIN + [
        _el("wnd[0]/usr/lblAmount2", "GuiLabel", "Amount", box=(300, 80, 60, 20)),
        _el("wnd[0]/usr/txtAMOUNT2", "GuiTextField", "", changeable=True,
            box=(370, 80, 60, 20)),
    ]
    lib = _lib(deux)
    lib.session = _NoFindSession()
    with pytest.raises(AssertionError):
        lib.resolve_element_with_healing(
            "wnd[0]/usr/ctxtZZ-TOTALEMENT-DIFFERENT", label="Amount")


def test_actionable_targets_champs_modifiables_et_boutons_seulement():
    from sapfx_common.semantic import actionable_targets
    ids = [el.id for el in actionable_targets(LOGIN)]
    assert "wnd[0]/usr/txtRSYST-MANDT" in ids       # champ modifiable
    assert "wnd[0]/tbar[0]/btn[0]" in ids           # bouton
    assert "wnd[0]/usr/lblClient" not in ids        # libellé : pas une cible
    assert "wnd[0]" not in ids                      # structurel : pas une cible


def test_affordances_champ_avec_libelle_verifie_et_valeur():
    from sapfx_common.semantic import screen_affordances
    lines = screen_affordances(LOGIN)
    ligne_client = next(line for line in lines if "txtRSYST-MANDT" in line)
    # champ modifiable : marqué *, libellé vérifié, id, type, valeur courante
    assert ligne_client.startswith("* Client\t")
    assert "GuiTextField" in ligne_client
    assert ligne_client.endswith("= 001")


def test_affordances_bouton_par_texte_et_par_tooltip():
    from sapfx_common.semantic import screen_affordances
    lines = screen_affordances(LOGIN)
    enter = next(line for line in lines if "btn[0]" in line)
    executer = next(line for line in lines if "btn[8]" in line)
    assert enter.startswith("  Enter\t")
    assert executer.startswith("  Exécuter (F8)\t")   # tooltip = localisateur


def test_affordances_sans_libelle_fiable_marque_interrogation():
    # deux libellés "Amount" -> describe_element ne re-résout plus de façon
    # unique : la ligne garde "?" (jamais de devinette), l'id reste le chemin.
    deux = LOGIN + [
        _el("wnd[0]/usr/lblAmount2", "GuiLabel", "Amount", box=(300, 80, 60, 20)),
        _el("wnd[0]/usr/txtAMOUNT2", "GuiTextField", "", changeable=True,
            box=(300, 105, 60, 20)),
    ]
    from sapfx_common.semantic import screen_affordances
    lines = screen_affordances(deux)
    amount2 = next(line for line in lines if "txtAMOUNT2" in line)
    assert amount2.startswith("* ?\t")


def test_changeable_ne_suffit_jamais_lecon_live_a4h():
    # le vrai SAP GUI marque Changeable=True sur GuiUserArea et les boutons de
    # toolbar (constaté live A4H) : ni l'un ni l'autre n'est un champ de saisie.
    from sapfx_common.semantic import is_editable_field, screen_affordances
    usr = _el("wnd[0]/usr", "GuiUserArea", changeable=True, box=(0, 0, 800, 600))
    btn = _el("wnd[0]/tbar[1]/btn[32]", "GuiButton", "Refresh", changeable=True,
              box=(90, 0, 30, 18))
    assert not is_editable_field(usr)
    assert not is_editable_field(btn)
    lines = screen_affordances([usr, btn])
    assert len(lines) == 1                      # GuiUserArea : pas une cible
    assert lines[0].startswith("  Refresh\t")   # bouton : clic, pas saisie
    assert "= " not in lines[0]                 # jamais de « valeur » de bouton
