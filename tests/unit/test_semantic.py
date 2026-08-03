"""Tests off-SAP du moteur de localisateurs humains (convention #5 du CLAUDE.md).

Moteur pur ``sapfx_common.semantic`` (géométrie libellé -> cible, grammaire,
ambiguïté jamais tranchée en silence) + mixin ``SemanticKeywords`` (unicité,
erreurs auto-corrigibles, délégation aux keywords upstream) + voie « ancre de
libellé » de ``Resolve Element With Healing``.
"""
import pytest

from SapEccLibrary import SapEccLibrary
from sapfx_common.object_tree import ScreenElement
from sapfx_common.semantic import (
    is_label,
    nearby_labels,
    resolve_semantic,
    text_matches,
)


def _el(eid, etype, text="", tooltip="", changeable=False, box=None):
    left, top, width, height = box if box else (None, None, None, None)
    return ScreenElement(id=eid, type=etype, text=text, tooltip=tooltip,
                         changeable=changeable, left=left, top=top,
                         width=width, height=height)


# Un dynpro de connexion simplifié : libellés à gauche, champs à droite,
# un en-tête de colonne avec champ dessous, deux boutons, une intersection.
LOGIN = [
    _el("wnd[0]", "GuiMainWindow", "SAP", box=(0, 0, 800, 600)),
    _el("wnd[0]/usr/lblClient", "GuiLabel", "Client", box=(10, 20, 80, 20)),
    _el("wnd[0]/usr/txtRSYST-MANDT", "GuiTextField", "001", changeable=True,
        box=(100, 20, 60, 20)),
    _el("wnd[0]/usr/lblUser", "GuiLabel", "User", box=(10, 50, 80, 20)),
    _el("wnd[0]/usr/txtRSYST-BNAME", "GuiTextField", "", changeable=True,
        box=(100, 50, 120, 20)),
    # 2e champ de la même ligne, plus loin mais encore dans la tolérance :
    # seul le PLUS PROCHE doit être désigné par le libellé.
    _el("wnd[0]/usr/txtRSYST-LANGU", "GuiTextField", "", changeable=True,
        box=(115, 50, 40, 20)),
    _el("wnd[0]/usr/lblAmount", "GuiLabel", "Amount", box=(300, 20, 60, 20)),
    _el("wnd[0]/usr/txtAMOUNT", "GuiTextField", "42,00", changeable=True,
        box=(300, 45, 60, 20)),
    _el("wnd[0]/tbar[0]/btn[0]", "GuiButton", "Enter", box=(10, 0, 30, 18)),
    _el("wnd[0]/tbar[1]/btn[8]", "GuiButton", "", tooltip="Exécuter (F8)",
        box=(50, 0, 30, 18)),
    # intersection ligne/colonne (grille de champs)
    _el("wnd[0]/usr/lblLigne1", "GuiLabel", "Ligne1", box=(40, 300, 50, 20)),
    _el("wnd[0]/usr/lblQte", "GuiLabel", "Qté", box=(100, 270, 40, 20)),
    _el("wnd[0]/usr/txtQTY-1", "GuiTextField", "", changeable=True,
        box=(100, 300, 40, 20)),
]


def _ids(matches):
    return [m.element.id for m in matches]


# --- moteur pur ---------------------------------------------------------------

def test_champ_a_droite_du_libelle():
    matches = resolve_semantic(LOGIN, "Client")
    assert _ids(matches) == ["wnd[0]/usr/txtRSYST-MANDT"]
    assert matches[0].via == "right-of-label"
    assert matches[0].anchor.id == "wnd[0]/usr/lblClient"


def test_seul_le_plus_proche_voisin_est_designe_par_une_ancre():
    # deux champs à droite de "User" dans la tolérance -> un seul match, le plus proche
    assert _ids(resolve_semantic(LOGIN, "User")) == ["wnd[0]/usr/txtRSYST-BNAME"]


def test_prefixe_insensible_a_la_casse_par_defaut_et_exact_strict():
    assert _ids(resolve_semantic(LOGIN, "clie")) == ["wnd[0]/usr/txtRSYST-MANDT"]
    assert resolve_semantic(LOGIN, "clie", exact=True) == []


