"""Tests hors SAP des keywords de **sécurité du transport** du canal API
(`Get Api Cookie Security`, `Get Api Security Headers`,
`Confront Security Control`). Convention #5.

Ce fichier existe à cause d'une réserve de la revue indépendante, et elle
était imparable : la campagne conclut « aucun cookie ne porte HttpOnly », et
un lecteur INCAPABLE de voir le drapeau produirait exactement cette
conclusion. Un résultat négatif obtenu par un instrument dont on n'a jamais
vérifié qu'il sait dire « oui » n'est pas une mesure.

Le chemin éprouvé ici est donc celui que la campagne EMPRUNTE : le keyword lit
un vrai bocal à cookies, pas des en-têtes bruts. Les tests de
`sapfx_common.http_security` couvrent le parseur d'en-têtes, que le mixin
n'appelle jamais sur ce chemin.
"""
from http.cookiejar import Cookie, CookieJar

import pytest

from SapApiLibrary import SapApiLibrary


def _cookie(name: str, httponly: bool = False, secure: bool = False,
            attr_case: str = "HttpOnly") -> Cookie:
    """Un cookie tel que `http.cookiejar` le construit à partir d'un en-tête.

    Le drapeau HttpOnly n'a PAS d'accesseur dédié : il atterrit dans les
    attributs non standard, et c'est par là qu'il faut le lire.
    """
    rest = {attr_case: None} if httponly else {}
    return Cookie(
        version=0, name=name, value="valeur-secrete", port=None,
        port_specified=False, domain="localhost", domain_specified=False,
        domain_initial_dot=False, path="/", path_specified=True,
        secure=secure, expires=None, discard=True, comment=None,
        comment_url=None, rest=rest, rfc2109=False)


def _lib(cookies, base_url="http://localhost:50100", headers=None):
    """Une `SapApiLibrary` dont la session API est doublée sur l'INSTANCE."""
    lib = SapApiLibrary()
    jar = CookieJar()
    for c in cookies:
        jar.set_cookie(c)

    class _Session:
        def __init__(self):
            self.cookies = jar
            self.base_url = base_url

    lib.appels = []
    lib._session = lambda alias="default": _Session()

    def _request(alias, method, path, query, **kw):
        lib.appels.append({"method": method, "path": path})
        return 200, dict(headers or {}), b""

    lib._request = _request
    return lib


# --------------------------------------------------------------------- #
# LE test que la revue réclamait : l'instrument sait-il dire « oui » ?
# --------------------------------------------------------------------- #
def test_le_lecteur_voit_un_cookie_reellement_protege():
    """Contre-épreuve POSITIVE. Sans elle, la conclusion « aucun cookie n'est
    protégé » serait indiscernable de « le lecteur ne sait pas voir le
    drapeau », et un lecteur cassé donnerait le résultat publié."""
    lib = _lib([_cookie("PROTEGE", httponly=True)])
    resume = lib.get_api_cookie_security()
    assert resume["without_httponly"] == []
    assert resume["all_protected"] is True


def test_le_lecteur_voit_un_cookie_non_protege():
    """Contre-épreuve NÉGATIVE, le cas mesuré sur la cible."""
    lib = _lib([_cookie("NU")])
    resume = lib.get_api_cookie_security()
    assert resume["without_httponly"] == ["NU"]
    assert resume["all_protected"] is False


def test_le_lecteur_distingue_les_deux_dans_le_meme_relevé():
    """La preuve la plus forte : le même appel sépare les deux, donc il
    MESURE au lieu de rendre une constante."""
    lib = _lib([_cookie("PROTEGE", httponly=True), _cookie("NU")])
    resume = lib.get_api_cookie_security()
    assert resume["without_httponly"] == ["NU"]
    assert resume["total"] == 2


@pytest.mark.parametrize("casse", ["HttpOnly", "httponly", "HTTPOnly",
                                   "httpOnly", "HTTPONLY"])
def test_le_drapeau_est_vu_quelle_que_soit_sa_casse(casse):
    """Un en-tête HTTP est insensible à la casse, et `http.cookiejar` range
    l'attribut TEL QU'IL EST ÉCRIT. Deviner deux orthographes laissait passer
    les autres, et chacune produisait un faux « non protégé »."""
    lib = _lib([_cookie("C", httponly=True, attr_case=casse)])
    assert lib.get_api_cookie_security()["without_httponly"] == []


def test_le_drapeau_secure_est_lu():
    lib = _lib([_cookie("S", secure=True), _cookie("N")])
    resume = lib.get_api_cookie_security()
    assert resume["without_secure"] == ["N"]


def test_le_canal_https_est_rapporte():
    lib = _lib([_cookie("C")], base_url="https://localhost:50101")
    assert lib.get_api_cookie_security()["over_https"] is True


def test_aucune_valeur_de_cookie_ne_sort():
    """Un identifiant de session recopié dans un artefact committé serait un
    secret exposé."""
    resume = _lib([_cookie("SID", httponly=True)]).get_api_cookie_security()
    assert "valeur-secrete" not in repr(resume)


def test_la_sonde_declenche_bien_un_appel():
    """Sans appel préalable, une session fraîche n'a aucun cookie à observer
    et le résumé vide se lirait comme « aucun cookie non protégé »."""
    lib = _lib([_cookie("C")])
    lib.get_api_cookie_security(probe_path="/sonde")
    assert lib.appels == [{"method": "GET", "path": "/sonde"}]


def test_sans_sonde_aucun_appel_n_est_emis():
    lib = _lib([_cookie("C")])
    lib.get_api_cookie_security()
    assert lib.appels == []


def test_un_releve_sans_cookie_n_est_pas_une_conformite():
    resume = _lib([]).get_api_cookie_security()
    assert resume["total"] == 0 and resume["all_protected"] is False


# --------------------------------------------------------------------- #
# En-têtes et confrontation
# --------------------------------------------------------------------- #
def test_les_en_tetes_de_securite_sont_lus_sur_la_reponse():
    lib = _lib([], headers={"Strict-Transport-Security": "max-age=31536000"})
    verdict = lib.get_api_security_headers("/chemin")
    assert "strict-transport-security" in verdict["present"]
    assert lib.appels == [{"method": "GET", "path": "/chemin"}]


def test_une_cible_sans_en_tete_de_securite_les_declare_tous_absents():
    lib = _lib([], headers={"content-type": "application/json"})
    verdict = lib.get_api_security_headers("/chemin")
    assert verdict["present"] == [] and verdict["count_present"] == 0


def test_la_confrontation_accepte_les_formes_de_robot():
    """Via la frontière Robot, un booléen arrive volontiers en chaîne."""
    lib = _lib([])
    assert lib.confront_security_control("x", "3", "False")["verdict"] == \
        "declared_without_effect"
    assert lib.confront_security_control("x", "3", "True")["verdict"] == \
        "confirmed"
    assert lib.confront_security_control("x", "3", "")["verdict"] == \
        "undetermined"
