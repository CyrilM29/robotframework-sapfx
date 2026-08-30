---
name: la-langue-peut-basculer-en-cours-de-run
description: 2026-08-30, la langue servie par une application est passée de fr-FR à en-US ENTRE DEUX PAGES du même run et du même contexte navigateur, avec un popover mêlant les deux langues ; la convention « jamais un texte localisé » ne protège pas d'une locale supposée stable, elle protège d'une locale qui bouge
metadata:
  type: project
---

Relevé pendant l'exploration du Demo Kit OpenUI5 : l'attribut de langue du
document valait `fr-FR` sur une page et `en-US` sur la suivante, dans le MÊME
contexte navigateur et le MÊME run, les libellés suivant la bascule. Un popover
a même été observé portant les deux langues à la fois. Aucun réglage n'avait
été touché. Sur la même cible, les en-têtes des tables de documentation restent
en anglais quelle que soit la langue de l'interface.

**Pourquoi :** on applique la règle « asserter le type, le code, la clé
technique, jamais le texte traduit » en imaginant une cible mono-langue dont on
ignore juste laquelle. La réalité est pire et plus banale : la langue est un
état négocié (préférence du navigateur, ressources chargées à la demande,
repli d'une traduction manquante, cache), donc elle peut changer PENDANT
l'exécution. Une campagne qui relève la langue au setup pour choisir ses
libellés attendus est fausse à partir de la page où ça bascule, et elle échoue
sur une assertion de texte, c'est-à-dire là où le diagnostic ressemble à une
dérive de localisateur.

**Comment appliquer :** ne jamais dériver un localisateur ni une assertion d'un
libellé, même relevé live au début du run. Les ancres qui tiennent sur une
interface UI5 sont la `key` technique d'une entrée de menu, d'un onglet ou
d'une rubrique, l'icône, le `type` d'un bouton de dialogue, la POSITION dans un
dialogue dont la structure a été vérifiée, et le nom qualifié d'une entité. La
langue, elle, se MESURE et se journalise (`Get Page Languages`) comme un fait
d'environnement, jamais comme une prémisse. Prolonge [[assertion-fiori-ni-trop-tot-ni-localisee]]
d'un cran : la localisation n'est pas seulement inconnue, elle est instable.
