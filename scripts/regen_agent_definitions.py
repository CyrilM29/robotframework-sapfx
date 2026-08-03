"""Décline les définitions d'agents SAP (source canonique :
``.claude/agents/sap-*.md``, format subagent Claude Code) en chat modes GitHub
Copilot pour VS Code (``.github/chatmodes/<name>.chatmode.md``).

Même esprit que ``SapFioriLibrary.regen_recorder`` : une source unique, des
cibles GÉNÉRÉES (jamais éditées à la main), et un mode ``--check`` façon
``check_bilingual_docs.py`` qui vérifie que les cibles committées correspondent
encore à la source. Le corps (les instructions de l'agent) est copié tel quel —
seul le frontmatter change de dialecte :

- Claude Code : ``name``/``description``/``tools``, outils MCP nommés
  ``mcp__<serveur>__<outil>`` ;
- VS Code / Copilot : ``description``/``tools`` en formes **qualifiées** —
  ``jeu/outil`` pour les builtins (``search/readFile``, ``edit/editFiles``…)
  et ``<serveur-mcp>/<outil>`` pour les outils MCP — le dialecte qu'émet le
  générateur de référence de Playwright
  (``packages/playwright/src/agents/generateAgents.ts``), granularité
  par outil préservée.

Usage ::

    python scripts/regen_agent_definitions.py           # (ré)écrit .github/chatmodes/
    python scripts/regen_agent_definitions.py --check   # vérifie sans écrire (CI)
"""
import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# Outils Claude Code -> outils qualifiés VS Code / Copilot (agent mode), même
# dialecte que le generateAgents.ts de Playwright (`vscodeToolMap`). Un outil
# absent de cette table fait échouer la génération (fail loud) : l'ajouter ici
# (et à VSCODE_TOOLS_ORDER) en même temps qu'on l'ajoute au frontmatter d'un
# agent. `runCommands` n'a pas de forme qualifiée de référence (Playwright
# n'émet aucun outil shell) : l'alias de jeu historique reste valide.
TOOL_MAP = {
    "Read": ["search/readFile"],
    "Glob": ["search/fileSearch"],
    "Grep": ["search/textSearch"],
    "Write": ["edit/createFile", "edit/createDirectory"],
    "Edit": ["edit/editFiles"],
    "Bash": ["runCommands"],
    "PowerShell": ["runCommands"],
}

# Ordre d'émission des builtins (calqué sur `vscodeToolsOrder` de Playwright,
# + runCommands en dernier) ; les outils MCP suivent, dans leur ordre
# d'apparition dans la source.
VSCODE_TOOLS_ORDER = [
    "edit/createFile",
    "edit/createDirectory",
    "edit/editFiles",
    "search/fileSearch",
    "search/textSearch",
    "search/listDirectory",
    "search/readFile",
    "runCommands",
]

_BANNER = (
    "<!-- FICHIER GÉNÉRÉ — ne pas éditer. Source : {source} ;\n"
    "     régénérer : python scripts/regen_agent_definitions.py -->"
)


def _read_text(path):
    """Lit un fichier texte en normalisant les fins de ligne (checkout CRLF
    possible sur les runners Windows) : la comparaison ``--check`` et le parse
    du frontmatter raisonnent toujours en ``\\n``."""
    return Path(path).read_text(encoding="utf-8").replace("\r\n", "\n")


def parse_front_matter(text):
    """Sépare ``(méta, corps)`` d'un markdown à frontmatter YAML *plat*
    (``clé: valeur`` par ligne — le seul dialecte utilisé par nos agents)."""
    if not text.startswith("---\n"):
        raise ValueError("missing front matter (expected leading '---')")
    try:
        end = text.index("\n---\n", 4)
    except ValueError:
        raise ValueError("unterminated front matter (no closing '---')") from None
    meta = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError("front matter line without ':': %r" % line)
        meta[key.strip()] = value.strip()
    return meta, text[end + len("\n---\n"):]


def map_tools(tools_value):
    """Traduit la liste d'outils Claude Code (chaîne ``A, B, C``) en outils
    qualifiés VS Code : builtins dédupliqués puis triés selon
    ``VSCODE_TOOLS_ORDER``, suivis des outils MCP (``<serveur>/<outil>``)
    dans leur ordre d'apparition."""
    builtins = []
    mcp = []
    for tool in (item.strip() for item in tools_value.split(",")):
        if not tool:
            continue
        if tool.startswith("mcp__"):
            parts = tool.split("__")
            if len(parts) < 3 or not parts[1] or not parts[2]:
                raise ValueError("unrecognized MCP tool name: %r" % tool)
            mcp.append(parts[1] + "/" + "__".join(parts[2:]))
        elif tool in TOOL_MAP:
            builtins.extend(TOOL_MAP[tool])
        else:
            raise ValueError(
                "no VS Code mapping for tool %r -- extend TOOL_MAP in "
                "scripts/regen_agent_definitions.py" % tool)
    ordered = sorted(
        dict.fromkeys(builtins),
        key=lambda t: (VSCODE_TOOLS_ORDER.index(t)
                       if t in VSCODE_TOOLS_ORDER else len(VSCODE_TOOLS_ORDER)))
    return ordered + list(dict.fromkeys(mcp))


def render_chatmode(source_rel, meta, body):
    """Rend un chat mode VS Code depuis (méta, corps) d'une définition Claude
    Code. Les valeurs du frontmatter sont sérialisées en JSON — sous-ensemble
    de YAML — pour un échappement correct sans dépendance."""
    for required in ("description", "tools"):
        if required not in meta:
            raise ValueError("front matter of %s lacks %r" % (source_rel, required))
    front = "---\ndescription: %s\ntools: %s\n---\n" % (
        json.dumps(meta["description"], ensure_ascii=False),
        json.dumps(map_tools(meta["tools"]), ensure_ascii=False))
    return front + "\n" + _BANNER.format(source=source_rel) + "\n" + body


def iter_renders(root):
    """Liste des couples ``(cible, contenu rendu)`` pour chaque source
    ``.claude/agents/sap-*.md``, triée (sortie déterministe)."""
    root = Path(root)
    agents_dir = root / ".claude" / "agents"
    sources = sorted(agents_dir.glob("sap-*.md"))
    if not sources:
        raise FileNotFoundError("no agent definition found under %s" % agents_dir)
    renders = []
    for src in sources:
        meta, body = parse_front_matter(_read_text(src))
        name = meta.get("name", src.stem)
        source_rel = src.relative_to(root).as_posix()
        dest = root / ".github" / "chatmodes" / (name + ".chatmode.md")
        renders.append((dest, render_chatmode(source_rel, meta, body)))
    return renders


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true",
        help="vérifie que les chat modes committés correspondent à la source (CI)")
    parser.add_argument("--root", default=str(_ROOT), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    renders = iter_renders(args.root)
    if args.check:
        problems = []
        for dest, content in renders:
            if not dest.is_file():
                problems.append("chat mode manquant : %s" % dest)
            elif _read_text(dest) != content:
                problems.append("chat mode obsolète : %s" % dest)
        if problems:
            print("[regen_agent_definitions] ECHEC :")
            for problem in problems:
                print("  - %s" % problem)
            print("  -> régénérer : python scripts/regen_agent_definitions.py")
            return 1
        print("[regen_agent_definitions] OK -- chat modes alignés sur .claude/agents/.")
        return 0

    for dest, content in renders:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8", newline="\n")
        print("écrit : %s" % dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
