"""Tests hors SAP de la surface du canal RFC : artefact et comparaison.

Aucun `pyrfc`, aucun serveur, aucun fichier hors ``tmp_path`` : la logique
est pure et l'écriture est la seule frontière. Ce qui est verrouillé ici est
ce qui rend une comparaison HONNÊTE : un hash indépendant de l'horodatage, un
périmètre qui refuse au lieu de moyenner, une identité conservée avec
l'artefact, et des composants rendus dans les trois catégories utiles.
"""
import json

import pytest

from SapApiLibrary import SapApiLibrary
from sapfx_common import rfc_surface

IDENTITE_2023 = {"system_id": "A4H", "client": "001", "release": "758",
                 "kernel": "793", "database": "HDB",
                 "operating_system": "Linux", "host": "vhcala4h"}
IDENTITE_1909 = dict(IDENTITE_2023, release="754", kernel="777")

MESURES_2023 = {"remote_enabled_function_modules": 22047,
                "published_business_interfaces": 735,
                "modern_programming_model_objects": 688}

COMPOSANTS_2023 = [{"name": "SAP_BASIS", "release": "758",
                    "support_level": "0000000002"},
                   {"name": "S4FND", "release": "108",
                    "support_level": "0000000002"}]


def _surface(target="2023", identity=None, measures=None, components=None,
             observed="2026-08-28T10:00:00+00:00"):
    return rfc_surface.build_surface(
        target, IDENTITE_2023 if identity is None else identity,
        MESURES_2023 if measures is None else measures, observed,
        components=COMPOSANTS_2023 if components is None else components)


# --- l'artefact ------------------------------------------------------------

def test_le_perimetre_est_derive_des_mesures_jamais_declare_a_part():
    # Les deux ne peuvent donc pas diverger : un artefact ne peut pas
    # prétendre couvrir une mesure qu'il ne porte pas.
    surface = _surface()
    assert surface["scope"]["measures"] == sorted(MESURES_2023)
    assert surface["summary"] == {"measures": 3, "components": 2}


def test_les_composants_sont_tries_et_dedoublonnes():
    surface = _surface(components=[
        {"name": "SAP_BASIS", "release": "758", "support_level": "2"},
        {"name": "SAP_BASIS", "release": "758", "support_level": "2"},
        {"name": "DMIS", "release": "2020", "support_level": "8"}])
    assert [c["name"] for c in surface["components"]] == ["DMIS", "SAP_BASIS"]


def test_un_composant_repete_avec_deux_releases_est_refuse():
    # Un inventaire ambigu produirait une comparaison dépendant de l'ordre de
    # lecture : mieux vaut refuser à l'écriture.
    with pytest.raises(ValueError, match="deux fois"):
        _surface(components=[{"name": "SAP_BASIS", "release": "758"},
                             {"name": "SAP_BASIS", "release": "757"}])


def test_un_composant_sans_nom_est_refuse():
    with pytest.raises(ValueError, match="sans nom"):
        _surface(components=[{"release": "758"}])


def test_une_mesure_non_entiere_est_refusee_a_l_ecriture():
    # Le cas réel : une valeur laissée telle quelle par une lecture de table,
    # ou un None d'une sonde qui a échoué. La refuser ici évite de la
    # comparer plus tard comme si elle voulait dire quelque chose.
    with pytest.raises(ValueError, match="entier"):
        _surface(measures={"modules": "vingt-deux mille"})
    with pytest.raises(ValueError, match="entier"):
        _surface(measures={"modules": None})


def test_une_mesure_negative_est_refusee():
    with pytest.raises(ValueError, match="positive"):
        _surface(measures={"modules": -1})


def test_un_perimetre_vide_est_refuse():
    with pytest.raises(ValueError, match="Périmètre vide"):
        _surface(measures={})


def test_une_cle_d_identite_inconnue_est_refusee_pas_ignoree():
    # L'ignorer laisserait croire qu'une valeur est comparée alors qu'elle
    # n'est jamais relue. L'adresse IP en est le cas typique : volatile,
    # elle est délibérément hors du modèle.
    with pytest.raises(ValueError, match="ip_address"):
        _surface(identity=dict(IDENTITE_2023, ip_address="172.17.0.4"))