def test_sous_le_libelle_via_arobase_et_cascade_auto():
    # forme explicite `@ label`
    assert _ids(resolve_semantic(LOGIN, "@ Amount")) == ["wnd[0]/usr/txtAMOUNT"]
    # cascade auto : pas de voisin de droite pour "Amount" -> seule la voie dessous matche
    matches = resolve_semantic(LOGIN, "Amount")
    assert _ids(matches) == ["wnd[0]/usr/txtAMOUNT"]
    assert matches[0].via == "below-label"


def test_texte_propre_puis_tooltip_pour_les_boutons():
    assert _ids(resolve_semantic(LOGIN, "Enter")) == ["wnd[0]/tbar[0]/btn[0]"]
    # tooltip "Exécuter (F8)" matché par préfixe (l'équivalent du ~ RoboSAPiens)
    matches = resolve_semantic(LOGIN, "Exécuter")
    assert _ids(matches) == ["wnd[0]/tbar[1]/btn[8]"]
    assert matches[0].via == "tooltip"


def test_contenu_exact_via_egal():
    assert _ids(resolve_semantic(LOGIN, "= 42,00")) == ["wnd[0]/usr/txtAMOUNT"]
    assert resolve_semantic(LOGIN, "= 42") == []   # `=` est toujours exact


def test_intersection_gauche_arobase_haut():
    matches = resolve_semantic(LOGIN, "Ligne1 @ Qté")
    assert _ids(matches) == ["wnd[0]/usr/txtQTY-1"]
    assert matches[0].via == "intersection"


# --- grilles de position : `N @ libellé` (verticale) / `libellé @ N` (horizontale) --

GRID = [
    _el("wnd[0]/usr/lblAddress", "GuiLabel", "Address", box=(10, 100, 80, 20)),
    _el("wnd[0]/usr/txtLINE1", "GuiTextField", "", changeable=True, box=(10, 130, 100, 20)),
    _el("wnd[0]/usr/txtLINE2", "GuiTextField", "", changeable=True, box=(10, 160, 100, 20)),
    _el("wnd[0]/usr/txtLINE3", "GuiTextField", "", changeable=True, box=(10, 190, 100, 20)),
    _el("wnd[0]/usr/lblPeriod", "GuiLabel", "Period", box=(10, 400, 60, 20)),
    _el("wnd[0]/usr/txtFROM", "GuiTextField", "", changeable=True, box=(80, 400, 50, 20)),
    _el("wnd[0]/usr/txtTO", "GuiTextField", "", changeable=True, box=(140, 400, 50, 20)),
]


def test_grille_verticale_n_arobase_libelle():
    assert _ids(resolve_semantic(GRID, "1 @ Address")) == ["wnd[0]/usr/txtLINE1"]
    matches = resolve_semantic(GRID, "2 @ Address")
    assert _ids(matches) == ["wnd[0]/usr/txtLINE2"]
    assert matches[0].via == "below-label-grid"
    assert _ids(resolve_semantic(GRID, "3 @ Address")) == ["wnd[0]/usr/txtLINE3"]


def test_grille_verticale_position_hors_limites_ne_matche_rien():
    assert resolve_semantic(GRID, "4 @ Address") == []
    assert resolve_semantic(GRID, "0 @ Address") == []


def test_grille_horizontale_libelle_arobase_n():
    matches = resolve_semantic(GRID, "Period @ 2")
    assert _ids(matches) == ["wnd[0]/usr/txtTO"]
    assert matches[0].via == "right-of-label-grid"
    assert _ids(resolve_semantic(GRID, "Period @ 1")) == ["wnd[0]/usr/txtFROM"]


def test_grille_horizontale_position_hors_limites_ne_matche_rien():
    assert resolve_semantic(GRID, "Period @ 3") == []


