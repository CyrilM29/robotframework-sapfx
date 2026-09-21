"""Tests hors navigateur des critères de sélection SE16 du canal WebGUI.

La capacité existe parce qu'un SID de critère gravé dans une couche métier
est faux en SILENCE : un autre critère se remplit et la lecture qui suit rend
des lignes parfaitement lisibles qui ne sont pas les bonnes. Les cas ci-dessous
visent donc d'abord les façons de se tromper sans que rien ne proteste.

Géométrie de référence : celle MESURÉE live le 2026-09-21 sur `SNWD_PD`
(A4H, client 001), où `PRODUCT_ID` est le deuxième critère et porte le préfixe
`ctxt` quand son voisin du dessus porte `txt`.
"""
import pytest

from SapFioriLibrary._ui5_js import WEBGUI_SELECTION_PROBE_JS
from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary
from sapfx_common.webgui_selection import (
    is_technical_label,
    missing_criterion_message,
    selection_criteria,
    selection_field_rank,
)


def _label(text, top, left, largeur=80, hauteur=16):
    return {"text": text, "top": top, "bottom": top + hauteur,
            "left": left, "right": left + largeur}


def _champ(sid, top, left=357, largeur=188, hauteur=20):
    return {"sid": sid, "top": top, "bottom": top + hauteur,
            "left": left, "right": left + largeur}


# L'écran réel, aux pixels relevés live (les libellés sont 3 px sous leur
# champ : c'est justement ce décalage qu'une égalité stricte raterait).
ECRAN_SNWD_PD_LABELS = [
    _label("NODE_KEY", 151, 276),
    _label("PRODUCT_ID", 215, 261),
    _label("TYPE_CODE", 247, 269),
    _label("CATEGORY", 279, 276),
    _label("Maximum No. of Hits", 600, 100),
]
ECRAN_SNWD_PD_CHAMPS = [
    _champ("wnd[0]/usr/txtI1-LOW", 148),
    _champ("wnd[0]/usr/ctxtI2-LOW", 212),
    _champ("wnd[0]/usr/ctxtI3-LOW", 244),
    _champ("wnd[0]/usr/ctxtI4-LOW", 276),
    _champ("wnd[0]/usr/txtMAX_SEL", 597),
]


class TestAppariement:
    def test_ecran_reel_apparie_chaque_critere_a_son_champ(self):
        criteres = selection_criteria(ECRAN_SNWD_PD_LABELS,
                                      ECRAN_SNWD_PD_CHAMPS)
        assert criteres == {
            "CATEGORY": "wnd[0]/usr/ctxtI4-LOW",
            "NODE_KEY": "wnd[0]/usr/txtI1-LOW",
            "PRODUCT_ID": "wnd[0]/usr/ctxtI2-LOW",
            "TYPE_CODE": "wnd[0]/usr/ctxtI3-LOW",
        }

    def test_le_prefixe_de_type_n_est_jamais_suppose(self):
        """Le premier critère porte `txt` et le deuxième `ctxt` : une carte
        construite par formule se tromperait sur l'un des deux."""
        criteres = selection_criteria(ECRAN_SNWD_PD_LABELS,
                                      ECRAN_SNWD_PD_CHAMPS)
        assert criteres["NODE_KEY"].endswith("txtI1-LOW")
        assert criteres["PRODUCT_ID"].endswith("ctxtI2-LOW")

    def test_le_rang_ne_fait_pas_le_nom(self):
        """Contre-épreuve du piège central : le MÊME rang désigne un autre
        champ dès que le choix des champs de sélection change."""
        autres = selection_criteria(
            [_label("CATEGORY", 215, 261)],
            [_champ("wnd[0]/usr/ctxtI2-LOW", 212)])
        assert autres == {"CATEGORY": "wnd[0]/usr/ctxtI2-LOW"}

    def test_un_libelle_traduit_n_est_pas_un_critere(self):
        criteres = selection_criteria(ECRAN_SNWD_PD_LABELS,
                                      ECRAN_SNWD_PD_CHAMPS)
        assert "Maximum No. of Hits" not in criteres
        assert all(not sid.endswith("MAX_SEL") for sid in criteres.values())

    def test_un_libelle_a_droite_du_champ_est_ecarte(self):
        """La colonne de droite d'un écran de sélection (la borne haute, une
        unité) ne doit jamais être prise pour le libellé du champ."""
        assert selection_criteria(
            [_label("PRODUCT_ID", 215, 600)],
            [_champ("wnd[0]/usr/ctxtI2-LOW", 212)]) == {}

    def test_le_libelle_d_une_autre_ligne_est_ecarte(self):
        assert selection_criteria(
            [_label("PRODUCT_ID", 400, 261)],
            [_champ("wnd[0]/usr/ctxtI2-LOW", 212)]) == {}

    def test_seule_la_borne_basse_est_retenue(self):
        assert selection_criteria(
            [_label("PRODUCT_ID", 215, 261)],
            [_champ("wnd[0]/usr/ctxtI2-HIGH", 212)]) == {}

    def test_un_champ_hors_ecran_de_selection_est_ignore(self):
        assert selection_criteria(
            [_label("TABLENAME", 215, 261)],
            [_champ("wnd[0]/usr/ctxtDATABROWSE-TABLENAME", 212)]) == {}

    def test_geometrie_illisible_ignoree_jamais_devinee(self):
        assert selection_criteria(
            [{"text": "PRODUCT_ID", "top": None, "bottom": 231,
              "left": 261, "right": 341}],
            [_champ("wnd[0]/usr/ctxtI2-LOW", 212)]) == {}

    def test_entrees_vides_rendent_une_carte_vide(self):
        assert selection_criteria([], []) == {}
        assert selection_criteria(None, None) == {}


