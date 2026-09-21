"""Tests hors SAP des keywords de **surface d'attaque** du canal RFC
(`Read Account Usability`, `Read Icf Exposure`, `Read External Commands`,
`Read Audit Log Coverage`, `Read Rfc Trust Surface`,
`Count Authorization Object Usage`, `Read Role Assignments`,
`Read Forbidden Password Count`). Convention #5.

Aucun `pyrfc`, aucun serveur : le canal est DOUBLÉ sur l'instance, et la
doublure ENREGISTRE ses appels, parce qu'un test qui ne prouve pas que la
doublure a répondu n'éprouve rien (leçon du dépôt, 2026-08-19).

Ce fichier verrouille surtout les trois pièges d'appel mesurés le 2026-09-14,
qui produisent tous un résultat plausible plutôt qu'une erreur :

- l'intervalle obligatoire du lecteur de journal, et l'orthographe de ses
  champs ;
- la jointure des DEUX tables de services web ;
- les colonnes réelles de la table des relations de confiance.
"""
import pytest

from SapApiLibrary import SapApiLibrary


def _lib(tables=None, calls=None, raises=None):
    """Une `SapApiLibrary` dont le canal RFC est doublé sur l'INSTANCE."""
    lib = SapApiLibrary()
    lib.lectures = []
    lib.appels = []

    def read_rfc_table(table, fields, alias="default", options=None,
                       rowcount=0, delimiter="|"):
        lib.lectures.append({"table": table, "fields": list(fields),
                             "options": options, "alias": alias})
        return [dict(r) for r in (tables or {}).get(table, [])]

    def call_rfc(function_name, alias="default", **params):
        lib.appels.append({"function": function_name, "params": dict(params),
                           "alias": alias})
        if raises and function_name in raises:
            raise RuntimeError(raises[function_name])
        return dict((calls or {}).get(function_name, {}))

    lib.read_rfc_table = read_rfc_table
    lib.call_rfc = call_rfc
    return lib


def test_doublure_est_bien_celle_qui_repond():
    """Contre-épreuve : une bibliothèque NON doublée réclame une connexion.

    Sans elle, une doublure posée dans le mauvais espace de noms laisserait
    passer le vrai appel et tous les tests de ce fichier seraient verts sans
    rien éprouver (leçon du dépôt, 2026-08-19). L'exception est assertée
    PRÉCISÉMENT : un `raises(Exception)` aveugle serait satisfait par une
    faute de frappe dans le nom du keyword, donc ne prouverait pas que c'est
    bien l'absence de connexion qui a parlé."""
    with pytest.raises(RuntimeError, match="Open Rfc Connection"):
        SapApiLibrary().read_forbidden_password_count(alias="absent")


# --------------------------------------------------------------------- #
# Comptes
# --------------------------------------------------------------------- #
_COMPTES = [
    {"BNAME": "DEVELOPER", "UFLAG": "0", "CLASS": "SUPER", "USTYP": "A",
     "GLTGV": "00000000", "GLTGB": "00000000", "TRDAT": "20260914", "CODVN": "H"},
    {"BNAME": "DEVELOPER_5", "UFLAG": "0", "CLASS": "", "USTYP": "A",
     "GLTGV": "00000000", "GLTGB": "20241231", "TRDAT": "20230321", "CODVN": "H"},
]


def test_read_account_usability_separe_expire_de_verrouille():
    lib = _lib(tables={"USR02": _COMPTES})
    resume = lib.read_account_usability(alias="secu", client="001",
                                        today="20260914")
    assert resume["usable"] == ["DEVELOPER"]
    assert resume["unusable"] == ["DEVELOPER_5"]
    assert resume["by_status"]["expired"] == ["DEVELOPER_5"]
    assert resume["client"] == "001" and resume["as_of"] == "20260914"


def test_read_account_usability_rapporte_les_versions_de_hachage():
    lib = _lib(tables={"USR02": _COMPTES})
    resume = lib.read_account_usability(alias="secu", today="20260914")
    assert resume["hash_versions"] == {"H": 2}


def test_read_account_usability_projette_les_dates_de_validite():
    """Sans GLTGV/GLTGB, le keyword ne pourrait pas distinguer expiré de
    verrouillé : la projection fait partie du contrat."""
    lib = _lib(tables={"USR02": _COMPTES})
    lib.read_account_usability(alias="secu", today="20260914")
    champs = lib.lectures[0]["fields"]
    assert "GLTGB" in champs and "GLTGV" in champs and "UFLAG" in champs


