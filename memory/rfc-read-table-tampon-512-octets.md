---
name: rfc-read-table-tampon-512-octets
description: 2026-08-29, la ligne projetée de RFC_READ_TABLE est bornée à 512 octets et une projection CDPOS portant VALUE_NEW ET VALUE_OLD sort en DATA_BUFFER_EXCEEDED (AD/E/559), code qui ne nomme pas la cause ; et BP_JOBLOG_READ n'est pas appelable à distance, la voie externe du journal de job est la chaîne XBP
type: projet
date: 2026-08-29
---

En montant les lectures de preuves d'exploitation (documents de modification,
journal de job), deux refus du canal RFC ont coûté leur diagnostic.

**Le tampon de 512 octets.** `RFC_READ_TABLE` borne la ligne PROJETÉE (la
somme des largeurs des champs demandés) à 512 octets. Une projection CDPOS
portant `VALUE_NEW` ET `VALUE_OLD` (254 caractères chacun) dépasse et sort en
`DATA_BUFFER_EXCEEDED`, identifiant de message `AD/E/559`, dont le texte
(`CDPOS 512`) nomme la table et le plafond mais pas le remède.

**Pourquoi :** le code oriente vers « la table est trop large », alors que la
table n'y est pour rien : c'est la PROJECTION qui l'est, et elle se découpe.
Restreindre les champs ne suffit pas quand deux champs légitimes du besoin
dépassent à eux seuls le plafond.

**Comment appliquer :** lire en DEUX projections partageant la clé du poste
(`CHANGENR`, `TABNAME`, `TABKEY`, `FNAME`, `CHNGIND`), l'une avec la valeur
nouvelle, l'autre avec l'ancienne, et fusionner côté client ; une ligne vue
d'un seul côté garde l'autre valeur vide plutôt que de disparaître. Encodé
dans `Read Change Documents` (`sapfx_common.rfc_reads.merge_change_items`).

**Second enseignement de la même passe : `BP_JOBLOG_READ` n'est pas
remote-enabled.** Sur la cible (release 754), l'appel sort en
`CALL_FUNCTION_NOT_REMOTE`, quelle que soit la forme (nom TemSe ou
nom/numéro de job). La voie externe officielle est la chaîne **XBP** :
`BAPI_XMI_LOGON` (interface `XBP` 3.0), `BAPI_XBP_JOB_JOBLOG_READ` (table
`JOB_PROTOCOL`), et `BAPI_XMI_LOGOFF` exécuté MÊME sur échec : une session
XMI orpheline reste ouverte côté serveur, même hygiène que les connexions
([[rfc-champ-inexistant-accuse-la-table]] pour les autres refus classés).
