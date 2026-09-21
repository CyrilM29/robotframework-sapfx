"""Le rendu d'un relevé tabulaire en SVG (`sapfx_common.table_svg`).

Ce que ces tests verrouillent tient en trois propriétés, et aucune n'est
cosmétique. Le document produit doit être du XML VALIDE (une visionneuse
stricte rejette tout le fichier pour un seul `&` nu, et une valeur de
paramètre SAP en contient volontiers) ; une troncature de rendu doit rester
ANNONCÉE et réversible (ellipse, infobulle portant la valeur entière, note de
pied) ; et deux rendus de la même donnée doivent être identiques, sans quoi un
artefact committé serait bruyant à chaque run.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from sapfx_common.table_svg import (
    column_widths,
    render_table_svg,
    svg_escape,
    table_columns,
    write_table_svg,
)

RELEVE = [
    {"NAME": "login/min_password_lng", "USER_VALUE": "", "DEFAULT_VALUE": "10"},
    {"NAME": "gw/reg_info", "USER_VALUE": "/usr/sap/A4H/reg_info",
     "DEFAULT_VALUE": "/usr/sap/A4H/reg_info"},
]


def test_echappement_traite_l_esperluette_en_premier():
    assert svg_escape("a & <b>") == "a &amp; &lt;b&gt;"
    assert "&amp;lt;" not in svg_escape("<")


def test_echappement_retire_les_caracteres_de_controle():
    # Non représentables en XML 1.0 : leur présence ferait rejeter le document
    # entier, et une valeur lue sur un écran peut en porter.
    assert svg_escape("a\x00b\x07c") == "abc"


def test_echappement_rend_une_valeur_absente_comme_une_chaine_vide():
    assert svg_escape(None) == ""


def test_les_colonnes_sont_l_union_ordonnee_des_cles():
    lignes = [{"A": 1}, {"A": 2, "B": 3}]
    assert table_columns(lignes) == ["A", "B"]


def test_une_colonne_absente_du_releve_echoue_en_listant_ce_qui_existe():
    with pytest.raises(ValueError) as echec:
        table_columns(RELEVE, ["NAME", "ABSENTE"])
    assert "ABSENTE" in str(echec.value)
    assert "DEFAULT_VALUE" in str(echec.value)


def test_une_liste_de_colonnes_vide_est_refusee():
    with pytest.raises(ValueError):
        table_columns(RELEVE, [])


def test_la_largeur_d_une_colonne_tient_compte_de_son_en_tete():
    # Les valeurs sont courtes, le nom technique long : une largeur dérivée des
    # seules valeurs couperait l'en-tête.
    etroit = column_widths([{"DEFAULT_VALUE": "1"}], ["DEFAULT_VALUE"])
    assert etroit[0] > len("DEFAULT_VALUE") * 6


def test_le_document_rendu_est_du_xml_valide():
    svg = render_table_svg(RELEVE, title="Profile parameters")
    racine = ET.fromstring(svg)
    assert racine.tag.endswith("svg")
    assert racine.get("viewBox")


def test_une_valeur_hostile_ne_casse_pas_le_document():
    svg = render_table_svg([{"NAME": 'a & b <script>', "V": '"x"'}])
    ET.fromstring(svg)  # ne doit pas lever
    assert "<script>" not in svg


def test_chaque_valeur_rendue_apparait_dans_le_document():
    svg = render_table_svg(RELEVE, columns=["NAME", "DEFAULT_VALUE"])
    textes = [n.text for n in ET.fromstring(svg).iter()
              if n.tag.endswith("text")]
    assert "login/min_password_lng" in textes
    assert "/usr/sap/A4H/reg_info" in textes


def test_une_cellule_coupee_porte_son_ellipse_et_sa_valeur_entiere():
    longue = "x" * 200
    svg = render_table_svg([{"V": longue}], max_cell_chars=20)
    racine = ET.fromstring(svg)
    textes = [n for n in racine.iter() if n.tag.endswith("text")]
    coupe = [n for n in textes if n.text and n.text.endswith("…")]
    assert coupe, "la cellule aurait dû être coupée"
    assert len(coupe[0].text) == 20
    infobulles = [n.text for n in coupe[0] if n.tag.endswith("title")]
    assert infobulles == [longue], "la valeur complète doit rester lisible"


def test_une_coupe_de_cellule_est_annoncee_en_pied():
    svg = render_table_svg([{"V": "x" * 200}], max_cell_chars=20)
    assert "coupée" in svg or "coupées" in svg


def test_un_plafond_nul_ne_coupe_rien():
    longue = "x" * 200
    svg = render_table_svg([{"V": longue}], max_cell_chars=0)
    assert longue in svg
    assert "…" not in svg


def test_un_tableau_borne_dit_qu_il_est_tronque():
    lignes = [{"N": str(i)} for i in range(10)]
    svg = render_table_svg(lignes, max_rows=3)
    assert "TRONQUÉ" in svg
    assert "3 ligne(s) rendues sur 10" in svg


def test_un_tableau_complet_annonce_ses_dimensions_sans_parler_de_troncature():
    svg = render_table_svg(RELEVE)
    assert "2 ligne(s), 3 colonne(s)." in svg
    assert "TRONQUÉ" not in svg


def test_un_releve_vide_rend_un_document_valide():
    svg = render_table_svg([], title="rien")
    ET.fromstring(svg)
    assert "0 ligne(s)" in svg


def test_deux_rendus_de_la_meme_donnee_sont_identiques():
    # Aucun horodatage n'est injecté : c'est ce qui rend un artefact comparable
    # d'un run à l'autre, comme les artefacts JSON du dépôt.
    assert render_table_svg(RELEVE) == render_table_svg(RELEVE)


def test_l_ecriture_rend_un_verdict_qui_decrit_ce_qui_a_ete_rendu(tmp_path):
    cible = tmp_path / "sous" / "releve.svg"
    verdict = write_table_svg(str(cible), RELEVE, columns=["NAME"])
    assert verdict["rows"] == 2
    assert verdict["total_rows"] == 2
    assert verdict["columns"] == ["NAME"]
    assert verdict["truncated_rows"] is False
    assert verdict["bytes"] > 0
    assert cible.exists()
    ET.fromstring(cible.read_text(encoding="utf-8"))


def test_le_verdict_signale_un_tableau_incomplet(tmp_path):
    lignes = [{"N": str(i)} for i in range(5)]
    verdict = write_table_svg(str(tmp_path / "t.svg"), lignes, max_rows=2)
    assert verdict["rows"] == 2
    assert verdict["total_rows"] == 5
    assert verdict["truncated_rows"] is True


def test_le_verdict_compte_les_cellules_coupees(tmp_path):
    lignes = [{"V": "x" * 100}, {"V": "court"}]
    verdict = write_table_svg(str(tmp_path / "t.svg"), lignes,
                              max_cell_chars=20)
    assert verdict["truncated_cells"] == 1


def test_le_fichier_est_ecrit_en_lf_quel_que_soit_le_poste(tmp_path):
    cible = tmp_path / "t.svg"
    write_table_svg(str(cible), RELEVE)
    assert b"\r\n" not in cible.read_bytes()
