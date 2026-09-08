---
name: garde-agent-point-execution-reel
description: La passerelle des providers ne couvre pas tous les appels rf-mcp
type: projet
date: 2026-09-06
---

Le pont `run_keyword_in_context` des providers SAPFX ne constitue pas le point
de passage universel des appels `execute_step` du serveur rf-mcp.

**Pourquoi :** une proposition de garde placee ici aurait protege les lectures
d'etat tout en laissant l'execution ordinaire hors controle. Un nom de fonction
central ne prouve pas la couverture des chemins d'execution.

**Comment appliquer :** verifier chaque transport avant d'annoncer une barriere
globale. Le hook PreToolUse est une barriere d'hote, pas une autorisation SAP
serveur. Son chargement doit etre qualifie separement des tests du script.

**Complement, qualification du meme jour :** sur Claude Code CLI, les
evenements natifs PreToolUse (`--output-format stream-json
--include-hook-events`) montrent les deux branches, `ask` puis `deny`, sur un
canari reste inchange. Sous Copilot dans VS Code, une sonde de refus strict
jouee en nouvelle conversation a laisse passer l'ecriture : le chargement
n'y est pas prouve, et le canal Output « GitHub Copilot Chat Hooks » doit
etre lu pour une erreur de lancement de `python`, pas seulement pour
l'absence d'evenement. Deux faits de format expliquent le piege : VS Code
lit `.claude/settings.json` et honore la cle `env` d'un hook, Claude Code ne
documente pas cette cle. Un bloc `env` pose pour une sonde est donc un residu
invisible d'un cote et un refus global de l'autre, et le test de
configuration ne le voit pas (il relance le script sans l'environnement
configure). La preuve de restauration est le hash du fichier sans le bloc,
compare a une reference relevee AVANT la sonde.
