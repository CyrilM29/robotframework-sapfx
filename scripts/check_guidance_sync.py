"""Vérifie que les hints de guidance rf-mcp
(``integrations/robotmcp/sap_robotmcp/_guidance.py``) restent alignés sur les
conventions numérotées de CLAUDE.md dont elles sont la traduction pour l'agent
(convention #1 « pas d'id brut / pas de DOM », #2 « jamais time.sleep »,
#3 « assertions indépendantes de la locale »).

Vérifie de la même façon que les définitions des agents de test
(``.claude/agents/sap-*.md`` — planner/generator/healer, déclinées en chat
modes VS Code par ``regen_agent_definitions.py``) continuent de porter ces
conventions vers les agents.

Ce n'est PAS un générateur : CLAUDE.md est de la prose libre destinée à des
lecteurs humains/IA, pas une donnée structurée — en extraire mécaniquement du
texte serait fragile et produirait des hints de piètre qualité. C'est un
garde-fou de COHÉRENCE, dans le même esprit que ``check_bilingual_docs.py`` et
``check_vendor_drift.py``. Pour chaque convention suivie, il vérifie :

1. Que le passage est encore présent dans CLAUDE.md tel quel (sinon la
   convention a été reformulée/déplacée : ce script doit être mis à jour, pas
   rester silencieux sur une correspondance qu'il ne peut plus établir) ;
2. Que le concept correspondant est toujours présent dans les hints de
   ``_guidance.py`` ;
3. Que chaque définition d'agent contient encore les marqueurs des conventions
   (``_AGENT_MARKERS``).

Vérifie enfin la **fraîcheur des cartes de keywords** des plugins rf-mcp
(``_MAP_MARKERS``) : chaque mixin « valeur ajoutée » des bibliothèques doit
garder au moins ses keywords phares dans la carte d'intention du plugin
correspondant (``get_keyword_library_map``). C'est le garde qui aurait attrapé
la dérive 0.5.6 → 0.6.1 : trois releases de keywords (multi-session, screenshot
annoté, effecteur pointer…) absents de la carte, donc invisibles au routage
d'intention des agents. Contrôle TEXTUEL (les plugins importent ``robotmcp``,
qu'on ne veut pas exiger ici) — un keyword renommé côté bibliothèque fera
échouer ce garde : mettre à jour la carte ET cette liste.

Usage : python scripts/check_guidance_sync.py
"""
import importlib.util
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CLAUDE_MD = os.path.join(_ROOT, "CLAUDE.md")
_GUIDANCE_PY = os.path.join(_ROOT, "integrations", "robotmcp", "sap_robotmcp", "_guidance.py")

# (n° de convention CLAUDE.md, passage attendu tel quel, jeu de hints concerné,
# mots-clés attendus -- en minuscules -- dans ce jeu de hints).
_TRACKED = [
    (1, "Tests contain no raw SAP ids / no CSS-XPath", "common",
     ["id sap brut"]),
    (1, "never DOM ids", "fiori",
     ["ids dom"]),
    (2, "Never `time.sleep` to wait for SAP", "common",
     ["time.sleep"]),
    (3, "Check status-bar message *type*", "ecc",
     ["type du message de barre d'état"]),
]

# Définitions d'agents de test : chaque fichier ``sap-*.md`` doit encore
# mentionner ces marqueurs (en minuscules) — la traduction des conventions #1
# (localisateurs dans la couche resources), #2 (pas d'attente fixe) et #3
# (assertions par type de message) pour les agents planner/generator/healer.
_AGENTS_DIR = os.path.join(_ROOT, ".claude", "agents")
_AGENT_MARKERS = [
    (1, "resources/"),
    (2, "time.sleep"),
    (3, "message type"),
]