class TestFragmentsDAccelerateur:
    """Le rendu DIFFÈRE d'une release à l'autre, et la seconde a fait échouer
    la capacité là où la première passait (mesuré le 2026-09-21).

    Sur ABAP Platform 2023, le WebGUI isole le caractère d'ACCÉLÉRATEUR
    clavier dans sa propre feuille : `CATEGORY` se rend en un parent
    `CATEGORY` (x 292 à 364) contenant une feuille `C` (x 292 à 302), et la
    barre de menus en ajoute autant qu'elle a d'entrées. Quatre critères se
    disputaient alors un champ nommé « C ».
    """

    # Le libellé complet et son fragment, aux pixels relevés live sur la 2023.
    LIBELLE = {"text": "CATEGORY", "top": 279, "bottom": 295,
               "left": 292, "right": 364}
    FRAGMENT = {"text": "C", "top": 280, "bottom": 294,
                "left": 292, "right": 302}
    CHAMP = _champ("wnd[0]/usr/ctxtI4-LOW", 276, left=373)

    def test_le_libelle_entier_gagne_sur_son_fragment(self):
        assert selection_criteria([self.LIBELLE, self.FRAGMENT],
                                  [self.CHAMP]) == {
            "CATEGORY": "wnd[0]/usr/ctxtI4-LOW"}

    def test_ordre_de_perception_indifferent(self):
        assert selection_criteria([self.FRAGMENT, self.LIBELLE],
                                  [self.CHAMP]) == {
            "CATEGORY": "wnd[0]/usr/ctxtI4-LOW"}

    def test_deux_criteres_ne_se_disputent_plus_la_meme_lettre(self):
        """Le cas EXACT qui a fait échouer le run de portabilité : deux lignes
        dont les libellés commencent par la même lettre."""
        criteres = selection_criteria(
            [self.LIBELLE, self.FRAGMENT,
             {"text": "CREATED_BY", "top": 311, "bottom": 327,
              "left": 278, "right": 364},
             {"text": "C", "top": 312, "bottom": 326,
              "left": 278, "right": 288}],
            [self.CHAMP, _champ("wnd[0]/usr/txtI5-LOW", 308, left=373)])
        assert criteres == {"CATEGORY": "wnd[0]/usr/ctxtI4-LOW",
                            "CREATED_BY": "wnd[0]/usr/txtI5-LOW"}

    def test_le_meme_libelle_a_trois_niveaux_du_dom_n_est_pas_ambigu(self):
        """Le parent, son `span` et son `label` portent le MÊME texte : trois
        candidats au même bord droit, un seul libellé."""
        criteres = selection_criteria(
            [{"text": "CATEGORY", "top": 272, "bottom": 296,
              "left": 52, "right": 372},
             {"text": "CATEGORY", "top": 275, "bottom": 295,
              "left": 52, "right": 372},
             self.LIBELLE, self.FRAGMENT],
            [self.CHAMP])
        assert criteres == {"CATEGORY": "wnd[0]/usr/ctxtI4-LOW"}

    def test_un_accelerateur_en_fin_de_libelle_ne_trompe_pas_non_plus(self):
        """Le fragment a alors presque le même bord droit que son libellé :
        c'est l'inclusion géométrique qui tranche, pas la distance."""
        criteres = selection_criteria(
            [{"text": "PRODUCT_ID", "top": 215, "bottom": 231,
              "left": 261, "right": 341},
             {"text": "D", "top": 216, "bottom": 230,
              "left": 333, "right": 341}],
            [_champ("wnd[0]/usr/ctxtI2-LOW", 212)])
        assert criteres == {"PRODUCT_ID": "wnd[0]/usr/ctxtI2-LOW"}

    def test_un_vrai_libelle_d_une_lettre_reste_lisible(self):
        """Contre-épreuve : la règle est l'INCLUSION, pas la longueur du
        texte, donc un champ réellement nommé d'une lettre est conservé."""
        assert selection_criteria(
            [{"text": "C", "top": 215, "bottom": 231,
              "left": 261, "right": 341}],
            [_champ("wnd[0]/usr/ctxtI2-LOW", 212)]) == {
            "C": "wnd[0]/usr/ctxtI2-LOW"}

    def test_un_libelle_voisin_de_meme_prefixe_n_est_pas_un_fragment(self):
        """Deux libellés distincts ne s'englobent jamais : `CAT` sur une autre
        ligne n'est pas un fragment de `CATEGORY`."""
        criteres = selection_criteria(
            [self.LIBELLE,
             {"text": "CAT", "top": 311, "bottom": 327,
              "left": 292, "right": 330}],
            [self.CHAMP, _champ("wnd[0]/usr/txtI5-LOW", 308, left=373)])
        assert criteres == {"CATEGORY": "wnd[0]/usr/ctxtI4-LOW",
                            "CAT": "wnd[0]/usr/txtI5-LOW"}