# --------------------------------------------------------------------- #
# Exposition web : la jointure des deux tables
# --------------------------------------------------------------------- #
def test_read_icf_exposure_joint_les_deux_tables():
    """Le drapeau d'activation vit dans une table, le nom dans l'autre :
    lire la seconde seule donne des noeuds dont on ignore lesquels
    répondent."""
    lib = _lib(tables={
        "ICFSERVLOC": [{"ICF_NAME": "H1", "ICFACTIVE": "X"},
                       {"ICF_NAME": "H2", "ICFACTIVE": ""}],
        "ICFSERVICE": [{"ICF_NAME": "H1", "ORIG_NAME": "webgui",
                        "SSLFLAG": "", "ICF_USER": "", "ICF_MANDT": "001"},
                       {"ICF_NAME": "H2", "ORIG_NAME": "dormant",
                        "SSLFLAG": "X", "ICF_USER": "", "ICF_MANDT": "001"}],
        "ICFVIRHOST": [{"ICF_NAME": "DEFAULT_HOST", "HOSTNUMBER": "0",
                        "PROTOCOL": "HTTP"}],
    })
    resume = lib.read_icf_exposure(alias="secu")
    assert resume["declared"] == 2
    assert resume["active"] == 1
    assert resume["active_without_ssl"] == 1
    assert resume["sensitive_active"] == ["webgui"]
    assert resume["virtual_hosts"][0]["protocol"] == "HTTP"
    lues = [lecture["table"] for lecture in lib.lectures]
    assert "ICFSERVLOC" in lues and "ICFSERVICE" in lues


def test_read_icf_exposure_retombe_sur_l_identifiant_si_le_nom_manque():
    """Un noeud actif dont la fiche est absente reste COMPTÉ : le perdre
    sous-estimerait la surface, ce qui est le mauvais sens de l'erreur. Mais
    il est SIGNALÉ comme non apparié, sans quoi une jointure entièrement
    perdue rendrait le résumé d'un système sain."""
    lib = _lib(tables={"ICFSERVLOC": [{"ICF_NAME": "ORPHELIN",
                                       "ICFACTIVE": "X"}],
                       "ICFSERVICE": [], "ICFVIRHOST": []})
    resume = lib.read_icf_exposure(alias="secu")
    assert resume["active"] == 1
    assert resume["matched"] == 0
    assert resume["unmatched"] == 1


def test_read_icf_exposure_joint_sur_la_cle_complete_noeud_et_parent():
    """Un même NOM est porté par plusieurs noeuds de l'arbre (324 sur la
    cible, dont 18 aux propriétés différentes). Joindre sur le nom seul
    attribue les propriétés du premier à tous les autres, et la propriété qui
    diverge est justement celle qui compte : le compte de service."""
    lib = _lib(tables={
        "ICFSERVLOC": [{"ICF_NAME": "N", "ICFPARGUID": "P1", "ICFACTIVE": "X"},
                       {"ICF_NAME": "N", "ICFPARGUID": "P2", "ICFACTIVE": "X"}],
        "ICFSERVICE": [
            {"ICF_NAME": "N", "ICFPARGUID": "P1", "ORIG_NAME": "sain",
             "SSLFLAG": "X", "ICF_USER": "", "ICF_MANDT": "001"},
            {"ICF_NAME": "N", "ICFPARGUID": "P2", "ORIG_NAME": "anonyme",
             "SSLFLAG": "", "ICF_USER": "SERVICE", "ICF_MANDT": "001"}],
        "ICFVIRHOST": []})
    resume = lib.read_icf_exposure(alias="secu")
    assert resume["active"] == 2
    # Sans la clé complète, le second noeud hériterait des propriétés du
    # premier et le compte de service disparaîtrait du rapport.
    assert resume["with_stored_user"] == ["anonyme"]
    assert resume["active_without_ssl"] == 1


