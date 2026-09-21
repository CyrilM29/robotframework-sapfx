"""Tests hors SAP de l'extraction tabulaire du canal RFC
(`Count Rfc Table Rows`, `Extract Rfc Table`) et de sa logique pure
``sapfx_common.rfc_extract``.

La propriété centrale, et la seule qui vaille d'être outillée : une lecture
``RFC_READ_TABLE`` bornée par ``ROWCOUNT`` rend N lignes PROPRES sans aucun
témoin de la troncature (mesuré live le 2026-09-16 : 50 lignes rendues sur
les 205 de ``SNWD_PD``, identifiants consécutifs). Le test qui compte est
donc la contre-épreuve : le relevé borné doit être REFUSÉ par la garde
partagée, alors même qu'il est parfaitement cohérent avec lui-même.
"""
import pytest

from sapfx_common import rfc_extract, table_extract
from SapApiLibrary import SapApiLibrary


def _reponse(*couples):
    return {"IT_TABLES": [{"TABNAME": n, "TABROWS": v} for n, v in couples]}


# --- logique pure ------------------------------------------------------------

def test_entries_total_trouve_la_table_sans_tenir_compte_de_la_casse():
    assert rfc_extract.entries_total(_reponse(("SBOOK", 28782)), "sbook") == 28782


def test_entries_total_refuse_une_table_absente_de_la_reponse():
    with pytest.raises(ValueError, match="aucune ligne pour la table SNWD_PD"):
        rfc_extract.entries_total(_reponse(("SCARR", 18)), "SNWD_PD")


def test_entries_total_refuse_une_reponse_sans_it_tables():
    with pytest.raises(ValueError, match="IT_TABLES est absente"):
        rfc_extract.entries_total({"AUTRE": []}, "SBOOK")


def test_entries_total_ne_prend_jamais_un_total_illisible_pour_zero():
    # Le repli sûr du dépôt : « non mesuré » n'est jamais « vide ».
    with pytest.raises(ValueError, match="total illisible"):
        rfc_extract.entries_total(_reponse(("SBOOK", "beaucoup")), "SBOOK")


def test_entries_total_laisse_passer_un_zero_legitime():
    # Une table réellement vide existe : c'est à l'appelant de trancher.
    assert rfc_extract.entries_total(_reponse(("SNWD_AD", 0)), "SNWD_AD") == 0


def test_require_bounded_scope_rend_le_total_fourni_et_refuse_un_negatif():
    assert rfc_extract.require_bounded_scope("SBOOK", None, 205) == 205
    with pytest.raises(ValueError, match="declared_rows"):
        rfc_extract.require_bounded_scope("SBOOK", None, -1)


def test_require_bounded_scope_laisse_mesurer_quand_rien_ne_filtre():
    assert rfc_extract.require_bounded_scope("SBOOK", None, None) is None
    assert rfc_extract.require_bounded_scope("SBOOK", "", None) is None
    assert rfc_extract.require_bounded_scope("SBOOK", [], None) is None


@pytest.mark.parametrize("options", [
    "CARRID EQ 'LH'",
    ["CARRID EQ 'LH'"],
    [{"TEXT": "CARRID EQ 'LH'"}],
])
def test_require_bounded_scope_refuse_filtre_sans_total_sous_ses_trois_formes(options):
    # Les trois formes traversent la frontière Robot ; aucune ne doit passer
    # entre les mailles, sans quoi le refus dépendrait de l'écriture choisie.
    with pytest.raises(ValueError, match="Lecture FILTRÉE"):
        rfc_extract.require_bounded_scope("SBOOK", options, None)


def test_le_refus_du_filtre_nomme_les_deux_sorties_honnetes():
    with pytest.raises(ValueError) as refus:
        rfc_extract.require_bounded_scope("SBOOK", "CARRID EQ 'LH'", None)
    message = str(refus.value)
    assert "retirer le filtre" in message and "declared_rows=" in message


def test_describe_rfc_source_annonce_le_plafond_demande():
    # Le plafond est l'information que le canal ne redonne nulle part.
    libelle = rfc_extract.describe_rfc_source("snwd_pd", ["A", "B"], None, 50)
    assert "SNWD_PD" in libelle and "PLAFOND demandé 50" in libelle
    assert "PLAFOND" not in rfc_extract.describe_rfc_source("SNWD_PD", ["A"], None, 0)


# --- keywords ----------------------------------------------------------------

def _lib_comptant(total, journal=None):
    lib = SapApiLibrary()

    def call_rfc(name, alias="default", **params):
        if journal is not None:
            journal.append((name, params))
        assert name == rfc_extract.COUNT_FUNCTION
        return _reponse((params["IT_TABLES"][0]["TABNAME"], total))

    lib.call_rfc = call_rfc
    return lib


