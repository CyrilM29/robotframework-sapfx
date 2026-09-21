"""Tests hors SAP de `sapfx_common.security_surface` (convention #5).

Ce fichier éprouve la logique pure de la **surface d'attaque**. Chaque groupe
de tests fige une mesure faite le 2026-09-14 sur ABAP Platform 2023, et
surtout l'écart entre ce qu'une lecture naïve conclut et ce que le système
fait : un compte non verrouillé mais expiré, un service déclaré mais inactif,
une commande qui accepte des arguments, un journal armé qui n'enregistre rien.
"""
import pytest

from sapfx_common.security_surface import (
    AUDIT_COVERAGE_VERDICTS,
    classify_account_usability,
    classify_external_command,
    corroborate_audit_coverage,
    summarize_accounts,
    summarize_external_commands,
    summarize_icf_exposure,
    summarize_trust_surface,
)

AUJOURDHUI = "20260914"


# --------------------------------------------------------------------- #
# Comptes : utilisable n'est PAS la même chose que non verrouillé
# --------------------------------------------------------------------- #
def test_compte_sans_limite_ni_verrou_est_actif():
    fiche = classify_account_usability(
        {"user": "DEVELOPER", "locked": False, "valid_to": "00000000"},
        AUJOURDHUI)
    assert fiche["usable"] is True
    assert fiche["status"] == "active"
    assert fiche["reasons"] == []


def test_compte_expire_n_est_pas_utilisable_meme_sans_verrou():
    """La mesure qui a fait naître ce module : deux comptes de la cible
    portent une date de fin échue alors que le masque de verrouillage dit
    « non verrouillé ». Les compter comme actifs surestime la surface."""
    fiche = classify_account_usability(
        {"user": "DEVELOPER_5", "locked": False, "valid_to": "20241231"},
        AUJOURDHUI)
    assert fiche["usable"] is False
    assert fiche["status"] == "expired"
    assert fiche["reasons"] == ["expired"]


def test_compte_verrouille_et_expire_porte_les_deux_raisons():
    """Lever le verrou ne suffirait pas à rendre ce compte utilisable : la
    première raison ne doit donc pas masquer la seconde."""
    fiche = classify_account_usability(
        {"user": "X", "locked": True, "valid_to": "20241231"}, AUJOURDHUI)
    assert fiche["status"] == "locked"
    assert sorted(fiche["reasons"]) == ["expired", "locked"]
    assert fiche["usable"] is False


def test_compte_pas_encore_valide():
    fiche = classify_account_usability(
        {"user": "FUTUR", "valid_from": "20991231"}, AUJOURDHUI)
    assert fiche["status"] == "not_yet_valid"
    assert fiche["usable"] is False


def test_date_illisible_rend_unknown_jamais_actif():
    """Le repli sûr de tout ce domaine : ne jamais inventer une
    disponibilité."""
    fiche = classify_account_usability(
        {"user": "X", "valid_to": "pas-une-date"}, AUJOURDHUI)
    assert fiche["status"] == "unknown"
    assert fiche["usable"] is False


def test_date_vide_signifie_pas_de_limite_pas_absence_de_donnee():
    for vide in ("", "00000000", "0"):
        fiche = classify_account_usability(
            {"user": "X", "valid_to": vide}, AUJOURDHUI)
        assert fiche["status"] == "active", vide


def test_compte_sans_nom_refuse():
    with pytest.raises(ValueError, match="nom"):
        classify_account_usability({"user": ""}, AUJOURDHUI)


def test_today_doit_etre_une_date_fournie_par_l_appelant():
    """La logique pure ne lit jamais l'horloge : c'est ce qui la rend
    reproductible."""
    with pytest.raises(ValueError, match="AAAAMMJJ"):
        classify_account_usability({"user": "X"}, "aujourd'hui")


