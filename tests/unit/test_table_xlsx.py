"""L'écriture d'un relevé en classeur Excel (`sapfx_common.table_xlsx`).

Un .xlsx écrit à la main échoue d'une façon particulièrement ingrate : le
fichier existe, il pèse le bon nombre d'octets, et Excel le déclare corrompu à
l'ouverture sans nommer la partie fautive. Ces tests relisent donc l'archive
partie par partie, et vérifient que chaque XML est bien formé, que les
relations pointent sur ce qui existe, et que la donnée écrite est celle qu'on
a passée.

Le reste verrouille le choix central du module : les cellules sont du TEXTE.
Un mandant `000` doit rester `000`, faute de quoi le classeur ment sur ce que
la campagne a mesuré.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile

import pytest

from sapfx_common.table_xlsx import (
    MAX_CELL_CHARS,
    build_xlsx,
    column_letter,
    normalize_sheet_name,
    read_table_xlsx,
    write_table_xlsx,
)

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
RELEVE = [
    {"MANDT": "000", "NAME": "login/min_password_lng", "VALUE": "10"},
    {"MANDT": "001", "NAME": "gw/reg_info", "VALUE": "/usr/sap/reg_info"},
]


def _feuille(octets: bytes) -> ET.Element:
    with zipfile.ZipFile(__import__("io").BytesIO(octets)) as archive:
        return ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))


def _valeurs(octets: bytes) -> list[list[str]]:
    lignes = []
    for row in _feuille(octets).find("m:sheetData", NS):
        lignes.append([(c.findtext("m:is/m:t", default="", namespaces=NS))
                       for c in row])
    return lignes


def test_les_lettres_de_colonne_passent_la_vingt_sixieme():
    assert column_letter(0) == "A"
    assert column_letter(25) == "Z"
    assert column_letter(26) == "AA"
    assert column_letter(27) == "AB"


def test_un_index_de_colonne_negatif_est_refuse():
    with pytest.raises(ValueError):
        column_letter(-1)


def test_un_nom_de_feuille_illegal_est_normalise_au_lieu_de_corrompre():
    # Excel refuse ces caractères en déclarant tout le fichier corrompu.
    assert normalize_sheet_name("Param[2023]:*") == "Param-2023---"
    assert len(normalize_sheet_name("x" * 60)) == 31
    assert normalize_sheet_name("   ") == "Relevé"


def test_l_archive_porte_les_six_parties_attendues():
    with zipfile.ZipFile(__import__("io").BytesIO(build_xlsx(RELEVE))) as arch:
        noms = set(arch.namelist())
    assert noms == {
        "[Content_Types].xml", "_rels/.rels", "xl/workbook.xml",
        "xl/_rels/workbook.xml.rels", "xl/styles.xml",
        "xl/worksheets/sheet1.xml"}


def test_chaque_partie_est_du_xml_bien_forme():
    with zipfile.ZipFile(__import__("io").BytesIO(build_xlsx(RELEVE))) as arch:
        for nom in arch.namelist():
            ET.fromstring(arch.read(nom))  # ne doit pas lever


def test_les_relations_pointent_sur_des_parties_existantes():
    with zipfile.ZipFile(__import__("io").BytesIO(build_xlsx(RELEVE))) as arch:
        noms = set(arch.namelist())
        rels = ET.fromstring(arch.read("xl/_rels/workbook.xml.rels"))
    cibles = {"xl/" + r.get("Target", "") for r in rels}
    assert cibles <= noms, "une relation désigne une partie absente"


def test_l_en_tete_puis_les_lignes_portent_la_donnee_passee():
    lignes = _valeurs(build_xlsx(RELEVE))
    assert lignes[0] == ["MANDT", "NAME", "VALUE"]
    assert lignes[1] == ["000", "login/min_password_lng", "10"]
    assert lignes[2][1] == "gw/reg_info"


def test_toute_cellule_est_ecrite_en_texte_explicite():
    # Le zéro de tête d'un mandant ne survit pas au retypage d'Excel : c'est
    # le piège que le module ferme, et il se vérifie sur le type de cellule.
    feuille = _feuille(build_xlsx(RELEVE))
    cellules = [c for row in feuille.find("m:sheetData", NS) for c in row
                if c.findtext("m:is/m:t", namespaces=NS)]
    assert all(c.get("t") == "inlineStr" for c in cellules)


def test_les_espaces_de_bord_sont_preserves():
    octets = build_xlsx([{"V": "  X  "}])
    feuille = _feuille(octets)
    # La première cellule est l'en-tête : la valeur est celle de la ligne 2.
    textes = feuille.findall(".//m:is/m:t", NS)
    assert [t.text for t in textes] == ["V", "  X  "]
    espace = "{http://www.w3.org/XML/1998/namespace}space"
    assert textes[1].get(espace) == "preserve"


def test_une_valeur_hostile_ne_casse_pas_le_classeur():
    octets = build_xlsx([{"V": 'a & b <c> "d"'}])
    assert _valeurs(octets)[1] == ['a & b <c> "d"']


def test_l_en_tete_est_fige_et_le_filtre_pose():
    feuille = _feuille(build_xlsx(RELEVE))
    assert feuille.find(".//m:pane", NS).get("state") == "frozen"
    assert feuille.find("m:autoFilter", NS).get("ref") == "A1:C3"


def test_l_en_tete_peut_ne_pas_etre_fige():
    feuille = _feuille(build_xlsx(RELEVE, freeze_header=False))
    assert feuille.find(".//m:pane", NS) is None


def test_un_releve_vide_reste_un_classeur_valide():
    lignes = _valeurs(build_xlsx([]))
    assert lignes == [[]]


def test_une_colonne_absente_echoue_en_listant_ce_qui_existe():
    with pytest.raises(ValueError) as echec:
        build_xlsx(RELEVE, columns=["NAME", "ABSENTE"])
    assert "ABSENTE" in str(echec.value)


def test_une_liste_de_valeurs_seules_n_est_pas_un_releve():
    # Confondre une colonne et un relevé produirait un classeur vide et
    # plausible : l'erreur doit tomber ici.
    with pytest.raises(ValueError) as echec:
        build_xlsx(["A", "B"])
    assert "dictionnaires" in str(echec.value)


def test_deux_ecritures_de_la_meme_donnee_sont_identiques():
    assert build_xlsx(RELEVE) == build_xlsx(RELEVE)


def test_une_cellule_trop_longue_pour_excel_est_coupee_et_comptee(tmp_path):
    verdict = write_table_xlsx(str(tmp_path / "t.xlsx"),
                               [{"V": "x" * (MAX_CELL_CHARS + 10)}])
    assert verdict["oversized_cells"] == 1


def test_le_verdict_decrit_ce_qui_a_ete_ecrit(tmp_path):
    cible = tmp_path / "sous" / "releve.xlsx"
    verdict = write_table_xlsx(str(cible), RELEVE, columns=["NAME", "VALUE"],
                               sheet_name="Paramètres")
    assert verdict["rows"] == 2
    assert verdict["total_rows"] == 2
    assert verdict["columns"] == ["NAME", "VALUE"]
    assert verdict["sheet"] == "Paramètres"
    assert verdict["truncated_rows"] is False
    assert verdict["bytes"] == cible.stat().st_size
    assert zipfile.is_zipfile(cible)


def test_le_verdict_signale_un_classeur_incomplet(tmp_path):
    lignes = [{"N": str(i)} for i in range(5)]
    verdict = write_table_xlsx(str(tmp_path / "t.xlsx"), lignes, max_rows=2)
    assert verdict["rows"] == 2
    assert verdict["truncated_rows"] is True


def test_l_aller_retour_rend_exactement_le_releve_ecrit(tmp_path):
    cible = tmp_path / "t.xlsx"
    write_table_xlsx(str(cible), RELEVE)
    assert read_table_xlsx(str(cible)) == RELEVE


def test_la_relecture_garde_les_valeurs_en_texte(tmp_path):
    # Retyper à la lecture réintroduirait le piège que l'écriture ferme.
    cible = tmp_path / "t.xlsx"
    write_table_xlsx(str(cible), [{"MANDT": "000", "N": "0012"}])
    assert read_table_xlsx(str(cible))[0] == {"MANDT": "000", "N": "0012"}


def test_une_ligne_a_trous_ne_decale_pas_les_colonnes(tmp_path):
    # Une cellule vide au MILIEU : lue sans sa référence, la valeur suivante
    # remonterait d'une colonne et le relevé serait faux mais plausible.
    cible = tmp_path / "t.xlsx"
    write_table_xlsx(str(cible), [{"A": "1", "B": "", "C": "3"}])
    assert read_table_xlsx(str(cible))[0] == {"A": "1", "B": "", "C": "3"}


def test_la_relecture_resout_une_table_de_chaines_partagees(tmp_path):
    # La forme qu'Excel écrit en réenregistrant : le lecteur doit la suivre,
    # sinon il ne sait relire que ses propres fichiers.
    cible = tmp_path / "partage.xlsx"
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    partagees = ('<sst xmlns="%s" count="2" uniqueCount="2">'
                 '<si><t>NAME</t></si><si><t>gw/reg_info</t></si></sst>' % ns)
    feuille = ('<worksheet xmlns="%s"><sheetData>'
               '<row r="1"><c r="A1" t="s"><v>0</v></c></row>'
               '<row r="2"><c r="A2" t="s"><v>1</v></c></row>'
               '</sheetData></worksheet>' % ns)
    with zipfile.ZipFile(cible, "w") as archive:
        archive.writestr("xl/sharedStrings.xml", partagees)
        archive.writestr("xl/worksheets/sheet1.xml", feuille)
    assert read_table_xlsx(str(cible)) == [{"NAME": "gw/reg_info"}]
