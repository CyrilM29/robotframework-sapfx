"""Tests hors SAP des keywords de **posture de sécurité** du canal RFC
(`Read Profile Parameters`, `Profile Parameters Should Be Defined`,
`Read Standard Users Status`, `Build`/`Write`/`Read Security Posture`,
`Security Posture Should Not Have Drifted`). Convention #5.

Aucun `pyrfc`, aucun serveur : le canal est DOUBLÉ sur l'instance, et la
première chose que ce fichier prouve est que la doublure est bien celle qui
répond. Le piège est connu du dépôt : une doublure posée dans le mauvais
espace de noms laisse passer le vrai appel et le test devient vert sans rien
éprouver. Ici la contre-épreuve est directe, une bibliothèque NON doublée
échoue en réclamant `Open Rfc Connection`.

Les fichiers ne sortent jamais de ``tmp_path``.
"""
import pytest

from SapApiLibrary import SapApiLibrary
from SapApiLibrary._rfc_security import STANDARD_USERS
from sapfx_common import rfc_tables, security_baseline

#: Un profil de réponses ``{nom: (RC, valeur)}``. Un nom absent de la carte
#: reçoit la réponse RÉELLE du système pour un paramètre sans valeur
#: effective : ``RC = 4`` et une chaîne VIDE.
_PROFIL = {
    "login/min_password_lng": (0, "8"),
    "login/fails_to_user_lock": (0, "5"),
    "gw/reg_no_conn_info": (0, "255"),
}

_CONTROLES = [
    {"key": "longueur_mot_de_passe", "parameter": "login/min_password_lng",
     "comparison": "at_least", "expected": "8", "severity": "high"},
    {"key": "verrouillage", "parameter": "login/fails_to_user_lock",
     "comparison": "at_most", "expected": "5", "severity": "medium"},
    {"key": "journal_passerelle", "parameter": "gw/faute_de_frappe",
     "comparison": "enabled", "expected": "1", "severity": "high"},
]


def _lib(parametres=None, lignes=None):
    """Une `SapApiLibrary` dont le canal RFC est doublé sur l'INSTANCE :
    ``call_rfc`` sert des codes de retour par paramètre, ``read_rfc_table``
    des lignes par table, et les deux ENREGISTRENT leurs appels (une doublure
    doit être prouvée appelée, sinon le test n'éprouve rien)."""
    lib = SapApiLibrary()
    lib.appels = []
    lib.lectures = []

    def call_rfc(function_name, alias="default", **params):
        lib.appels.append({"function": function_name, "alias": alias,
                           "params": dict(params)})
        code, valeur = (parametres or {}).get(
            params.get("PARAMETER_NAME"), (4, ""))
        return {"RC": code, "PARAMETER_VALUE": valeur}

    def read_rfc_table(table, fields, alias="default", options=None,
                       rowcount=0, delimiter="|"):
        lib.lectures.append({"table": table, "fields": list(fields),
                             "alias": alias, "options": options})
        return [dict(row) for row in (lignes or {}).get(table, [])]

    lib.call_rfc = call_rfc
    lib.read_rfc_table = read_rfc_table
    return lib


def _lib_canal_reel():
    """Une bibliothèque dont SEUL ``call_rfc`` est doublé : `Read Rfc Table`
    reste le vrai, donc la clause OPTIONS passe par le garde ABAP des 72
    caractères avant tout appel réseau."""
    lib = SapApiLibrary()
    lib.params = []

    def call_rfc(function_name, alias="default", **params):
        lib.params.append(dict(params))
        return {"DATA": [], "FIELDS": []}

    lib.call_rfc = call_rfc
    return lib


def _fiches(profil):
    """Des fiches de mesure depuis un profil ``{nom: (RC, valeur)}``."""
    return [security_baseline.classify_parameter(nom, code, valeur)
            for nom, (code, valeur) in profil.items()]


def _compter_les_ecritures(lib):
    """Espionne `Write Security Posture` sur l'instance et rend la liste des
    chemins écrits. « Ne réécrit pas » ne se prouve pas sur le contenu du
    fichier, qui serait identique dans les deux cas."""
    ecritures = []
    ecriture_reelle = lib.write_security_posture

    def espion(path, artifact):
        ecritures.append(str(path))
        return ecriture_reelle(path, artifact)

    lib.write_security_posture = espion
    return ecritures


