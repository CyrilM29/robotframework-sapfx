# La surface d'écriture des deux cibles ABAP, mesurée

**2026-09-17, étude des capacités d'écriture, sondes en lecture seule sur les
deux conteneurs** (dictionnaire, répertoire des modules fonction, catalogue
Gateway v2, métadonnées v4). Trois faits qu'aucune campagne n'avait posés
côte à côte, et qui décident où une écriture de test est possible.

## Par l'écran, le dictionnaire décide, table par table

`DD02L.MAINFLAG` est identique sur les deux releases : toutes les tables du
modèle de vol sont maintenables par SE16 SAUF `SCUSTOM` ; le cœur métier EPM
(`SNWD_PD`, `SNWD_SO`, `SNWD_PO`, `SNWD_BPA`...) ne l'est pas, seules 15
tables EPM annexes le sont (dont `SNWD_PD_CATGOS`, la cible déjà validée) ;
aucune table `/DMO/*` ne l'est (11 sur la 754, 47 sur la 758). Le cycle
d'écriture par l'écran validé sur la 754 est donc rejouable sur la 758 sans
changer de table.

## Par RFC, le même catalogue de BAPI, et l'API RAP héritée fermée

Mêmes 78 modules activés RFC sur les deux releases, dont 41 à verbe
d'écriture : création et suppression EPM (produit, partenaire, commande,
demande de congé), réservation de vol (`CREATEFROMDATA` / `CANCEL`), voyage
(`CREATE` / `CANCEL`), et les BAPI utilisateur. Le client de vol se crée sans
BAPI de suppression (non réversible). Les modules `/DMO/FLIGHT_TRAVEL_*`
existent mais ne sont PAS remote : le modèle RAP ne s'écrit que par OData.

## Par OData, rien n'est déclaré permissif et beaucoup est silencieux

Sur les deux Gateway, AUCUN entity set ne déclare une capacité d'écriture
vraie (la règle stricte du dépôt rend zéro candidat, comme le 2026-08-22).
Les sets écrivables par DÉFAUT sont pourtant nombreux (avis et panier de la
boutique EPM, brouillons produit et commande, `GWSAMPLE_BASIC` en CRUD
complet, bindings RAP locaux), et un function import de remise à zéro de
masse existe (`RegenerateAllData`) : silencieux ne veut dire ni accepté ni
anodin, chaque set se prouve par un cycle créer-lire-supprimer.

La 758 est la seule cible « moderne » : sept services RAP en v2 (managed
avec brouillon, managed sans brouillon, unmanaged, Web API, approbateur) et
cinq bindings v4 tous draft-enabled, qui RÉPONDENT bien que le catalogue v4
ne soit pas publié. Un `$metadata` v4 demandé en JSON reçoit un 406, ce qui
ressemble à un service absent et n'en est pas un : le demander en XML.

**Comment appliquer :** avant de concevoir un cycle d'écriture, lire
`MAINFLAG` (écran), `TFDIR.FMODE` (RFC) et les sets silencieux du
`$metadata` (OData) sur LA cible, puis prouver le set retenu par un cycle
réversible ; ne jamais extrapoler d'une release à l'autre, même quand les
comptes coïncident. Voir [[table-lisible-nest-pas-table-ecrivable]] et
[[annotation-odata-declaree-non-permissive]].