def test_read_icf_exposure_marque_les_noeuds_apparies():
    lib = _lib(tables={
        "ICFSERVLOC": [{"ICF_NAME": "H1", "ICFACTIVE": "X"}],
        "ICFSERVICE": [{"ICF_NAME": "H1", "ORIG_NAME": "webgui",
                        "SSLFLAG": "", "ICF_USER": "", "ICF_MANDT": "001"}],
        "ICFVIRHOST": []})
    resume = lib.read_icf_exposure(alias="secu")
    assert resume["matched"] == 1 and resume["unmatched"] == 0


# --------------------------------------------------------------------- #
# Journal d'audit : l'intervalle obligatoire
# --------------------------------------------------------------------- #
def _config(verdict="armed_without_filter"):
    return {"ENABLE": "X", "SLOTCOUNT": 10, "SLOTINFO": [], "VERSION": "2",
            "FILESTATUS": ""} if verdict == "armed_without_filter" else {}


def test_read_audit_log_coverage_passe_un_intervalle_bien_orthographie():
    """Le piège central : appelé sans son intervalle, le module rend zéro
    entrée SANS erreur, et l'orthographe plausible `DATE_FROM` est refusée
    côté client. Le keyword compose l'intervalle pour que l'appelant ne
    puisse commettre ni l'un ni l'autre."""
    lib = _lib(calls={"RSAU_GET_AUDIT_CONFIG": _config(),
                      "RSAU_READ_LOG": {"ET_DATA": [], "ET_STAT": []}})
    lib.read_audit_log_coverage(alias="secu", window_days=365,
                                today="20260914")
    lecture = [a for a in lib.appels if a["function"] == "RSAU_READ_LOG"][0]
    intv = lecture["params"]["IS_INTV"]
    assert set(intv) == {"DAT_FROM", "DAT_TO", "TIM_FROM", "TIM_TO"}
    assert intv["DAT_TO"] == "20260914"
    assert intv["DAT_FROM"] == "20250914"


def test_read_audit_log_coverage_constate_le_silence():
    lib = _lib(calls={"RSAU_GET_AUDIT_CONFIG": _config(),
                      "RSAU_READ_LOG": {"ET_DATA": [], "ET_STAT": []}})
    verdict = lib.read_audit_log_coverage(alias="secu", today="20260914")
    assert verdict["verdict"] == "armed_without_filter_and_silent"
    assert verdict["entries"] == 0
    assert verdict["configuration"]["slots_declared"] == 10


def test_read_audit_log_coverage_ne_transforme_pas_un_refus_en_zero():
    """Une lecture qui échoue rend `not_measured`, jamais zéro."""
    lib = _lib(calls={"RSAU_GET_AUDIT_CONFIG": _config()},
               raises={"RSAU_READ_LOG": "pas de droit"})
    verdict = lib.read_audit_log_coverage(alias="secu", today="20260914")
    assert verdict["verdict"] == "not_measured"
    assert verdict["entries"] is None


def test_read_audit_log_coverage_refuse_une_reponse_sans_ses_tables():
    """Le piège de l'appel sans intervalle, déplacé d'un cran, et signalé par
    la revue indépendante : une réponse VIDE ou de forme inattendue (module
    renommé sur une autre release, refus rendu sans exception) donnerait zéro
    entrée et « lecture réussie », soit exactement le verdict de silence
    recherché, obtenu sans avoir rien lu."""
    lib = _lib(calls={"RSAU_GET_AUDIT_CONFIG": _config(),
                      "RSAU_READ_LOG": {}})
    verdict = lib.read_audit_log_coverage(alias="secu", today="20260914")
    assert verdict["verdict"] == "not_measured"
    assert verdict["entries"] is None


def test_read_audit_log_coverage_accepte_une_reponse_vide_mais_bien_formee():
    """Contre-épreuve du test précédent : une réponse qui PORTE ses tables et
    les rend vides est une mesure, pas une panne."""
    lib = _lib(calls={"RSAU_GET_AUDIT_CONFIG": _config(),
                      "RSAU_READ_LOG": {"ET_DATA": [], "ET_STAT": []}})
    verdict = lib.read_audit_log_coverage(alias="secu", today="20260914")
    assert verdict["verdict"] == "armed_without_filter_and_silent"
    assert verdict["entries"] == 0


def test_read_audit_log_coverage_refuse_une_fenetre_non_entiere():
    """Via la frontière MCP tout arrive en chaîne : l'échec doit NOMMER
    l'argument plutôt que de sortir en conversion opaque."""
    lib = _lib(calls={"RSAU_GET_AUDIT_CONFIG": _config()})
    with pytest.raises(ValueError, match="window_days"):
        lib.read_audit_log_coverage(alias="secu", window_days="un an")