def test_resume_comptes_separe_utilisables_et_verrouilles():
    """Sur la cible : six comptes, zéro verrouillé, deux expirés, donc
    quatre utilisables. `usable` et `locked` ne sont pas complémentaires."""
    comptes = [
        {"user": "DEVELOPER", "locked": False, "valid_to": "00000000"},
        {"user": "DDIC", "locked": False, "valid_to": "00000000"},
        {"user": "SAP*", "locked": False, "valid_to": "00000000"},
        {"user": "BWDEVELOPER", "locked": False, "valid_to": "00000000"},
        {"user": "DEVELOPER_5", "locked": False, "valid_to": "20241231"},
        {"user": "SDMI_DLRYYAU", "locked": False, "valid_to": "20241231"},
    ]
    resume = summarize_accounts(comptes, AUJOURDHUI)
    assert resume["total"] == 6
    assert resume["usable"] == ["BWDEVELOPER", "DDIC", "DEVELOPER", "SAP*"]
    assert resume["unusable"] == ["DEVELOPER_5", "SDMI_DLRYYAU"]
    assert resume["by_status"]["expired"] == ["DEVELOPER_5", "SDMI_DLRYYAU"]
    # Aucun compte verrouillé, et pourtant deux inutilisables : c'est tout
    # l'objet de la fonction.
    assert "locked" not in resume["by_status"]


def test_resume_comptes_est_trie_donc_comparable():
    a = summarize_accounts([{"user": "B"}, {"user": "A"}], AUJOURDHUI)
    b = summarize_accounts([{"user": "A"}, {"user": "B"}], AUJOURDHUI)
    assert a == b


# --------------------------------------------------------------------- #
# Exposition web : déclaré n'est pas servi
# --------------------------------------------------------------------- #
def _noeud(nom, actif=True, ssl=False, user="", named=True):
    return {"name": nom, "active": actif, "ssl": ssl, "stored_user": user,
            "named": named}


def test_exposition_compte_les_appariements_de_la_jointure():
    """Le témoin que la revue indépendante a fait ajouter : comparer « actifs »
    et « déclarés » ne dit RIEN de la seconde table, les deux venant de la
    table d'activation. Sans `matched`, une jointure cassée rend un résumé
    indistinguable d'un système sain."""
    resume = summarize_icf_exposure(
        [_noeud("webgui"), _noeud("H2", named=False)])
    assert resume["active"] == 2
    assert resume["matched"] == 1
    assert resume["unmatched"] == 1


def test_exposition_jointure_cassee_ressemble_a_un_systeme_sain():
    """La contre-épreuve qui montre pourquoi le témoin est nécessaire : tous
    les autres champs prennent exactement la forme d'un système sans défaut."""
    casse = summarize_icf_exposure(
        [_noeud("H1", named=False), _noeud("H2", named=False)], ("webgui",))
    assert casse["with_stored_user"] == []      # aucun compte de service
    assert casse["sensitive_active"] == []      # aucun service sensible
    assert casse["active"] == 2                 # et le compte d'actifs est juste
    # Seul ce champ trahit la jointure perdue.
    assert casse["unmatched"] == 2


def test_exposition_compte_les_actifs_pas_les_declares():
    """3410 déclarés pour 219 actifs sur la cible : rapporter le grand chiffre
    donne une surface que personne ne peut auditer."""
    noeuds = [_noeud(f"s{i}", actif=False) for i in range(30)]
    noeuds += [_noeud("webgui"), _noeud("its")]
    resume = summarize_icf_exposure(noeuds, ("webgui",))
    assert resume["declared"] == 32
    assert resume["active"] == 2
    assert resume["exposure_ratio"] == round(2 / 32, 4)


def test_exposition_compte_les_actifs_sans_chiffrement():
    noeuds = [_noeud("a", ssl=True), _noeud("b", ssl=False),
              _noeud("c", ssl=False, actif=False)]
    resume = summarize_icf_exposure(noeuds)
    assert resume["active"] == 2
    # Le noeud inactif sans SSL ne compte pas : il ne répond pas.
    assert resume["active_without_ssl"] == 1


