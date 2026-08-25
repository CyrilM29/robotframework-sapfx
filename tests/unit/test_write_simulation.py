"""Tests hors SAP de la simulation d'écriture réversible (convention 5).

Deux niveaux, comme pour l'inventaire DDIC et le croisement :

* la logique **pure** de ``sapfx_common.write_simulation`` : périmètre
  d'écriture, perception de l'écran de saisie SE16, verdict de réversibilité ;
* les propriétés de SÛRETÉ du page object ``resources/page_objects/
  se16_table_entry.resource``, vérifiées sur le fichier réel. Ces trois-là ne
  sont pas des détails de style : elles sont ce qui empêche une suppression de
  masse, et aucune d'elles n'est prouvable par un dry run.

Les échantillons d'écran sont ceux RELEVÉS live (A4H, 2026-08-22) : écran de
saisie ``SNWD_PD_CATGOS`` généré par SE16, préfixes de type inclus.
"""
import os

import pytest

from sapfx_common.write_simulation import (
    build_reversibility_observation,
    normalize_table_name,
    reversibility_observation_json,
    table_entry_fields,
    validate_write_target,
)

# Vue sémantique de l'écran de saisie, telle que `Get Screen Signature
# mode=semantic` la rend : « libellé <TAB> id <TAB> type <TAB> = valeur ». Le
# libellé du premier champ est « 001 » sur cette cible, ce qui illustre
# pourquoi il ne sert jamais d'ancre.
SEMANTIC_ENTRY_SCREEN = "\n".join([
    "# screen /1BCDWB/DBSNWD_PD_CATGOS/SE16/101",
    "* 001\twnd[0]/usr/ctxtSNWD_PD_CATGOS-CATEGORY\tGuiCTextField\t= ",
    "* MAIN CATEGORY\twnd[0]/usr/ctxtSNWD_PD_CATGOS-MAIN_CATEGORY"
    "\tGuiCTextField\t= ",
])

# Vue complète du même écran : « id <TAB> type <TAB> texte ».
FULL_ENTRY_SCREEN = "\n".join([
    "# screen /1BCDWB/DBSNWD_PD_CATGOS/SE16/101",
    "  wnd[0]/usr/lbl001\tGuiLabel\t001",
    "* wnd[0]/usr/ctxtSNWD_PD_CATGOS-CATEGORY\tGuiCTextField\t",
    "* wnd[0]/usr/txtSNWD_PD_CATGOS-MAIN_CATEGORY\tGuiTextField\t",
])

# Écran de SÉLECTION de la même table : critères positionnels, aucun champ de
# saisie d'enregistrement. La carte doit y être vide.
SELECTION_SCREEN = "\n".join([
    "# screen /1BCDWB/DBSNWD_PD_CATGOS/SE16/1000",
    "* CATEGORY\twnd[0]/usr/ctxtI1-LOW\tGuiCTextField\t= ",
    "* MAIN_CATEGORY\twnd[0]/usr/ctxtI2-LOW\tGuiCTextField\t= ",
    "* Maximum No. of Hits\twnd[0]/usr/txtMAX_SEL\tGuiTextField\t= 200",
])


# --- périmètre d'écriture ----------------------------------------------------

def test_le_perimetre_vide_refuse_tout_au_lieu_d_autoriser_tout():
    """Le défaut d'une liste blanche ne peut pas être « le système entier »."""
    with pytest.raises(ValueError) as err:
        validate_write_target("SNWD_PD_CATGOS", [])
    assert "refuse tout" in str(err.value)


def test_une_cible_hors_perimetre_est_refusee_en_nommant_le_perimetre():
    with pytest.raises(ValueError) as err:
        validate_write_target("SCARR", ["SNWD_PD_CATGOS"])
    assert "SCARR" in str(err.value)
    assert "SNWD_PD_CATGOS" in str(err.value)


def test_une_cible_declaree_traverse_normalisee():
    assert validate_write_target("  snwd_pd_catgos ",
                                 ["SNWD_PD_CATGOS"]) == "SNWD_PD_CATGOS"


def test_une_cible_vide_est_refusee_avant_toute_action():
    with pytest.raises(ValueError):
        validate_write_target("   ", ["SNWD_PD_CATGOS"])


def test_un_perimetre_scalaire_compte_pour_une_entree_pas_ses_caracteres():
    """Les variables ``-v`` de Robot sont toujours scalaires : une chaîne seule
    doit valoir une entrée, jamais la liste de ses lettres."""
    assert validate_write_target("SCARR", "SCARR") == "SCARR"


def test_un_nom_d_espace_de_noms_reste_distinct():
    assert normalize_table_name("/dmo/carrier") == "/DMO/CARRIER"
    with pytest.raises(ValueError):
        validate_write_target("/DMO/CARRIER", ["DMOCARRIER"])


