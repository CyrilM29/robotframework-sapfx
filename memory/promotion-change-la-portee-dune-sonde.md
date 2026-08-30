# Promouvoir une sonde inline change sa PORTÉE, en silence

Observation datée : 2026-08-29.

`Evaluate JavaScript ${None} <sonde>` s'évalue sur la PAGE, quelle que soit la
pile de frames de la bibliothèque web : le sélecteur `${None}` n'entre pas dans
la portée courante, il l'ignore. Un keyword de bibliothèque, lui, honore la pile
(`Set Ui5 Frame` / `Push Ui5 Frame`), comme tous ses voisins et comme sa
documentation l'annonce.

Promouvoir l'un en l'autre (convention #12) est donc un changement de
SÉMANTIQUE pour tous les appelants, et ce changement est muet. Mesuré sur
`List Page Iframes` : six appelants sur sept lisaient depuis le shell et n'ont
rien vu, le septième lisait après être entré dans l'iframe applicative, qui
n'imbrique aucune iframe, et recevait une liste VIDE au lieu d'une erreur.

Ce qui rend le cas traître : la liste vide est un résultat parfaitement
plausible, puisque « l'accueil ne porte aucune iframe » est justement une
assertion de la même campagne. L'échec ne dit donc pas « mauvaise portée », il
dit « aucune iframe », et le diagnostic part vers le launchpad au lieu du
scénario.

Règle : à chaque promotion d'une sonde inline, établir sur QUOI l'ancienne
s'évaluait, puis vérifier que la nouvelle voit la même chose depuis TOUS ses
appelants, pas seulement depuis celui qu'on a sous les yeux. Un keyword de page
object dont le nom dit « du shell » force la portée du shell et restaure la pile
sur tous les chemins (`TRY`/`FINALLY`), plutôt que de dépendre de l'endroit d'où
on l'appelle : une portée laissée ailleurs fait ensuite échouer le scénario sur
des contrôles pourtant présents.

Voir [[capacite-en-couche-robot-angle-sans-garde]] pour l'inventaire de cette
dette, et [[promotion-ne-doit-pas-tuer-la-surface-de-healing]] pour l'autre
effet de bord à surveiller à chaque promotion.
