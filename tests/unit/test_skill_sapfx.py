"""La skill `sapfx` ne cite pas de keyword mort et ne pointe pas dans le vide.

La skill est la boîte à outils qu'un agent charge en UN appel, et elle voyage
dans le pack Windows comme dans le dépôt public. Une skill qui cite un keyword
supprimé ou renommé est pire qu'une skill absente : l'agent l'appelle, échoue,
et cherche la cause dans le système sous test.

Le garde vérifie deux propriétés, sur l'arbre RÉEL :

* tout nom de keyword cité existe (bibliothèques `src/` ou couche `resources/`) ;
* tout fichier `references/` est atteignable depuis `SKILL.md`, et réciproquement
  (une référence orpheline n'est jamais lue, un lien mort casse la navigation).

Il ne juge PAS la prose : la fraîcheur du contenu reste une revue humaine.
"""
from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SKILL = RACINE / ".claude" / "skills" / "sapfx" / "SKILL.md"
REFERENCES = SKILL.parent / "references"

# Un nom de keyword Robot cité en code span : « Get Screen Map », « Fill Wc
# Input ». Deux mots au moins, chaque mot capitalisé (la casse des keywords du
# dépôt). Les barres obliques d'une forme condensée (« Open/Close Rfc Channel »)
# sont développées avant le test.
KEYWORD = re.compile(r"^[A-Z][A-Za-z0-9]*(?: [A-Z0-9][A-Za-z0-9]*)+$")

# Ce que la regex attrape sans que ce soit un keyword.
NON_KEYWORDS = {
    "Library Browser",          # une ligne de *** Settings ***
    "Force Tags",               # idem
    "Suite Setup", "Suite Teardown",
    "Should Be True", "Should Not Be Empty", "Log",   # keywords BuiltIn
    "Evaluate JavaScript",      # keyword de la bibliothèque Browser, cité comme contre-exemple
}


def _keywords_du_depot():
    """Les noms exposés : fonctions publiques des libs + keywords resources."""
    noms = set()
    for chemin in (RACINE / "src").rglob("*.py"):
        for m in re.finditer(r"^\s*def ([a-z_][a-z0-9_]*)\(", chemin.read_text(
                encoding="utf-8", errors="ignore"), re.M):
            noms.add(m.group(1))
    for chemin in (RACINE / "resources").rglob("*.resource"):
        texte = chemin.read_text(encoding="utf-8")
        dans_keywords = False
        for ligne in texte.splitlines():
            if ligne.startswith("*** "):
                dans_keywords = ligne.startswith("*** Keywords")
                continue
            if dans_keywords and ligne and not ligne[0].isspace() and not ligne.startswith(("#", "...")):
                noms.add(ligne.strip().lower().replace(" ", "_"))
    return noms


def _fichiers_de_la_skill():
    return [SKILL] + sorted(REFERENCES.glob("*.md"))


def _cites(texte):
    for brut in re.findall(r"`([^`\n]+)`", texte):
        brut = brut.strip()
        # « Open/Close Rfc Channel » et « Get/Log Annotated Screenshot ».
        candidats = [brut]
        if "/" in brut:
            tete, _, reste = brut.partition(" ")
            if "/" in tete:
                candidats = [f"{part} {reste}".strip() for part in tete.split("/")]
        for candidat in candidats:
            if KEYWORD.fullmatch(candidat) and candidat not in NON_KEYWORDS:
                yield candidat


def test_chaque_keyword_cite_existe():
    connus = _keywords_du_depot()
    inconnus = {}
    for chemin in _fichiers_de_la_skill():
        for nom in _cites(chemin.read_text(encoding="utf-8")):
            if nom.lower().replace(" ", "_") not in connus:
                inconnus.setdefault(chemin.name, set()).add(nom)
    assert not inconnus, (
        "la skill sapfx cite des keywords introuvables dans src/ ou resources/ : "
        f"{ {k: sorted(v) for k, v in inconnus.items()} }")


def test_les_references_sont_liees_dans_les_deux_sens():
    texte = SKILL.read_text(encoding="utf-8")
    liees = set(re.findall(r"references/([a-z0-9-]+\.md)", texte))
    presentes = {chemin.name for chemin in REFERENCES.glob("*.md")}
    assert liees - presentes == set(), (
        f"SKILL.md pointe vers des références absentes : {sorted(liees - presentes)}")
    assert presentes - liees == set(), (
        "références jamais liées depuis SKILL.md, donc jamais lues : "
        f"{sorted(presentes - liees)}")


def test_la_skill_reste_une_carte_d_orientation():
    """SKILL.md est chargé À CHAQUE invocation : le détail vit dans references/.

    Le seuil n'a rien de sacré, il sert d'alarme : au-delà, c'est qu'un
    chapitre entier est remonté dans la carte au lieu de rester dans sa
    référence.
    """
    lignes = SKILL.read_text(encoding="utf-8").splitlines()
    assert len(lignes) <= 200, (
        f"SKILL.md fait {len(lignes)} lignes : déplacer un chapitre dans "
        "references/ plutôt que gonfler la carte d'orientation")