# --- perception de l'écran de saisie -----------------------------------------

def test_les_champs_de_saisie_sont_derives_de_la_vue_semantique():
    fields = table_entry_fields(SEMANTIC_ENTRY_SCREEN, "SNWD_PD_CATGOS")
    assert fields == {
        "CATEGORY": "wnd[0]/usr/ctxtSNWD_PD_CATGOS-CATEGORY",
        "MAIN_CATEGORY": "wnd[0]/usr/ctxtSNWD_PD_CATGOS-MAIN_CATEGORY",
    }


def test_la_vue_complete_donne_la_meme_carte_avec_des_prefixes_differents():
    """Le préfixe de type varie d'un champ à l'autre (``ctxt`` puis ``txt``) :
    c'est précisément pourquoi les identifiants se perçoivent au lieu de se
    déclarer."""
    fields = table_entry_fields(FULL_ENTRY_SCREEN, "snwd_pd_catgos")
    assert fields == {
        "CATEGORY": "wnd[0]/usr/ctxtSNWD_PD_CATGOS-CATEGORY",
        "MAIN_CATEGORY": "wnd[0]/usr/txtSNWD_PD_CATGOS-MAIN_CATEGORY",
    }


def test_un_ecran_de_selection_ne_donne_aucun_champ_de_saisie():
    """Le garde-fou qui distingue « je suis sur l'écran de saisie » de « je
    suis resté sur l'écran de sélection » : les critères ``I<n>-LOW`` ne sont
    pas des champs d'enregistrement."""
    assert table_entry_fields(SELECTION_SCREEN, "SNWD_PD_CATGOS") == {}


def test_les_champs_d_une_autre_table_n_entrent_jamais_dans_la_carte():
    screen = "* wnd[0]/usr/ctxtSCARR-CARRID\tGuiCTextField\t= "
    assert table_entry_fields(screen, "SNWD_PD_CATGOS") == {}
    assert table_entry_fields(screen, "SCARR") == {
        "CARRID": "wnd[0]/usr/ctxtSCARR-CARRID"}


def test_une_table_d_espace_de_noms_est_reconnue_sans_ses_barres():
    """SAP ne reproduit pas toujours les barres d'espace de noms dans un
    identifiant de contrôle : la comparaison les ignore, la carte non."""
    screen = "* wnd[0]/usr/ctxtDMOCARRIER-CARRIER_ID\tGuiCTextField\t= "
    assert table_entry_fields(screen, "/DMO/CARRIER") == {
        "CARRIER_ID": "wnd[0]/usr/ctxtDMOCARRIER-CARRIER_ID"}


def test_une_signature_donnee_en_lignes_est_acceptee():
    fields = table_entry_fields(SEMANTIC_ENTRY_SCREEN.splitlines(),
                                "SNWD_PD_CATGOS")
    assert set(fields) == {"CATEGORY", "MAIN_CATEGORY"}


def test_une_signature_vide_ne_leve_pas_elle_rend_une_carte_vide():
    assert table_entry_fields(None, "SNWD_PD_CATGOS") == {}


# --- verdict de réversibilité -------------------------------------------------

def _observation(**overrides):
    payload = dict(
        target="SNWD_PD_CATGOS", key_field="CATEGORY",
        key_value="ZZ_SAPFX_TEST_CATEGORY",
        observed_at_utc="2026-08-22T13:29:37+00:00",
        entity_set="SubCategories", service="/sap/opu/odata/sap/SEPMRA_SHOP",
        screen_count_before=32, screen_count_after_write=33,
        screen_count_after_delete=32, api_count_before=32,
        api_count_after_write=33, api_count_after_delete=32,
        seen_by_observation_channel=True, values_match=True,
        gone_from_observation_channel=True)
    payload.update(overrides)
    return build_reversibility_observation(**payload)


def test_un_cycle_complet_est_declare_reversible():
    observation = _observation()
    assert observation["verdict"] == "reversible"
    assert observation["reversible"] is True
    assert observation["initial_state_restored"] is True


def test_une_ecriture_jamais_vue_par_l_autre_canal_ne_prouve_rien():
    """Le cycle a pu se dérouler entièrement : s'il n'a pas été CONSTATÉ, il
    n'est pas « non réversible », il n'est pas concluant."""
    assert _observation(seen_by_observation_channel=False)[
        "verdict"] == "not_observed"


def test_des_valeurs_qui_ne_correspondent_pas_ne_prouvent_rien_non_plus():
    """« Une ligne est apparue » n'est pas « ma ligne est apparue »."""
    assert _observation(values_match=False)["verdict"] == "not_observed"


def test_une_entite_qui_repond_encore_a_sa_cle_n_est_pas_reversible():
    observation = _observation(gone_from_observation_channel=False)
    assert observation["verdict"] == "not_reversible"
    assert observation["reversible"] is False


