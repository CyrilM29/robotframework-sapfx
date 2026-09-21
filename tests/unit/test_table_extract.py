"""Le contrat d'extraction commun aux trois canaux (2026-09-15).

Ce module est né d'un constat mesuré : les trois canaux matérialisent leur
tableau paresseusement, et DEUX d'entre eux ne laissent aucune trace. Les
tests ci-dessous établissent donc autant les propriétés attendues que les
situations gênantes qui justifient la garde.
"""
from __future__ import annotations

import pytest

from sapfx_common.table_extract import (
    build_table_extract,
    describe_table_extract,
    project_extract_rows,
    table_extract_should_be_complete,
)

#: Un relevé complet et propre, la référence.
PLEIN = [{"SPRSL": "E", "ARBGB": "MD_LOG", "MSGNR": "001"},
         {"SPRSL": "F", "ARBGB": "MEMORY", "MSGNR": "002"}]


class TestAssemblage:
    def test_le_releve_porte_ses_colonnes_ses_titres_et_son_total(self):
        extrait = build_table_extract(
            PLEIN, headers={"SPRSL": "Langue", "ARBGB": "Classe"},
            declared_rows=2, source="T100")
        assert extrait["columns"] == ["SPRSL", "ARBGB", "MSGNR"]
        assert extrait["headers"] == {"SPRSL": "Langue", "ARBGB": "Classe",
                                      "MSGNR": "MSGNR"}
        assert extrait["row_count"] == 2
        assert extrait["declared_rows"] == 2
        assert extrait["missing_rows"] == 0
        assert extrait["complete"] is True
        assert extrait["source"] == "T100"

    def test_une_colonne_sans_titre_garde_son_identifiant(self):
        # Mieux vaut un nom technique qu'une colonne sans nom.
        extrait = build_table_extract(PLEIN, headers={"SPRSL": "   "})
        assert extrait["headers"]["SPRSL"] == "SPRSL"

    def test_un_total_non_declare_ne_vaut_jamais_complet(self):
        # Le repli sûr du dépôt : une absence de mesure n'est pas un verdict.
        extrait = build_table_extract(PLEIN)
        assert extrait["declared_rows"] is None
        assert extrait["missing_rows"] is None
        assert extrait["complete"] is None, "ni True ni False : non mesuré"

    def test_le_relevé_court_est_compte_sans_etre_juge(self):
        extrait = build_table_extract(PLEIN, declared_rows=4133)
        assert extrait["missing_rows"] == 4131
        assert extrait["complete"] is False

    def test_les_lignes_vides_et_sans_cle_sont_comptees_a_part(self):
        releve = PLEIN + [{"SPRSL": "", "ARBGB": "", "MSGNR": ""},
                          {"SPRSL": "", "ARBGB": "X", "MSGNR": "9"}]
        extrait = build_table_extract(releve, declared_rows=4, key="SPRSL")
        assert extrait["blank_rows"] == 1
        # La ligne creuse ET celle qui a perdu sa seule clé.
        assert extrait["keyless_rows"] == 2
        assert extrait["complete"] is False

    def test_une_colonne_sans_nom_est_laissee_de_cote_mais_pas_en_silence(self):
        # Mesuré sur cap-sflight le 2026-09-15 : une table Fiori Elements porte
        # une colonne à en-tête VIDE (l'indicateur de brouillon). Elle n'est pas
        # extractible, et la retirer est juste ; le faire sans le dire ne l'est
        # pas, parce que le même symptôme apparaîtrait sur un DÉCALAGE de
        # colonnes, où les valeurs ont glissé d'un cran.
        # Le retrait n'a lieu que sur le chemin où les colonnes sont DEMANDÉES,
        # qui est celui du canal UI5 (`Get Ui5 Table Info` les fournit).
        releve = [{"  ": "", "ID": "1", "Nom": "Benz"}]
        extrait = build_table_extract(releve, columns=["  ", "ID", "Nom"],
                                      declared_rows=1)
        assert extrait["columns"] == ["ID", "Nom"]
        assert extrait["ignored_columns"] == ["  "]
        # Sans liste demandée, rien n'est retiré : l'union des clés fait foi,
        # et c'est ce qui permet à une colonne inattendue de se voir.
        assert build_table_extract(releve)["columns"] == ["  ", "ID", "Nom"]

    def test_une_colonne_NOMMEE_laissee_de_cote_est_le_temoin_d_un_decalage(self):
        releve = [{"ID": "1", "Nom": "Benz", "COL9": "glissée"}]
        extrait = build_table_extract(releve, columns=["ID", "Nom"])
        assert extrait["ignored_columns"] == ["COL9"]
        assert "COL9" in describe_table_extract(extrait)

    def test_rien_n_est_laisse_de_cote_sur_un_releve_ordinaire(self):
        assert build_table_extract(PLEIN)["ignored_columns"] == []

    def test_les_arguments_arrivent_en_chaine_par_la_frontiere_robot(self):
        # Via `execute_step` et la ligne de commande, tout est une chaîne.
        extrait = build_table_extract(PLEIN, columns="SPRSL,ARBGB",
                                      declared_rows="2")
        assert extrait["columns"] == ["SPRSL", "ARBGB"]
        assert extrait["declared_rows"] == 2

    def test_un_total_negatif_est_refuse_en_le_disant(self):
        with pytest.raises(ValueError, match="négatif"):
            build_table_extract(PLEIN, declared_rows=-1)

    def test_un_total_PROVISOIRE_ne_vaut_pas_complet(self):
        # `isLengthFinal` à False : la source n'a pas fini de compter, donc
        # l'égalité lu == déclaré peut être vraie un instant et fausse le
        # suivant. Ni True ni False : non mesurable.
        extrait = build_table_extract(PLEIN, declared_rows=2,
                                      declared_final=False)
        assert extrait["declared_final"] is False
        assert extrait["complete"] is None

    def test_une_source_qui_n_expose_pas_la_notion_a_un_total_definitif(self):
        # Un modèle client connaît ses données : son binding n'a pas
        # d'`isLengthFinal` et rend None. Le traiter comme provisoire
        # refuserait des relevés légitimement complets.
        assert build_table_extract(PLEIN, declared_rows=2,
                                   declared_final=None)["complete"] is True

    def test_le_drapeau_survit_a_la_frontiere_robot(self):
        # Via la ligne de commande et `execute_step`, un booléen arrive en
        # chaîne, et "False" est une chaîne NON VIDE, donc vraie en Python.
        assert build_table_extract(PLEIN, declared_rows=2,
                                   declared_final="False")["complete"] is None
        assert build_table_extract(PLEIN, declared_rows=2,
                                   declared_final="True")["complete"] is True