# --- la doublure est-elle bien celle qui répond ------------------------------

def test_sans_doublure_le_keyword_atteint_le_vrai_canal():
    # La contre-épreuve de la doublure elle-même : si l'espace de noms était
    # mauvais, les tests suivants passeraient par ce chemin sans le dire.
    with pytest.raises(RuntimeError, match="Open Rfc Connection"):
        SapApiLibrary().read_profile_parameters("login/min_password_lng")


def test_la_doublure_repond_et_l_appel_est_celui_du_module_standard():
    lib = _lib(_PROFIL)
    fiches = lib.read_profile_parameters("login/min_password_lng",
                                         alias="audit")
    assert fiches == [{"name": "login/min_password_lng", "status": "defined",
                       "value": "8"}]
    assert lib.appels == [{"function": "TH_GET_PARAMETER", "alias": "audit",
                           "params": {
                               "PARAMETER_NAME": "login/min_password_lng"}}]


# --- read_profile_parameters -------------------------------------------------

@pytest.mark.parametrize("demande", [
    ["login/min_password_lng", "login/fails_to_user_lock"],
    "login/min_password_lng,login/fails_to_user_lock",
    "['login/min_password_lng', 'login/fails_to_user_lock']",
])
def test_les_trois_formes_d_argument_donnent_le_meme_lot(demande):
    # Via `execute_step` (rf-mcp), TOUT argument arrive en chaîne.
    fiches = _lib(_PROFIL).read_profile_parameters(demande)
    assert [f["name"] for f in fiches] == ["login/min_password_lng",
                                           "login/fails_to_user_lock"]
    assert [f["value"] for f in fiches] == ["8", "5"]


def test_l_ordre_demande_est_preserve_pas_l_ordre_alphabetique():
    # Les comparaisons de deux relevés en dépendent.
    lib = _lib(_PROFIL)
    ordre = ["login/min_password_lng", "gw/reg_no_conn_info",
             "login/fails_to_user_lock"]
    assert [f["name"] for f in lib.read_profile_parameters(ordre)] == ordre
    assert [a["params"]["PARAMETER_NAME"] for a in lib.appels] == ordre


def test_la_casse_des_noms_n_est_jamais_normalisee():
    """``TH_GET_PARAMETER`` est sensible à la CASSE, et le dépôt porte deux
    normaliseurs voisins : celui qui préserve la casse
    (``robot_args.as_name_list``, celui du keyword) et celui qui CAPITALISE
    pour le dictionnaire ABAP (``rfc_tables.as_field_list``). Les intervertir
    ferait remonter tout le lot sans valeur effective, avec un code de retour
    parfaitement plausible et aucune erreur. Le nom reçu par le canal doit
    donc être identique octet pour octet à celui demandé."""
    lib = _lib({"login/min_password_lng": (0, "8"),
                "Login/Min_Password_Lng": (0, "PIEGE")})
    demande = ["login/min_password_lng", "Login/Min_Password_Lng",
               "GW/reg_no_conn_info"]
    fiches = lib.read_profile_parameters(demande)
    assert [a["params"]["PARAMETER_NAME"] for a in lib.appels] == demande
    assert [f["name"] for f in fiches] == demande
    # et la casse fait bien une différence de mesure sur ce canal
    assert fiches[0]["value"] == "8" and fiches[1]["value"] == "PIEGE"
    assert fiches[2]["status"] == "unknown"


@pytest.mark.parametrize("vide", [None, [], "", "   ", ",,", "[]"])
def test_un_lot_vide_est_refuse_en_le_disant(vide):
    lib = _lib(_PROFIL)
    with pytest.raises(ValueError, match="aucun paramètre demandé"):
        lib.read_profile_parameters(vide)
    assert lib.appels == []


def test_un_parametre_sans_valeur_effective_remonte_unknown_et_pas_une_chaine_vide():
    # Le piège central côté keyword : le module rend RC=4 et une chaîne VIDE,
    # que rien ne distingue d'un paramètre à zéro.
    lib = _lib(_PROFIL)
    fiches = lib.read_profile_parameters(
        "login/min_password_lng,login/faute_de_frappe")
    assert fiches[0] == {"name": "login/min_password_lng",
                         "status": "defined", "value": "8"}
    assert fiches[1] == {"name": "login/faute_de_frappe",
                         "status": "unknown", "value": None}


