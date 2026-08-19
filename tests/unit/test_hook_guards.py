"""Tests du hook post-édition (``scripts/hook_guards.py``).

C'était le seul script de ``scripts/`` sans test, et le seul à porter deux
bugs de sortie : sous Windows, le rapport d'un garde en échec arrivait en
mojibake sur ``stderr``, et la branche INFORMATIVE (dérive plan/suite) mourait
en ``UnicodeEncodeError`` sur ``stdout``, sur la flèche de son propre message.
Un hook qui plante au lieu d'informer est pire que pas de hook : les deux
régressions sont verrouillées ici.

La décision est testée sur un lanceur de gardes factice (les quatre branches,
sans dépôt jetable ni garde réellement en échec) ; l'encodage l'est en
sous-processus, seul endroit où l'encodage des flux standard est observable.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

import hook_guards as hook  # noqa: E402

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SCRIPTS = os.path.join(_ROOT, "scripts")


def _runner(failing=(), stdout="rapport"):
    """Lanceur factice : les scripts nommés dans ``failing`` sortent en 1.

    Retourne aussi la liste des appels, pour prouver qu'un garde NON pertinent
    n'est pas lancé (le hook tourne à chaque édition : ce qu'il ne lance pas
    compte autant que ce qu'il lance).
    """
    calls = []

    def run(script, *args):
        calls.append((script,) + args)
        code = 1 if script in failing else 0
        return subprocess.CompletedProcess(
            args=[script], returncode=code,
            stdout=stdout if code else "OK", stderr="")

    return run, calls


# --- les quatre branches de decide() ------------------------------------------

def test_fichier_hors_perimetre_ne_lance_que_le_garde_de_redaction():
    run, calls = _runner()
    code, err, out = hook.decide("e:/depot/src/module.py", run)
    assert (code, err, out) == (0, "", "")
    assert calls == [("check_no_em_dash.py", "e:/depot/src/module.py")]


def test_cadratin_detecte_est_bloquant_et_relaie_le_rapport():
    run, _ = _runner(failing=("check_no_em_dash.py",), stdout="a corriger")
    code, err, out = hook.decide("e:/depot/docs/x.md", run)
    assert code == 2
    assert "a corriger" in err
    assert out == ""


def test_version_perimee_dans_un_md_est_bloquante():
    run, calls = _runner(failing=("check_published_versions.py",))
    code, err, _ = hook.decide("e:/depot/README.md", run)
    assert code == 2
    assert "rapport" in err
    assert ("check_published_versions.py",) in calls


def test_le_garde_des_versions_ne_tourne_que_sur_les_documents():
    run, calls = _runner()
    hook.decide("e:/depot/tests/robot/x.robot", run)
    assert ("check_published_versions.py",) not in calls


def test_convention_violee_dans_un_artefact_surveille_est_bloquante():
    run, _ = _runner(failing=("check_conventions.py",), stdout="Sleep interdit")
    code, err, out = hook.decide("e:/depot/tests/robot/ui/ecc/x.robot", run)
    assert code == 2
    assert "Sleep interdit" in err
    assert out == ""


def test_derive_spec_suite_informe_sans_bloquer():
    run, _ = _runner(failing=("check_spec_sync.py",), stdout="suite PERIMEE")
    code, err, out = hook.decide("e:/depot/specs/plan.md", run)
    assert code == 0
    assert err == ""
    payload = json.loads(out)
    assert payload["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "suite PERIMEE" in payload["hookSpecificOutput"]["additionalContext"]
    # La flèche du message : c'est elle qui faisait planter le hook.
    assert "\u2194" in payload["systemMessage"]


def test_sans_chemin_de_fichier_les_gardes_de_redaction_sont_sautes():
    run, calls = _runner()
    code, _, _ = hook.decide("", run)
    assert code == 0
    assert calls == []


def test_les_chemins_windows_sont_normalises():
    run, calls = _runner()
    hook.decide(r"e:\depot\resources\page_objects\x.resource", run)
    assert ("check_conventions.py",) in calls


# --- encodage : les deux régressions Windows ----------------------------------

def _run_python(code, encoding):
    env = dict(os.environ, PYTHONIOENCODING=encoding)
    env.pop("PYTHONUTF8", None)
    return subprocess.run([sys.executable, "-X", "utf8=0", "-c", code],
                          capture_output=True, env=env, cwd=_ROOT)


_PRINT_ARROW = (
    "import sys; sys.path.insert(0, %r)\n"
    "%s"
    "print('derive plan \\u2194 suite')\n"
)


def test_sans_bascule_utf8_une_fleche_tue_le_processus_sous_cp1252():
    # Le témoin : c'est exactement ce que faisait le hook avant correction.
    result = _run_python(_PRINT_ARROW % (_SCRIPTS, ""), "cp1252")
    assert result.returncode != 0
    assert b"UnicodeEncodeError" in result.stderr


def test_la_bascule_utf8_fait_passer_la_fleche_sous_cp1252():
    result = _run_python(
        _PRINT_ARROW % (_SCRIPTS,
                        "from _common import force_utf8_stdio\nforce_utf8_stdio()\n"),
        "cp1252")
    assert result.returncode == 0
    assert "\u2194" in result.stdout.decode("utf-8")


def test_le_hook_reel_repond_sur_un_fichier_anodin():
    # Bout en bout : prouve le câblage (import de ``_common`` depuis
    # ``scripts/``, lecture du JSON d'entrée) sans dépendre d'un garde rouge.
    payload = json.dumps({"tool_input": {"file_path": "README.md"}}).encode()
    result = subprocess.run(
        [sys.executable, os.path.join(_SCRIPTS, "hook_guards.py")],
        input=payload, capture_output=True, cwd=_ROOT)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