def test_exposition_isole_les_services_a_compte_de_service():
    """Un service qui porte un compte s'exécute sans authentifier son
    appelant : la propriété la plus intéressante de l'inventaire."""
    resume = summarize_icf_exposure(
        [_noeud("anonyme", user="SERVICE_USER"), _noeud("normal")])
    assert resume["with_stored_user"] == ["anonyme"]


def test_exposition_sans_motif_sensible_ne_signale_rien():
    resume = summarize_icf_exposure([_noeud("webgui")])
    assert resume["sensitive_active"] == []


def test_exposition_vide_ne_divise_pas_par_zero():
    resume = summarize_icf_exposure([])
    assert resume["declared"] == 0 and resume["exposure_ratio"] == 0.0


# --------------------------------------------------------------------- #
# Commandes du système d'exploitation
# --------------------------------------------------------------------- #
def test_commande_acceptant_des_arguments_est_distinguee():
    """L'écart entre « exécuter une sauvegarde » et « exécuter ce que
    l'appelant voudra »."""
    ouverte = classify_external_command(
        {"NAME": "CAT", "OPSYSTEM": "UNIX", "OPCOMMAND": "cat", "ADDPAR": "X"})
    figee = classify_external_command(
        {"NAME": "FIXE", "OPSYSTEM": "UNIX", "OPCOMMAND": "ls", "ADDPAR": ""})
    assert ouverte["accepts_additional"] is True
    assert figee["accepts_additional"] is False


def test_commande_client_est_reperee():
    for nom in ("ZBACKUP", "YTOOL", "/ACME/RUN"):
        assert classify_external_command({"NAME": nom})["customer_defined"]
    assert not classify_external_command({"NAME": "BRBACKUP"})["customer_defined"]


def test_commande_sans_nom_refusee():
    with pytest.raises(ValueError, match="nom"):
        classify_external_command({"NAME": ""})


def test_resume_commandes_croise_client_et_arguments():
    """Le cas le plus ouvert : une commande définie sur le système ET
    acceptant des arguments."""
    resume = summarize_external_commands([
        {"NAME": "BRBACKUP", "ADDPAR": "X", "OPSYSTEM": "ANYOS"},
        {"NAME": "ZDANGER", "ADDPAR": "X", "OPSYSTEM": "UNIX"},
        {"NAME": "ZSAFE", "ADDPAR": "", "OPSYSTEM": "UNIX"},
    ])
    assert resume["total"] == 3
    assert resume["accepting_additional"] == 2
    assert resume["fixed"] == 1
    assert resume["customer_defined"] == ["ZDANGER", "ZSAFE"]
    assert resume["customer_defined_accepting_additional"] == ["ZDANGER"]
    assert resume["by_os"] == {"ANYOS": 1, "UNIX": 2}


def test_resume_commandes_accepte_la_forme_deja_normalisee():
    resume = summarize_external_commands(
        [{"name": "X", "accepts_additional": True, "os": "UNIX"}])
    assert resume["accepting_additional"] == 1


# --------------------------------------------------------------------- #
# Couverture d'audit : la configuration CROISÉE avec le contenu
# --------------------------------------------------------------------- #
def test_arme_sans_filtre_et_silencieux_est_constate_pas_deduit():
    """Le verdict de la cible : le paramètre annonce une couverture, le
    contenu prouve qu'elle n'existe pas."""
    verdict = corroborate_audit_coverage(
        {"verdict": "armed_without_filter"}, 0, files_seen=0, window_days=365)
    assert verdict["verdict"] == "armed_without_filter_and_silent"
    assert verdict["consistent"] is True
    assert "CONSTATÉ" in verdict["note"]


def test_lecture_echouee_ne_vaut_jamais_zero():
    """Le faux positif que tout ce module existe pour empêcher : confondre
    « le journal est vide » et « je n'ai pas su le lire »."""
    verdict = corroborate_audit_coverage(
        {"verdict": "armed_without_filter"}, None, read_succeeded=False)
    assert verdict["verdict"] == "not_measured"
    assert verdict["entries"] is None
    assert verdict["consistent"] is None
    assert "pas un journal vide" in verdict["note"]


