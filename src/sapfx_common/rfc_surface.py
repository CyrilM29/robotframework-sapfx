"""Surface du canal RFC : artefact déterministe et comparaison de deux cibles.

Logique pure (aucune E/S, aucun réseau) du besoin que la campagne RFC
multi-release a fait apparaître (spec ``specs/canal-rfc-abap2023.md``,
scénario 9) : « quels modules fonction ici et pas là-bas » ne se répond pas
par une note dans un document, mais par un relevé produit sur CHAQUE cible et
comparé hors système. Le dépôt possédait déjà ce patron pour l'inventaire du
dictionnaire (``ddic_inventory``) et pour le croisement entre canaux
(``cross_channel``) ; le canal RFC ne l'avait pas.

Deux propriétés sont délibérées, et ce sont elles qui rendent la comparaison
honnête :

* **Un artefact porte l'identité de la cible qui l'a produit** (release,
  kernel, base, système). Sans elle, comparer deux artefacts revient à
  comparer deux inconnues, et le relevé live qui fonde ce module dit pourquoi :
  les deux conteneurs du poste portent le MÊME identifiant système et le MÊME
  nom d'hôte applicatif, seules la release et la liste des composants les
  distinguent.
* **Un artefact porte son périmètre**, c'est-à-dire l'ensemble des mesures
  relevées. Comparer deux cibles dont les périmètres diffèrent est REFUSÉ
  (marqué non probant), jamais moyenné : une mesure absente d'un côté ne vaut
  pas zéro.

Les lectures (``TFDIR``, ``TADIR``, ``CVERS``, volumétries) vivent dans la
couche resource du canal, et l'écriture du fichier dans le keyword.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = 1

#: Les clés d'identité qu'un artefact conserve, dans cet ordre. Elles sont
#: TOUTES optionnelles à la lecture (une cible peut ne pas les publier), mais
#: aucune autre n'entre : un artefact n'est pas un fourre-tout, et l'adresse
#: IP en est absente à dessein (mesurée volatile, elle change au redémarrage
#: d'un conteneur et ne prouve donc rien le lendemain).
IDENTITY_KEYS = (
    "system_id",
    "client",
    "release",
    "kernel",
    "database",
    "operating_system",
    "host",
)

#: Les clés d'une entrée de composant logiciel.
COMPONENT_KEYS = ("name", "release", "support_level")


def _text(value: Any) -> str:
    """Une valeur rendue en texte épuré (jamais ``None`` dans un artefact)."""
    return "" if value is None else str(value).strip()


def normalize_identity(identity: Mapping[str, Any] | None) -> dict[str, str]:
    """L'identité d'une cible, restreinte à `IDENTITY_KEYS` et rendue en texte.

    Une clé inconnue est REFUSÉE plutôt qu'ignorée : elle signale soit une
    faute de frappe, soit une valeur qu'on croit comparer alors qu'elle ne
    sera jamais relue. Les clés admises mais absentes valent la chaîne vide.
    """
    provided = dict(identity or {})
    unknown = sorted(set(provided) - set(IDENTITY_KEYS))
    if unknown:
        raise ValueError(
            "Clé d'identité inconnue : %s. Clés admises : %s."
            % (", ".join(unknown), ", ".join(IDENTITY_KEYS)))
    return {key: _text(provided.get(key)) for key in IDENTITY_KEYS}


def normalize_measures(measures: Mapping[str, Any] | None) -> dict[str, int]:
    """Les mesures de surface, validées comme des ENTIERS positifs.

    Un relevé de surface est un décompte : une valeur non entière (une chaîne
    de la lecture de table oubliée telle quelle, un ``None`` d'une sonde qui a
    échoué) doit être refusée à l'écriture plutôt que comparée plus tard. Un
    périmètre vide est refusé aussi : un artefact sans mesure ne compare rien.
    """
    provided = dict(measures or {})
    if not provided:
        raise ValueError(
            "Périmètre vide : un artefact de surface exige au moins une mesure.")
    normalized: dict[str, int] = {}
    for raw_name, raw_value in provided.items():
        name = _text(raw_name)
        if not name:
            raise ValueError("Nom de mesure vide dans le périmètre.")
        try:
            number = int(str(raw_value).strip())
        except (TypeError, ValueError):
            raise ValueError(
                "La mesure %r doit être un entier, reçu %r." % (name, raw_value))
        if number < 0:
            raise ValueError(
                "La mesure %r doit être positive, reçu %d." % (name, number))
        normalized[name] = number
    return normalized


def normalize_components(
    components: Iterable[Mapping[str, Any]] | None,
) -> list[dict[str, str]]:
    """L'inventaire des composants logiciels, trié par nom et dédoublonné.

    Chaque entrée porte ``name``, ``release`` et ``support_level`` (clés
    métier : la traduction depuis les noms techniques de la table appartient à
    la couche resource, convention n°1). Un composant sans nom est refusé, un
    nom répété avec deux releases différentes aussi : un inventaire ambigu
    produirait une comparaison qui dépend de l'ordre de lecture.
    """
    entries: dict[str, dict[str, str]] = {}
    for raw in components or []:
        entry = {key: _text(dict(raw).get(key)) for key in COMPONENT_KEYS}
        if not entry["name"]:
            raise ValueError("Composant logiciel sans nom dans l'inventaire.")
        previous = entries.get(entry["name"])
        if previous is not None and previous != entry:
            raise ValueError(
                "Le composant %r apparaît deux fois avec des valeurs "
                "différentes (%r puis %r)."
                % (entry["name"], previous, entry))
        entries[entry["name"]] = entry
    return [entries[name] for name in sorted(entries)]


def build_surface(
    target_id: str,
    identity: Mapping[str, Any] | None,
    measures: Mapping[str, Any],
    observed_at_utc: str,
    components: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble l'artefact de surface d'UNE cible.

    Le périmètre (``scope.measures``) est DÉRIVÉ des mesures fournies, jamais
    déclaré à part : les deux ne peuvent donc pas diverger. ``observed_at_utc``
    est fourni par l'appelant, ce module restant pur et rejouable.
    """
    normalized_measures = normalize_measures(measures)
    normalized_components = normalize_components(components)
    return {
        "schema_version": SCHEMA_VERSION,
        "target_id": _text(target_id),
        "observed_at_utc": _text(observed_at_utc),
        "identity": normalize_identity(identity),
        "scope": {"measures": sorted(normalized_measures)},
        "summary": {
            "measures": len(normalized_measures),
            "components": len(normalized_components),
        },
        "measures": normalized_measures,
        "components": normalized_components,
    }


