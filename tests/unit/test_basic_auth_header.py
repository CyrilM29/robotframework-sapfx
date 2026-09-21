"""L'en-tête d'authentification HTTP de base (2026-09-15).

Il existe parce qu'un formulaire de connexion n'est pas toujours atteignable :
le WebGUI d'un des systèmes du banc rend TOUS les champs du sien à 0x0 sans
parent de mise en page, en HTTP comme en HTTPS, et la même adresse répond
parfaitement à une authentification d'en-tête.
"""
from __future__ import annotations

import base64

import pytest

from sapfx_common.auth_flows import basic_auth_header


def _decode(entete: str) -> str:
    schema, valeur = entete.split(" ", 1)
    assert schema == "Basic"
    return base64.b64decode(valeur).decode("utf-8")


def test_l_entete_porte_le_couple_encode():
    assert _decode(basic_auth_header("DEVELOPER", "motdepasse")) \
        == "DEVELOPER:motdepasse"


def test_un_secret_rf_est_deballe_a_la_frontiere():
    """Un `Secret` RF 7.4 traverse ici et NULLE PART ailleurs : la couche
    Robot ne doit jamais manipuler la valeur claire.

    Le VRAI type de Robot, jamais une doublure : une doublure passerait le
    test en ne prouvant rien, puisque `reveal_secret` reconnaît le type par
    `isinstance` et qu'un faux `Secret` sortirait en `<secret>`, ce qu'une
    assertion sur la chaîne rendue n'aurait pas forcément vu."""
    from robot.api.types import Secret

    assert _decode(basic_auth_header("DEVELOPER", Secret("s3cr3t"))) \
        == "DEVELOPER:s3cr3t"


def test_l_encodage_est_utf8_quel_que_soit_le_contenu():
    # L'encodage historique des navigateurs essaie latin-1 d'abord, si bien
    # que le même mot de passe part encodé de deux façons selon qu'il tient
    # ou non dans latin-1 : l'échec dépend alors du CONTENU du secret, ce qui
    # est le pire endroit où mettre une variabilité.
    for mot in ("ascii", "mot·de·passé", "пароль", "密码"):
        assert _decode(basic_auth_header("u", mot)) == "u:%s" % mot
    # Un caractère représentable en latin-1 doit sortir en UTF-8 comme les
    # autres : c'est cette coïncidence-là qui masquait le choix.
    assert base64.b64decode(
        basic_auth_header("u", "é").split(" ", 1)[1]) == "u:é".encode("utf-8")


def test_un_deux_points_dans_l_identifiant_est_REFUSE():
    # La RFC ne permet pas de le représenter : tronquer en silence enverrait
    # chercher un problème de droits qui n'existe pas.
    with pytest.raises(ValueError, match="ne peut pas contenir"):
        basic_auth_header("DOMAINE:USER", "x")


def test_un_mot_de_passe_absent_reste_un_couple_valide():
    # Un mot de passe vide est un cas limite RÉEL (l'utilisateur mock de
    # cap-sflight en a un), pas une erreur d'appel.
    assert _decode(basic_auth_header("alice", "")) == "alice:"
    assert _decode(basic_auth_header("alice", None)) == "alice:"
