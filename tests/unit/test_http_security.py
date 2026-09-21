"""Tests hors SAP de `sapfx_common.http_security` (convention #5).

Le sujet : ce que la réponse HTTP révèle de la posture, et surtout la
confrontation entre ce qu'un paramètre DÉCLARE et ce que le fil MONTRE.
Mesures du 2026-09-14 sur ABAP Platform 2023.
"""
import pytest

from sapfx_common.http_security import (
    SECURITY_HEADERS,
    assess_security_headers,
    confront_declared_and_observed,
    parse_set_cookie,
    summarize_cookie_security,
)


# --------------------------------------------------------------------- #
# Décomposition d'un cookie
# --------------------------------------------------------------------- #
def test_les_drapeaux_sont_reconnus_quelle_que_soit_la_casse():
    fiche = parse_set_cookie("SID=abc; Path=/; HttpOnly; Secure; SameSite=Lax")
    assert fiche["name"] == "SID"
    assert fiche["httponly"] is True and fiche["secure"] is True
    assert fiche["samesite"] == "lax" and fiche["path"] == "/"


def test_la_valeur_du_cookie_n_est_jamais_rendue():
    """Un identifiant de session recopié dans un artefact committé serait un
    secret exposé."""
    fiche = parse_set_cookie("SAP_SESSIONID_A4H_001=O3yZ4-secret; path=/")
    assert "value" not in fiche
    assert "secret" not in repr(fiche)


def test_un_cookie_sans_drapeau_est_rendu_sans_drapeau():
    fiche = parse_set_cookie("sap-usercontext=sap-client=001; path=/")
    assert fiche["httponly"] is False and fiche["secure"] is False
    assert fiche["samesite"] is None


def test_une_fiche_deja_decomposee_est_acceptee():
    """Un appelant qui tient un bocal à cookies n'a pas à reconstruire un
    en-tête artificiel pour le faire re-parser."""
    fiche = parse_set_cookie({"name": "SID", "httponly": True, "secure": False})
    assert fiche["name"] == "SID" and fiche["httponly"] is True


def test_un_en_tete_vide_ou_sans_nom_est_refuse():
    with pytest.raises(ValueError):
        parse_set_cookie("")
    with pytest.raises(ValueError):
        parse_set_cookie("=valeur; path=/")
    with pytest.raises(ValueError, match="nom"):
        parse_set_cookie({"httponly": True})


# --------------------------------------------------------------------- #
# Le résumé, et le cas mesuré
# --------------------------------------------------------------------- #
def test_le_cas_mesure_aucun_cookie_protege():
    """Les trois cookies de la cible, ticket d'authentification compris."""
    resume = summarize_cookie_security([
        "sap-usercontext=sap-client=001; path=/",
        "MYSAPSSO2=AjQx; path=/",
        "SAP_SESSIONID_A4H_001=O3yZ; path=/"])
    assert resume["total"] == 3
    assert resume["without_httponly"] == ["MYSAPSSO2", "SAP_SESSIONID_A4H_001",
                                          "sap-usercontext"]
    assert resume["all_protected"] is False


def test_un_relevé_vide_n_est_pas_une_conformite():
    """`all_protected` est faux sur zéro cookie : sans cette garde, une
    session qui n'a rien observé passerait pour protégée."""
    resume = summarize_cookie_security([])
    assert resume["total"] == 0 and resume["all_protected"] is False


def test_tous_proteges_quand_ils_le_sont():
    resume = summarize_cookie_security(["A=1; HttpOnly", "B=2; HttpOnly"])
    assert resume["all_protected"] is True and resume["without_httponly"] == []


def test_le_resume_rapporte_le_canal_sans_le_juger():
    """Exiger Secure d'un banc servi en clair rendrait une suite rouge à vie :
    le fait est rapporté, la décision reste à l'appelant."""
    resume = summarize_cookie_security(["A=1"], over_https=False)
    assert resume["over_https"] is False
    assert resume["without_secure"] == ["A"]


# --------------------------------------------------------------------- #
# En-têtes de sécurité
# --------------------------------------------------------------------- #
def test_les_en_tetes_sont_compares_sans_tenir_compte_de_la_casse():
    """Les en-têtes HTTP sont insensibles à la casse : une lecture sensible
    déclarerait absent un en-tête présent."""
    verdict = assess_security_headers({"Strict-Transport-Security": "max-age=1"})
    assert "strict-transport-security" in verdict["present"]
    assert verdict["count_present"] == 1


def test_une_cible_sans_aucun_en_tete_de_securite():
    """Le cas mesuré : aucun des cinq n'est posé."""
    verdict = assess_security_headers({"content-type": "application/json"})
    assert verdict["present"] == []
    assert sorted(verdict["missing"]) == sorted(SECURITY_HEADERS)


# --------------------------------------------------------------------- #
# La confrontation, coeur de la campagne multi-canal
# --------------------------------------------------------------------- #
def test_declare_sans_effet_est_le_faux_positif_de_conformite():
    """Le cas mesuré : le paramètre vaut 3 et aucun cookie ne porte le
    drapeau. Un audit qui s'arrête à la valeur conclut à une protection qui
    n'existe pas."""
    verdict = confront_declared_and_observed(
        "cookies.httponly", declared="3", observed=False)
    assert verdict["verdict"] == "declared_without_effect"
    assert "curseur" in verdict["note"]


def test_effet_observe_confirme_la_declaration():
    verdict = confront_declared_and_observed("x", declared="3", observed=True)
    assert verdict["verdict"] == "confirmed"


def test_effet_sans_declaration_est_signale():
    verdict = confront_declared_and_observed("x", declared="0", observed=True,
                                             expectation=False)
    assert verdict["verdict"] == "effect_without_declaration"


def test_observation_absente_ne_vaut_jamais_conformite():
    verdict = confront_declared_and_observed("x", declared="3", observed=None)
    assert verdict["verdict"] == "undetermined"
    assert "jamais une conformité" in verdict["note"]


def test_la_valeur_declaree_n_est_pas_interpretee_comme_un_niveau():
    """Lire une échelle numérique comme un curseur de durcissement est
    l'erreur que l'observation a démentie : le verdict ne dépend QUE de
    l'effet, jamais de la valeur."""
    for valeur in ("0", "1", "3", "OFF", ""):
        verdict = confront_declared_and_observed("x", valeur, observed=False)
        assert verdict["verdict"] == "declared_without_effect", valeur


def test_un_controle_sans_nom_est_refuse():
    with pytest.raises(ValueError, match="nom"):
        confront_declared_and_observed("", "3", True)