# --- profile_parameters_should_be_defined ------------------------------------

def test_la_garde_passe_quand_tout_est_mesure_et_rend_les_fiches():
    fiches = _lib(_PROFIL).profile_parameters_should_be_defined(list(_PROFIL))
    assert [f["status"] for f in fiches] == ["defined"] * 3


def test_la_garde_echoue_en_nommant_les_parametres_restes_sans_valeur():
    lib = _lib({"login/min_password_lng": (0, "8")})
    with pytest.raises(AssertionError) as erreur:
        lib.profile_parameters_should_be_defined(
            "login/min_password_lng,login/absent_ici,gw/faute")
    message = str(erreur.value)
    assert "2 paramètre(s)" in message
    assert "login/absent_ici" in message and "gw/faute" in message
    # le paramètre correctement mesuré ne figure pas dans l'échec
    assert "login/min_password_lng" not in message


# --- read_standard_users_status ----------------------------------------------

def test_les_comptes_standards_sont_lus_dans_l_ordre_et_le_verrou_decode():
    lib = _lib(lignes={"USR02": [
        {"BNAME": "DDIC", "UFLAG": "0", "CLASS": "SUPER", "USTYP": "A",
         "TRDAT": "20260101"},
        {"BNAME": "SAP*", "UFLAG": "96", "CLASS": "SUPER", "USTYP": "A",
         "TRDAT": "20260828"},
    ]})
    fiches = lib.read_standard_users_status(users="SAP*,DDIC", client="001")
    assert [f["user"] for f in fiches] == ["SAP*", "DDIC"]
    assert fiches[0]["uflag"] == 96 and fiches[0]["locked"] is True
    assert fiches[0]["reasons"] == ["locked_by_admin",
                                    "locked_by_failed_logons"]
    assert fiches[0]["user_group"] == "SUPER" and fiches[0]["user_type"] == "A"
    assert fiches[0]["last_logon"] == "20260828"
    assert fiches[1]["locked"] is False and fiches[1]["reasons"] == []
    assert {f["client"] for f in fiches} == {"001"}


def test_la_lecture_est_projetee_et_filtree_sur_les_comptes_demandes():
    lib = _lib(lignes={"USR02": []})
    lib.read_standard_users_status(users=["SAP*", "DDIC"], alias="audit")
    lecture = lib.lectures[0]
    assert lecture["table"] == "USR02" and lecture["alias"] == "audit"
    assert lecture["fields"] == ["BNAME", "UFLAG", "CLASS", "USTYP", "TRDAT"]
    assert lecture["options"] == ["BNAME IN ('SAP*','DDIC')"]


def test_un_compte_absent_est_rendu_present_faux_jamais_omis():
    # « Le compte n'existe pas ici » est une réponse ; l'omettre ferait
    # disparaître le contrôle du rapport, et `locked` reste None parce
    # qu'absent n'est pas « déverrouillé ».
    lib = _lib(lignes={"USR02": [{"BNAME": "DDIC", "UFLAG": "64"}]})
    fiches = lib.read_standard_users_status(users=["SAPCPIC", "DDIC"])
    assert [f["user"] for f in fiches] == ["SAPCPIC", "DDIC"]
    assert fiches[0] == {"user": "SAPCPIC", "present": False, "uflag": None,
                         "locked": None, "reasons": [], "user_type": None,
                         "user_group": None, "last_logon": None,
                         "client": None}
    assert fiches[1]["present"] is True and fiches[1]["locked"] is True


def test_la_clause_de_la_liste_par_defaut_tient_dans_la_limite_abap():
    """``RFC_READ_TABLE`` refuse une clause ``OPTIONS`` de plus de 72
    caractères, et la liste par défaut en produit une de 69 : trois caractères
    de marge. Ajouter un compte au barème casserait la lecture AVANT tout
    appel réseau, sur une erreur qui parle de découper en clauses ``AND``,
    ce que l'appelant du keyword ne peut pas faire. Ce garde est le seul
    endroit qui le dira."""
    lib = _lib_canal_reel()
    lib.read_standard_users_status()
    params = lib.params[0]
    assert params["QUERY_TABLE"] == "USR02"
    clauses = [o["TEXT"] for o in params["OPTIONS"]]
    assert clauses[0].startswith("BNAME IN (")
    # Chaque ligne d'OPTIONS reste sous la limite ABAP, y compris quand la
    # liste demandée déborde : c'est le keyword qui compose la clause, donc
    # l'appelant ne pourrait pas la découper lui-même.
    assert all(len(c) <= rfc_tables.OPTIONS_LINE_LIMIT for c in clauses)