# Une ligne de selection screen SE16 réelle (géométrie relevée live sur A4H,
# table T000) : libellé de ligne et séparateur « to » = champs texte en LECTURE
# SEULE, bornes LOW/HIGH modifiables, bouton multi-valeurs en bout de ligne.
SELECTION_ROW = [
    _el("wnd[0]/usr/txt%_I1_%_APP_%-TEXT", "GuiTextField", "MTEXT",
        box=(27, 197, 231, 24)),
    _el("wnd[0]/usr/txtI1-LOW", "GuiTextField", "", changeable=True,
        box=(283, 197, 151, 24)),
    _el("wnd[0]/usr/txt%_I1_%_APP_%-TO_TEXT", "GuiTextField", "to",
        box=(435, 197, 47, 24)),
    _el("wnd[0]/usr/txtI1-HIGH", "GuiTextField", "", changeable=True,
        box=(483, 197, 151, 24)),
    _el("wnd[0]/usr/btn%_I1_%_APP_%-VALU_PUSH", "GuiButton", "",
        box=(635, 196, 32, 26)),
]

_SELECTION_INPUT_TYPES = ("GuiTextField", "GuiCTextField")


def test_grille_changeable_only_exclut_les_separateurs_lecture_seule():
    # Bug constaté live (SE16/T000) : avec un filtre de types explicite, le
    # « to » en lecture seule comptait comme position -> `MTEXT @ 2` désignait
    # le séparateur (saisie impossible, AttributeError COM) au lieu de HIGH.
    fill = resolve_semantic(SELECTION_ROW, "MTEXT @ 2",
                            types=_SELECTION_INPUT_TYPES, changeable_only=True)
    assert _ids(fill) == ["wnd[0]/usr/txtI1-HIGH"]
    assert _ids(resolve_semantic(SELECTION_ROW, "MTEXT @ 1",
                                 types=_SELECTION_INPUT_TYPES,
                                 changeable_only=True)) == ["wnd[0]/usr/txtI1-LOW"]
    # Sans changeable_only, le filtre de types garde les champs en lecture
    # seule : voulu pour LIRE un dynpro d'affichage (valeurs non modifiables).
    lecture = resolve_semantic(SELECTION_ROW, "MTEXT @ 2",
                               types=_SELECTION_INPUT_TYPES)
    assert _ids(lecture) == ["wnd[0]/usr/txt%_I1_%_APP_%-TO_TEXT"]


def test_grille_par_defaut_et_fill_donnent_les_memes_positions():
    # Cibles par défaut (labels exclus) et cibles de saisie (changeable_only)
    # doivent compter les MÊMES positions de champ : Find et Fill cohérents.
    assert _ids(resolve_semantic(SELECTION_ROW, "MTEXT @ 2")) \
        == ["wnd[0]/usr/txtI1-HIGH"]


def test_ancrage_simple_changeable_only_saute_le_separateur():
    # Forme ancrée simple : la cible de saisie la plus proche à droite du
    # libellé est LOW (le « to » n'est jamais candidat à la saisie).
    matches = resolve_semantic(SELECTION_ROW, "MTEXT",
                               types=_SELECTION_INPUT_TYPES, changeable_only=True)
    assert _ids(matches) == ["wnd[0]/usr/txtI1-LOW"]


# --- opérateur de portée `ancre >> reste` -------------------------------------

SCOPED = [
    # deux groupes avec le MÊME libellé non-unique ("Amount"), chacun ancré
    # sous un libellé unique différent ("Header" / "Item").
    _el("wnd[0]/usr/lblHeader", "GuiLabel", "Header", box=(10, 500, 60, 20)),
    _el("wnd[0]/usr/lblAmountH", "GuiLabel", "Amount", box=(10, 530, 60, 20)),
    _el("wnd[0]/usr/txtAMOUNTH", "GuiTextField", "", changeable=True, box=(80, 530, 60, 20)),
    _el("wnd[0]/usr/lblItem", "GuiLabel", "Item", box=(300, 500, 60, 20)),
    _el("wnd[0]/usr/lblAmountI", "GuiLabel", "Amount", box=(300, 530, 60, 20)),
    _el("wnd[0]/usr/txtAMOUNTI", "GuiTextField", "", changeable=True, box=(370, 530, 60, 20)),
    # deux champs SANS libellé propre, identifiés par tooltip (l'équivalent F1),
    # chacun proche d'une ancre unique différente.
    _el("wnd[0]/usr/lblSearch", "GuiLabel", "Search", box=(10, 700, 60, 20)),
    _el("wnd[0]/usr/txtNOLABEL", "GuiTextField", "", changeable=True,
        tooltip="Reference number", box=(80, 700, 100, 20)),
    _el("wnd[0]/usr/lblOther", "GuiLabel", "Other", box=(300, 700, 60, 20)),
    _el("wnd[0]/usr/txtNOLABEL2", "GuiTextField", "", changeable=True,
        tooltip="Reference number", box=(370, 700, 100, 20)),
]