def test_un_compte_qui_ne_revient_pas_a_l_initial_n_est_pas_reversible():
    observation = _observation(api_count_after_delete=33)
    assert observation["verdict"] == "not_reversible"
    assert observation["initial_state_restored"] is False


def test_le_retour_du_compte_seul_ne_suffit_pas_a_conclure():
    """Deux écritures et une suppression donneraient le même compte : c'est la
    disparition de l'entité IDENTIFIÉE qui tranche."""
    observation = _observation(gone_from_observation_channel=False,
                               api_count_after_delete=32,
                               screen_count_after_delete=32)
    assert observation["initial_state_restored"] is True
    assert observation["verdict"] == "not_reversible"


def test_l_observation_ne_porte_ni_identifiant_ni_secret():
    dump = reversibility_observation_json(_observation()).lower()
    for forbidden in ("password", "authorization", "user", "developer"):
        assert forbidden not in dump


def test_les_comptes_arrivent_en_entiers_meme_donnes_en_chaines():
    """Robot passe volontiers des chaînes : un compte doit rester comparable."""
    observation = _observation(api_count_after_write="33")
    assert observation["api_counts"]["after_write"] == 33


def test_un_compte_illisible_est_refuse_en_nommant_le_champ():
    with pytest.raises(ValueError) as err:
        _observation(api_count_before="beaucoup")
    assert "api_count_before" in str(err.value)


def test_un_booleen_donne_en_texte_robot_est_compris():
    assert _observation(gone_from_observation_channel="False")[
        "verdict"] == "not_reversible"


def test_la_serialisation_est_deterministe_et_triee():
    first = reversibility_observation_json(_observation())
    second = reversibility_observation_json(_observation())
    assert first == second
    assert first.startswith("{\n  \"api_counts\"")
    assert first.endswith("}\n")


# --- propriétés de sûreté du page object -------------------------------------
# Aucune de ces trois-là n'est prouvable par un dry run, et chacune est ce qui
# sépare une suppression ciblée d'une suppression de masse.

_PAGE_OBJECT = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "resources", "page_objects",
    "se16_table_entry.resource"))


def _page_object_text():
    with open(_PAGE_OBJECT, "r", encoding="utf-8") as handle:
        return handle.read()


def _keyword_body(name):
    """Corps (lignes indentées) du mot-clé ``name`` du page object ; lève
    explicitement s'il a été renommé, pour que le garde échoue bruyamment
    plutôt que de passer sur du vide."""
    lines = _page_object_text().splitlines()
    try:
        start = lines.index(name)
    except ValueError:
        raise AssertionError(
            "Mot-clé %r introuvable dans %s : renommé ou déplacé ?"
            % (name, _PAGE_OBJECT))
    body = []
    for line in lines[start + 1:]:
        if line and not line[0].isspace():
            break
        body.append(line)
    return body


def test_le_menu_de_suppression_de_masse_n_est_jamais_reference():
    """« Delete all » jouxte « Delete » d'un seul cran, et l'écart est
    irréversible. Le page object ne doit contenir AUCUNE référence à l'indice
    voisin, pas même en variable inutilisée."""
    assert "menu[0]/menu[5]" not in _page_object_text()


def test_la_suppression_relit_le_contenu_avant_de_cliquer_le_menu():
    """La sûreté ne repose pas sur l'indice du menu mais sur le contenu : la
    grille filtrée est relue, et son unicité vérifiée, AVANT toute action."""
    body = _keyword_body("Delete Table Entry")
    joined = "\n".join(body)
    lecture = joined.index("Length Should Be")
    controle_de_cle = joined.index("Should Be Equal    ${key_seen}")
    suppression = joined.index("${SE16_MENU_DELETE_SELECTED}")
    assert lecture < suppression, (
        "Le contrôle d'unicité de la sélection doit précéder le clic de "
        "suppression.")
    assert controle_de_cle < suppression, (
        "Le contrôle de la clé affichée doit précéder le clic de suppression.")


@pytest.mark.parametrize("keyword", ["Open Table Entry Creation",
                                     "Delete Table Entry"])
def test_chaque_mot_cle_qui_ecrit_passe_par_la_liste_blanche(keyword):
    body = "\n".join(_keyword_body(keyword))
    assert "Validate Write Target" in body, (
        "%s écrit sans passer par le périmètre déclaré : la règle de sûreté "
        "n'est plus mécanique." % keyword)


def test_le_perimetre_d_ecriture_par_defaut_du_page_object_est_vide():
    """Une campagne déclare son périmètre ; le page object n'en offre aucun par
    défaut, sans quoi une suite oublieuse écrirait où bon lui semble."""
    assert "@{WRITE_TARGET_ALLOWLIST}\n" in _page_object_text()