class TestGarde:
    def test_un_releve_complet_passe_et_rend_le_relevé(self):
        extrait = build_table_extract(PLEIN, declared_rows=2)
        assert table_extract_should_be_complete(
            extrait, min_rows=2, min_columns=3)["row_count"] == 2

    def test_un_total_provisoire_est_refuse_comme_un_total_absent(self):
        # Le contrôle vit ICI et non dans un scénario : les suites sont faites
        # pour être jouées un scénario à la fois, et un contrôle qui ne vit
        # que dans le scénario de lecture disparaît dès qu'on joue une
        # extraction seule.
        extrait = build_table_extract(PLEIN, declared_rows=2,
                                      declared_final=False, source="liste UI5")
        with pytest.raises(AssertionError) as echec:
            table_extract_should_be_complete(extrait)
        assert "PROVISOIRE" in str(echec.value)
        assert "liste UI5" in str(echec.value)

    def test_le_silence_sur_le_total_est_refuse(self):
        # C'est le cas le plus dangereux : le canal qui se tait est celui qui
        # ne laisse aucune autre trace.
        extrait = build_table_extract(PLEIN)
        with pytest.raises(AssertionError, match="DÉCLARÉ aucun total"):
            table_extract_should_be_complete(extrait)

    def test_le_releve_court_est_refuse_en_nommant_le_manque(self):
        extrait = build_table_extract(PLEIN, declared_rows=4133,
                                      source="liste des voyages")
        with pytest.raises(AssertionError) as echec:
            table_extract_should_be_complete(extrait)
        message = str(echec.value)
        assert "2 ligne(s) lues pour 4133 DÉCLARÉES" in message
        assert "il en manque 4131" in message
        assert "liste des voyages" in message

    def test_le_releve_creux_est_refuse_meme_au_bon_nombre_de_lignes(self):
        creux = [{"A": "", "B": ""} for _ in range(3)]
        extrait = build_table_extract(creux, declared_rows=3)
        with pytest.raises(AssertionError, match="ENTIÈREMENT vides"):
            table_extract_should_be_complete(extrait)

    def test_une_cle_manquante_est_refusee(self):
        releve = [{"NAME": "abap/heap", "V": "1"}, {"NAME": "", "V": "2"}]
        extrait = build_table_extract(releve, declared_rows=2, key="NAME")
        with pytest.raises(AssertionError, match="colonne clé"):
            table_extract_should_be_complete(extrait)

    def test_les_planchers_sont_verifies_apres_la_completude(self):
        extrait = build_table_extract(PLEIN, declared_rows=2)
        with pytest.raises(AssertionError, match="le plancher attendu est 10"):
            table_extract_should_be_complete(extrait, min_rows=10)
        with pytest.raises(AssertionError, match="colonne"):
            table_extract_should_be_complete(extrait, min_columns=9)

    def test_l_ordre_des_refus_designe_la_cause_la_plus_amont(self):
        # Un relevé à la fois court ET creux est d'abord un relevé court :
        # corriger la lecture fait disparaître les deux, l'inverse est faux.
        creux = [{"A": ""} for _ in range(3)]
        extrait = build_table_extract(creux, declared_rows=99)
        with pytest.raises(AssertionError, match="DÉCLARÉES"):
            table_extract_should_be_complete(extrait)


