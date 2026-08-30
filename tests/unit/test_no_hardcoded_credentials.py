"""Aucun identifiant en dur dans les artefacts Robot Framework.

Les identifiants entrent par la ligne de commande (`-v "X: Secret:…"`) ou par
l'environnement, jamais par une valeur par défaut committée. Ce garde existe
parce que le scan anti-fuite de `export_public_tree.py` est une **liste noire
de chaînes connues** : il arrête ce qu'on lui a appris à reconnaître, donc il
ne verrait PAS une clé d'API inconnue de lui. Le seul filet qui vaille est donc
en amont, sur la FORME : une variable d'identifiant garde sa valeur vide.

Le cas réaliste n'est pas la malveillance, c'est la commodité : coller une clé
dans la resource « juste pour ce run », et l'oublier. Le dépôt privé le
tolérerait ; le dépôt public, alimenté par export à chaque release, ne le
tolère pas.
"""
from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
ARBRES = ("resources", "tests/robot", "variables")
SUFFIXES = (".resource", ".robot")

# Un nom de variable qui parle d'authentification.
NOM_IDENTIFIANT = re.compile(
    r"^\$\{([A-Z0-9_]*(?:PASSWORD|PASSWD|PWD|SECRET|TOKEN|APIKEY|API_KEY|KEY))\}$")
DEFINITION = re.compile(r"^(\$\{[A-Z0-9_]+\})\s+(.+?)\s*$")
VALEURS_VIDES = {"${EMPTY}", ""}

# Exceptions, chacune avec sa raison. Aucune n'est un identifiant d'accès à un
# système réel : une clé MÉTIER (une valeur de table), le mot de passe d'un faux
# fournisseur d'identité servi par une fixture HTML locale dont l'existence même
# est le sujet du test, et un SÉLECTEUR de champ de saisie, que le garde ne peut
# distinguer d'un secret que par son contenu.
TOLERES: dict[tuple[str, str], str] = {
    ("resources/cross_channel_keywords.resource", "WRITE_SIMULATION_KEY"):
        "clé métier (valeur de table), pas un identifiant d'accès",
    ("tests/robot/fiori_auth_smoke.robot", "IDP_PASSWORD"):
        "mot de passe du faux IDP de fixtures/idp_login_fixture.html",
    ("resources/page_objects/abap_flp.resource", "ABAP_FLP_LOGIN_PASSWORD"):
        "sélecteur CSS du champ de saisie du formulaire ICF, pas un secret",
    ("resources/rfc_keywords.resource", "WRONG_PASSWORD"):
        "sonde de refus : un mot de passe qui DOIT être rejeté, jamais un accès",
    # Le mot « key » d'un contrôle UI5 désigne sa CLÉ TECHNIQUE (propriété
    # `key` d'une entrée de menu, d'un onglet, d'une colonne) : justement
    # l'ancre qui rend une assertion indépendante de la locale (convention #3),
    # là où le libellé visible est traduit. Aucune de ces valeurs n'ouvre quoi
    # que ce soit, et la cible est un site public sans authentification.
    ("resources/page_objects/openui5_demokit.resource", "DEMOKIT_MENU_SETTINGS_KEY"):
        "clé technique d'entrée de menu UI5, pas un identifiant d'accès",
    ("resources/page_objects/openui5_demokit.resource", "DEMOKIT_MENU_APPEARANCE_KEY"):
        "clé technique d'entrée de menu UI5, pas un identifiant d'accès",
    ("resources/page_objects/openui5_demokit.resource", "DEMOKIT_DOC_NAME_KEY"):
        "clé technique de colonne de documentation, pas un identifiant d'accès",
    ("resources/page_objects/openui5_demokit.resource", "DEMOKIT_ALTERNATE_THEME_KEY"):
        "clé technique de thème UI5 (sap_horizon_dark), pas un identifiant d'accès",
}


