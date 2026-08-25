# L'iframe d'application d'un launchpad n'a pas d'identifiant stable

**2026-08-23, premier pilotage d'un VRAI cFLP** (SAP Build Work Zone sur un
trial BTP, avec sa nouvelle barre shell), après des mois où la pile de frames
n'avait été éprouvée que contre `shell_iframe_fixture.html` et
`shell_multi_iframe_fixture.html`, écrites en imaginant ce que fait un
launchpad.

La chaîne complète a fonctionné du premier coup : login sur un IAS réel par
`Log In Via Identity Provider` (preset `sap-ias`, alors que le tenant présente
un formulaire en UNE page là où la fixture en a deux), navigation par intent,
détection de l'iframe, descente dedans, 844 contrôles perçus dans
l'application contre 84 pour le shell.

Le seul défaut trouvé était dans la DOCUMENTATION et dans l'usage :

```
run 1   iframe id = __container1
run 2   iframe id = __container4
run 3   iframe id = __container3      même page, même application
```

`__containerN` est un identifiant **généré** par UI5, dont le compteur dépend
du nombre de composants instanciés depuis le chargement. Et la docstring de
`Set Ui5 Frame` donnait pour exemple `iframe[id*="application"]`, motif qui ne
correspond à AUCUNE iframe du launchpad actuel : un utilisateur suivant notre
documentation échouait.

**Pourquoi :** une fixture fige ce que son auteur a imaginé. J'avais donné à mes
iframes des identifiants lisibles, parce qu'un humain qui écrit un fixture
nomme les choses. Le vrai launchpad ne nomme rien, il numérote. L'erreur n'est
pas d'avoir mal deviné : c'est d'avoir cru qu'une hypothèse écrite par soi-même
pouvait servir de preuve.

**Comment appliquer :** `Get Ui5 App Frame` désigne la frame par ce qu'elle EST
(visible, chargeant un document, occupant la plus grande surface, donc la zone
de contenu du shell) et rend un sélecteur positionnel `iframe >> nth=N` ;
`Push Ui5 App Frame` l'empile directement. Logique pure dans
`_ui5_runtime.choose_app_frame`, testée hors navigateur. Ne jamais écrire un
identifiant de conteneur UI5 dans un test.

**Complément du 2026-08-24**, deux campagnes plus tard, sur la même cible. Le
compteur bouge aussi À L'INTÉRIEUR d'une session (`__container4` puis
`__container5` sur deux runs consécutifs). Et surtout : entrer dans l'iframe ne
veut pas dire que l'application a DÉMARRÉ. La frame existe, sa portée est déjà
utilisable, et une perception immédiate rapporte `ui5_controls: 0` sur une
application parfaitement saine. Le pilotage interactif ne montre jamais cet
état, chaque tour d'agent laissant passer des secondes ; une suite, elle, tombe
dedans au premier run. Le mot-clé d'entrée attend donc le premier contrôle
construit, puis le repos réseau réel.

Deux constats annexes du même run, à ne pas perdre. La nouvelle barre shell de
Work Zone est en **Web Components** (`wc_hosts: 7` sur le shell, `engines`
proposant `wc` au niveau supérieur et pas dans la frame) : le moteur `wc`,
écrit pour les pages SuccessFactors sans runtime UI5, sert au launchpad
d'avenir de SAP. Et l'iframe de l'application est créée **après** le retour de
`Open App By Intent` : une perception immédiate ne voit que le shell et
rapporte `frames: []`, ce que j'ai d'abord pris pour une cécité de la sonde.
Voir aussi [[alv-enveloppee-dans-un-splitter-en-2023]], même leçon sur l'autre
canal : adresser l'identité, jamais la mise en page.