class TestJournal:
    def test_le_resume_dit_toujours_le_total_declare(self):
        # Y compris quand il coïncide : c'est ce qui distingue un journal qui
        # prouve d'un journal qui rassure.
        assert "2/2 ligne(s), complet" in describe_table_extract(
            build_table_extract(PLEIN, declared_rows=2))

    def test_le_resume_nomme_l_incompletude(self):
        resume = describe_table_extract(
            build_table_extract(PLEIN, declared_rows=4133))
        assert "2/4133 ligne(s), INCOMPLET (4131 manquantes)" in resume

    def test_le_resume_ne_maquille_pas_un_total_absent(self):
        resume = describe_table_extract(build_table_extract(PLEIN))
        assert "NON DÉCLARÉ" in resume
        assert "complet" not in resume

    def test_le_resume_ne_maquille_pas_un_total_provisoire(self):
        # Le cas le plus traître du journal : lu et déclaré COÏNCIDENT, donc
        # un résumé naïf écrirait « complet » sur une mesure qui ne l'établit
        # pas.
        resume = describe_table_extract(
            build_table_extract(PLEIN, declared_rows=2, declared_final=False))
        assert "PROVISOIRE" in resume
        assert "complet" not in resume


class TestReleveTropLong:
    """Un relevé PLUS LONG que le total déclaré (2026-09-16).

    Relevé par une revue indépendante : `complete` valait bien `False`, mais
    la garde ne refusait que le cas COURT, donc les cinq fichiers étaient
    écrits et la campagne ne rougissait qu'après coup, sur son bilan. Le cas
    n'est pas théorique sur les deux canaux dont le total est publié par la
    couche de rendu : un total de grille périmé ou une longueur de binding lue
    avant la dernière page suffisent.
    """

    def test_le_verdict_le_voyait_deja(self):
        extrait = build_table_extract(PLEIN, declared_rows=1)
        assert extrait["complete"] is False

    def test_mais_la_garde_le_laissait_passer_et_ne_le_laisse_plus(self):
        extrait = build_table_extract(PLEIN, declared_rows=1, source="grille")
        with pytest.raises(AssertionError) as echec:
            table_extract_should_be_complete(extrait)
        message = str(echec.value)
        assert "2 ligne(s) lues pour 1 DÉCLARÉES" in message
        assert "de PLUS" in message
        assert "même instant" in message

    def test_l_egalite_reste_le_seul_cas_accepte(self):
        assert table_extract_should_be_complete(
            build_table_extract(PLEIN, declared_rows=2))["complete"] is True


class TestProjection:
    """La moitié de l'assertion reine : mettre le relevé dans la forme du
    fichier avant de les confronter (promue le 2026-09-16)."""

    def test_le_releve_est_re_cle_sur_les_entetes_du_fichier(self):
        extrait = build_table_extract(PLEIN, declared_rows=2)
        projete = project_extract_rows(extrait, ["Langue", "Classe", "Numéro"])
        assert projete[0] == {"Langue": "E", "Classe": "MD_LOG",
                              "Numéro": "001"}

    def test_la_borne_ramene_aux_lignes_reellement_ecrites(self):
        # Sans elle, une extraction bornée comparerait un extrait à un relevé
        # complet et échouerait sur une troncature pourtant demandée.
        extrait = build_table_extract(PLEIN, declared_rows=2)
        assert len(project_extract_rows(extrait, ["a", "b", "c"], 1)) == 1
        assert len(project_extract_rows(extrait, ["a", "b", "c"])) == 2

    def test_un_nombre_d_entetes_different_est_REFUSE(self):
        # Les deux ne décrivent alors pas le même tableau : les confronter ne
        # prouverait rien, et `zip` tronquerait en silence.
        extrait = build_table_extract(PLEIN, declared_rows=2)
        with pytest.raises(ValueError, match="ne décrivent pas le même tableau"):
            project_extract_rows(extrait, ["Langue", "Classe"])

    def test_les_entetes_arrivent_en_chaine_par_la_frontiere_robot(self):
        extrait = build_table_extract(PLEIN, declared_rows=2)
        assert project_extract_rows(extrait, "a,b,c")[0] == {
            "a": "E", "b": "MD_LOG", "c": "001"}