class TestAmbiguite:
    def test_deux_libelles_a_la_meme_distance_sont_refuses(self):
        with pytest.raises(ValueError) as refus:
            selection_criteria(
                [_label("PRODUCT_ID", 215, 261), _label("CATEGORY", 215, 261)],
                [_champ("wnd[0]/usr/ctxtI2-LOW", 212)])
        assert "PRODUCT_ID" in str(refus.value)
        assert "CATEGORY" in str(refus.value)

    def test_le_plus_proche_l_emporte_quand_il_n_y_a_pas_egalite(self):
        """Deux libellés sur la ligne, l'un nettement plus près : c'est le
        cas NORMAL d'un écran à deux colonnes, pas une ambiguïté."""
        criteres = selection_criteria(
            [_label("MANDT", 215, 20), _label("PRODUCT_ID", 215, 261)],
            [_champ("wnd[0]/usr/ctxtI2-LOW", 212)])
        assert criteres == {"PRODUCT_ID": "wnd[0]/usr/ctxtI2-LOW"}

    def test_un_nom_revendique_par_deux_criteres_est_refuse(self):
        with pytest.raises(ValueError) as refus:
            selection_criteria(
                [_label("PRODUCT_ID", 215, 261), _label("PRODUCT_ID", 247, 261)],
                [_champ("wnd[0]/usr/ctxtI2-LOW", 212),
                 _champ("wnd[0]/usr/ctxtI3-LOW", 244)])
        assert "PRODUCT_ID" in str(refus.value)
        assert "ctxtI2-LOW" in str(refus.value)
        assert "ctxtI3-LOW" in str(refus.value)


