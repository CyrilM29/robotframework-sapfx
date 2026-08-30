# Un shell peut imbriquer ses Web Components les uns dans les autres

Relevé le 2026-08-26 sur un launchpad SAP Build Work Zone (cFLP, SAPUI5
1.151), en montant trois campagnes d'exploration.

## Le fait

La barre d'un shell cFLP rend des UI5 Web Components **DANS le shadow root
d'autres Web Components**. Mesuré sur la même page : **6 hôtes `ui5-*` en
light DOM, 16 en profondeur**, dont trois `ui5-button` qu'un
`document.querySelectorAll` ne peut pas atteindre.

C'est l'inverse de l'hypothèse sur laquelle le moteur `wc` avait été écrit,
et que la documentation énonçait encore : « le contenu applicatif reste dans
le light DOM via les slots, seuls les internals des composants vivent dans
les shadow roots ». Vrai d'une page de démonstration, faux d'un shell réel.

## Les trois conséquences pratiques

1. **Un scan qui s'arrête au light DOM sous-estime la page sans le dire.**
   Il ne rend pas d'erreur : il rend zéro, ce qui ressemble à un mauvais
   localisateur. Un moteur qui prétend voir les Web Components doit empiler
   les shadow roots ouverts dans ses portées de scan.
2. **Le chemin retourné doit joindre les frontières par un combinateur
   DESCENDANT** (l'espace), jamais par un enfant direct (`>`) : c'est la
   seule forme que le CSS de Playwright sait percer. Le chemin ressemble
   alors à `[id="hote"] div:nth-of-type(1) > ui5-button:nth-of-type(1)`,
   l'espace après l'ancre marquant le franchissement.
3. **Filtrer des candidats avec `matches()` ne suffit pas.** La méthode
   évalue les ancêtres dans l'ARBRE de l'élément : depuis un élément vivant
   dans un shadow root, les hôtes light-DOM ne sont pas des ancêtres, donc un
   chemin qui FRANCHIT une frontière (celui du point 2) ne matche jamais
   l'élément qu'il désigne. Symptôme : la même chaîne CSS rend 1
   correspondance via la bibliothèque Browser et 0 via un moteur maison. Le
   remède est une résolution segment par segment, chaque segment cherché dans
   le contexte courant ET dans les shadow roots qu'il contient.

## Deux corollaires relevés dans la même passe

- **Les tags composés mélangent les orthographes** : `ui5-shellbar` (collé),
  `ui5-side-navigation` (à tirets) et `ui5-shellbar-item` (MIXTE). Essayer
  seulement les deux formes extrêmes laisse un type court sans
  correspondance ; il faut générer toutes les combinaisons collé/tiret.
- **Les popups Web Components sont invisibles à `sap.m.InstanceManager`** :
  un menu utilisateur ouvert n'y figure pas. Leur témoin d'ouverture est la
  propriété `open` de l'hôte, et leurs entrées restent RENDUES menu fermé,
  donc ni un comptage ni une résolution ne distinguent ouvert de fermé.
  À filtrer par type et par technologie, jamais par identifiant : un tel
  popover remonte l'id de l'hôte INTERNE au shadow root, et un
  `controlType` portant le suffixe de scoping de l'application, jamais
  l'identifiant ushell qu'on croirait trouver.

Voir [[bundle-injecte-garde-a-vie-par-la-page]] pour l'autre piège de la
couche d'injection, et [[gardes-qui-ne-peuvent-pas-echouer]] pour la famille
d'erreurs dont relève le point 3 (une mesure qui rend zéro sans jamais
échouer).