def test_sans_scope_le_libelle_non_unique_est_ambigu():
    assert len(resolve_semantic(SCOPED, "Amount")) == 2
    assert len(resolve_semantic(SCOPED, "Reference number")) == 2


def test_scope_desambiguise_un_libelle_non_unique_pres_d_une_ancre_unique():
    assert _ids(resolve_semantic(SCOPED, "Header >> Amount")) == ["wnd[0]/usr/txtAMOUNTH"]
    assert _ids(resolve_semantic(SCOPED, "Item >> Amount")) == ["wnd[0]/usr/txtAMOUNTI"]


def test_scope_desambiguise_un_champ_par_tooltip_pres_d_une_ancre_unique():
    matches = resolve_semantic(SCOPED, "Search >> Reference number")
    assert _ids(matches) == ["wnd[0]/usr/txtNOLABEL"]
    assert matches[0].via == "tooltip"
    assert _ids(resolve_semantic(SCOPED, "Other >> Reference number")) \
        == ["wnd[0]/usr/txtNOLABEL2"]


def test_scope_sur_ancre_absente_ou_ambigue_ne_matche_rien():
    assert resolve_semantic(SCOPED, "Inconnu >> Amount") == []
    # "Amount" lui-même est non-unique : inutilisable comme ancre de portée.
    assert resolve_semantic(SCOPED, "Amount >> Reference number") == []


def test_scope_imbrique():
    proches = [
        _el("wnd[0]/usr/lblA", "GuiLabel", "A", box=(10, 900, 20, 20)),
        _el("wnd[0]/usr/lblB", "GuiLabel", "B", box=(40, 900, 20, 20)),
        _el("wnd[0]/usr/txtC", "GuiTextField", "", changeable=True,
            tooltip="Target C", box=(70, 900, 60, 20)),
    ]
    assert _ids(resolve_semantic(proches, "A >> B >> Target C")) == ["wnd[0]/usr/txtC"]


# Une cible au-delà du rayon par défaut (100 px) de son ancre unique : le cas
# relevé live sur SE16 (un écran réel est bien plus large que 100 px).
SCOPE_FAR = [
    _el("wnd[0]/usr/lblZone", "GuiLabel", "Zone", box=(0, 0, 50, 20)),
    _el("wnd[0]/usr/txtFAR", "GuiTextField", "", changeable=True,
        tooltip="Currency Key", box=(300, 0, 60, 20)),
]


def test_scope_radius_etend_le_voisinage():
    # défaut (100 px) : la cible à 250 px du bord de l'ancre est hors zone
    assert resolve_semantic(SCOPE_FAR, "Zone >> Currency") == []
    assert _ids(resolve_semantic(SCOPE_FAR, "Zone >> Currency", scope_radius=300)) \
        == ["wnd[0]/usr/txtFAR"]


def test_scope_radius_herite_par_les_scopes_imbriques():
    lointains = [
        _el("wnd[0]/usr/lblA", "GuiLabel", "A", box=(0, 0, 20, 20)),
        _el("wnd[0]/usr/lblB", "GuiLabel", "B", box=(200, 0, 20, 20)),
        _el("wnd[0]/usr/txtC", "GuiTextField", "", changeable=True,
            tooltip="Target C", box=(400, 0, 60, 20)),
    ]
    assert resolve_semantic(lointains, "A >> B >> Target C") == []
    # les portées s'INTERSECTENT (chaque `>>` réduit l'univers) : le rayon
    # hérité doit couvrir la cible depuis la PREMIÈRE ancre aussi.
    assert _ids(resolve_semantic(lointains, "A >> B >> Target C",
                                 scope_radius=400)) == ["wnd[0]/usr/txtC"]