def test_count_rfc_table_rows_passe_par_le_module_de_comptage():
    journal = []
    lib = _lib_comptant(28782, journal)
    assert lib.count_rfc_table_rows("sbook") == 28782
    nom, params = journal[0]
    # Le module qui COMPTE n'est pas celui qui LIT : c'est cette différence
    # qui empêche la garde de comparer une lecture à elle-même.
    assert nom == "EM_GET_NUMBER_OF_ENTRIES"
    assert params["IT_TABLES"] == [{"TABNAME": "SBOOK"}]


def test_count_rfc_table_rows_refuse_une_table_non_nommee():
    with pytest.raises(ValueError, match="Aucune table nommée"):
        SapApiLibrary().count_rfc_table_rows("   ")


def test_un_module_de_comptage_indisponible_nomme_ses_replis():
    lib = SapApiLibrary()

    def call_rfc(name, alias="default", **params):
        raise RuntimeError("FU_NOT_FOUND")

    lib.call_rfc = call_rfc
    with pytest.raises(RuntimeError) as refus:
        lib.count_rfc_table_rows("SBOOK")
    message = str(refus.value)
    assert "S_RFC" in message and "declared_rows=" in message
    assert "$count" in message   # le repli par un canal tiers est nommé


def _lib_lisant(lignes, total, journal=None):
    lib = _lib_comptant(total, journal)

    def read_rfc_table(table, fields, alias="default", options=None,
                       rowcount=0, delimiter="|"):
        if journal is not None:
            journal.append(("READ", {"table": table, "rowcount": rowcount}))
        return lignes[:rowcount] if rowcount else list(lignes)

    lib.read_rfc_table = read_rfc_table
    return lib


def _produits(n):
    return [{"PRODUCT_ID": "P-%04d" % i, "CATEGORY": "Trays", "PRICE": "3.25"}
            for i in range(n)]


def test_extract_rfc_table_rend_la_forme_commune_aux_quatre_canaux():
    lib = _lib_lisant(_produits(205), 205)
    releve = lib.extract_rfc_table("SNWD_PD", "PRODUCT_ID,CATEGORY,PRICE",
                                   key="PRODUCT_ID")
    assert releve["row_count"] == 205 and releve["declared_rows"] == 205
    assert releve["complete"] is True
    assert releve["columns"] == ["PRODUCT_ID", "CATEGORY", "PRICE"]
    # La forme est celle que la garde partagée et les cinq écrivains attendent.
    assert table_extract.table_extract_should_be_complete(releve)["complete"]


def test_une_lecture_bornee_est_propre_et_pourtant_refusee():
    """LA contre-épreuve : le relevé borné est cohérent avec lui-même.

    Ses 50 lignes sont pleines, ordonnées, sans clé manquante, donc AUCUNE
    garde de contenu ne peut le démasquer. Seul le total, qui vient d'un
    autre module, le fait.
    """
    journal = []
    lib = _lib_lisant(_produits(205), 205, journal)
    releve = lib.extract_rfc_table("SNWD_PD", "PRODUCT_ID,CATEGORY,PRICE",
                                   rowcount=50, key="PRODUCT_ID")
    assert releve["row_count"] == 50 and releve["declared_rows"] == 205
    assert releve["blank_rows"] == 0 and releve["keyless_rows"] == 0
    assert releve["complete"] is False
    with pytest.raises(AssertionError, match="il en manque 155"):
        table_extract.table_extract_should_be_complete(releve)
    assert ("READ", {"table": "SNWD_PD", "rowcount": 50}) in journal


def test_un_total_fourni_dispense_du_comptage():
    # Le cas de la preuve par un canal TIERS (le $count d'un service OData) :
    # ni le module de lecture ni celui de comptage n'y participent.
    journal = []
    lib = _lib_lisant(_produits(205), 999, journal)
    releve = lib.extract_rfc_table("SNWD_PD", "PRODUCT_ID", declared_rows=205)
    assert releve["declared_rows"] == 205
    assert not [nom for nom, _ in journal if nom == rfc_extract.COUNT_FUNCTION]


def test_un_filtre_sans_total_est_refuse_avant_tout_appel_reseau():
    """Le refus tombe À L'ENTRÉE, et c'est la moitié qui compte.

    Un refus qui constate après coup n'empêche rien : la leçon de la garde de
    cible qui rougissait dans un scénario pendant que les suivants écrivaient
    les fichiers du mauvais système.
    """
    journal = []
    lib = _lib_lisant(_produits(205), 205, journal)
    with pytest.raises(ValueError, match="Lecture FILTRÉE"):
        lib.extract_rfc_table("SBOOK", "CARRID", options="CARRID EQ 'LH'")
    assert journal == []   # ni lecture, ni comptage


def test_une_projection_vide_est_refusee_en_nommant_la_contrainte():
    lib = _lib_lisant(_produits(3), 3)
    with pytest.raises(ValueError, match="512 octets"):
        lib.extract_rfc_table("SBOOK", "")


