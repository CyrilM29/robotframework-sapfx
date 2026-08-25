"""Choix de l'iframe d'application d'un launchpad, hors navigateur.

Relevé live le 2026-08-23 sur SAP Build Work Zone : l'iframe qui porte
l'application reçoit un identifiant GÉNÉRÉ par UI5 (`__container1` à une
exécution, `__container4` à la suivante, pour la même application sur la même
page). Aucun identifiant, aucune classe, aucun attribut de nommage ne survit
d'un run à l'autre. La désignation doit donc porter sur ce que la frame EST.
"""
from SapFioriLibrary._ui5_runtime import choose_app_frame


def _frame(src="https://app.example/index.html", width=1280, height=668):
    return {"src": src, "width": width, "height": height}


def test_l_application_est_la_plus_grande_frame_visible():
    frames = [_frame("https://tracker.example/px", 1, 1),
              _frame("https://app.example/index.html", 1280, 668)]
    assert choose_app_frame(frames) == 1


def test_l_ordre_du_document_ne_decide_pas():
    """L'application peut précéder les iframes techniques : c'est la surface
    qui tranche, pas la position."""
    frames = [_frame("https://app.example/index.html", 1280, 668),
              _frame("https://tracker.example/px", 1, 1)]
    assert choose_app_frame(frames) == 0


def test_une_iframe_sans_src_est_ignoree():
    """Une iframe déclarée mais sans document ne porte aucune application ;
    elle peut pourtant être grande, un conteneur préparé par le shell."""
    frames = [{"src": "", "width": 1280, "height": 668}]
    assert choose_app_frame(frames) is None


def test_les_iframes_minuscules_sont_ecartees():
    """Pixels de suivi et iframes de notification : présents, avec un src, et
    jamais l'application."""
    frames = [_frame("https://tracker.example/px", 1, 1),
              _frame("https://notif.example/n", 40, 40)]
    assert choose_app_frame(frames) is None


def test_aucune_iframe_donne_none():
    """Cas de l'accueil du launchpad : aucune application ouverte. Le keyword
    au-dessus doit alors dire CELA, et non « sélecteur introuvable »."""
    assert choose_app_frame([]) is None
    assert choose_app_frame(None) is None


def test_dimensions_illisibles_sans_exception():
    """Le DOM est interrogé à travers une frontière JS : une valeur inattendue
    ne doit pas faire échouer la détection, seulement écarter le candidat."""
    frames = [{"src": "https://a", "width": "large", "height": None},
              _frame("https://app.example/index.html", 800, 600)]
    assert choose_app_frame(frames) == 1


def test_la_plus_grande_gagne_entre_deux_applications():
    """Un shell peut porter deux applications ouvertes ; celle qui occupe la
    zone de contenu est la visible, donc la plus grande."""
    frames = [_frame("https://app1.example/i", 1280, 668),
              _frame("https://app2.example/i", 300, 200)]
    assert choose_app_frame(frames) == 0
