# Le shell du Demo Kit est passé aux Web Components en quatre jours, sans préavis

Observation datée : 2026-09-01, Demo Kit OpenUI5 public (`sdk.openui5.org`).

Entre le 2026-08-25 (dernier passage vert de la CI ui5-compat) et le
2026-09-01, le SDK est passé de 1.151.0 à 1.152.0 et le SHELL du Demo Kit
(barre, recherche globale, menu Options) est passé aux UI5 Web Components :
68 hôtes WC mesurés là où la campagne du 2026-08-30, validée 12/12, en
relevait 0. Aucun commit du dépôt entre les deux runs de CI : la cible seule
a bougé. Cinq tests du smoke et quatre scénarios de la campagne sont tombés
d'un coup.

Ce que la ré-exploration a établi, et qui borne la casse :

- les composants du shell sont ENCAPSULÉS dans des wrappers
  `sap.f.gen.ui5.webcomponents*` présents AU REGISTRE : les moteurs role et
  xpath continuent de les adresser, et les ids STABLES survivent
  (`searchControl`, `aboutMenuButton`, `aboutMenu`) ;
- ce qui casse est plus fin : un enfant disparu
  (`searchControl-searchField`), une propriété disparue (`key` des entrées de
  menu, la clé migrant dans le suffixe d'id `menuItem-<clé>`), une portée de
  containment déplacée (les suggestions ne sont pas DOM-contenues dans le
  popover WC, qui vit dans un shadow root : elles le sont dans le contrôle de
  recherche), et une pile de popups qui compte les couches d'implémentation
  (menu ouvert = 2 entrées, cascade = 3) ;
- le CONTENU des pages (arbre d'API, tables de doc, filtres, iframe
  d'échantillon) reste en UI5 classique : le `sap.m.SearchField` unique de la
  Référence API est devenu le nouveau point d'entrée du smoke des moteurs du
  registre.

Trois leçons durables :

- une cible publique dérive VITE : quatre jours entre une validation 12/12 et
  une migration de technologie du shell ; une campagne validée avant un
  changement de SDK se rejoue après, et la sentinelle de composition
  (`wc_hosts`) est ce qui a nommé la dérive du premier coup ;
- une assertion de composition est une sentinelle qui EXPIRE et se retourne :
  « zéro hôte WC » était la bonne assertion avant, « des hôtes WC présents »
  est la bonne après, et dans les deux cas l'écart signale un changement de
  cible, pas un défaut du produit ;
- sur un shell WC, l'ancre qui survit est l'ID STABLE posé par l'application
  (le suffixe `menuItem-<clé>` vaut l'ancienne propriété `key`) ; la
  propriété et le containment sont les premiers à bouger.

Voir aussi `bundle-injecte-garde-a-vie-par-la-page.md` (l'autre famille de
dérive web) et l'entrée du 2026-09-01 de `docs/heal-journal.md` (le détail de
la réparation).
