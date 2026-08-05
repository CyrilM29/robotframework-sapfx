> [🇬🇧 English](PRIVACY.md) · **🇫🇷 Français**

# Politique de confidentialité : SAP UI5 / WebGUI Locator Recorder

_Dernière mise à jour : 2026-06-26_

Cette extension est un outil de développement qui aide à capturer des localisateurs de
test UI5/WebGUI stables et à enregistrer des déroulés d'actions sur la page consultée.

## Données traitées

- **Le contenu de la page que vous ciblez.** Quand vous démarrez le recorder et
  survolez/cliquez des contrôles, l'extension lit les métadonnées des contrôles (type,
  propriétés, ids) et les valeurs que vous saisissez, pour construire des lignes de
  keywords Robot Framework. Tout se passe **entièrement dans votre navigateur**.
- **Les champs password ne sont jamais capturés en clair.** Les steps `Fill Ui5
  Input` / `Fill Sid Input` enregistrés pour un champ `type="password"` notent
  `<REDACTED>` comme valeur (le localisateur du champ, id/xpath/sid, reste
  enregistré, donc le step reste exploitable une fois une vraie valeur injectée à
  la main).

## L'indicateur d'enregistrement est purement indicatif

- Le badge de la barre d'outils et le point d'enregistrement dans le panneau
  reflètent un signal d'état émis par le script recorder injecté dans la page.
  Ce signal transitant par un événement DOM que les scripts de la page hôte
  peuvent aussi observer et déclencher, un script de page compromis ou malveillant
  pourrait en principe le falsifier (afficher « pas d'enregistrement » alors que
  c'est actif, ou l'inverse). Cela n'a aucun impact sur les données capturées ni
  sur leur destination (toujours nulle part ailleurs que votre machine), mais ne
  traitez pas ce badge comme une garantie infalsifiable : c'est un indicateur de
  confort, pas une frontière de sécurité.

## Ce qu'elle en fait

- Les lignes de localisateurs/steps générées sont **copiées dans le presse-papiers**,
  affichées dans un panneau intégré, **enregistrées dans le `sessionStorage` de la
  page** (pour qu'un enregistrement survive à un rechargement), et, à l'**Export**,
  **téléchargées en fichier `.robot`** sur votre ordinateur.
- **Rien n'est envoyé où que ce soit.** L'extension n'a **aucun serveur, aucune
  analytique, aucune télémétrie, ni requête réseau propre.** Aucune donnée ne quitte
  votre machine.

## Permissions

- `activeTab` + `scripting` : injectent le recorder dans l'onglet **uniquement quand
  vous cliquez sur l'icône ou utilisez le raccourci**. **Aucune permission d'hôte** :
  l'extension ne peut pas accéder à des sites sur lesquels vous n'agissez pas
  explicitement.

## Conservation

- L'extension ne conserve rien de façon persistante de son côté. Le `sessionStorage` est
  vidé par le navigateur à la fin de l'onglet/session, ou par le bouton **clear** du
  panneau. Les fichiers `.robot` téléchargés résident sur votre ordinateur, sous votre
  contrôle.

## Contact

Questions : ouvrez une issue sur le dépôt du projet.