class TestPrimitives:
    @pytest.mark.parametrize("texte", ["PRODUCT_ID", "MANDT", "I1", "A"])
    def test_noms_techniques(self, texte):
        assert is_technical_label(texte) is True

    @pytest.mark.parametrize("texte", ["Maximum No. of Hits", "Produit",
                                       "product_id", "", None, "A B"])
    def test_libelles_non_techniques(self, texte):
        assert is_technical_label(texte) is False

    @pytest.mark.parametrize("sid,rang", [
        ("wnd[0]/usr/ctxtI2-LOW", 2),
        ("wnd[0]/usr/txtI13-LOW", 13),
        ("wnd[0]/usr/ctxtI2-HIGH", None),
        ("wnd[0]/usr/ctxtDATABROWSE-TABLENAME", None),
        ("", None),
    ])
    def test_rang_de_critere(self, sid, rang):
        assert selection_field_rank(sid) == rang

    def test_message_d_absence_liste_ce_que_l_ecran_porte(self):
        message = missing_criterion_message(
            "PRICE", {"PRODUCT_ID": "a", "CATEGORY": "b"})
        assert "PRICE" in message
        assert "CATEGORY, PRODUCT_ID" in message

    def test_message_d_absence_sur_un_ecran_sans_critere(self):
        assert "aucun" in missing_criterion_message("PRICE", {})


class FakeBrowser:
    def __init__(self, reponse):
        self.reponse = reponse
        self.appels = []

    def evaluate_javascript(self, selector, js, arg=None):
        self.appels.append((js, arg))
        return self.reponse


def _lib(browser):
    lib = SapFioriLibrary(ui5_timeout="2s")
    lib._browser = lambda: browser
    return lib


class TestKeyword:
    def test_le_gabarit_commence_par_sa_fonction(self):
        """Un commentaire posé AVANT ferait évaluer la source comme une
        expression : la fonction ne serait jamais appelée, le résultat
        reviendrait vide et l'appel RÉUSSIRAIT."""
        assert WEBGUI_SELECTION_PROBE_JS.startswith("() => {")

    def test_la_sonde_rend_la_carte_de_l_ecran(self):
        browser = FakeBrowser({"labels": ECRAN_SNWD_PD_LABELS,
                               "fields": ECRAN_SNWD_PD_CHAMPS})
        criteres = _lib(browser).get_webgui_selection_criteria()
        assert criteres["PRODUCT_ID"] == "wnd[0]/usr/ctxtI2-LOW"
        assert browser.appels[0][0] == WEBGUI_SELECTION_PROBE_JS

    def test_ecran_sans_critere_echoue_en_nommant_le_remede(self):
        browser = FakeBrowser({"labels": [], "fields": []})
        with pytest.raises(AssertionError) as refus:
            _lib(browser).get_webgui_selection_criteria()
        assert "écran de sélection" in str(refus.value)
        assert "Get Page Composition" in str(refus.value)

    def test_sonde_illisible_echoue_plutot_que_de_rendre_une_carte_vide(self):
        with pytest.raises(AssertionError):
            _lib(FakeBrowser(None)).get_webgui_selection_criteria()


