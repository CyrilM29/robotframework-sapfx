"""Assemblage pur du **diagnostic Fiori agrégé** (`Get Fiori Diagnostics`).

Browser 20 expose séparément le log console (`Get Console Log`), les erreurs
JS non interceptées (`Get Page Errors`) et le snapshot ARIA (`Get Aria
Snapshot`) ; le projet a de son côté l'arbre UI5 (`Get Ui5 Page Tree`) et la
sonde de composition hybride (`Get Page Composition`). Sur un écran qui ne se
comporte pas comme attendu, l'information utile est la CONJONCTION de ces vues :
une erreur console explique souvent un arbre UI5 vide, la composition dit
quel moteur adresser à la place, l'ARIA couvre les zones non-SAP.

Ce module tient la partie pure de l'agrégation : normalisation des entrées
console/erreurs en dicts JSON-safe à forme stable, troncature explicite
(jamais silencieuse), synthèse d'anomalies **actionnable** (chaque problème
nomme le keyword ou le moteur qui débloque) et rapport Markdown pour le log
Robot. Les E/S Browser vivent dans le keyword (`SapFioriLibrary`). Typé.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

# Sections collectables par `Get Fiori Diagnostics`, dans l'ordre de rendu du
# rapport. La liste est la référence unique : le keyword valide contre elle.
VALID_SECTIONS = ("composition", "tree", "console", "errors", "aria")

# Types d'entrée console Playwright considérés comme anomalies.
_CONSOLE_ERROR_TYPES = frozenset({"error", "assert"})
_CONSOLE_WARNING_TYPES = frozenset({"warning", "warn"})


def parse_sections(sections: object) -> list[str]:
    """Valide et normalise le paramètre ``sections`` (chaîne ``a,b,c`` ou
    liste). Section inconnue = erreur listant les valides, jamais ignorée en
    silence (le contrat des presets IDP / du vocabulaire métier)."""
    if isinstance(sections, str):
        wanted = [part.strip().lower() for part in sections.split(",") if part.strip()]
    elif isinstance(sections, Sequence):
        wanted = [str(part).strip().lower() for part in sections]
    else:
        raise ValueError(
            "sections must be a comma-separated string or a list, got %r."
            % (sections,))
    unknown = [name for name in wanted if name not in VALID_SECTIONS]
    if unknown or not wanted:
        raise ValueError(
            "Unknown diagnostics section(s) %s. Valid sections: %s."
            % (", ".join(repr(name) for name in unknown) or "(none given)",
               ", ".join(VALID_SECTIONS)))
    # dédoublonne en préservant l'ordre canonique de VALID_SECTIONS
    return [name for name in VALID_SECTIONS if name in wanted]


def _location_to_str(location: object) -> str:
    """Compacte la localisation Playwright (``{url, lineNumber, columnNumber}``)
    en ``url:ligne:colonne``, une chaîne stable plutôt qu'un dict imbriqué."""
    if isinstance(location, Mapping):
        url = str(location.get("url", "") or "")
        line = location.get("lineNumber", "")
        column = location.get("columnNumber", "")
        if url or line != "" or column != "":
            return "%s:%s:%s" % (url, line, column)
        return ""
    return str(location or "")


def normalize_console_entries(entries: object) -> list[dict[str, str]]:
    """Normalise les entrées de `Get Console Log` (Browser) en dicts JSON-safe
    à forme stable ``{type, text, location, time}`` (chaînes partout). Une
    entrée inattendue (non-dict) devient ``type=log, text=str(entrée)`` :
    best-effort, un diagnostic ne doit jamais échouer sur sa propre matière."""
    normalized: list[dict[str, str]] = []
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        return normalized
    for entry in entries:
        if isinstance(entry, Mapping):
            normalized.append({
                "type": str(entry.get("type", "log") or "log").lower(),
                "text": str(entry.get("text", "") or ""),
                "location": _location_to_str(entry.get("location")),
                "time": str(entry.get("time", "") or ""),
            })
        else:
            normalized.append({"type": "log", "text": str(entry),
                               "location": "", "time": ""})
    return normalized


def normalize_page_errors(errors: object) -> list[dict[str, str]]:
    """Normalise les entrées de `Get Page Errors` (Browser) en dicts JSON-safe
    ``{name, message, stack, time}`` (chaînes partout, mêmes règles best-effort
    que :func:`normalize_console_entries`)."""
    normalized: list[dict[str, str]] = []
    if not isinstance(errors, Sequence) or isinstance(errors, (str, bytes)):
        return normalized
    for error in errors:
        if isinstance(error, Mapping):
            normalized.append({
                "name": str(error.get("name", "Error") or "Error"),
                "message": str(error.get("message", "") or ""),
                "stack": str(error.get("stack", "") or ""),
                "time": str(error.get("time", "") or ""),
            })
        else:
            normalized.append({"name": "Error", "message": str(error),
                               "stack": "", "time": ""})
    return normalized