# Fraîcheur des cartes de keywords des plugins rf-mcp : pour chaque mixin
# « valeur ajoutée », les keywords phares qui doivent apparaître (tels quels)
# dans le fichier du plugin. Étendre cette liste à CHAQUE nouveau mixin/moteur.
_PLUGINS_DIR = os.path.join(_ROOT, "integrations", "robotmcp", "sap_robotmcp")
_MAP_MARKERS = {
    "ecc_plugin.py": [
        # _connection.py / _sessions.py
        "Attach To Open Session", "Open Sap Session", "Create Gui Session",
        "Close All Sap Sessions",
        # _waits.py (réglage dynamique)
        "Set Default Timeout", "Set Poll Interval",
        # _perception.py (sémantique/annoté/visuel/sentinelle/fenêtres)
        "Get Open Windows", "Get Annotated Screenshot",
        "Screen Should Match Baseline", "Check Screen Against Watch",
        # _perception.py (carte numérotée + action par référence @N)
        "Get Screen Map", "Click Screen Ref",
        # _pointer.py
        "Click Element At Offset",
        # _semantic.py / _diagnostics.py
        "Lookup Business Term", "Client Security Should Be Hardened",
    ],
    "fiori_plugin.py": [
        # pile de frames + moteur dom + diagnostic (sessions hybrides)
        "Push Ui5 Frame", "Resolve Dom Element", "Get Page Composition",
        "Get Fiori Diagnostics",
        # navigation FLP / IDP / vocabulaire (ports playwright-praman)
        "Open Fiori App", "Log In Via Identity Provider", "Lookup Business Term",
        # parité visuelle + réglage dynamique
        "Ui5 Screen Should Match Baseline", "Set Ui5 Timeout",
        # carte numérotée + action par référence @N
        "Get Ui5 Page Map", "Click Ui5 Ref",
    ],
    "api_plugin.py": [
        # sessions par alias + introspection d'état (le canal sans écran)
        "Open Api Session", "Close All Api Sessions", "List Api Sessions",
        # OData v2/v4 + CSRF, RFC optionnel
        "Get Odata Count", "Post Odata", "Call Rfc",
    ],
}


def _load_guidance():
    """Charge ``_guidance.py`` par chemin, sans passer par le paquet
    ``sap_robotmcp`` (dont ``__init__.py`` importe les plugins, qui exigent
    ``sapfx_common``/``src`` sur le path) : ``_guidance.py`` lui-même n'a aucune
    dépendance externe, ce détour est donc inutile pour ce garde-fou."""
    spec = importlib.util.spec_from_file_location("_guidance", _GUIDANCE_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {
        "common": " ".join(module.COMMON_HINTS).lower(),
        "ecc": " ".join(module.ECC_HINTS + module.COMMON_HINTS).lower(),
        "fiori": " ".join(module.FIORI_HINTS + module.COMMON_HINTS).lower(),
    }


def check():
    """Retourne la liste des messages de problème (vide si tout est aligné)."""
    with open(_CLAUDE_MD, "r", encoding="utf-8") as f:
        claude_md = f.read()
    blobs = _load_guidance()

    problems = []
    for num, claude_anchor, which, keywords in _TRACKED:
        if claude_anchor not in claude_md:
            problems.append(
                "CLAUDE.md convention #%d : passage attendu introuvable (%r) -- "
                "reformulée/déplacée ? Mettre à jour scripts/check_guidance_sync.py."
                % (num, claude_anchor))
            continue
        for kw in keywords:
            if kw not in blobs[which]:
                problems.append(
                    "CLAUDE.md convention #%d toujours présente, mais les hints "
                    "%s de _guidance.py ne mentionnent plus %r -- la guidance "
                    "a-t-elle dérivé ?" % (num, which, kw))

    try:
        agent_files = sorted(
            name for name in os.listdir(_AGENTS_DIR)
            if name.startswith("sap-") and name.endswith(".md"))
    except OSError:
        agent_files = []
    if not agent_files:
        problems.append(
            "aucune définition d'agent sap-*.md sous %s -- déplacées/renommées ? "
            "Mettre à jour scripts/check_guidance_sync.py." % _AGENTS_DIR)
    for filename in agent_files:
        with open(os.path.join(_AGENTS_DIR, filename), "r", encoding="utf-8") as f:
            agent_text = f.read().lower()
        for num, marker in _AGENT_MARKERS:
            if marker not in agent_text:
                problems.append(
                    "convention #%d : la définition d'agent %s ne mentionne "
                    "plus %r -- a-t-elle dérivé ?" % (num, filename, marker))

    for plugin_file, keywords in _MAP_MARKERS.items():
        path = os.path.join(_PLUGINS_DIR, plugin_file)
        try:
            with open(path, "r", encoding="utf-8") as f:
                plugin_text = f.read()
        except OSError:
            problems.append(
                "plugin rf-mcp introuvable : %s -- déplacé/renommé ? Mettre à "
                "jour scripts/check_guidance_sync.py." % path)
            continue
        for kw in keywords:
            if kw not in plugin_text:
                problems.append(
                    "carte de keywords : %s ne mentionne plus %r -- keyword "
                    "renommé, ou carte en retard sur la bibliothèque ?"
                    % (plugin_file, kw))
    return problems


def main(argv=None):
    problems = check()
    if not problems:
        print("[check_guidance_sync] OK -- hints rf-mcp alignés sur CLAUDE.md.")
        return 0
    print("[check_guidance_sync] ECHEC :")
    for p in problems:
        print("  - %s" % p)
    return 1


if __name__ == "__main__":
    sys.exit(main())
