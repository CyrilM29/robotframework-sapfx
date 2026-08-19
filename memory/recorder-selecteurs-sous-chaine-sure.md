# Recorder web : textes de sélecteur assainis, pas échappés

**Date : 2026-08-17.** Constat d'une revue de code complète, corrigé le jour
même.

## Le problème

Les VALEURS enregistrées (saisies, textes assertionnés) passaient bien par
`rfEscape`/`rfUnescape`, mais les textes embarqués dans les ARGUMENTS DE
SÉLECTEUR ne passaient par rien : la propriété du littéral
`properties={'text': '…'}` (moteur role), le `text=` du moteur wc, le `name=`
du moteur dom. Une apostrophe cassait le littéral Python, un `${` réveillait
une variable RF au replay, un run de 2+ espaces coupait la cellule.

## Pourquoi assainir plutôt qu'échapper

L'échappement aurait dû traverser TOUTE la chaîne de consommateurs (regex du
resource-first `properties=\{'[^']+': '([^']*)'\}`, parse du replay in-page,
round-trip d'import .robot) et l'inverse exact aurait dû être appliqué au bon
moment par chacun. Or les moteurs matchent par SOUS-CHAÎNE insensible à la
casse (`valueMatches`) : émettre le plus long segment SÛR du texte
(`safeMatchText` : espaces normalisés, découpe sur `'`, `\` et les amorces
`${`/`@{`/`&{`/`%{`) garde la sémantique de résolution sans toucher aucun
consommateur. Rien d'exploitable = dégradation en `controlType=` seul (le
repli xpath existe déjà). Même logique pour l'indice `# xpath:` : un xpath qui
casserait la ligne (saut de ligne, 2+ espaces) est OMIS, jamais émis corrompu
(`rfSafeCell`).

## La leçon générale

Quand un texte issu de la page doit entrer dans un format à métacaractères et
que le matching aval est par sous-chaîne, la sous-chaîne sûre est plus robuste
que l'échappement : zéro consommateur à synchroniser, zéro inverse à
appliquer.

## Correction du 2026-08-18 : la sous-chaîne sûre a deux angles morts

Une revue de code a montré que le raisonnement ci-dessus est bon mais avait
été appliqué trop largement. Trois défauts réels en découlaient :

1. **Tronquer peut RECIBLER en silence.** « Editor's Choice » devenait
   « s Choice », qui matche aussi « Boss Choice » ; la résolution role prend
   le PREMIER match (INFO au log, jamais d'échec). Un clic rejoué ailleurs
   sans bruit est pire qu'une ligne visiblement cassée. Corrigé en
   **choisissant le guillemet** du littéral Python (`properties={'text':
   "Editor's Choice"}`) au lieu de couper : `ast.literal_eval` gère nativement
   les guillemets mixtes, donc aucun consommateur à synchroniser, et le
   contrat « zéro échappement à inverser » est préservé.
2. **Assainir d'un côté sans normaliser de l'autre ne résout rien.**
   `safeMatchText` normalisait les blancs, mais le moteur **role** comparait
   la valeur BRUTE (`matchProps` n'appelait pas `wsCollapse`, contrairement
   aux moteurs wc et dom) : un texte contenant un saut de ligne produisait un
   sélecteur qui ne pouvait JAMAIS résoudre. La normalisation doit être des
   DEUX côtés, et le chemin regex garde la valeur brute.
3. **Une dégradation muette ment.** L'omission de l'indice `# xpath:` et la
   chute en `controlType=` seul se faisaient en silence : le step paraissait
   auto-réparable ou discriminant alors qu'il ne l'était plus. Les deux
   l'ANNONCENT désormais dans la ligne émise (sous un préfixe que l'export
   resource-first ne peut pas confondre avec un vrai localisateur).

Reste vrai : le **backslash** est le seul caractère qui impose encore la
troncature (Robot le consomme à la relecture de la cellule), et il fallait
l'ajouter au refus de `rfSafeCell` pour les xpath.

**La leçon corrigée :** « assainir plutôt qu'échapper » vaut tant que
l'assainissement ne change pas ce que le sélecteur DÉSIGNE. Dès qu'il peut
élargir la cible, préférer un encodage sans perte (ici : choisir le
guillemet), et si une dégradation reste inévitable, la rendre VISIBLE dans
l'artefact produit. Vérifier aussi la chaîne complète de bout en bout : ici
la ligne traverse DEUX déséchappements successifs (cellule Robot, puis
`ast.literal_eval`), ce qu'aucun grep du JS ni `--dryrun` ne voit, d'où le
test unitaire qui rejoue la chaîne réelle avec le vrai moteur Robot.