def surface_json(surface: Mapping[str, Any]) -> str:
    """Sérialisation déterministe : clés triées, indentation fixe, fins LF."""
    return json.dumps(surface, ensure_ascii=False, indent=2,
                      sort_keys=True) + "\n"


def comparison_hash(surface: Mapping[str, Any]) -> str:
    """SHA-256 de l'artefact HORS horodatage.

    Deux exécutions sur la même cible, lisant les mêmes chiffres, produisent
    le même hash quel que soit le moment du relevé : ``observed_at_utc`` est
    exclu explicitement, tout le reste compte, l'identité comprise.
    """
    stripped = {key: value for key, value in surface.items()
                if key != "observed_at_utc"}
    return hashlib.sha256(surface_json(stripped).encode("utf-8")).hexdigest()


def _identity_differences(a: Mapping[str, Any],
                          b: Mapping[str, Any]) -> list[dict[str, str]]:
    """Les clés d'identité qui diffèrent entre deux artefacts.

    Informatif et NON bloquant : deux cibles distinctes DOIVENT différer ici,
    c'est précisément ce qu'on veut lire. C'est l'inverse qui mérite un
    regard, deux artefacts d'identité identique censés venir de cibles
    différentes.
    """
    return [{"key": key, "a": _text(a.get(key)), "b": _text(b.get(key))}
            for key in IDENTITY_KEYS
            if _text(a.get(key)) != _text(b.get(key))]