def tail_entries(entries: list[dict[str, str]],
                 limit: int) -> tuple[list[dict[str, str]], int]:
    """Garde les ``limit`` DERNIÈRES entrées (les plus récentes, celles qui
    expliquent l'état courant) et retourne ``(gardées, nb_écartées)``. La
    troncature est toujours annoncée par l'appelant (pas de cap silencieux) ;
    ``limit <= 0`` = tout garder."""
    if limit <= 0 or len(entries) <= limit:
        return entries, 0
    return entries[-limit:], len(entries) - limit


def summarize_issues(diagnostics: Mapping[str, Any]) -> list[str]:
    """Synthèse **actionnable** du diagnostic assemblé : une ligne par anomalie,
    nommant à chaque fois la piste qui débloque (moteur recommandé, keyword de
    frame, section insondable). Liste vide = rien d'anormal détecté."""
    issues: list[str] = []
    page_errors = diagnostics.get("page_errors") or []
    if page_errors:
        first = page_errors[0]
        issues.append(
            "%d erreur(s) JS non interceptée(s), première : %s: %s"
            % (len(page_errors), first.get("name", "Error"),
               first.get("message", "")))
    console = diagnostics.get("console") or []
    errors = [e for e in console if e.get("type") in _CONSOLE_ERROR_TYPES]
    warnings = [e for e in console if e.get("type") in _CONSOLE_WARNING_TYPES]
    if errors:
        issues.append("%d erreur(s) console, première : %s"
                      % (len(errors), errors[0].get("text", "")))
    if warnings:
        issues.append("%d avertissement(s) console" % len(warnings))
    composition = diagnostics.get("composition")
    sections = diagnostics.get("sections") or []
    if "tree" in sections and not diagnostics.get("ui5_tree"):
        hint = ""
        if isinstance(composition, Mapping):
            engines = [e for e in composition.get("engines", [])
                       if e not in ("role", "xpath")]
            frames = composition.get("frames") or []
            if engines:
                hint = " ; moteurs recommandés sur cette portée : %s" % ", ".join(engines)
            if frames:
                hint += (" ; la page a %d iframe(s), l'app est peut-être dans "
                         "une frame (Set Ui5 Frame / Push Ui5 Frame)" % len(frames))
        issues.append("pas d'arbre UI5 sur la portée courante (registre vide "
                      "ou pas une app UI5)%s" % hint)
    for section, error in sorted((diagnostics.get("collection_errors") or {}).items()):
        issues.append("section '%s' insondable : %s" % (section, error))
    return issues


def render_diagnostics_report(diagnostics: Mapping[str, Any]) -> str:
    """Rapport Markdown du diagnostic : anomalies d'abord, puis chaque section
    collectée en résumé compact (le dict complet reste la donnée de travail ;
    le rapport est la vue humaine à coller dans le log Robot ou une issue)."""
    lines = ["# Diagnostic Fiori"]
    scope = diagnostics.get("frame_scope")
    context = [str(part) for part in (diagnostics.get("url"),
                                      diagnostics.get("title")) if part]
    if context:
        lines.append("- page : %s" % " · ".join(context))
    lines.append("- portée : %s" % (scope or "page principale"))
    issues = diagnostics.get("issues") or []
    lines.append("")
    if issues:
        lines.append("## Anomalies (%d)" % len(issues))
        lines += ["- %s" % issue for issue in issues]
    else:
        lines.append("## Anomalies : aucune détectée")
    lines.append("")
    composition = diagnostics.get("composition")
    if isinstance(composition, Mapping):
        frames = composition.get("frames") or []
        lines.append("## Composition")
        lines.append(
            "- runtime UI5 : %s%s · hôtes WC : %s · éléments WebGUI : %s · "
            "frameworks : %s · iframes : %d"
            % (composition.get("ui5_runtime"),
               " (%s)" % composition["ui5_version"]
               if composition.get("ui5_version") else "",
               composition.get("wc_hosts", 0),
               composition.get("webgui_elements", 0),
               ", ".join(composition.get("frameworks") or []) or "aucun",
               len(frames)))
        lines.append("- moteurs recommandés : %s"
                     % ", ".join(composition.get("engines") or []))
        lines.append("")
    tree = diagnostics.get("ui5_tree")
    if tree:
        lines += ["## Arbre UI5", "", "```xml", str(tree), "```", ""]
    for key, title, renderer in (
            ("console", "Console",
             lambda e: "[%s] %s" % (e.get("type"), e.get("text"))),
            ("page_errors", "Erreurs de page",
             lambda e: "%s: %s" % (e.get("name"), e.get("message")))):
        entries = diagnostics.get(key)
        if entries is None:
            continue
        dropped = int(diagnostics.get("%s_dropped" % key, 0) or 0)
        suffix = " (+%d plus ancienne(s) écartée(s))" % dropped if dropped else ""
        lines.append("## %s : %d entrée(s)%s" % (title, len(entries), suffix))
        lines += ["- %s" % renderer(entry) for entry in entries]
        lines.append("")
    aria = diagnostics.get("aria")
    if aria:
        lines += ["## Snapshot ARIA", "", "```yaml", str(aria).rstrip(), "```", ""]
    return "\n".join(lines).rstrip() + "\n"
