---
name: execute-step-cle-odata-argument-nomme
description: Via rf-mcp, un chemin OData dont la clé porte un `=` (`DraftUUID=guid'...'`) passé en dur dans les arguments d'execute_step est lu comme un argument nommé et l'appel est refusé ; construire le chemin dans une variable
type: projet
date: 2026-09-21
---

# Un `=` dans une clé OData devient un argument nommé pour `execute_step`

**Relevé le 2026-09-21**, deux fois (à l'exploration puis à la génération), en
pilotant un service draft-enabled par rf-mcp.

## Le fait

`execute_step` reçoit ses arguments en liste de chaînes et y reconnaît la
forme `nom=valeur`. Un chemin d'entité draft-enabled porte cette forme dans sa
clé : `...Product(Product='',DraftUUID=guid'0242...',IsActiveEntity=false)`.
Passé en dur, il est découpé : le keyword voit un argument nommé `DraftUUID`
et refuse (« expected 1 to 3 non-named arguments, got 0 », ou « got positional
argument after named arguments » selon la position du chemin).

## Ce qu'on en fait

- Construire le chemin dans une **variable** (`Evaluate` puis `${var}`) : la
  variable traverse intacte.
- Le refus est bruyant, donc sans danger ; le coût est le temps perdu à
  chercher un défaut du keyword.
- Une casse annexe avait été observée à l'exploration (registre de sessions
  API vidé pour le reste de la session après le refus). Elle ne s'est PAS
  reproduite à la génération, où plusieurs appels ont suivi le refus sans
  perdre la session : le piège d'argument est établi, la casse de registre
  reste à confirmer.
