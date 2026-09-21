# Une garde qui ne tourne nulle part, et le récit unique qui couvre ses échecs

**Relevé le 2026-09-16**, en lançant à la main, pour la première fois depuis sa
mise en place, le contrôle d'intégrité des sidecars de mission du cycle
d'agents.

## Le fait

Le script existait, il était documenté dans le contrat d'agents, et il n'était
appelé **nulle part** : ni par la CI, ni par le hook de post-édition, ni par un
test. Au premier balayage réel, **trois sidecars sur six étaient invalides**.

Ce n'est pas le nombre qui compte, c'est la suite : les trois échouaient pour
**trois causes différentes**.

| Artefact | Cause réelle |
|---|---|
| A | une clé libre hors schéma (le schéma est fermé à dessein) |
| B | l'empreinte de la SUITE, éditée pendant le tour de corrections d'une revue puis jamais re-signée |
| C | l'empreinte du PLAN, annoté par l'agent générateur, dont le contrat lui impose justement de l'annoter |

## Le piège, et c'est lui qui vaut d'être retenu

Une explication unique et parfaitement plausible circulait : les artefacts de
preuve portent un horodatage, donc leur empreinte de fichier change à chaque
reconstruction, donc épingler cette empreinte est fragile par construction.
Le raisonnement est juste. **Il était faux sur les trois cas.** Mesuré : les
empreintes des preuves horodatées étaient toutes bonnes, personne ne les ayant
reconstruites.

Agir sur ce récit aurait changé le format de preuve de quatre campagnes, pour
ne réparer aucun des trois défauts. C'est le mode de panne d'un diagnostic
plausible : il est cohérent, il explique tout, et il ne touche rien.

La règle qui en sort : quand plusieurs artefacts du même genre tombent
ensemble après une longue absence de contrôle, **ne pas chercher LA cause**.
Les vérifier un par un, chacun avec sa cause nommée, avant toute théorie.

## Pourquoi personne ne l'avait réparé

Le script refusait par un message générique, du type « artefact invalide ou
illisible », sans jamais dire lequel des huit contrôles avait échoué. Diagnostiquer
les trois cas a demandé de réécrire la vérification à côté. Une garde qui ne
dit pas POURQUOI elle refuse est une garde que personne ne répare, même
quand elle tourne.

## Ce qu'on en fait

- Le refus NOMME sa cause (clé en trop, empreinte dérivée et sur quel fichier),
  et il nomme son remède.
- La garde sait BALAYER (`--all`) : un contrôle qui ne prend qu'un fichier à la
  fois ne peut pas devenir un garde de dépôt.
- Re-signer est un geste EXPLICITE (`--refresh`) qui affiche ce qui a dérivé.
  Une attestation qui se répare en silence n'atteste plus rien, mais sans
  affordance de re-signature, la garde devient infranchissable et finit
  désactivée.
- Deux sévérités, comme ailleurs ici : **bloquant** au repos (test unitaire,
  donc CI), **informatif** pendant une édition (hook), parce qu'en plein tour
  de génération le plan bouge avant que le sidecar ne soit ré-émis, et
  bloquer là-dessus arrêterait le cycle pour une dérive attendue.
- Un balayage vide ne vaut pas un balayage vert : le test exige qu'il existe au
  moins un sidecar, sinon il ne rougirait jamais faute de regarder quoi que ce
  soit (même mode de panne que [[gardes-qui-ne-peuvent-pas-echouer]]).

Voir aussi [[une-garde-qui-compare-deux-lectures-de-la-meme-source]] : là une
assertion ne pouvait pas échouer, ici une garde ne s'exécutait pas. Les deux
produisent le même silence, et le même faux sentiment de couverture.
