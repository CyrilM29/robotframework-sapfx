---
name: rien-ne-relie-un-run-a-un-livrable
description: 2026-08-25, le projet produit des preuves techniques excellentes et aucun livrable de restitution : `output.xml` jamais lu, rapports Markdown enfouis dans le log, documents ISTQB déconnectés des résultats
type: projet
date: 2026-08-25
---

Inventaire de la couche restitution, fait à l'occasion de l'étude d'un voisin
adjacent (une extension de reporting exécutif pour un ALM du marché). Le
constat tient en une phrase : **rien ne relie un run d'exécution à un livrable
destiné à être lu par un humain qui n'est pas testeur.**

Ce qui existe, et qui est bon :

- rapport HTML auto-contenu du recorder (CSS inline, captures en data-URI),
  mais il documente un ENREGISTREMENT, pas une exécution : ni statut
  PASS/FAIL, ni durée, ni horodatage de run ;
- gabarit ISTQB / ISO 29119-3 avec bloc `replay` neutre vis-à-vis du
  framework, mais statique et déconnecté des résultats ;
- artefacts JSON triés avec hash SHA-256 hors horodatage : le déterminisme est
  déjà là, et c'est la brique la plus solide ;
- quatre `render_*_report()` rendant du Markdown (sentinelle, diagnostic
  Fiori, comparaisons d'artefacts) plus un rapport de dérive de healing avec
  code retour exploitable en CI.

Ce qui manque, et le trou est structurel :

- **`output.xml` n'est jamais lu.** Aucun `ExecutionResult`, aucun
  `ResultVisitor`, aucun `rebot` nulle part. La stratégie de fait est « le
  `log.html` autoporteur de Robot Framework est le rapport » ;
- **aucune agrégation multi-runs**, donc aucune tendance ;
- **aucun verdict de release** (le pendant du GO/NO-GO que vend le voisin) ;
- **aucun format d'échange** (JUnit XML, Allure, JSON de résultats), donc
  aucune porte vers un ALM ;
- la **traçabilité est rédigée en prose par un LLM**, pas calculée : la chaîne
  `specs/*.md` → suite `.robot` → keywords `resources/` → objet SAP existe et
  est meilleure que celle du voisin (elle descend jusqu'à la transaction ou
  l'entity set), mais rien ne la parcourt, donc rien ne la vérifie.

**Pourquoi :** les quatre rapports Markdown sont poussés par `Log` /
`logger.info`, donc ils finissent DANS le `log.html`. Chacun est utile et
aucun n'est un livrable : pour les lire, il faut déjà savoir ouvrir un log
Robot Framework et chercher au bon endroit. Le public visé (manager, auditeur,
client) ne le fera jamais. Le même travail produit donc à la fois une preuve
excellente et zéro restitution, ce qui se voit d'autant moins que la
couverture de tests, elle, reste excellente : c'est le même angle mort que
[[angle-mort-canal-teste-en-indirect]], déplacé du code vers le livrable.

Le voisin étudié vend exactement ce chaînon, et sur des convictions qui sont
déjà les nôtres : score déterministe explicable (notre hash hors horodatage),
tout en local sans serveur (notre `log.html` autoporteur), écriture seulement
sur geste explicite (notre opt-in à deux tours de la simulation d'écriture).
Nous avons les propriétés techniques ; il leur manque d'être servies à
quelqu'un.

**Comment appliquer :** avant d'ajouter une capacité de perception ou
d'exécution de plus, se demander si un run peut déjà produire autre chose
qu'un `log.html`. Le point d'entrée est `output.xml` lu par
`robot.api.ExecutionResult` (stdlib Robot, rien à parser à la main), et la
logique reste pure dans `sapfx_common` au titre de la convention #12 : un
verdict de release est une CAPACITÉ, pas un helper de campagne. Les signaux
qui manquent au voisin, nous les avons déjà et ils ne demandent qu'à être
croisés : télémétrie de healing, verdicts de sonde, dérives de sentinelle,
`collection_errors`. Un score qui intègre « trois localisateurs réparés cette
semaine » dit ce qu'aucun taux de réussite ne dit.