class TestLibelleDuVoisin:
    """Un libellé appartient au PREMIER critère à sa droite, et à lui seul.

    La réserve de la revue indépendante du 2026-09-21 : les candidats n'étant
    bornés par aucune distance, un critère dépourvu de libellé propre adoptait
    celui d'un voisin, et la garde de doublon ne l'attrapait que lorsque le
    propriétaire légitime revendiquait AUSSI ce libellé, donc seulement quand
    les deux critères partageaient une ligne. C'était la seule mauvaise carte
    qui passait sans protester.
    """

    def test_un_critere_sans_libelle_propre_n_emprunte_pas_celui_du_voisin(self):
        # PRODUCT_ID est le libellé du premier critère ; le second, sur la même
        # ligne et plus à droite, n'a aucun libellé. Avant correction il
        # héritait de PRODUCT_ID et la carte pointait le mauvais champ.
        labels = [_label("PRODUCT_ID", top=100, left=20)]
        champs = [_champ("wnd[0]/usr/ctxtI2-LOW", top=100, left=120),
                  _champ("wnd[0]/usr/txtI7-LOW", top=100, left=400)]
        carte = selection_criteria(labels, champs)
        assert carte == {"PRODUCT_ID": "wnd[0]/usr/ctxtI2-LOW"}

    def test_le_critere_le_plus_proche_garde_son_libelle(self):
        """La contre-épreuve : sans champ interposé, l'appariement tient."""
        labels = [_label("PRODUCT_ID", top=100, left=20)]
        champs = [_champ("wnd[0]/usr/ctxtI2-LOW", top=100, left=120)]
        assert selection_criteria(labels, champs) == {
            "PRODUCT_ID": "wnd[0]/usr/ctxtI2-LOW"}

    def test_un_champ_interpose_sur_une_AUTRE_ligne_n_empeche_rien(self):
        """La règle ne vaut que sur la ligne du libellé : un critère d'une
        autre ligne, même horizontalement entre les deux, ne s'interpose pas.
        """
        labels = [_label("PRODUCT_ID", top=100, left=20)]
        champs = [_champ("wnd[0]/usr/ctxtI2-LOW", top=100, left=400),
                  _champ("wnd[0]/usr/txtI7-LOW", top=200, left=120)]
        assert selection_criteria(labels, champs) == {
            "PRODUCT_ID": "wnd[0]/usr/ctxtI2-LOW"}

    def test_chaque_critere_garde_le_sien_quand_chacun_a_son_libelle(self):
        """Deux couples libellé-champ alignés sur la même ligne : chacun garde
        le sien, la règle d'interposition ne doit pas les casser."""
        labels = [_label("PRODUCT_ID", top=100, left=20, largeur=60),
                  _label("CATEGORY", top=100, left=300, largeur=60)]
        champs = [_champ("wnd[0]/usr/ctxtI2-LOW", top=100, left=120),
                  _champ("wnd[0]/usr/txtI7-LOW", top=100, left=400)]
        assert selection_criteria(labels, champs) == {
            "CATEGORY": "wnd[0]/usr/txtI7-LOW",
            "PRODUCT_ID": "wnd[0]/usr/ctxtI2-LOW"}

    def test_le_cas_SILENCIEUX_un_champ_non_critere_possede_le_libelle(self):
        """Le cas que la garde de doublon ne pouvait PAS voir.

        Quand le propriétaire légitime du libellé n'est pas un critère (ici un
        champ de portée générale de l'écran), aucun autre critère ne revendique
        ce libellé : la garde de doublon reste muette et la carte nommait le
        critère d'après le libellé d'un AUTRE champ. C'est la seule mauvaise
        carte qui passait sans protester.
        """
        labels = [_label("PRODUCT_ID", top=100, left=20, largeur=60)]
        champs = [
            # Le propriétaire du libellé : un champ de l'écran qui n'est pas un
            # critère de table (pas de forme `I<N>-LOW`), donc jamais apparié.
            _champ("wnd[0]/usr/txtMAX_SEL", top=100, left=100, largeur=60),
            # Le critère sans libellé propre, plus à droite sur la même ligne.
            _champ("wnd[0]/usr/txtI7-LOW", top=100, left=400),
        ]
        assert selection_criteria(labels, champs) == {}


class TestSeuilsDeLaSonde:
    """Les deux seuils de la sonde sont ÉPINGLÉS, pas seulement écrits.

    Ce sont les deux endroits où un changement de rendu viderait la liste des
    libellés, et la revue indépendante du 2026-09-21 les avait relevés comme
    couverts par aucun test. L'issue resterait bruyante (carte vide donc échec
    actionnable), mais un seuil modifié sans intention resterait invisible.
    """

    def test_la_borne_a_un_enfant_est_conservee(self):
        """Élargir cette borne ramènerait des conteneurs dont le rectangle ne
        désigne aucune ligne ; la réduire aux seules feuilles reperdrait les
        libellés de la release qui isole le caractère d'accélérateur."""
        assert "childElementCount > 1" in WEBGUI_SELECTION_PROBE_JS

    def test_la_borne_de_longueur_du_texte_est_conservee(self):
        """Un texte plus long qu'un nom de champ est une phrase, pas un
        libellé de critère : la borne écarte les textes de portée générale de
        l'écran sans avoir à les connaître."""
        assert "texte.length > 40" in WEBGUI_SELECTION_PROBE_JS

    def test_les_deux_encodages_du_sid_sont_reconnus(self):
        """Le WebGUI live rend `SID:'...'` en littéral JS là où les fixtures
        rendent `\"SID\":\"...\"` : ne matcher que le second ne rendrait RIEN
        sur un vrai système."""
        assert '["\']?SID["\']?' in WEBGUI_SELECTION_PROBE_JS
