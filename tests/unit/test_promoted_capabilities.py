"""Tests hors SAP des capacités promues de la couche Robot (convention #12).

Second lot de la passe du 2026-08-29, celui que le garde des conventions ne
pouvait PAS détecter : il ne voit que le motif JS/``__import__``, jamais une
capacité écrite en Robot pur. Sont couverts ici : les deux primitives d'écran
SE16 (le réglage d'affichage ALV et le comptage « Number of Entries »), le
prédicat de présence d'un secret, le chemin d'entité draft OData v4, et la
classification structurelle d'une réponse HTTP.
"""
import pytest

from sapfx_common.gateway_status import (ROUTER_ERROR_HEADER,
                                         classify_http_response,
                                         looks_like_json)
from sapfx_common.secrets import secret_is_provided


class FakeSecret:
    """Doublure du type ``Secret`` de RF 7.4 : sa valeur ne se MESURE pas."""

    def __init__(self, value):
        self.value = value

    def __len__(self):
        raise TypeError("Could not get length of '<secret>'")

    def __bool__(self):
        raise TypeError("Could not evaluate '<secret>' as a boolean")


class TestSecretIsProvided:
    """Le prédicat des gardes de préflight des quatre canaux : il doit
    répondre SANS jamais lire ni mesurer la valeur."""

    def test_un_secret_est_fourni_sans_etre_mesure(self):
        # Le contrat tient précisément parce que la doublure EXPLOSE si on
        # tente `len()` ou `bool()` dessus, comme le vrai type Secret.
        assert secret_is_provided(FakeSecret("motdepasse")) is True

    def test_la_chaine_vide_du_defaut_n_est_pas_fournie(self):
        assert secret_is_provided("") is False
        assert secret_is_provided(None) is False

    def test_une_valeur_publique_non_vide_est_fournie(self):
        assert secret_is_provided("DEVELOPER") is True

    def test_une_garde_naive_aurait_echoue_sur_le_secret(self):
        """Contre-épreuve : c'est bien le piège que le prédicat contourne."""
        with pytest.raises(TypeError, match="Could not get length"):
            len(FakeSecret("x"))


class TestClassifyHttpResponse:
    """Les familles de reconnaissance : trois 404 distincts sous un même
    statut, et un 200 qui n'est pas une donnée."""

    def test_les_trois_familles_de_404(self):
        assert classify_http_response(
            404, {ROUTER_ERROR_HEADER: "unknown route"}, "") == "unknown_route"
        # casse indifférente : l'en-tête arrive tel que le serveur l'écrit
        assert classify_http_response(
            404, {"X-Cf-RouterError": "x"}, "") == "unknown_route"
        assert classify_http_response(
            404, {"content-type": "text/html"}, "Cannot GET /x") == "missing_route"

    def test_un_2xx_html_n_est_pas_une_donnee(self):
        """Le « vert et faux » des cibles derrière un fournisseur d'identité :
        toute route déclarée répond 200 avec la page de connexion."""
        assert classify_http_response(
            200, {}, "<!DOCTYPE html><html>") == "login_page"
        assert classify_http_response(200, {}, '{"d":[]}') == "data"

    def test_un_4xx_json_est_un_dialogue(self):
        assert classify_http_response(400, {}, '{"errors":[]}') == "dialog"
        # sans corps JSON, un 4xx quelconque reste « autre »
        assert classify_http_response(418, {}, "teapot") == "other"

    def test_refus_d_autorisation_et_injoignable(self):
        assert classify_http_response(403, {}, "") == "forbidden"
        assert classify_http_response(None, {}, "") == "unreachable"

    def test_headers_absents_ou_en_liste(self):
        assert classify_http_response(404, None, "") == "missing_route"
        assert classify_http_response(
            404, [ROUTER_ERROR_HEADER], "") == "unknown_route"

    def test_looks_like_json_regarde_le_debut_du_document(self):
        assert looks_like_json('  {"a": 1}') is True
        assert looks_like_json("[1, 2]") is True
        # un texte qui CITE une accolade plus loin n'est pas du JSON
        assert looks_like_json("erreur : {voir plus haut}") is False
        assert looks_like_json("") is False


class TestBuildDraftEntityPath:
    """La clé COMPOSITE d'un service draft-enabled : savoir de protocole."""

    def _lib(self):
        from SapApiLibrary.SapApiLibrary import SapApiLibrary
        return SapApiLibrary()

    def test_chemin_compose_avec_l_etat_d_activite(self):
        path = self._lib().build_draft_entity_path(
            "/processor/Travel", "TravelUUID", "abc-123")
        assert path == "/processor/Travel(TravelUUID=abc-123,IsActiveEntity=false)"

    def test_variante_active(self):
        path = self._lib().build_draft_entity_path(
            "/processor/Travel", "TravelUUID", "abc", active="true")
        assert path.endswith("IsActiveEntity=true)")

    def test_slash_final_et_espaces_normalises(self):
        path = self._lib().build_draft_entity_path(
            "/processor/Travel/", " TravelUUID ", " abc ")
        assert path == "/processor/Travel(TravelUUID=abc,IsActiveEntity=false)"

    @pytest.mark.parametrize("entity_set, key_field", [
        ("", "TravelUUID"), ("/processor/Travel", "   ")])
    def test_arguments_vides_refuses(self, entity_set, key_field):
        with pytest.raises(ValueError, match="Build Draft Entity Path"):
            self._lib().build_draft_entity_path(entity_set, key_field, "x")