def test_la_liste_par_defaut_est_celle_des_comptes_livres_par_sap():
    lib = _lib(lignes={"USR02": []})
    fiches = lib.read_standard_users_status()
    assert [f["user"] for f in fiches] == list(STANDARD_USERS)
    assert all(f["present"] is False for f in fiches)
    clauses = lib.lectures[0]["options"]
    assert any("'EARLYWATCH'" in c for c in clauses)


def test_une_liste_de_comptes_trop_longue_est_decoupee_et_jamais_refusee():
    # Le défaut que ce test ferme : la liste par défaut occupe 69 des 72
    # caractères permis, donc un SEUL compte de plus faisait échouer le
    # keyword sur une clause que l'appelant n'a jamais écrite, alors que
    # l'argument est documenté comme surchargeable.
    lib = _lib(lignes={"USR02": []})
    lib.read_standard_users_status(
        users=list(STANDARD_USERS) + ["SAPJSF", "SAPSYS", "TMSADM_BIS"])
    clauses = lib.lectures[0]["options"]
    assert len(clauses) > 1
    assert all(len(c) <= rfc_tables.OPTIONS_LINE_LIMIT for c in clauses)
    assert clauses[0].startswith("BNAME IN (")
    assert all(c.startswith("OR BNAME IN (") for c in clauses[1:])
    assert any("'SAPJSF'" in c for c in clauses)


# --- build / write / read security posture ------------------------------------

def test_la_posture_assemble_identite_mesures_verdicts_et_resume():
    lib = _lib(_PROFIL)
    mesures = lib.read_profile_parameters(list(_PROFIL))
    artefact = lib.build_security_posture({"release": "758", "kernel": "793"},
                                          mesures, _CONTROLES)
    assert artefact["identity"] == {"kernel": "793", "release": "758"}
    assert artefact["summary"] == {
        "total": 3, "compliant": 2, "deviation": 0, "not_measurable": 1,
        "deviations_by_severity": {}, "deviating_keys": [],
        "not_measurable_keys": ["journal_passerelle"]}
    assert [r["name"] for r in artefact["readings"]] == sorted(_PROFIL)
    assert len(artefact["hash"]) == 64
    assert artefact["generated_at"].endswith("+00:00")


def test_le_hash_de_la_posture_ne_bouge_pas_avec_l_horodatage():
    lib = _lib(_PROFIL)
    artefact = lib.build_security_posture(
        {"release": "758"}, lib.read_profile_parameters(list(_PROFIL)),
        _CONTROLES)
    autre_heure = dict(artefact, generated_at="1999-01-01T00:00:00+00:00")
    assert security_baseline.posture_hash(autre_heure) == artefact["hash"]


def test_l_assemblage_de_la_posture_n_ouvre_aucune_connexion():
    # Hors ligne par contrat : tout vient des lectures déjà faites.
    lib = _lib(_PROFIL)
    mesures = lib.read_profile_parameters(list(_PROFIL))
    lib.appels.clear()
    lib.lectures.clear()
    lib.build_security_posture({"release": "758"}, mesures, _CONTROLES)
    assert lib.appels == [] and lib.lectures == []


def test_l_artefact_ecrit_est_du_json_deterministe_relu_par_un_keyword(tmp_path):
    lib = _lib(_PROFIL)
    artefact = lib.build_security_posture(
        {"release": "758"}, lib.read_profile_parameters(list(_PROFIL)),
        _CONTROLES)
    chemin = tmp_path / "postures" / "a4h.json"
    preuve = lib.write_security_posture(str(chemin), artefact)
    assert preuve == {"path": str(chemin), "sha256": artefact["hash"]}
    brut = chemin.read_bytes().decode("utf-8")
    assert "\r\n" not in brut and brut.endswith("\n")
    assert lib.read_security_posture(str(chemin)) == artefact


# --- security_posture_should_not_have_drifted : la sentinelle -----------------

