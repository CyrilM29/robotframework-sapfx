# La remasterisation des 500 lignes : découper 23 fichiers sans rien casser

Date : 2026-08-25. Contexte : la convention #13 (aucun fichier de code
au-delà de 500 lignes) est née avec une dette de 23 fichiers (~22 000
lignes), apurée le jour même en une passe. Quatre leçons payées en route,
pour la prochaine décomposition de cette ampleur :

1. **Un gabarit JS injecté se découpe à l'octet près.** Les chapitres
   `_ui5_bundle_*.js.tpl` / `_ui5_spy_*.js.tpl` sont concaténés par
   `_ui5_js.py` : tant que l'assemblage est identique octet pour octet
   (couper aux frontières de lignes, joindre sans séparateur), la version du
   bundle (empreinte du contenu) ne bouge pas, donc aucun artefact généré à
   régénérer et aucun test d'synchronisation à retoucher. Vérifier
   l'empreinte AVANT/APRÈS est la preuve en une ligne.

2. **Un monkeypatch suit le site d'appel, pas la façade.** Une fonction
   déplacée lit ses collaborateurs dans les globals de SON module : patcher
   le nom re-exporté par la façade ne change rien pour elle. Tout test qui
   patche un collaborateur doit viser le module propriétaire (les lectures,
   elles, passent très bien par la façade). C'est LE poste de travail des
   découpes : recenser les `monkeypatch.setattr` avant de couper.

3. **`ruff --fix` mange les surfaces de re-export.** Dans un module de
   fixtures ou une façade, les imports « inutilisés » sont la marchandise :
   sans `X as X` (façades) ou sans directive `# ruff: noqa: F401` en tête
   (fixtures de tests), un autofix les supprime et casse les consommateurs.
   Poser la protection AVANT le premier `--fix`.

4. **mypy ne vérifie que les corps annotés.** Les mixins non typés (ECC,
   Fiori) se composent librement ; le canal API, typé, exige que ses mixins
   héritent d'un socle (`_ApiCore`) qui déclare l'état partagé, sinon chaque
   `self._request` est une erreur. Le choix du patron de découpe dépend donc
   du typage du fichier, pas seulement de son contenu.

5. **Une découpe SUPPRIME des fichiers, et un `build/` résiduel les
   ressuscite.** setuptools réutilise `build/lib/` s'il existe : les gabarits
   supprimés du dépôt (`_ui5_bundle.js.tpl`, `_ui5_spy_listener.js.tpl`) sont
   repartis dans le wheel du pack, invisibles à l'arbre de travail comme à
   `git status`. Rien n'échoue, le code lit les nouveaux chapitres : on livre
   simplement du code mort et un build non reproductible. Après toute
   modification de la DISPOSITION des fichiers, purger `build/` avant de
   construire, et vérifier le wheel en le comparant à `src/` (ce que le wheel
   contient et que `src/` n'a pas est, par définition, périmé).

6. **Le scan anti-fuite de l'export public se déclenche sur le TEXTE d'une
   convention.** Énoncer la règle des 500 lignes exigeait de nommer le dossier
   privé dans ses exemptions : la mention est partie dans les deux miroirs de
   doc, dans le garde, dans le hook et dans son test, et l'export a refusé
   l'arbre entier. Deux remèdes coexistent déjà dans `_export_rules.py`, et le
   bon dépend de la nature du fichier : une TRANSFORMATION pour un document
   (l'arbre public ne doit pas décrire un dossier absent), l'ALLOWLIST pour un
   garde (un préfixe d'exemption devenu sans objet est inoffensif, précédent
   `check_bilingual_docs.py`). À vérifier au plus tard le jour où l'on écrit la
   convention, pas le jour de la release.

La règle est tenue par `scripts/check_file_length.py` (CI + hook + test
unitaire), allowlist à compte exact, vide : l'état à préserver.
