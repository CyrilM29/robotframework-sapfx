# Pièges relevés live

Chacun a coûté du temps de débogage sur un vrai système. Aucun ne se déduit du
code. Ils sont datés parce qu'une observation n'est pas un état permanent :
vérifier avant d'affirmer.

## Le motif commun : vert et faux

La famille d'incidents la plus coûteuse n'est pas le test rouge, c'est le test
VERT qui n'a rien mesuré. On la reconnaît à trois formes :

- **une absence prise pour une valeur** (un paramètre inconnu rendu comme une
  chaîne vide, une liste vide au lieu d'une erreur de portée) ;
- **un plafond pris pour un total** (une lecture bornée rend une liste
  d'apparence complète, dont les lignes sont corrélées par l'ordre physique) ;
- **une présence prise pour une disponibilité** (un contrôle au registre mais
  rendu à 0x0, un import qui réussit en rendant un module incomplet).

Devant un résultat plausible, se demander d'abord ce qui le rendrait plausible
ET faux.

## ECC et SAP GUI

- **SE16 rend une liste ABAP classique par défaut** (dynpro `SAPMSSY0/120`),
  sans AUCUN objet grille scriptable. Appeler `Use ALV Grid In Data Browser`
  une fois par utilisateur (réglage persistant) avant toute lecture de grille.
- **L'écran de sélection SE16 est GÉNÉRÉ au premier accès** (programme
  `/1BCDWB/DB<table>`) : la fin du « busy » ne garantit pas que l'écran est là.
  Attendre un champ de l'écran généré avant de cliquer. La génération peut
  aussi émettre un dialogue modal d'information, à détecter STRUCTURELLEMENT
  (fenêtre modale plus champ de message), jamais par son texte.
- **Les champs d'un écran de sélection sont POSITIONNELS** (`I<n>-LOW/HIGH`
  suit l'ordre des champs de la table) et le type de contrôle varie
  (`ctxtI2-LOW` contre `txtI3-LOW`) : sonder avec `Get Screen Signature` avant
  d'écrire un dictionnaire de critères. Au-delà de 40 champs, une popup de
  choix des champs apparaît, et ce choix PERSISTE par utilisateur.
- **`RowCount` d'un GuiTableControl compte les lignes RÉSERVÉES, pas remplies**
  (mesuré 47 annoncées, 26 remplies) : ne jamais dimensionner une boucle
  dessus. La scrollbar plafonne à `total - visible`, donc la dernière fenêtre
  recouvre la précédente et se lit à un index local décalé.
- **Une ALV peut être enveloppée dans des `GuiSplitterShell`**, à une
  profondeur qui VARIE par transaction : adresser le CONTRÔLE, jamais la mise
  en page.
- **Les listes ABAP modernes sont rendues dans un GuiShell opaque** tant que le
  mode accessibilité SAP GUI n'est pas actif. Ce mode ne s'active PAS depuis un
  test : c'est un réglage du poste, à provisionner et à CONSTATER.
- **Les menus dupliquent le texte des boutons de toolbar**, d'où l'exclusion
  des `GuiMenu` des cibles de `Click Button By Label`.
