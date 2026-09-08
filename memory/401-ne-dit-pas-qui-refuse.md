---
name: 401-ne-dit-pas-qui-refuse
description: 2026-09-06, un HTTP 401 derrière une couche de gestion d'API ne dit pas si c'est elle qui refuse la clé ou le système derrière ; la clé du bac à sable SAP était saine, le backend en panne, et le diagnostic « vérifiez vos identifiants » envoyait régénérer ce qui marchait
type: projet
date: 2026-09-06
---

Trois scénarios d'une campagne API sont passés au rouge sur un HTTP 401 en
lisant le bac à sable public de SAP. Le réflexe évident, et faux, est de
conclure que la clé d'API a expiré. Mesures faites avant de toucher à quoi que
ce soit :

- une clé volontairement fausse est refusée par la **couche de gestion d'API**,
  qui répond dans son propre format (document JSON portant son code d'erreur) ;
- notre clé, elle, **traverse** cette couche et se fait refuser par le
  **système ABAP derrière** : la réponse porte `sap-system`,
  `sap-authenticated: false` et un défi `www-authenticate` nommant le serveur
  d'applications ;
- la **même clé** lit sans peine un autre bac à sable du même fournisseur.

La clé était donc parfaitement valide, et la panne entièrement chez le
fournisseur. Le classifieur du dépôt rangeait pourtant les deux cas dans un
`auth_failed` unique, dont la remédiation dit « vérifier les identifiants » :
suivi à la lettre, il faisait régénérer une clé saine, puis chercher un défaut
inexistant dans notre canal.

**Pourquoi :** un 401 nomme un refus, jamais son AUTEUR. Dès qu'une couche de
gestion d'API (SAP API Management, un approuter, un relais) s'intercale, deux
refus très différents partagent le statut, et leurs remèdes sont opposés :
changer d'identifiants d'un côté, attendre ou changer de cible de l'autre.

**Comment l'appliquer :** le discriminant est STRUCTUREL et vit dans les
en-têtes, jamais dans le corps : la page de refus d'un serveur ABAP est
LOCALISÉE, et l'a prouvé ici en revenant en allemand sur une cible dont rien
d'autre n'est en allemand (convention #3, vérifiée là où on ne l'attendait
pas). Un seul marqueur suffit : `sap-authenticated: false`, un défi nommant le
serveur d'applications, ou l'en-tête `sap-system`. Attention au dernier pas du
raisonnement : ces marqueurs ne suffisent PAS seuls, puisqu'un ABAP attaqué en
direct sans couche devant les émet aussi, et là ce sont bien les identifiants
du client qui sont refusés. La distinction tient à ce que le client sait de
son PROPRE mode d'authentification (une clé d'API s'adresse à la couche, pas
au système), et aucun en-tête de la réponse ne la porte : vérifié, la cible
n'expose aucun marqueur de sa couche de gestion.

**État à la date de la fiche, à ne pas re-diagnostiquer :** la panne est
toujours en cours côté SAP, et la lane bac à sable de
`tests/robot/api/canal_api_odata.robot` SAUTE trois scénarios exprès, ce qui
est le comportement voulu et non un défaut à réparer. Le contrôle périodique
tient en une commande, la lane `sandbox` de cette suite : trois scénarios
sautés = panne toujours en cours côté fournisseur, rien à faire ; cinq réussis
= le service est revenu ; un ÉCHEC, en revanche, nous concerne, et son verdict
nomme la couche en cause. La clé ne sera à régénérer que si cet échec sort en
`auth_failed`, c'est-à-dire refusé par la couche de gestion d'API elle-même.

Deux tests de la campagne ont été refaits dans la foulée, pour la même raison
de fond : ils ne savaient pas distinguer une panne de cible d'un défaut chez
nous. L'un affirmait qu'une clé authentifie le canal en ne regardant que
l'état LOCAL de la session, donc restait vert pendant que rien ne passait ;
l'autre attendait « une erreur quelconque » sur une clé invalide, donc restait
vert pendant que la cible refusait tout, y compris avec la bonne clé. Voir
[[gardes-qui-ne-peuvent-pas-echouer]] et
[[lecture-vide-ou-illisible-indiscernables]] : c'est la même famille, un test
qui ne peut pas échouer pour la raison qu'il annonce.