def test_une_cle_d_identite_admise_mais_absente_vaut_la_chaine_vide():
    surface = _surface(identity={"system_id": "A4H"})
    assert surface["identity"]["release"] == ""
    assert set(surface["identity"]) == set(rfc_surface.IDENTITY_KEYS)


# --- le hash ---------------------------------------------------------------

def test_deux_releves_identiques_a_deux_moments_ont_le_meme_hash():
    tot = rfc_surface.comparison_hash(_surface(observed="2026-01-01T00:00:00Z"))
    tard = rfc_surface.comparison_hash(_surface(observed="2026-12-31T23:59:59Z"))
    assert tot == tard


def test_le_hash_couvre_l_identite_et_les_mesures():
    reference = rfc_surface.comparison_hash(_surface())
    assert rfc_surface.comparison_hash(_surface(identity=IDENTITE_1909)) != reference
    assert rfc_surface.comparison_hash(
        _surface(measures=dict(MESURES_2023, published_business_interfaces=736))
    ) != reference


def test_la_serialisation_est_deterministe():
    rendu = rfc_surface.surface_json(_surface())
    assert rendu == rfc_surface.surface_json(_surface())
    assert rendu.endswith("\n") and "\r" not in rendu
    assert json.loads(rendu)["target_id"] == "2023"


# --- la comparaison --------------------------------------------------------

def test_deux_perimetres_differents_sont_refuses_pas_moyennes():
    # Une mesure absente d'un côté ne vaut PAS zéro : la comparaison le dit
    # au lieu de fabriquer un écart.
    a = _surface("2023")
    b = _surface("1909", identity=IDENTITE_1909,
                 measures={"remote_enabled_function_modules": 20000})
    comparaison = rfc_surface.compare_surfaces(a, b)
    assert comparaison["compatible"] is False
    assert comparaison["measures_only_in_a"] == [
        "modern_programming_model_objects", "published_business_interfaces"]
    assert comparaison["measures_only_in_b"] == []
    # Les mesures COMMUNES restent chiffrées, elles.
    assert comparaison["measure_differences"] == [
        {"measure": "remote_enabled_function_modules", "a": 22047, "b": 20000,
         "delta": -2047}]


def test_la_comparaison_nomme_les_ecarts_de_mesure_et_leur_sens():
    a = _surface("2023")
    b = _surface("autre", measures=dict(MESURES_2023,
                                        modern_programming_model_objects=700))
    ecarts = rfc_surface.compare_surfaces(a, b)
    assert ecarts["compatible"] is True
    assert ecarts["measure_differences"] == [
        {"measure": "modern_programming_model_objects", "a": 688, "b": 700,
         "delta": 12}]


def test_les_composants_sortent_en_trois_categories():
    a = _surface("2023")
    b = _surface("1909", identity=IDENTITE_1909, components=[
        {"name": "SAP_BASIS", "release": "754", "support_level": "0"},
        {"name": "ST-PI", "release": "740", "support_level": "28"}])
    comparaison = rfc_surface.compare_surfaces(a, b)
    assert comparaison["components_common"] == ["SAP_BASIS"]
    assert comparaison["components_only_in_a"] == ["S4FND"]
    assert comparaison["components_only_in_b"] == ["ST-PI"]
    assert comparaison["component_release_changed"] == [
        {"name": "SAP_BASIS", "a": "758", "b": "754"}]


def test_les_differences_d_identite_sont_rendues_sans_bloquer():
    # Deux cibles distinctes DOIVENT différer ici : c'est ce qu'on veut lire,
    # pas une incompatibilité.
    comparaison = rfc_surface.compare_surfaces(
        _surface("2023"), _surface("1909", identity=IDENTITE_1909))
    assert comparaison["compatible"] is True
    assert comparaison["identity_differences"] == [
        {"key": "release", "a": "758", "b": "754"},
        {"key": "kernel", "a": "793", "b": "777"}]


def test_deux_identites_egales_ne_produisent_aucune_difference():
    comparaison = rfc_surface.compare_surfaces(_surface("a"), _surface("b"))
    assert comparaison["identity_differences"] == []


def test_un_schema_different_refuse_la_comparaison():
    autre = dict(_surface(), schema_version=99)
    with pytest.raises(ValueError, match="schema_version"):
        rfc_surface.compare_surfaces(_surface(), autre)


