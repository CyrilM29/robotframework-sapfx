# Une annotation OData déclarée n'est pas une annotation permissive

**2026-08-22, campagne de croisement ECC ↔ API.** Une garde qui qualifie les
entity sets ouverts à l'écriture, à partir des seules annotations `sap:` du
`$metadata`, a été écrite fausse **deux fois dans la même passe**. Les deux
versions étaient vertes, et la seconde erreur n'a été vue qu'en confrontant le
verdict à une cible réelle.

## Premier défaut : la garde était posée au niveau du SERVICE

Raisonnement initial : un service qui n'annote aucune restriction rend toutes
ses capacités vraies par défaut, donc ne prouve rien. La garde demandait donc
« ce service déclare-t-il des restrictions ».

Mesuré : un service de démonstration déclare bien une restriction, sur **un**
de ses seize entity sets, tout en restant muet sur quatre autres. La garde
était donc verte pour le document entier, et les quatre entity sets muets
remontaient comme candidats à l'écriture. Un service n'est pas une unité de
déclaration : chaque entity set l'est.

## Second défaut : compter la PRÉSENCE de l'annotation, pas sa VALEUR

Une fois la garde descendue au niveau de l'entity set, elle demandait « ce
verbe est-il déclaré ». Or `sap:creatable="false"` **est** déclaré, et
interdit.

La forme réellement rencontrée sur la cible : un entity set déclare
`sap:creatable="false"` et `sap:deletable="false"`, et se tait sur `updatable`.
Il a donc des capacités déclarées, mais la seule qu'il **autorise** vient du
silence. Les deux seuls candidats retenus par la campagne étaient exactement
dans ce cas : deux fiches dont pas une capacité n'était appuyée.

Le critère juste croise les deux ensembles : un verbe n'engage que s'il est à
la fois **autorisé** et **déclaré**. Corrigé, le compte de candidats sur cette
cible tombe de deux à **zéro**. C'est le résultat honnête, et il vaut mieux que
deux pistes d'écriture que rien ne soutient.

## Ce qui généralise

- Trois valeurs distinctes à ne jamais confondre dans un contrat de
  métadonnées : l'effectif (défaut appliqué), le déclaré (l'attribut est
  présent), et le déclaré-permissif (présent ET vrai). Le nom `declared`
  employé pour le deuxième invitait à le lire comme le troisième.
- Le silence d'un fournisseur vaut permission par défaut, donc une capacité
  obtenue par défaut est un critère **nécessaire, jamais suffisant**.
- Une garde qui ne peut pas rendre « aucun candidat » est suspecte : c'est le
  verdict vide qui prouve qu'elle mord. Voir [[gardes-qui-ne-peuvent-pas-echouer]].
- Le contre-exemple utile ne vient pas de la fixture, il vient de la cible :
  les deux fixtures écrites à la main passaient, seule la mesure live a montré
  la forme fautive.

Fait voisin, même campagne : [[correspondance-entity-set-table-non-deductible]].