def _definitions_d_identifiants(racine: Path = RACINE,
                                arbres: tuple[str, ...] = ARBRES
                                ) -> list[tuple[str, int, str, str]]:
    """(chemin, ligne, nom, valeur) de chaque variable d'identifiant définie.

    ``racine`` est paramétrable pour que la contre-épreuve puisse pointer un
    arbre synthétique : un garde dont on n'a jamais vu l'échec n'est pas un
    garde.
    """
    trouvees = []
    for arbre in arbres:
        base = racine / arbre
        if not base.exists():
            continue
        for fichier in sorted(base.rglob("*")):
            if not fichier.is_file() or fichier.suffix not in SUFFIXES:
                continue
            rel = fichier.relative_to(racine).as_posix()
            dans_variables = False
            for numero, ligne in enumerate(
                    fichier.read_text(encoding="utf-8").splitlines(), 1):
                if ligne.startswith("***"):
                    dans_variables = ligne.lower().startswith("*** variables")
                    continue
                if not dans_variables:
                    continue
                trouve = DEFINITION.match(ligne)
                if not trouve:
                    continue
                nom_complet, valeur = trouve.group(1), trouve.group(2)
                nom = NOM_IDENTIFIANT.match(nom_complet)
                if not nom:
                    continue
                # Un commentaire de fin de ligne n'appartient pas à la valeur.
                valeur = re.split(r"\s{2,}#", valeur)[0].strip()
                trouvees.append((rel, numero, nom.group(1), valeur))
    return trouvees


def test_les_variables_d_identifiants_restent_vides():
    fautives = [
        (rel, numero, nom, valeur)
        for rel, numero, nom, valeur in _definitions_d_identifiants()
        if valeur not in VALEURS_VIDES and (rel, nom) not in TOLERES
    ]
    assert fautives == [], (
        "identifiant en dur dans un artefact committé : "
        + "; ".join("%s:%d %s = %r" % f for f in fautives)
        + ". Le passer en ligne de commande (-v \"NOM: Secret:…\") ou par "
          "l'environnement, ou l'inscrire dans TOLERES avec sa raison.")


def test_le_garde_voit_bien_les_variables_qu_il_pretend_surveiller():
    """Contre-épreuve : un garde qui ne trouve rien à inspecter passerait au
    vert sans rien garder. On vérifie qu'il voit les variables réelles du
    dépôt, y compris celles des trois canaux."""
    vues = {(rel, nom) for rel, _, nom, _ in _definitions_d_identifiants()}
    for attendu in (("resources/api_keywords.resource", "API_KEY"),
                    ("resources/api_keywords.resource", "API_PASSWORD"),
                    ("resources/ecc_keywords.resource", "SAP_PASSWORD"),
                    ("resources/fiori_keywords.resource", "FIORI_PASSWORD")):
        assert attendu in vues, "variable non inspectée : %s" % (attendu,)


def test_le_garde_attrape_une_cle_collee_dans_une_resource(tmp_path):
    """Contre-épreuve. Le cas simulé est le vrai : quelqu'un colle une clé d'API
    dans la resource pour faire tourner un run, et l'oublie."""
    resources = tmp_path / "resources"
    resources.mkdir()
    (resources / "api_keywords.resource").write_text(
        "*** Variables ***\n"
        "${API_KEY}                  TsAPlMsVCWzz0000exemple0000\n"
        "${API_PASSWORD}             ${EMPTY}\n",
        encoding="utf-8")

    trouvees = _definitions_d_identifiants(tmp_path, ("resources",))
    fautives = [(rel, nom, valeur) for rel, _, nom, valeur in trouvees
                if valeur not in VALEURS_VIDES]
    assert fautives == [("resources/api_keywords.resource", "API_KEY",
                         "TsAPlMsVCWzz0000exemple0000")]
    # et la variable restée vide, elle, ne remonte pas
    assert [nom for _, _, nom, valeur in trouvees
            if valeur in VALEURS_VIDES] == ["API_PASSWORD"]


def test_le_garde_ignore_ce_qui_n_est_pas_une_section_variables(tmp_path):
    """Une ligne de documentation qui CITE une variable d'identifiant ne doit
    pas être prise pour une définition : un garde qui crie au loup finit
    désactivé."""
    resources = tmp_path / "resources"
    resources.mkdir()
    (resources / "faux.resource").write_text(
        "*** Settings ***\n"
        "Documentation    Passer ${API_KEY}    une-valeur-citee-en-exemple\n"
        "\n*** Keywords ***\n"
        "Ouvrir\n"
        "    Log    ${SAP_PASSWORD}    valeur\n",
        encoding="utf-8")
    assert _definitions_d_identifiants(tmp_path, ("resources",)) == []


def test_les_exceptions_tolerees_existent_encore():
    """Une exception qui ne correspond plus à rien est une exception morte :
    elle donnerait l'illusion d'un périmètre couvert."""
    reelles = {(rel, nom) for rel, _, nom, _ in _definitions_d_identifiants()}
    orphelines = [cle for cle in TOLERES if cle not in reelles]
    assert orphelines == [], (
        "exception sans variable correspondante (à retirer) : %s" % orphelines)