def test_lecture_reussie_a_zero_entree_reste_une_mesure():
    """La contre-épreuve du test précédent : zéro MESURÉ n'est pas
    `not_measured`."""
    verdict = corroborate_audit_coverage(
        {"verdict": "armed_without_filter"}, 0, read_succeeded=True)
    assert verdict["verdict"] == "armed_without_filter_and_silent"


def test_entrees_sans_filtre_signalent_une_incoherence():
    verdict = corroborate_audit_coverage(
        {"verdict": "armed_without_filter"}, 12)
    assert verdict["verdict"] == "entries_without_filter"
    assert verdict["consistent"] is False


def test_journal_filtrant_et_alimente_est_coherent():
    verdict = corroborate_audit_coverage({"verdict": "filtering"}, 40)
    assert verdict["verdict"] == "filtering_and_recording"
    assert verdict["consistent"] is True


def test_journal_filtrant_mais_vide_est_signale():
    verdict = corroborate_audit_coverage({"verdict": "filtering"}, 0)
    assert verdict["verdict"] == "filtering_but_silent"
    assert verdict["consistent"] is False


def test_journal_desarme():
    assert corroborate_audit_coverage(
        {"verdict": "disabled"}, 0)["verdict"] == "disabled_and_silent"
    assert corroborate_audit_coverage(
        {"verdict": "disabled"}, 3)["verdict"] == "entries_while_disabled"


def test_configuration_non_classee_ne_produit_pas_de_verdict():
    verdict = corroborate_audit_coverage({}, 0)
    assert verdict["verdict"] == "not_measured"


def test_tous_les_verdicts_sont_declares():
    """Le tuple exporté sert de contrat aux suites : il doit rester complet."""
    produits = {
        corroborate_audit_coverage({"verdict": v}, n)["verdict"]
        for v in ("disabled", "armed_without_filter", "filtering", "")
        for n in (0, 5)}
    produits.add(corroborate_audit_coverage({}, None,
                                            read_succeeded=False)["verdict"])
    assert produits <= set(AUDIT_COVERAGE_VERDICTS)
    assert set(AUDIT_COVERAGE_VERDICTS) == produits


# --------------------------------------------------------------------- #
# Relations de confiance
# --------------------------------------------------------------------- #
def test_surface_de_confiance_vide_est_un_resultat():
    """Un inventaire vide MESURÉ est un résultat ; un inventaire jamais lu
    est un angle mort. C'est la raison d'être de ce résumé."""
    resume = summarize_trust_surface([], [], [])
    assert resume["trusted_systems"] == 0
    assert resume["any_trust_configured"] is False


def test_surface_de_confiance_compte_les_trois_canaux():
    resume = summarize_trust_surface(
        [{"system": "PRD"}], [{"system": "QAS"}],
        [{"destination": "D1"}, {"destination": "D2"}])
    assert resume["trusted_ids"] == ["PRD"]
    assert resume["trusting_ids"] == ["QAS"]
    assert resume["callback_allowlist_entries"] == 2
    assert resume["callback_destinations"] == ["D1", "D2"]
    assert resume["any_trust_configured"] is True


def test_surface_de_confiance_accepte_les_noms_de_colonnes_bruts():
    resume = summarize_trust_surface(
        [{"RFCTRUSTSY": "PRD"}], [{"RFCSYSID": "QAS"}],
        [{"DESTINATION": "D1"}])
    assert resume["trusted_ids"] == ["PRD"]
    assert resume["trusting_ids"] == ["QAS"]


def test_surface_de_confiance_ignore_les_identifiants_vides():
    resume = summarize_trust_surface([{"system": ""}], [], [])
    assert resume["trusted_ids"] == []
    # Une ligne sans identifiant reste COMPTÉE : elle existe.
    assert resume["trusted_systems"] == 1