def test_les_en_tetes_humains_n_effacent_pas_les_cles_techniques():
    # Propriété de canal : le RFC n'expose que des noms ABAP, l'exact inverse
    # du canal UI5 dont les seules clés sont des titres traduits.
    lib = _lib_lisant(_produits(2), 2)
    releve = lib.extract_rfc_table("SNWD_PD", "PRODUCT_ID,CATEGORY,PRICE",
                                   headers={"PRODUCT_ID": "Référence"})
    assert releve["columns"][0] == "PRODUCT_ID"
    assert releve["headers"]["PRODUCT_ID"] == "Référence"
    assert releve["headers"]["CATEGORY"] == "CATEGORY"


def test_une_table_inexistante_passe_toutes_les_egalites_et_seul_le_plancher_mord():
    """Le seul endroit de la chaîne où une faute de frappe sort au VERT.

    Le module de comptage annonce une table INEXISTANTE à zéro au lieu de la
    refuser. Le relevé est alors vide, le total vaut zéro, et les quatre
    égalités de la garde sont satisfaites : lu == déclaré, aucune ligne vide,
    aucune clé manquante. La contre-épreuve est donc en deux temps, sans quoi
    on ne saurait pas que le plancher est ce qui protège.
    """
    lib = _lib_lisant([], 0)
    releve = lib.extract_rfc_table("SNWD_TYPO", "PRODUCT_ID", key="PRODUCT_ID")
    assert releve["row_count"] == 0 and releve["declared_rows"] == 0
    assert releve["complete"] is True   # sans plancher, la garde passe

    table_extract.table_extract_should_be_complete(releve)   # et ne lève pas

    with pytest.raises(AssertionError, match="le plancher attendu est 1"):
        table_extract.table_extract_should_be_complete(releve, min_rows=1)


class _RefusDeTampon(Exception):
    """Doublure d'un refus applicatif pyrfc : le code vit dans ``key``."""

    key = rfc_extract.BUFFER_ERROR_CODE


def test_le_refus_de_tampon_est_relaye_INTACT_pour_rester_assertable(monkeypatch):
    """Le refus garde son type ET son code : c'est ce qui permet de l'asserter
    par `Rfc Should Fail With Code` plutôt que par un texte localisé.

    L'envelopper dans une erreur maison aurait donné un plus joli message et
    coûté l'attribut que `rfc_error_code` lit : un message amélioré ne vaut
    pas une assertion perdue.
    """
    from sapfx_common import rfc_channel

    lib = SapApiLibrary()
    lib.call_rfc = lambda *a, **k: _reponse(("SNWD_PD", 205))

    def read_rfc_table(*args, **kwargs):
        raise _RefusDeTampon("largeur de ligne dépassée")

    lib.read_rfc_table = read_rfc_table
    avertissements: list[str] = []
    monkeypatch.setattr("SapApiLibrary._rfc_extract.logger.warn",
                        lambda message: avertissements.append(str(message)))

    with pytest.raises(_RefusDeTampon) as refus:
        lib.extract_rfc_table("SNWD_PD", "A,B,C")
    assert rfc_channel.rfc_error_code(refus.value) == "DATA_BUFFER_EXCEEDED"

    # ... et le remède, lui, est JOURNALISÉ, parce qu'il ne se devine pas.
    assert len(avertissements) == 1
    assert "512 octets" in avertissements[0]
    assert "DEUX projections" in avertissements[0]
    assert "SNWD_PD" in avertissements[0] and "3 champ(s)" in avertissements[0]


def test_un_autre_refus_ne_declenche_aucun_avertissement_de_tampon(monkeypatch):
    """Contre-épreuve : l'avertissement ne doit pas se déclencher sur tout
    refus, sans quoi il deviendrait du bruit et n'orienterait plus rien."""
    class _AutreRefus(Exception):
        key = "TABLE_NOT_AVAILABLE"

    lib = SapApiLibrary()
    lib.call_rfc = lambda *a, **k: _reponse(("X", 1))

    def read_rfc_table(*args, **kwargs):
        raise _AutreRefus("table absente")

    lib.read_rfc_table = read_rfc_table
    avertissements: list[str] = []
    monkeypatch.setattr("SapApiLibrary._rfc_extract.logger.warn",
                        lambda message: avertissements.append(str(message)))

    with pytest.raises(_AutreRefus):
        lib.extract_rfc_table("X", "A")
    assert avertissements == []


def test_le_remede_de_tampon_nomme_la_largeur_et_les_deux_sorties():
    remede = rfc_extract.buffer_exceeded_remedy("snwd_pd", ["A", "B"])
    assert "SNWD_PD" in remede and "2 champ(s)" in remede
    assert "512 octets" in remede
    assert "restreindre la projection" in remede
    assert "DD03L" in remede   # comment mesurer la largeur soi-même


def test_le_libelle_de_provenance_voyage_dans_le_refus():
    lib = _lib_lisant(_produits(205), 205)
    releve = lib.extract_rfc_table("SNWD_PD", "PRODUCT_ID", rowcount=50)
    with pytest.raises(AssertionError) as refus:
        table_extract.table_extract_should_be_complete(releve)
    assert "PLAFOND demandé 50" in str(refus.value)