def compare_surfaces(surface_a: Mapping[str, Any],
                     surface_b: Mapping[str, Any]) -> dict[str, Any]:
    """Compare deux artefacts de surface, hors système.

    Retour JSON-safe. Le périmètre est une PORTE : deux artefacts dont les
    ensembles de mesures diffèrent sont marqués non comparables
    (``compatible=False``) et seules les mesures communes sont chiffrées, ce
    qui évite de présenter comme un écart ce qui n'est qu'une absence de
    relevé. Les composants logiciels sont rendus dans les trois catégories que
    le plan demande : présents des deux côtés, propres à la première cible,
    propres à la seconde, avec les changements de release des communs.
    """
    if surface_a.get("schema_version") != surface_b.get("schema_version"):
        raise ValueError(
            "schema_version différent : comparaison impossible (%r vs %r)."
            % (surface_a.get("schema_version"), surface_b.get("schema_version")))
    measures_a = dict(surface_a.get("measures", {}))
    measures_b = dict(surface_b.get("measures", {}))
    only_measures_a = sorted(set(measures_a) - set(measures_b))
    only_measures_b = sorted(set(measures_b) - set(measures_a))
    reasons = []
    if only_measures_a or only_measures_b:
        reasons.append(
            "périmètres de mesure différents (propres à A : %s ; propres à B : %s)"
            % (", ".join(only_measures_a) or "aucune",
               ", ".join(only_measures_b) or "aucune"))
    measure_diff = []
    for name in sorted(set(measures_a) & set(measures_b)):
        value_a, value_b = int(measures_a[name]), int(measures_b[name])
        if value_a != value_b:
            measure_diff.append({"measure": name, "a": value_a, "b": value_b,
                                 "delta": value_b - value_a})
    components_a = {entry["name"]: entry
                    for entry in surface_a.get("components", [])}
    components_b = {entry["name"]: entry
                    for entry in surface_b.get("components", [])}
    common = sorted(set(components_a) & set(components_b))
    release_changed = [
        {"name": name,
         "a": _text(components_a[name].get("release")),
         "b": _text(components_b[name].get("release"))}
        for name in common
        if _text(components_a[name].get("release"))
        != _text(components_b[name].get("release"))]
    return {
        "compatible": not reasons,
        "incompatibility_reasons": reasons,
        "target_a": _text(surface_a.get("target_id")),
        "target_b": _text(surface_b.get("target_id")),
        "identity_differences": _identity_differences(
            surface_a.get("identity", {}), surface_b.get("identity", {})),
        "measures_only_in_a": only_measures_a,
        "measures_only_in_b": only_measures_b,
        "measure_differences": measure_diff,
        "components_common": common,
        "components_only_in_a": sorted(set(components_a) - set(components_b)),
        "components_only_in_b": sorted(set(components_b) - set(components_a)),
        "component_release_changed": release_changed,
    }


def render_surface_report(comparison: Mapping[str, Any]) -> str:
    """Rapport Markdown d'une comparaison de surfaces, lisible hors SAP."""
    lines = [
        "# Comparaison de surfaces du canal RFC",
        "",
        "Cibles : `%s` vs `%s`." % (comparison["target_a"],
                                    comparison["target_b"]),
    ]
    if not comparison["compatible"]:
        lines += ["", "**Périmètres non équivalents, comparaison non probante :**"]
        lines += ["- %s" % reason
                  for reason in comparison["incompatibility_reasons"]]
    lines += ["", "## Identité"]
    differences = comparison["identity_differences"]
    if differences:
        lines += ["- `%s` : %s -> %s" % (d["key"], d["a"] or "(vide)",
                                         d["b"] or "(vide)")
                  for d in differences]
    else:
        lines.append("- identités identiques sur toutes les clés relevées")
    lines += ["", "## Mesures"]
    diffs = comparison["measure_differences"]
    if diffs:
        lines += ["- `%s` : %d -> %d (%+d)" % (d["measure"], d["a"], d["b"],
                                               d["delta"]) for d in diffs]
    else:
        lines.append("- aucune mesure commune ne diffère")
    lines += ["", "## Composants logiciels",
              "- communs : %d" % len(comparison["components_common"])]
    for key, label in (("components_only_in_a", "propres à A"),
                       ("components_only_in_b", "propres à B")):
        names = comparison[key]
        lines.append("- %s : %d%s" % (label, len(names),
                                      " (%s)" % ", ".join(names) if names else ""))
    changed = comparison["component_release_changed"]
    lines.append("- releases changées : %d" % len(changed))
    lines += ["  - `%s` : %s -> %s" % (c["name"], c["a"], c["b"])
              for c in changed]
    return "\n".join(lines) + "\n"
