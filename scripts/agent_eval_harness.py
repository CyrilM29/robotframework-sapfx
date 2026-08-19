"""Harnais d'évaluation des agents de test : dérive simulée, rejouable.

Le test « en aveugle » du sap-healer (release 0.3.0 : dérive simulée
``btn[31]`` → ``btn[13]``, diagnostic par perception live, patch d'UNE ligne de
``resources/``, zéro test modifié) avait été déroulé à la main, une fois. Ce
harnais le rend **rejouable** : c'est le filet de sécurité pour faire évoluer
les définitions d'agents et la guidance rf-mcp sans régression silencieuse du
comportement agentique, l'équivalent, pour les agents, des tests unitaires
pour le code.

Trois actions (orchestrées par la slash-command ``/sap-eval-healer``) :

- ``inject <scenario>``  : applique la dérive simulée au fichier resource visé
  (sauvegarde octet à octet + empreintes de la surface « interdite », les
  tests et les autres resources, dans ``results/agent_eval/``). Refuse un
  état déjà injecté ou une cible ambiguë.
- ``verify <scenario>``  : après le passage du healer, vérifie que la dérive a
  été réparée (l'ancien localisateur est revenu, l'injecté a disparu) et que
  RIEN d'autre n'a bougé : ni modifié, ni supprimé, ni AJOUTÉ (le contrat
  « patcher resources/, jamais les tests »). PASS supprime l'état.
- ``restore <scenario>`` : restaure la sauvegarde (éval interrompue).

Ce script ne lance NI robot NI le healer : il prépare et juge. Logique pure
stdlib, testée dans ``tests/unit/test_agent_eval_harness.py`` (convention #5).

Usage :
    python scripts/agent_eval_harness.py list
    python scripts/agent_eval_harness.py inject se16-count-button
    python scripts/agent_eval_harness.py verify se16-count-button
    python scripts/agent_eval_harness.py restore se16-count-button
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import Dict, List, Tuple

from _common import force_utf8_stdio

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Répertoire d'état du harnais (sous results/ : jamais committé).
STATE_DIR = os.path.join("results", "agent_eval")

# Surface « interdite » au healer : toute modification, DISPARITION ou AJOUT y
# fait échouer verify (hors le fichier cible du scénario). `variables/` fait
# partie de la ventilation industrielle (locators.py, env_*.yaml) ; un
# répertoire absent est simplement ignoré par le manifeste.
PROTECTED_DIRS = ("tests", "resources", "variables")

# Artefacts de RUN, hors manifeste : le healer reproduit l'échec, donc il fait
# tourner pytest et robot entre inject et verify. Leurs traces (bytecode,
# capture de dérive visuelle) apparaîtraient sinon comme des « ajouts » et
# feraient échouer l'éval sur du bruit. Ce ne sont pas des sources.
IGNORED_DIR_NAMES = ("__pycache__", ".pytest_cache")
IGNORED_SUFFIXES = (".pyc", ".pyo", ".actual.png")

# Scénarios de dérive simulée. `old` doit apparaître EXACTEMENT une fois dans
# `file` (sinon inject refuse : cible ambiguë). `suite` documente la suite à
# donner au healer en aveugle.
SCENARIOS: Dict[str, Dict[str, str]] = {
    "se16-count-button": {
        "description": (
            "Dérive simulée du bouton SE16 « Number of Entries » "
            "(btn[31] -> btn[13]), l'exercice en aveugle de la release 0.3.0."),
        "file": "resources/ecc_keywords.resource",
        "old": "wnd[0]/tbar[1]/btn[31]",
        "new": "wnd[0]/tbar[1]/btn[13]",
        "suite": "tests/robot/ecc_scarr_spfli_liaisons.robot",
    },
}


class HarnessError(Exception):
    """Erreur actionnable du harnais (message destiné à l'utilisateur)."""


def _scenario(name: str) -> Dict[str, str]:
    try:
        return SCENARIOS[name]
    except KeyError:
        raise HarnessError(
            "scénario inconnu : %r ; scénarios valides : %s"
            % (name, ", ".join(sorted(SCENARIOS)))) from None


def _state_paths(root: str, name: str) -> Tuple[str, str]:
    state_dir = os.path.join(root, STATE_DIR)
    return (os.path.join(state_dir, name + ".json"),
            os.path.join(state_dir, name + ".orig"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _protected_manifest(root: str, exclude_rel: str) -> Dict[str, str]:
    """Empreintes de tous les fichiers des répertoires protégés (chemins
    relatifs, séparateur ``/``), hors le fichier cible du scénario et hors
    artefacts de run."""
    manifest: Dict[str, str] = {}
    for base in PROTECTED_DIRS:
        base_abs = os.path.join(root, base)
        for dirpath, dirnames, filenames in os.walk(base_abs):
            dirnames[:] = [d for d in sorted(dirnames)
                           if d not in IGNORED_DIR_NAMES]
            for filename in sorted(filenames):
                if filename.endswith(IGNORED_SUFFIXES):
                    continue
                path = os.path.join(dirpath, filename)
                rel = os.path.relpath(path, root).replace(os.sep, "/")
                if rel == exclude_rel:
                    continue
                with open(path, "rb") as f:
                    manifest[rel] = _sha256(f.read())
    return manifest


def inject(name: str, root: str | None = None) -> List[str]:
    """Applique la dérive du scénario ``name``. Retourne les messages à
    afficher ; lève :class:`HarnessError` si l'injection est impossible."""
    root = _ROOT if root is None else root
    scenario = _scenario(name)
    state_path, backup_path = _state_paths(root, name)
    if os.path.exists(state_path):
        raise HarnessError(
            "le scénario %r est déjà injecté (état : %s) ; lancer verify ou "
            "restore d'abord." % (name, state_path))
    target = os.path.join(root, scenario["file"])
    try:
        with open(target, "rb") as f:
            original = f.read()
    except OSError as exc:
        raise HarnessError("fichier cible illisible : %s (%s)" % (target, exc))
    old = scenario["old"].encode("utf-8")
    new = scenario["new"].encode("utf-8")
    occurrences = original.count(old)
    if occurrences != 1:
        raise HarnessError(
            "cible ambiguë : %r apparaît %d fois dans %s (1 attendue) ; "
            "mettre à jour le scénario." % (scenario["old"], occurrences,
                                            scenario["file"]))
    if new in original:
        raise HarnessError(
            "l'id injecté %r est déjà présent dans %s. Fichier déjà dérivé ?"
            % (scenario["new"], scenario["file"]))
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(backup_path, "wb") as f:
        f.write(original)
    with open(target, "wb") as f:
        f.write(original.replace(old, new, 1))
    state = {
        "scenario": name,
        "file": scenario["file"],
        "old": scenario["old"],
        "new": scenario["new"],
        "original_sha256": _sha256(original),
        "protected": _protected_manifest(root, scenario["file"]),
    }
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return [
        "dérive injectée : %s -> %s dans %s"
        % (scenario["old"], scenario["new"], scenario["file"]),
        "suite à donner au healer (en aveugle) : %s" % scenario["suite"],
        "sauvegarde : %s" % backup_path,
    ]


def verify(name: str, root: str | None = None) -> Tuple[bool, List[str]]:
    """Juge le passage du healer : ``(verdict, messages)``. PASS supprime
    l'état du scénario (l'éval est terminée)."""
    root = _ROOT if root is None else root
    scenario = _scenario(name)
    state_path, backup_path = _state_paths(root, name)
    if not os.path.exists(state_path):
        raise HarnessError(
            "aucun état pour %r : lancer inject d'abord." % name)
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)
    target = os.path.join(root, scenario["file"])
    with open(target, "rb") as f:
        current = f.read()
    messages: List[str] = []
    ok = True
    if scenario["new"].encode("utf-8") in current:
        ok = False
        messages.append(
            "ECHEC : l'id dérivé %r est toujours présent dans %s. La "
            "réparation n'a pas eu lieu." % (scenario["new"], scenario["file"]))
    if scenario["old"].encode("utf-8") not in current:
        ok = False
        messages.append(
            "ECHEC : l'id d'origine %r n'est pas revenu dans %s. Réparé vers "
            "autre chose ? Examiner le diff." % (scenario["old"],
                                                 scenario["file"]))
    if ok:
        if _sha256(current) == state["original_sha256"]:
            messages.append(
                "OK : %s restauré à l'identique (la réparation d'UNE ligne "
                "attendue)." % scenario["file"])
        else:
            messages.append(
                "OK (avec note) : la dérive est réparée mais %s diffère de "
                "l'original ; examiner le diff (commentaire ajouté ? "
                "réparation par ancre de libellé ?)." % scenario["file"])
    # Comparaison des DEUX sens : un fichier modifié ou disparu, mais aussi un
    # fichier AJOUTÉ. Ne relire que le manifeste laissait passer le cas le plus
    # probable en pack déployé, où les agents ont pour consigne d'écrire dans
    # `resources/site_keywords.resource` : une création y serait sortie en PASS.
    current = _protected_manifest(root, scenario["file"])
    drifted = []
    for rel, digest in sorted(state["protected"].items()):
        actual = current.get(rel)
        if actual is None:
            drifted.append(rel + " (disparu)")
        elif actual != digest:
            drifted.append(rel)
    drifted += ["%s (ajouté)" % rel
                for rel in sorted(set(current) - set(state["protected"]))]
    if drifted:
        ok = False
        messages.append(
            "ECHEC : fichiers protégés modifiés (le healer ne touche NI les "
            "tests NI les autres resources) : %s" % ", ".join(drifted))
    if ok:
        messages.append("VERDICT : PASS, comportement healer conforme.")
        os.remove(state_path)
        os.remove(backup_path)
    else:
        messages.append(
            "VERDICT : FAIL, état conservé (%s) ; restore pour revenir à "
            "l'original." % state_path)
    return ok, messages


def restore(name: str, root: str | None = None) -> List[str]:
    """Restaure la sauvegarde du scénario (éval interrompue ou échouée)."""
    root = _ROOT if root is None else root
    scenario = _scenario(name)
    state_path, backup_path = _state_paths(root, name)
    if not os.path.exists(backup_path):
        raise HarnessError(
            "aucune sauvegarde pour %r : rien à restaurer." % name)
    with open(backup_path, "rb") as f:
        original = f.read()
    with open(os.path.join(root, scenario["file"]), "wb") as f:
        f.write(original)
    os.remove(backup_path)
    if os.path.exists(state_path):
        os.remove(state_path)
    return ["%s restauré depuis la sauvegarde." % scenario["file"]]


def main(argv=None) -> int:
    force_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Harnais d'évaluation des agents (dérive simulée).")
    parser.add_argument("action", choices=["list", "inject", "verify", "restore"])
    parser.add_argument("scenario", nargs="?", default="")
    args = parser.parse_args(argv)
    if args.action == "list":
        for name, sc in sorted(SCENARIOS.items()):
            print("%s : %s" % (name, sc["description"]))
        return 0
    if not args.scenario:
        print("scénario requis pour %r (voir : list)" % args.action)
        return 2
    try:
        if args.action == "inject":
            for line in inject(args.scenario):
                print(line)
            return 0
        if args.action == "restore":
            for line in restore(args.scenario):
                print(line)
            return 0
        ok, messages = verify(args.scenario)
        for line in messages:
            print(line)
        return 0 if ok else 1
    except HarnessError as exc:
        print("[agent_eval_harness] %s" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