# --------------------------------------------------------------------- #
# Relations de confiance : les colonnes réelles
# --------------------------------------------------------------------- #
def test_read_rfc_trust_surface_ne_demande_pas_de_colonne_inexistante():
    """La table des confiances entrantes n'a PAS de colonne d'identifiant
    système : la demander sort en « table sans donnée », code qui accuse la
    table et ferait conclure « aucune relation » sans avoir rien lu."""
    lib = _lib(tables={"RFCTRUST": [], "RFCSYSACL": [],
                       "RFCCBWHITELIST": []})
    lib.read_rfc_trust_surface(alias="secu")
    projete = {lecture["table"]: lecture["fields"] for lecture in lib.lectures}
    assert "RFCSYSID" not in projete["RFCTRUST"]
    assert "RFCTRUSTSY" in projete["RFCTRUST"]
    assert "RFCSYSID" in projete["RFCSYSACL"]


def test_read_rfc_trust_surface_vide_est_un_resultat():
    lib = _lib(tables={"RFCTRUST": [], "RFCSYSACL": [],
                       "RFCCBWHITELIST": [{"DESTINATION": "D1"}]})
    resume = lib.read_rfc_trust_surface(alias="secu")
    assert resume["any_trust_configured"] is False
    assert resume["callback_allowlist_entries"] == 1


# --------------------------------------------------------------------- #
# Commandes, autorisations, mots de passe interdits
# --------------------------------------------------------------------- #
def test_read_external_commands_resume_l_inventaire():
    lib = _lib(calls={"SXPG_COMMAND_LIST_GET": {"COMMAND_LIST": [
        {"NAME": "CAT", "ADDPAR": "X", "OPSYSTEM": "UNIX", "OPCOMMAND": "cat"},
        {"NAME": "FIXE", "ADDPAR": "", "OPSYSTEM": "UNIX", "OPCOMMAND": "ls"}]}})
    resume = lib.read_external_commands(alias="secu")
    assert resume["total"] == 2 and resume["accepting_additional"] == 1


def test_read_external_commands_supporte_un_inventaire_vide():
    lib = _lib(calls={"SXPG_COMMAND_LIST_GET": {}})
    assert lib.read_external_commands(alias="secu")["total"] == 0


def test_count_authorization_object_usage_compte_par_objet():
    lib = _lib(tables={"AGR_1251": [{"AGR_NAME": "R1"}, {"AGR_NAME": "R2"}]})
    comptes = lib.count_authorization_object_usage("S_RFC,S_DEVELOP",
                                                   alias="secu")
    assert comptes == {"S_RFC": 2, "S_DEVELOP": 2}
    assert lib.lectures[0]["options"] == "OBJECT = 'S_RFC'"


def test_count_authorization_object_usage_refuse_une_liste_vide():
    with pytest.raises(ValueError, match="aucun objet"):
        _lib().count_authorization_object_usage("", alias="secu")


def test_read_role_assignments_isole_les_attributions_sans_echeance():
    lib = _lib(tables={"AGR_USERS": [
        {"AGR_NAME": "ZDEV", "UNAME": "DEVELOPER", "FROM_DAT": "20230101",
         "TO_DAT": "99991231"},
        {"AGR_NAME": "ZTMP", "UNAME": "DEVELOPER", "FROM_DAT": "20230101",
         "TO_DAT": "20260101"}]})
    resume = lib.read_role_assignments(alias="secu")
    assert resume["total"] == 2
    assert resume["without_end_date"] == ["DEVELOPER:ZDEV"]
    assert resume["by_user"]["DEVELOPER"] == ["ZDEV", "ZTMP"]


def test_read_forbidden_password_count_projette_la_bonne_colonne():
    """Cette table n'a pas de colonne d'utilisateur : demander `BNAME`
    sortirait en « table sans donnée » et ferait conclure « liste vide »,
    conclusion qui se trouve être la bonne sur la cible, donc invisible."""
    lib = _lib(tables={"USR40": [{"BCODE": "x"}, {"BCODE": "y"}]})
    assert lib.read_forbidden_password_count(alias="secu") == 2
    assert lib.lectures[0]["fields"] == ["BCODE"]