def test_premiere_visite_la_reference_est_ecrite_et_le_passage_reussit(tmp_path):
    lib = _lib()
    chemin = tmp_path / "posture-reference.json"
    verdict = lib.security_posture_should_not_have_drifted(
        str(chemin), _fiches(_PROFIL), identity={"release": "758"})
    assert verdict == {"first_visit": True, "drifted": False,
                       "reference": str(chemin), "changed": [],
                       "appeared": [], "disappeared": [], "unchanged": 3}
    reference = lib.read_security_posture(str(chemin))
    assert reference["identity"] == {"release": "758"}
    assert [r["name"] for r in reference["readings"]] == sorted(_PROFIL)


def test_second_passage_inchange_ne_reecrit_pas_la_reference(tmp_path):
    lib = _lib()
    chemin = tmp_path / "posture-reference.json"
    lib.security_posture_should_not_have_drifted(str(chemin), _fiches(_PROFIL))
    ecritures = _compter_les_ecritures(lib)
    verdict = lib.security_posture_should_not_have_drifted(
        str(chemin), _fiches(_PROFIL))
    assert verdict == {"drifted": False, "changed": [], "appeared": [],
                       "disappeared": [], "unchanged": 3, "first_visit": False,
                       "reference": str(chemin)}
    assert ecritures == []


def test_une_derive_leve_une_erreur_qui_nomme_l_avant_et_l_apres(tmp_path):
    lib = _lib()
    chemin = tmp_path / "posture-reference.json"
    lib.security_posture_should_not_have_drifted(str(chemin), _fiches(_PROFIL))
    derive = dict(_PROFIL, **{"login/min_password_lng": (0, "3")})
    with pytest.raises(AssertionError) as erreur:
        lib.security_posture_should_not_have_drifted(str(chemin),
                                                     _fiches(derive))
    message = str(erreur.value)
    assert "login/min_password_lng" in message
    assert "'8'" in message and "'3'" in message and "->" in message
    assert str(chemin) in message
    # les paramètres inchangés ne polluent pas le message
    assert "gw/reg_no_conn_info" not in message


def test_une_derive_ne_reecrit_jamais_la_reference(tmp_path):
    # Sinon la dérive s'auto-acquitte : la référence du passage suivant serait
    # la configuration dérivée, et l'incident disparaîtrait tout seul.
    lib = _lib()
    chemin = tmp_path / "posture-reference.json"
    lib.security_posture_should_not_have_drifted(str(chemin), _fiches(_PROFIL))
    ecritures = _compter_les_ecritures(lib)
    with pytest.raises(AssertionError):
        lib.security_posture_should_not_have_drifted(
            str(chemin), _fiches(dict(_PROFIL,
                                      **{"login/min_password_lng": (0, "3")})))
    assert ecritures == []
    conservee = {r["name"]: r["value"]
                 for r in lib.read_security_posture(str(chemin))["readings"]}
    assert conservee["login/min_password_lng"] == "8"


def test_un_parametre_apparu_ou_disparu_est_une_derive_nommee(tmp_path):
    lib = _lib()
    chemin = tmp_path / "posture-reference.json"
    lib.security_posture_should_not_have_drifted(str(chemin), _fiches(_PROFIL))
    reduit = {nom: valeur for nom, valeur in _PROFIL.items()
              if nom != "gw/reg_no_conn_info"}
    with pytest.raises(AssertionError) as erreur:
        lib.security_posture_should_not_have_drifted(
            str(chemin), _fiches(dict(reduit, **{"rsau/enable": (0, "1")})))
    message = str(erreur.value)
    assert "rsau/enable : apparu" in message
    assert "gw/reg_no_conn_info : disparu" in message


@pytest.mark.parametrize("drapeau", [False, "False", "no", ""])
def test_fail_on_drift_faux_rapporte_sans_echouer(tmp_path, drapeau):
    lib = _lib()
    chemin = tmp_path / "posture-reference.json"
    lib.security_posture_should_not_have_drifted(str(chemin), _fiches(_PROFIL))
    derive = dict(_PROFIL, **{"login/min_password_lng": (4, "")})
    verdict = lib.security_posture_should_not_have_drifted(
        str(chemin), _fiches(derive), fail_on_drift=drapeau)
    assert verdict["drifted"] is True and verdict["first_visit"] is False
    assert verdict["changed"][0] == {
        "name": "login/min_password_lng",
        "before": {"status": "defined", "value": "8"},
        "after": {"status": "unknown", "value": None}}
