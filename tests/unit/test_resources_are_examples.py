"""`resources/` s'annonce comme un EXEMPLE, mécaniquement.

La couche `resources/` porte le vocabulaire métier d'UNE installation : chaque
identifiant, chemin de service et nom de table y a été relevé live sur les
cibles du laboratoire du dépôt. Beaucoup s'y réutilise ailleurs, rien n'y fait
autorité : c'est `src/`, les bibliothèques, qui vaut sur tout système SAP.

Pourquoi un garde plutôt qu'une phrase dans un guide : ces fichiers partent
tels quels dans le dépôt PUBLIC et dans le pack Windows, où le lecteur n'a ni
le contexte du laboratoire ni la conversation qui l'expliquait. Un fichier
livré sans son bandeau se lit comme un contrat, et le lecteur écrit alors des
tests contre les écrans d'un autre système. Le bandeau doit donc voyager AVEC
le fichier, et un `.resource` ajouté demain ne doit pas pouvoir l'oublier.

Même modèle que les autres gardes du dépôt : la propriété est vérifiée sur
l'arbre RÉEL, pas sur une copie de test.
"""
from __future__ import annotations

from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
DOSSIER = RACINE / "resources"

# Le bandeau est en français, comme la documentation des `.resource`.
MARQUEUR = "EXEMPLE À PERSONNALISER"
# Il doit être DANS l'en-tête `Documentation`, donc lu avant tout le reste, et
# rendu par Libdoc en tête de page.
LIGNES_ENTETE = 12


def _resources():
    fichiers = sorted(DOSSIER.rglob("*.resource"))
    assert fichiers, "aucun .resource trouvé : chemin du garde à revoir"
    return fichiers


def test_chaque_resource_porte_le_bandeau_exemple():
    manquants = []
    for chemin in _resources():
        entete = chemin.read_text(encoding="utf-8").splitlines()[:LIGNES_ENTETE]
        if not any(MARQUEUR in ligne for ligne in entete):
            manquants.append(chemin.relative_to(RACINE).as_posix())
    assert not manquants, (
        "ces fichiers de resources/ n'annoncent pas qu'ils sont des exemples à "
        f"personnaliser (bandeau « {MARQUEUR} » dans les {LIGNES_ENTETE} "
        f"premières lignes) : {manquants}. Voir resources/README.md.")


def test_le_bandeau_est_dans_la_documentation_robot():
    """Le bandeau vit dans l'en-tête `Documentation`, pas dans un commentaire.

    Un `#` disparaît de la page Libdoc, c'est-à-dire exactement là où un
    utilisateur de la bibliothèque lit le fichier.
    """
    hors_documentation = []
    for chemin in _resources():
        for ligne in chemin.read_text(encoding="utf-8").splitlines()[:LIGNES_ENTETE]:
            if MARQUEUR in ligne:
                if not ligne.startswith(("Documentation", "...")):
                    hors_documentation.append(chemin.relative_to(RACINE).as_posix())
                break
    assert not hors_documentation, (
        "bandeau présent mais hors de l'en-tête Documentation (invisible dans "
        f"Libdoc) : {hors_documentation}")


def test_le_readme_de_la_couche_existe_dans_les_deux_langues():
    for nom in ("README.md", "README.fr.md"):
        chemin = DOSSIER / nom
        assert chemin.exists(), f"resources/{nom} manquant"
        texte = chemin.read_text(encoding="utf-8")
        # Les deux moitiés de la clarification : ce qui fait foi, et ce qui est
        # un exemple. Sans elles, le README ne dit plus ce pour quoi il existe.
        assert "src/" in texte, f"resources/{nom} ne dit pas que src/ fait foi"
        assert "page_objects" in texte, (
            f"resources/{nom} ne mentionne pas la couche page objects")
