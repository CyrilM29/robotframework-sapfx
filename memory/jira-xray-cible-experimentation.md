---
name: jira-xray-cible-experimentation
description: 2026-08-26, un bac à sable Jira + Xray entièrement en conteneurs n'est plus ouvrable (licences Data Center fermées le 30/03/2026) : l'expérimentation ALM se fait sur la variante Cloud, Kiwi TCMS reste l'alternative self-hosted en réserve
type: projet
date: 2026-08-26
---

Le lot d'ouverture ALM (remonter les résultats d'un run, gérer les Test
Executions, redescendre une exigence vers un plan) a besoin d'une cible pour
être expérimenté. La voie qui paraissait évidente, tout monter en conteneurs,
est **fermée, et pour une raison licencielle et non technique** : depuis le
30 mars 2026 Atlassian ne délivre plus de licence d'évaluation en self-service
pour ses produits Data Center, et les ventes d'apps Marketplace Data Center
sont closes aux nouveaux clients à la même date. L'image Docker officielle de
Jira existe toujours et démarre, mais c'est du Data Center (l'édition Server
est morte en 2024) et son assistant de configuration réclame une clé qu'un
nouvel arrivant ne peut plus obtenir ; les licences développeur gratuites
supposent une licence commerciale déjà active. Xray Server/DC étant une app
installée dans cette même instance, il hérite du verrou.

**Décision du 2026-08-26** : l'expérimentation se fait sur la variante
**Cloud** (offre Jira gratuite jusqu'à 10 utilisateurs, essai Xray de 30 jours),
et **Kiwi TCMS** (open source, conteneurisable, API REST, plugins CI) reste
l'alternative self-hosted **gardée en réserve et non engagée**, pour le jour où
la question deviendrait « un gestionnaire de tests durable » plutôt que
« compatibilité Xray ».

**Pourquoi :** trois contraintes, dont deux se paient plus tard si on ne les
écrit pas maintenant. (1) Aucune ingéniosité d'infrastructure ne lève un
blocage de licence : insister sur le conteneur, c'est dépenser du temps sur le
seul endroit où il n'y a rien à trouver. (2) Xray a **deux variantes d'API
incompatibles**, Cloud et Server/DC, qui diffèrent sur l'authentification comme
sur la forme des requêtes : la cible choisie détermine le code de l'exporteur,
donc elle doit être annoncée dans la documentation du lot plutôt que découverte
par un utilisateur. (3) L'essai est borné à 30 jours, ce qui fait de la fenêtre
une ressource à dépenser sur le **relevé du contrat réel**, pas sur du
développement qui n'en a pas besoin.

**Comment appliquer :** garder l'ordre du lot 2.13 du backlog produit, où
l'étage 1 reste non négociable avant l'étage 2. L'export d'échange (JUnit XML
plus artefact JSON déterministe) ouvre d'un coup tous les ALM et rend le
connecteur remplaçable ; Xray ingère nativement le JUnit **et** le format
Robot Framework, donc le premier palier est presque gratuit une fois l'export
en place. Pendant l'essai, relever le contrat live (authentification, endpoints,
formes de réponse) puis figer ce relevé en double local, afin que l'intégration
se développe et tourne en intégration continue sans dépendre ni de l'essai ni
du réseau. Les identifiants suivent la convention #11 (jamais de valeur par
défaut committée), et l'écriture dans l'ALM ne se déclenche jamais depuis un
run automatique sans geste explicite, au même titre que la simulation
d'écriture SAP.
