"""Localisateurs humains : grammaire de resolution (ancres, grilles, portee >>). Doublures dans _semantic_fixtures (convention #13)."""
from sapfx_common.semantic import (
    is_label,
    nearby_labels,
    resolve_semantic,
    text_matches,
)

from _semantic_fixtures import (  # noqa: F401
    GRID,
    LOGIN,
    SCOPED,
    SCOPE_FAR,
    SELECTION_ROW,
    _SELECTION_INPUT_TYPES,
    _el,
    _ids,
)



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
