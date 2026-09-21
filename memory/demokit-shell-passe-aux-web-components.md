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

## Suite du 2026-09-16 : la réparation n'avait couvert qu'une suite sur deux

Quinze jours plus tard, un rejeu de TOUTES les suites du dépôt a trouvé
`exploratory_campaign_fiori.robot` rouge 6 sur 6, sans qu'une ligne du dépôt
ait bougé entre-temps. Elle visait encore l'ACCUEIL et son `sap.m.SearchField`,
c'est-à-dire exactement la dérive réparée le 2026-09-01 sur `fiori_smoke.robot`.
Mesuré ce jour-là sur la 1.152.0 : **zéro** `sap.m.SearchField` sur l'accueil
(la recherche y est un `ShellBarSearch` de Web Component), **un** sur `#/api`,
où les six types attendus par la campagne sont tous rendus. Le correctif est
donc le même, une URL, et la suite repasse 6/6 sur trois exécutions, balayage
dynamique compris (44 types découverts, wrappers WC inclus, tous convergents
entre les moteurs role et xpath).

**Ce qui vaut d'être retenu n'est pas le localisateur, c'est le périmètre du
correctif.** Réparer la suite qui a rougi ne suffit pas : il faut chercher
toutes celles qui visent la MÊME cible avec le MÊME contrôle. Ici la seconde
était une campagne exploratoire auto-suffisante, validée une fois en juillet et
jamais rejouée, donc structurellement invisible : aucune CI ne la joue (cible
publique, navigateur visible par défaut), et rien ne signale une suite qui
dort. Deux réflexes en découlent : au moment de corriger une dérive de cible,
`grep` l'URL et le contrôle dans TOUT `tests/robot/`, et rejouer périodiquement
les suites que la CI ne joue pas, sans quoi leur dernier verdict vieillit en
silence.

Voir aussi `bundle-injecte-garde-a-vie-par-la-page.md` (l'autre famille de
dérive web) et l'entrée du 2026-09-01 de `docs/heal-journal.md` (le détail de
la réparation).
