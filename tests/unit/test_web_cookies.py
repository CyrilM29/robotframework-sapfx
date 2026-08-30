"""Tests de la logique pure de résumé de cookies (`sapfx_common.web_cookies`).

La leçon encodée (live 2026-08-26, campagne Work Zone) : la bibliothèque
Browser rend un cookie de SESSION avec une date de 1969 (epoch moins un), et
le prédicat qui a un sens est « expiration FUTURE », jamais « expiration
renseignée ». Sans lui, six cookies de session passaient pour permanents et
le test de perte de session était vert à l'envers.
"""
import datetime

from sapfx_common.web_cookies import expires_in_future, summarize_cookies

_NOW = 1_000_000_000.0


class TestPredicat:
    def test_la_sentinelle_1969_est_fausse(self):
        epoch_moins_un = datetime.datetime(1969, 12, 31, 23, 59, 59)
        assert expires_in_future(epoch_moins_un, _NOW) is False

    def test_une_date_future_est_vraie(self):
        assert expires_in_future(datetime.datetime(2999, 1, 1), _NOW) is True

    def test_une_chaine_n_est_jamais_comparee(self):
        assert expires_in_future("2999-01-01", _NOW) is False

    def test_absence_et_zero(self):
        assert expires_in_future(None, _NOW) is False
        assert expires_in_future(0, _NOW) is False

    def test_un_epoch_numerique_est_compare(self):
        assert expires_in_future(_NOW + 60, _NOW) is True
        assert expires_in_future(_NOW - 60, _NOW) is False


class TestResume:
    def test_trie_par_domaine_puis_nom_et_ne_porte_aucune_valeur(self):
        cookies = [
            {"name": "b", "domain": "z.example", "value": "SECRET-1"},
            {"name": "a", "domain": "a.example", "value": "SECRET-2",
             "expires": datetime.datetime(2999, 1, 1)},
        ]
        resume = summarize_cookies(cookies, _NOW)
        assert [c["name"] for c in resume] == ["a", "b"]
        assert resume[0]["future_expiration"] is True
        assert resume[1]["future_expiration"] is False
        assert "SECRET" not in str(resume)

    def test_entree_vide_et_champs_absents(self):
        assert summarize_cookies(None, _NOW) == []
        resume = summarize_cookies([{}], _NOW)
        assert resume == [{"name": "", "domain": "",
                           "future_expiration": False}]