def test_scope_hint_diagnostique_chaque_echec():
    from sapfx_common.semantic import scope_hint
    # pas de `>>` : rien à diagnostiquer
    assert scope_hint(SCOPED, "Amount") is None
    assert "aucun libellé" in scope_hint(SCOPED, "Inconnu >> Amount")
    hint = scope_hint(SCOPED, "Amount >> Reference number")
    assert "ambiguë" in hint and "2" in hint
    # ancre unique, cible hors rayon : le diagnostic nomme le rayon et le remède
    hint = scope_hint(SCOPE_FAR, "Zone >> Currency")
    assert "100 px" in hint and "scope_radius" in hint
    # ancre unique mais voisinage vide (ancre seule à l'écran)
    seule = [_el("wnd[0]/usr/lblZone", "GuiLabel", "Zone", box=(0, 0, 50, 20))]
    assert "voisinage est vide" in scope_hint(seule, "Zone >> X")
    # ancre unique sans géométrie
    sans_geo = [_el("wnd[0]/usr/lblZone", "GuiLabel", "Zone")]
    assert "sans géométrie" in scope_hint(sans_geo, "Zone >> X")


def test_ambiguite_retourne_tous_les_candidats_jamais_le_premier():
    deux_montants = LOGIN + [
        _el("wnd[0]/usr/lblAmount2", "GuiLabel", "Amount", box=(300, 80, 60, 20)),
        _el("wnd[0]/usr/txtAMOUNT2", "GuiTextField", "", changeable=True,
            box=(370, 80, 60, 20)),
    ]
    matches = resolve_semantic(deux_montants, "Amount")
    assert len(matches) == 2   # l'appelant tranche, pas le moteur


def test_filtre_de_types_restreint_les_cibles():
    assert resolve_semantic(LOGIN, "Enter", types=("GuiTextField",)) == []
    assert _ids(resolve_semantic(LOGIN, "Enter", types=("GuiButton",))) \
        == ["wnd[0]/tbar[0]/btn[0]"]


def test_les_conteneurs_structurels_ne_sont_jamais_cibles_par_defaut():
    # "SAP" est le texte de la GuiMainWindow : exclue des cibles par défaut
    assert resolve_semantic(LOGIN, "SAP") == []


def test_un_champ_texte_non_modifiable_sert_d_ancre():
    affichage = [
        _el("wnd[0]/usr/txtLBL", "GuiTextField", "Statut", changeable=False,
            box=(10, 20, 60, 20)),
        _el("wnd[0]/usr/txtVAL", "GuiTextField", "Ouvert", changeable=True,
            box=(80, 20, 60, 20)),
    ]
    assert is_label(affichage[0]) and not is_label(affichage[1])
    assert _ids(resolve_semantic(affichage, "Statut")) == ["wnd[0]/usr/txtVAL"]


def test_sans_geometrie_seuls_texte_et_tooltip_matchent():
    plats = [_el("wnd[0]/usr/lblX", "GuiLabel", "Client"),
             _el("wnd[0]/usr/txtX", "GuiTextField", changeable=True),
             _el("wnd[0]/tbar[0]/btn[0]", "GuiButton", "Enter")]
    assert resolve_semantic(plats, "Client") == []          # ancre inutilisable
    assert _ids(resolve_semantic(plats, "Enter")) == ["wnd[0]/tbar[0]/btn[0]"]


def test_text_matches_et_nearby_labels():
    assert text_matches("  Exécuter (F8) ", "exécuter")
    assert not text_matches("Exécuter", "")
    labels = nearby_labels(LOGIN)
    assert labels[:3] == ["Client", "User", "Amount"]


# --- describe_element : l'inverse vérifié (usage recorder) ---------------------

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


# --- mixin SemanticKeywords ----------------------------------------------------

def _lib(elements=LOGIN):
    lib = SapEccLibrary(screenshots_on_error=False)
    lib._screen_elements = lambda: elements
    return lib


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
    # Dynpro d'AFFICHAGE : aucune cible modifiable — la cascade replie sur le
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
    # cascade ne replie PAS sur la lecture seule — l'ambiguïté est remontée.
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


# --- healing par ancre de libellé ----------------------------------------------

class _NoFindSession:
    """Session sans findById exploitable : _find retourne toujours None."""


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


# --- perception sémantique : affordances (mode=semantic) ------------------------

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
