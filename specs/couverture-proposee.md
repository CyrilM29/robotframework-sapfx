# Couverture proposée : les campagnes à ouvrir

Ce fichier n'est pas un plan de test. C'est la **liste des campagnes qui
restent à ouvrir**, avec pour chacune ce qu'elle prouverait, pourquoi elle
n'est pas couverte aujourd'hui, et ce qu'il faut réunir avant de la lancer. Les
plans exécutables vivent à côté, un par domaine ; `check_spec_sync.py` exempte
ce fichier de la liste des plans sans suite (`_UNLINKED_OK`).

Il existe parce que les campagnes de launchpad ABAP du 2026-08-24 ont produit
quatre points « reportés » qui ne sont pas des trous dans ces campagnes, mais
des campagnes à part entière. Les points **refusés** (seuil de verrouillage de
compte, retour utilisateur, bascule de langue et de thème, approbation de
commande, recherche par titre exact) sont tranchés dans les plans eux-mêmes et
n'ont pas à être rouverts ici.

Ordre de lecture : par valeur décroissante, pas par facilité.

---

## 1. Mode espaces et pages du launchpad (`Spaces & Pages`)

- **Ce que ça prouve** : la mise en page d'accueil que SAP a faite par défaut à
  partir de S/4HANA 2023. L'accueil n'est alors plus le `DashboardContent`
  classique mais un jeu d'espaces et de pages, avec un autre arbre de contrôles,
  une autre navigation et un autre mode d'édition. Toute la couche « accueil »
  du page object partagé repose aujourd'hui sur la seule mise en page
  historique.
- **État** : capacité **présente et non activée** sur l'ABAP 2023 (services
  `Pages` et `SpaceContent` observés le 2026-08-24), absente du 1909.
- **Prérequis** : activer le mode sur le système 2023, ce qui est un changement
  de configuration persistant. À faire en connaissance de cause : une fois
  activé, l'accueil classique n'est plus observable sur cette cible, donc les
  scénarios d'accueil des deux campagnes actuelles ne s'y rejouent plus. Prévoir
  une sauvegarde du conteneur avant (`backup-abap2023.ps1`).
- **Décision suggérée** : la plus rentable des quatre, parce que c'est la forme
  que rencontreront les clients récents, et parce qu'elle éprouve directement
  l'hypothèse structurante du page object partagé (« un accueil, un
  `DashboardContent` »). À ouvrir en premier, juste après une sauvegarde.

## 2. Premier chargement d'un système réellement froid

- **Ce que ça prouve** : que la bibliothèque reste **honnête** quand la lenteur
  vient du serveur et non de la page. Mesuré le 2026-08-24 : le premier
  chargement du FLP d'un conteneur fraîchement démarré dépasse deux minutes
  (compilation côté serveur), `Wait For Ui5 Idle` échoue alors avec un état
  illisible parce que `document.body` n'existe pas encore, et toutes les
  ressources ICF répondent pourtant 200. C'est le même motif que le premier
  `$count` OData d'un service jamais sollicité.
- **État** : observé une fois, jamais rejoué sous forme de test. Les campagnes
  actuelles tournent sur des conteneurs déjà chauds.
- **Prérequis** : maîtriser le froid, donc redémarrer un conteneur dans le
  scénario (les scripts `stop-abap2023.ps1` / `start-abap2023.ps1` existent). Un
  run complet coûte alors plusieurs minutes de démarrage, ce qui en fait une
  campagne à part et non un test à glisser dans une suite existante.
- **Ce qu'elle doit asserter** : le message d'échec **nomme la bonne cause**
  (serveur qui compile, pas page cassée, pas réseau), et le budget d'attente
  paramétré suffit quand on le donne. La valeur est dans le message, pas dans le
  chronomètre.
- **Décision suggérée** : à ouvrir quand un lot touchera les messages d'attente
  ou les budgets. Seule, elle mobilise beaucoup de temps machine pour une
  assertion.

