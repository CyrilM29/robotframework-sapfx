# Les conventions du dépôt

Les 13 conventions de `CLAUDE.md`, condensées. Elles sont pour la plupart tenues
MÉCANIQUEMENT, pas seulement énoncées.

1. **Aucun id SAP brut ni CSS/XPath dans un test.** Les localisateurs vivent
   dans `resources/` ; sur Fiori, adresser des CONTRÔLES UI5
   (`controlType`, `properties`, `bindingPath`), jamais des ids DOM.
   Ce que livre `resources/` est un EXEMPLE mesuré sur les cibles du
   laboratoire, à vérifier et adapter par cible et par métier
   (`resources/README.md`) ; ce qui fait foi partout est `src/`.
2. **Jamais `time.sleep`.** Attentes conditionnelles seulement.
3. **Assertions indépendantes de la locale** : TYPE de message, ids techniques,
   codes de refus, JAMAIS un texte traduit.
4. **Diff amont d'une ligne** : `_vendor/` est du code amont verbatim, le
   comportement neuf va dans un mixin.
5. **Tout nouveau keyword a un test unitaire hors SAP** (`tests/unit/`, COM et
   Browser simulés), même s'il a aussi un smoke live.
6. **`pywin32` épinglé** (`==`) dans les trois fichiers d'environnement, un
   plancher seulement dans `pyproject.toml` : une bibliothèque n'épingle pas
   ses consommateurs.
7. **Supports d'assistants synchronisés** : `CLAUDE.md` est canonique,
   `AGENTS.md` et `.github/copilot-instructions.md` en sont les miroirs, mis à
   jour dans le même commit.
8. **Marqueurs de cycle de vie des specs** : un plan devenu faux est marqué
   `PÉRIMÉE` (bloque `check_spec_sync.py`), les écarts constatés à la
   génération sont consignés dans le plan, chaque session de healing écrit dans
   `docs/heal-journal.md`.
9. **Vérifier les remotes** avant de commencer et avant tout commit, y compris
   le dépôt PUBLIC (les PR et issues des utilisateurs y arrivent, sans lien
   technique avec le dépôt privé).
10. **Docs et mémoire mises à jour AVANT le commit, dans le même lot.** Jamais
    « je committe, je documenterai après » : la session suivante travaillerait
    sur un guide qui ment.
11. **Aucun identifiant en dur.** Voir [demarrage.md](demarrage.md).
12. **Une lacune de capacité se comble DANS la bibliothèque.** Frontière : les
    bibliothèques portent les CAPACITÉS, `resources/` porte le VOCABULAIRE
    MÉTIER d'un site. Un keyword utile à un autre projet SAP appartient à la
    bibliothèque ; un keyword qui nomme l'écran de CETTE application appartient
    à `resources/`. Deux effets de bord à vérifier à chaque promotion : la
    PORTÉE peut changer en silence (un `Evaluate JavaScript` avec sélecteur nul
    s'évalue sur la page quelle que soit la pile de frames, un keyword de
    bibliothèque honore la pile), et la SURFACE DE HEALING se réduit (le healer
    répare `resources/`, jamais `src/`, donc ce qui reste doit être ce qui
    VARIE par site).
13. **Aucun fichier de code au-delà de 500 lignes.** Découper selon une couture
    existante (un mixin par capacité, logique pure dans `sapfx_common`), jamais
    à la ligne 500. Hors périmètre : Markdown, suites et `.resource`, artefacts
    générés, supports visuels, `_vendor/`.

## Posture générale : constater, ne pas corriger

Un test rouge, une violation d'accessibilité, une dérive de baseline se
RAPPORTENT (fichier, écran, règle, impact, sortie utile), puis on s'arrête. Pas
de mise à jour de baseline de confort, pas de `--update-snapshots` pour
verdir une suite, agents de healing sur demande seulement. En cas de doute :
constater, puis demander.

L'exception est la convention #12 : la cible se constate, NOTRE bibliothèque se
répare.

## Gardes mécaniques

| Garde | Ce qu'il refuse |
| --- | --- |
| `check_conventions.py` | localisateurs bruts dans une suite générée, `Sleep`, JS inline / `__import__` bloquant dans `resources/` ou une suite, `modules=` dans une suite |
| `check_no_em_dash.py` | le tiret cadratin, dans tout fichier texte suivi (allowlist à compte EXACT) |
| `check_file_length.py` | un fichier de code au-delà de 500 lignes |
| `check_spec_sync.py` | une suite en retard sur son plan, un plan marqué périmé |
| `check_bilingual_docs.py` | un `docs/*.md` sans sa traduction `.fr.md` |
| `check_guidance_sync.py` | hints rf-mcp et définitions d'agents désalignés de `CLAUDE.md` |
| `check_published_versions.py` | une version SAPFX périmée dans une instruction publiée |
| `check_vendor_drift.py` | une dérive du fichier vendorisé contre l'amont réel |
| tests unitaires | credentials par défaut, bandeau d'exemple absent d'un `.resource`, pins de dépendances désaccordés, versions incohérentes |

Un hook `PostToolUse` lance les gardes pertinents après chaque édition.