def test_le_rapport_nomme_les_cibles_et_les_ecarts():
    rapport = rfc_surface.render_surface_report(rfc_surface.compare_surfaces(
        _surface("2023"), _surface("1909", identity=IDENTITE_1909,
                                   components=[])))
    assert "`2023` vs `1909`" in rapport
    assert "758 -> 754" in rapport
    assert "S4FND" in rapport


def test_le_rapport_dit_quand_les_perimetres_ne_sont_pas_comparables():
    rapport = rfc_surface.render_surface_report(rfc_surface.compare_surfaces(
        _surface("2023"), _surface("1909", measures={"modules": 1})))
    assert "non probante" in rapport


# --- les keywords, seule frontière d'entrées-sorties -----------------------

def test_l_artefact_ecrit_est_relu_et_compare_par_les_keywords(tmp_path):
    lib = SapApiLibrary()
    chemin_a = tmp_path / "surface-2023.json"
    chemin_b = tmp_path / "surface-1909.json"
    preuve_a = lib.write_rfc_surface_artifact(
        str(chemin_a), "2023", IDENTITE_2023, MESURES_2023,
        components=COMPOSANTS_2023)
    lib.write_rfc_surface_artifact(
        str(chemin_b), "1909", IDENTITE_1909,
        dict(MESURES_2023, modern_programming_model_objects=0),
        components=[{"name": "SAP_BASIS", "release": "754",
                     "support_level": "0000000002"}])
    assert preuve_a["path"] == str(chemin_a)
    assert len(preuve_a["sha256"]) == 64
    assert preuve_a["summary"]["components"] == 2
    comparaison = lib.compare_rfc_surface_artifacts(str(chemin_a), str(chemin_b))
    assert comparaison["compatible"] is True
    assert comparaison["components_only_in_a"] == ["S4FND"]
    assert comparaison["measure_differences"][0]["delta"] == -688


def test_deux_ecritures_de_la_meme_cible_donnent_le_meme_hash(tmp_path):
    lib = SapApiLibrary()
    hashs = []
    for numero in (1, 2):
        preuve = lib.write_rfc_surface_artifact(
            str(tmp_path / f"s{numero}.json"), "2023", IDENTITE_2023,
            MESURES_2023, components=COMPOSANTS_2023)
        hashs.append(preuve["sha256"])
    assert hashs[0] == hashs[1]


def test_le_fichier_ecrit_est_du_json_deterministe_en_lf(tmp_path):
    chemin = tmp_path / "surface.json"
    SapApiLibrary().write_rfc_surface_artifact(
        str(chemin), "2023", IDENTITE_2023, MESURES_2023)
    brut = chemin.read_bytes().decode("utf-8")
    assert "\r\n" not in brut
    assert json.loads(brut)["identity"]["release"] == "758"


def test_l_artefact_se_relit_par_un_keyword_jamais_par_la_suite(tmp_path):
    # La contrepartie de l'écriture : une suite ne doit pas ouvrir le fichier
    # elle-même, sinon la lecture de l'artefact devient un import improvisé
    # dans un test.
    lib = SapApiLibrary()
    chemin = tmp_path / "surface.json"
    lib.write_rfc_surface_artifact(str(chemin), "2023", IDENTITE_2023,
                                   MESURES_2023, components=COMPOSANTS_2023)
    artefact = lib.read_rfc_surface_artifact(str(chemin))
    assert artefact["identity"]["kernel"] == "793"
    assert artefact["measures"]["published_business_interfaces"] == 735
    assert [c["name"] for c in artefact["components"]] == ["S4FND", "SAP_BASIS"]


def test_une_comparaison_impossible_devient_un_echec_actionnable(tmp_path):
    lib = SapApiLibrary()
    chemin_a = tmp_path / "a.json"
    chemin_b = tmp_path / "b.json"
    lib.write_rfc_surface_artifact(str(chemin_a), "2023", IDENTITE_2023,
                                   MESURES_2023)
    chemin_b.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    with pytest.raises(AssertionError, match="schema_version"):
        lib.compare_rfc_surface_artifacts(str(chemin_a), str(chemin_b))