## 3. Débordement de la barre shell (petit viewport)

- **Ce que ça prouve** : que les ancres de la barre shell tiennent quand la
  fenêtre rétrécit. UI5 déplace alors les éléments de tête dans un bouton de
  débordement, donc des contrôles parfaitement présents cessent d'être rendus à
  leur place habituelle. C'est exactement la famille de piège déjà payée deux
  fois sur ces campagnes (`visible=true` sur un contrôle sans nœud DOM, tuile
  masquée par une colonne repliée).
- **État** : jamais exercé, les deux campagnes tournent à une seule géométrie.
- **Prérequis** : aucun. C'est le seul point des quatre qui ne demande ni
  configuration, ni redémarrage, ni données : il suffit de piloter la taille du
  viewport et de rejouer les scénarios de barre shell.
- **Décision suggérée** : le meilleur rapport valeur sur coût du lot. À prendre
  dès qu'on rouvre ces suites, et à écrire sur les DEUX releases, la stratégie
  de débordement ayant changé entre 1.71 et 1.120.

## 4. Onglet des applications fréquemment utilisées

- **Ce que ça prouve** : le panneau d'activités au-delà de son onglet récent.
  L'onglet « Frequently Used » ne se remplit qu'à l'usage, donc il est vide sur
  un système de laboratoire et n'a pas pu être observé.
- **Prérequis** : semer l'historique, c'est-à-dire ouvrir plusieurs fois les
  mêmes applications avant d'observer. Cela **écrit** une personnalisation
  utilisateur, donc relève du même opt-in à deux tours que le cycle épingler et
  dépingler (tag `write` plus variable explicite).
- **Décision suggérée** : à greffer sur le lot d'écriture existant plutôt que
  d'ouvrir une campagne pour lui seul. Faible valeur isolée, valeur correcte en
  complément.

---

## Chantiers d'outillage, pas des campagnes

Deux points restés ouverts après le lot du 2026-08-24. Ils ne se traitent pas
par un test, mais ils ont leur place ici pour ne pas se perdre.

### rf-mcp fige aussi les resources déjà analysées

Un `import_resource` ressert la copie en mémoire : les variables et mots-clés
ajoutés à un `.resource` depuis le démarrage du serveur restent invisibles, et
rien ne le dit. C'est du comportement rf-mcp, pas du code SAPFX, donc rien à
corriger dans la bibliothèque.

**Décision du 2026-08-24 : ne rien construire.** Redémarrer le serveur rf-mcp
corrige tout (process neuf, caches neufs), et c'est déjà la voie nominale
documentée pour le code Python. Le piège ne mord que pendant qu'on DÉVELOPPE la
couche resources sous un serveur qui tourne : sur un pack déployé, les
`.resource` ne bougent pas en cours de session. Une détection `mtime` à la
`_staleness.py` et une éviction du cache Robot ont été envisagées puis
abandonnées : de l'outillage permanent pour une gêne de développement qui a un
remède d'une commande. Risque résiduel assumé : pendant une session de dev, un
`.resource` modifié ne déclenche AUCUN avertissement (le `stale_code_warning`
ne couvre que les modules Python) ; le réflexe est de redémarrer le serveur
après toute édition de resource, et la field note de `CLAUDE.md` le dit.

### Cas transitoire du bundle versionné

Une page portant un bundle **antérieur** au correctif de version voit ses
enveloppes réseau enveloppées une fois de plus, l'ancienne version ne portant
pas la marque qui permettrait de la reconnaître. **Décision : ne rien faire.**
Le comptage servi reste juste (mesuré), la surcouche disparaît au prochain
chargement de page, la fenêtre se limite à la durée de vie d'une page ouverte au
moment d'une mise à jour, et « corriger » supposerait de désenvelopper une
fermeture qu'on ne possède pas. Documenté vaut mieux qu'un contournement qui
prétendrait faire plus qu'il ne peut.
