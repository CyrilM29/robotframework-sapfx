---
name: sap-gui-fournit-le-runtime-rfc
description: 2026-08-27, le client SAP GUI 8.00 installe déjà le runtime NW RFC dans System32, donc pyrfc se charge ET appelle sans le SDK sous licence ; la contrainte Python 3.10-3.12, elle, ne tombe pas
type: projet
date: 2026-08-27
---

Sur un poste porteur de **SAP GUI for Windows 8.00**, le canal RFC fonctionne
sans télécharger le SAP NW RFC SDK. Le composant « SAP NWRFC x64 Shared » du
client dépose `sapnwrfc.dll` (version relevée 7530.1116) ainsi que
`icudt50.dll`, `icuin50.dll` et `icuuc50.dll` dans `C:\Windows\System32`, où le
loader Windows les trouve sans `SAPNWRFC_HOME` ni entrée de `PATH`. Vérifié
jusqu'à l'appel RÉEL et pas seulement à l'import : `STFC_CONNECTION` a renvoyé
son écho et `RFC_READ_TABLE` a lu T000, à travers `Open Rfc Connection` et
`Call Rfc`, contre une ABAP Platform trial.

**Pourquoi :** la documentation du dépôt présentait le SDK comme un préalable
absolu, ce qui envoie chercher un S-user, une autorisation Software Download et
une note SAP avant d'avoir mesuré si le poste en avait besoin. Or sur un poste
de test SAP, SAP GUI est installé par définition : la question méritait d'être
posée dans l'autre sens. Un import réussi ne prouvant rien du protocole, seule
la connexion réelle tranche.

**Comment appliquer :** mesurer d'abord (installer `pyrfc` épinglé, importer,
puis passer un appel réel), et ne dérouler la procédure S-user que si la mesure
échoue ou si l'une des trois réserves s'applique : licence et support (cette DLL
est livrée pour le client SAP GUI, et un runner de CI qui ne l'a pas installé ne
l'a pas non plus), patch level subi (celui du client, une incompatibilité ne se
verrait qu'à l'usage), compilation depuis les sources sur Python 3.13 et au-delà
(elle exige les en-têtes du SDK, que le client n'embarque pas). Ne pas confondre
les deux contraintes : SAP GUI dispense du SDK, **pas** de l'interpréteur
3.10-3.12, aucune roue `pyrfc` précompilée n'existant au-delà de 3.12, et ce
choix se fait à la création du venv, jamais après.

Le provisionnement a suivi le même jour : `install-rfc.ps1 -UseSapGuiRuntime`
est le mode sans archive (aucune variable posée, il n'y a rien à désigner) et
`-CheckOnly` nomme désormais le runtime qui répond au lieu de déclarer le SDK
manquant sur un poste où le canal fonctionne. Le refus sans archive propose
cette sortie courte AVANT le portail S-user quand le poste peut la prendre :
c'est le message que lit d'abord quelqu'un qui n'a pas de S-user, et l'envoyer
vers un portail fermé pour lui était le vrai défaut.
