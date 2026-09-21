---
name: commande-vente-epm-sepm-so
description: SEPM_SO existe et crée/supprime une commande de vente EPM réversible, cycle complet prouvé live
type: projet
date: 2026-09-18
---

La transaction `SEPM_SO` (programme `RS_EPM_SO_CLASSIC_DYNPRO`) existe sur
A4H et n'avait encore jamais été explorée dans ce dépôt (seule `SEPM_DG`, le
générateur de données de masse, était connue). Elle porte trois boutons
Create/Display/Delete sur son écran initial, un écran de saisie à deux
onglets (Header Data avec `Business Partner ID`, Items avec un table control
dont l'adressage de cellule est 0-INDEXÉ : `row=1` échoue par `com_error`
« invalid argument » sur une table à une seule ligne), et confirme chaque
action par un message de classe `SEPM_BOR_MESSAGES` dont le PARAMÈTRE porte
le numéro de commande créé/supprimé (`S/044` sauvegarde, `S/061`
suppression), jamais son texte localisé. Le numéro (10 chiffres) est
attribué par SAP à la sauvegarde, jamais choisi par le test : le cycle
créer → croiser par SE16 → supprimer est donc rejouable sans limite et sans
collision possible entre deux exécutions, y compris concurrentes. Le
croisement SE16 confirme la création (`SNWD_SO.LIFECYCLE_STATUS='N'` pour
une commande neuve, contre `'C'` pour les commandes de démonstration
livrées) et la suppression réelle (compte à 0 après Delete), vérifié deux
fois de suite en direct.

**Pourquoi** : une note de veille interne proposait ce scénario comme une
IDÉE de campagne future, jamais vérifiée live, à partir
d'un nom de transaction supposé par analogie avec `SEPM_DG`. La vérifier
d'abord (avant d'écrire un mot de test) a évité de fabriquer une suite pour
une transaction qui aurait pu ne jamais exister : elle existe bel et bien,
mais rien dans une note de veille ne le prouve tant qu'une session live ne
l'a pas confirmé.

**Comment appliquer** : avant de générer un test à partir d'une idée de
campagne (backlog, note de veille), relancer la transaction/l'écran visé en
direct et en isoler la structure RÉELLE (perception, table control, identité
de message) plutôt que de faire confiance au nom proposé. Le partenaire
commercial et le produit ne sont jamais choisis en dur : relus dans
`SNWD_BPA` (filtre `BP_ROLE=01`, jamais `02` = fournisseur) et `SNWD_PD` à
l'exécution, suite `tests/robot/ui/ecc/commande_vente_epm_order_to_cash.robot`.

Rappel utile trouvé en produisant cette suite : le marqueur de provenance
`Spec: ... (sha256:...)` d'une suite (12 hex, `check_spec_sync.py`, fins de
ligne normalisées LF) et l'empreinte d'un fichier de preuve dans un
`*.handoff.json` (64 hex, `agent_contract.py`, octets bruts du fichier) sont
deux schémas distincts, l'un tronqué et normalisant, l'autre entier et brut.

**Correction du 2026-09-21** : la conclusion qu'on en avait tirée, « ils sont
volontairement non comparables, ne pas s'étonner qu'ils diffèrent », était une
interprétation, et elle est fausse. Sur un fichier en LF les deux coïncident :
le marqueur est exactement le préfixe de 12 hex de l'empreinte du handoff
(vérifié sur les deux plans de ce lot). Ils ne divergeaient ce jour-là que
parce que le plan portait des CRLF locaux, qui ne survivent à aucun checkout
frais. C'était donc un symptôme à lire et non une propriété à admettre, et
il pointait le vrai défaut : une empreinte de handoff signée sur des CRLF est
verte sur le poste qui l'a signée et rouge partout ailleurs, CI comprise, sans
qu'aucun contenu n'ait bougé. Garde posé depuis (aucune preuve épinglée ne
porte de CRLF), cousin de [[baselines-visuelles-liees-a-la-resolution]] et de
[[echelle-de-rendu-et-localisateurs-humains]] : une empreinte qui encode le
POSTE au lieu du contenu. Leçon de méthode : une fiche qui explique un écart
par « c'est normal » mérite une mesure avant d'être écrite.