- **`Run Transaction` peut rapporter un succès avec un modal d'erreur ouvert**
  (cas SESSION_MANAGER) : percevoir l'écran avant de conclure, `Get Open
  Windows` tranche.
- **Fermer toute session ouverte, même sur échec** : une connexion orpheline
  décale les indices, et le prochain `Attach To Open Session` ou `--replay`
  saisit silencieusement la mauvaise session.
- **Les clés de noeud d'un TableTreeControl sont complétées à gauche**
  (`'         11'`) : une clé devinée sans son padding échoue par un `com_error`
  opaque.

## Fiori et web

- **Un contrôle au registre n'est pas un contrôle rendu.** Mesuré sur la
  recherche d'un shell FLP 1.71 : le premier clic crée le contrôle sans le
  rendre (champ ABSENT du DOM, bouton encore `visible=True`), le second l'ouvre
  vraiment. Le témoin est la SURFACE (rectangle non nul), et l'ouverture
  s'écrit idempotente.
- **`visible=true` peut mentir** sur un contrôle sans noeud DOM (relevé sur
  `homeBtn` d'un FLP 1.71).
- **Un cookie de session sans expiration est rendu daté de 1969** par la
  bibliothèque Browser (epoch moins un) : le prédicat correct est « aucune
  expiration FUTURE », sinon tous les cookies passent pour permanents et le
  test de perte de session est vert à l'envers.
- **Un identifiant d'iframe est un COMPTEUR** (`__container4` puis
  `__container5` dans la même session) : ne jamais l'ancrer.
- **La position des boutons d'un dialogue varie par release** : en UI5 1.120,
  un refus de navigation offre `[0] Copy` et `[1] Close`, donc acquitter en
  position 0 copie le message et laisse le dialogue ouvert.
- **Le premier chargement d'un FLP sur système froid peut dépasser deux
  minutes** (compilation côté serveur), et l'échec d'attente est alors honnête,
  pas une panne. Rejouer avant de conclure, comme pour le premier `$count` d'un
  service jamais sollicité.
- **Un hôte virtuel partagé peut vous envoyer sur le mauvais système** : un ICF
  qui redirige vers un nom d'hôte que DEUX conteneurs annoncent donne une
  perception parfaitement cohérente du mauvais système.
- **Une cible derrière un IdP répond 200 sur TOUTE route** avec sa page de
  connexion : détecter structurellement (corps HTML), jamais par texte.

## OData

- Le `+` comme espace dans une query est toléré par une Gateway v2 et REFUSÉ en
  400 par un service v4 : encoder l'espace en `%20`.
- Un service peut servir son `$metadata` en `Content-Encoding: gzip` SANS qu'un
  `Accept-Encoding` ait été envoyé, et les octets compressés atteignent alors
  le parseur XML, qui accuse le document là où le fautif est le transport.
- Un service draft-enabled ne rend ni le brouillon dans son `$count` ni dans
  une lecture ordinaire, et la clé d'un brouillon est COMPOSITE : un compte
  inchangé ne prouve donc AUCUN nettoyage, seule la disparition de l'entité
  identifiée tranche.
- Le `Location` annoncé à la création n'est pas toujours adressable.

## RFC

- **Un champ inexistant sort en `TABLE_WITHOUT_DATA`**, code qui accuse la
  TABLE d'être vide alors qu'elle est pleine : devant ce code, valider la liste
  de champs contre DD03L sur LA cible.
- **La ligne PROJETÉE est bornée à 512 octets** : deux champs légitimes de 254
  suffisent à sortir en `DATA_BUFFER_EXCEEDED`. Lire en deux projections
  partageant la clé et fusionner côté client.
- **Mot de passe faux et mandant inexistant partagent `RFC_LOGON_FAILURE`**, et
  sur certaines releases le texte est identique mot pour mot : un test ne peut
  qu'asserter l'indistinction.
- **`RFC_PING` répond par un dictionnaire VIDE** : seule l'absence d'exception
  fait foi. Et le champ `host` des attributs de connexion est le poste CLIENT,
  pas l'hôte SAP.
- **Le port du répartiteur est DÉRIVÉ du numéro d'instance** (3300 plus le
  numéro), ce qui oblige à un relais TCP local quand un conteneur publie ses
  ports décalés.
- Un même prix revient en chaîne `"666.00"` par `RFC_READ_TABLE` et en
  `Decimal('666.0000')` par une BAPI : convertir, jamais comparer les
  représentations.

## Identité de la cible

Ne se prouve **ni** par l'identifiant système, **ni** par le nom d'hôte
applicatif, **ni** par l'adresse IP : deux conteneurs d'un même poste peuvent
partager les deux premiers, et l'adresse a changé entre deux relevés du MÊME
système à un jour d'intervalle. Les ancres sont la RELEASE, le KERNEL et
l'inventaire des composants logiciels.

Corollaire de méthode : une campagne validée AVANT un durcissement de la
bibliothèque se REJOUE après, sinon le vert-et-faux survit à la correction qui
le visait.
