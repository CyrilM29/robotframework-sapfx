"""Tests hors-SAP de l'assembleur du pack de déploiement
(``scripts/build_release_pack.py``, convention #5 du CLAUDE.md, appliquée à un
script d'outillage). Aucun wheel n'est construit ici : on teste la logique pure
(version, exclusions, manifeste, zip) sur des arborescences factices."""
import importlib.util
import os
import re
import zipfile

import pytest

_SCRIPT_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "build_release_pack.py"))
_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load():
    spec = importlib.util.spec_from_file_location("build_release_pack", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


# --- read_version ---------------------------------------------------------------

def test_read_version_reads_project_section():
    text = '[project]\nname = "x"\nversion = "1.2.3"\n'
    assert mod.read_version(text) == "1.2.3"


def test_read_version_ignores_other_sections():
    # Un `version = "9.9"` hors [project] (ex. config d'outil) ne doit pas gagner.
    text = '[tool.autre]\nversion = "9.9"\n[project]\nversion = "0.1.0"\n'
    assert mod.read_version(text) == "0.1.0"


def test_read_version_missing_raises():
    with pytest.raises(ValueError):
        mod.read_version('[project]\nname = "x"\n')


def test_read_version_on_real_pyproject():
    with open(os.path.join(_REPO_ROOT, "pyproject.toml"), encoding="utf-8") as handle:
        version = mod.read_version(handle.read())
    assert version and version[0].isdigit()


# --- autonomie des scripts embarqués --------------------------------------------

def test_les_scripts_embarques_n_importent_que_des_modules_autonomes():
    """Les scripts de maintenance du pack doivent tourner SEULS depuis sa
    racine : aucun ne peut dépendre d'un voisin de ``scripts/`` **resté au
    dépôt**.

    La règle était « aucun import d'un voisin de ``scripts/`` », ce qui
    interdisait aussi l'import d'un voisin embarqué : trop fort. Depuis la revue
    packaging du 2026-08-19, le pack livre ``check_conventions.py`` (la gate que
    la définition de sap-generator lance) et donc son socle ``_common.py`` : la
    propriété réellement exigée est que la clôture des imports internes soit
    entièrement dans le pack. Les deux scripts de maintenance historiques
    gardent, eux, leur copie en ligne du bloc de bascule UTF-8, ce qui les rend
    utilisables même sortis seuls du pack.
    """
    import ast

    scripts_dir = os.path.join(_REPO_ROOT, "scripts")
    embarques = [src for src, _ in mod.PACK_FILES
                 if src.startswith("scripts/") and src.endswith(".py")]
    assert embarques, "le pack n'embarque plus aucun script de maintenance"
    for src in embarques:
        with open(os.path.join(_REPO_ROOT, src), encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            for name in names:
                voisin = "scripts/%s.py" % name
                if not os.path.isfile(os.path.join(scripts_dir, name + ".py")):
                    continue          # module stdlib ou tiers : hors sujet
                assert voisin in embarques, (
                    "%s importe %r, qui vit dans scripts/ et n'est PAS "
                    "embarqué : le script ne tournerait pas dans le pack"
                    % (src, name))


# --- stale_wheels ---------------------------------------------------------------

def _wheels(tmp_path, *names):
    for name in names:
        (tmp_path / name).write_bytes(b"PK")
    return tmp_path


def test_stale_wheels_accepte_les_wheels_de_la_version_du_pack(tmp_path):
    _wheels(tmp_path, "robotframework_sapfx-0.6.6-py3-none-any.whl",
            "sap_robotmcp-0.6.6-py3-none-any.whl")
    assert mod.stale_wheels(tmp_path, "0.6.6") == []


def test_stale_wheels_denonce_un_wheel_d_une_autre_version(tmp_path):
    # Régression : `--skip-wheels` réutilise wheels/ tel quel, un wheel de la
    # release précédente partait dans un ZIP nommé d'après la version courante.
    _wheels(tmp_path, "robotframework_sapfx-0.6.5-py3-none-any.whl",
            "sap_robotmcp-0.6.6-py3-none-any.whl")
    assert mod.stale_wheels(tmp_path, "0.6.6") == [
        "robotframework_sapfx-0.6.5-py3-none-any.whl"]


def test_stale_wheels_accepte_une_post_release(tmp_path):
    _wheels(tmp_path, "robotframework_sapfx-0.6.6.post1-py3-none-any.whl")
    assert mod.stale_wheels(tmp_path, "0.6.6.post1") == []
    assert mod.stale_wheels(tmp_path, "0.6.6") == [
        "robotframework_sapfx-0.6.6.post1-py3-none-any.whl"]


# --- is_excluded ----------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "__pycache__/x.py",
    "extension/__pycache__/gen.pyc",
    "captures/shot1.png",
    "extension/dist/pack.zip",
    "extension/store/screenshot.png",
    "module.pyc",
])
def test_is_excluded_true(path):
    assert mod.is_excluded(path)


@pytest.mark.parametrize("path", [
    "sapgui_recorder.py",
    "extension/manifest.json",
    "extension/recorder.js",
    "README.fr.md",
])
def test_is_excluded_false(path):
    assert not mod.is_excluded(path)


# --- build_manifest -------------------------------------------------------------

def _fake_repo(tmp_path):
    """Reproduit la forme minimale du dépôt attendue par le manifeste."""
    for rel, _dest in mod.PACK_FILES:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("contenu", encoding="utf-8")
    for tree, _dest in mod.PACK_TREES:
        (tmp_path / tree).mkdir(parents=True, exist_ok=True)
    (tmp_path / "resources" / "ecc_keywords.resource").write_text("k", encoding="utf-8")
    (tmp_path / "tools/recorder/sapgui_recorder.py").write_text("py", encoding="utf-8")
    # Pollution qui doit être filtrée.
    (tmp_path / "tools/recorder/__pycache__").mkdir()
    (tmp_path / "tools/recorder/__pycache__/x.pyc").write_text("x", encoding="utf-8")
    (tmp_path / "tools/recorder_web/captures").mkdir()
    (tmp_path / "tools/recorder_web/captures/shot.png").write_text("x", encoding="utf-8")
    return tmp_path


def test_build_manifest_includes_expected_and_filters_pollution(tmp_path):
    repo = _fake_repo(tmp_path)
    dests = [dest.as_posix() for _src, dest in mod.build_manifest(repo)]
    assert "README.md" in dests                      # packaging/README.md renommé à la racine
    assert "recorder.cmd" in dests
    assert "resources/ecc_keywords.resource" in dests
    assert "tools/recorder/sapgui_recorder.py" in dests
    assert not any("__pycache__" in dest for dest in dests)
    assert not any("captures" in dest for dest in dests)
    assert dests == sorted(dests)                    # déterministe (zip reproductible)


def test_build_manifest_missing_file_raises(tmp_path):
    repo = _fake_repo(tmp_path)
    (repo / "packaging" / "install.ps1").unlink()
    with pytest.raises(FileNotFoundError):
        mod.build_manifest(repo)


def test_build_manifest_on_real_repo_covers_the_three_deliverables():
    """Le vrai dépôt doit produire un manifeste couvrant bibliothèques (via wheels,
    hors manifeste), recorders, plugins MCP (config) et keywords métier."""
    dests = [dest.as_posix() for _src, dest in mod.build_manifest(_REPO_ROOT)]
    assert "tools/recorder/recorder_gui.py" in dests
    assert "tools/recorder_web/recorder_snippet.js" in dests
    assert "tools/recorder_web/extension/manifest.json" in dests
    assert "mcp.json.template" in dests
    assert "vscode-mcp.json.template" in dests
    assert "resources/fiori_keywords.resource" in dests
    assert "tests/robot/fiori_smoke.robot" in dests
    assert "tests/robot/fiori_wc_smoke.robot" in dests
    assert "tests/robot/fixtures/wc_fixture.html" in dests
    # Sentinelle + flagship (0.5.0) : la veille sans tests et la démonstration
    # écran <-> API font partie des suites d'exemple livrées.
    assert "tests/robot/ecc_drift_sentinel.robot" in dests
    assert "tests/robot/flagship_cross_paradigm.robot" in dests
    # Outillage de maintenance embarqué (stdlib pure, racine du pack).
    assert "scripts/healing_drift_report.py" in dests
    assert "scripts/check_spec_sync.py" in dests
    # Garde des conventions #1/#2 : sap-generator l'appelle comme gate, donc il
    # doit voyager avec la définition de l'agent (revue packaging 2026-08-19).
    assert "scripts/check_conventions.py" in dests
    assert "scripts/_common.py" in dests
    assert "LICENSE" in dests and "NOTICE" in dests  # attribution Apache-2.0 embarquée
    # Agents de test : définitions Claude Code + chat modes VS Code générés +
    # slash-commands + plans d'exemple (cycle plan -> generate -> heal du pack).
    assert ".claude/agents/sap-planner.md" in dests
    assert ".claude/agents/sap-generator.md" in dests
    assert ".claude/agents/sap-healer.md" in dests
    assert ".claude/commands/sap-plan.md" in dests
    # Skill « boîte à outils » (install-as-a-skill) embarquée avec les agents.
    assert ".claude/skills/sapfx/SKILL.md" in dests
    # ... et RIEN d'autre sous .claude/skills/ : le dossier abrite aussi la
    # skill PRIVÉE de communication du studio, réellement livrée dans le pack
    # 0.6.6 tant que l'arbre entier était copié (voir le garde de symétrie
    # ci-dessous). Assertion par liste blanche, pour ne pas avoir à nommer ici
    # ce que le scan anti-fuite de l'export public interdit d'écrire.
    skills = [dest for dest in dests if dest.startswith(".claude/skills/")]
    assert skills and all(dest.startswith(".claude/skills/sapfx/")
                          for dest in skills), skills
    assert ".github/chatmodes/sap-planner.chatmode.md" in dests
    assert "specs/README.md" in dests
    assert "specs/sflight-consultation-se16.md" in dests
    assert not any("__pycache__" in dest for dest in dests)
    assert not any(dest.endswith(".pyc") for dest in dests)


# --- assemble : lanceurs batch en CRLF -------------------------------------------

def test_normalize_crlf_converts_and_is_idempotent():
    assert mod.normalize_crlf(b"@echo off\nREM a\n") == b"@echo off\r\nREM a\r\n"
    assert mod.normalize_crlf(b"@echo off\r\nREM a\r\n") == b"@echo off\r\nREM a\r\n"


def test_assemble_forces_crlf_on_cmd_launchers(tmp_path):
    """cmd.exe exige du CRLF : un install.cmd livré en LF pur (checkout git eol=lf)
    crache «'M' n'est pas reconnu…» au double-clic (vécu sur le pack 0.6.2)."""
    repo = _fake_repo(tmp_path / "repo")
    (repo / "packaging" / "install.cmd").write_bytes(b"@echo off\nREM x\n")
    (repo / "packaging" / "README.md").write_bytes(b"ligne1\nligne2\n")
    stage = tmp_path / "stage"
    stage.mkdir()
    mod.assemble(repo, stage)
    assert (stage / "install.cmd").read_bytes() == b"@echo off\r\nREM x\r\n"
    # Seuls les .cmd sont normalisés : le reste du manifeste est copié tel quel.
    assert (stage / "README.md").read_bytes() == b"ligne1\nligne2\n"


# --- pack_name / write_zip --------------------------------------------------------

def test_pack_name():
    assert mod.pack_name("0.1.0") == "sapfx-pack-0.1.0-win"


def test_write_zip_prefixes_entries_with_pack_name(tmp_path):
    stage = tmp_path / "sapfx-pack-0.1.0-win"
    (stage / "wheels").mkdir(parents=True)
    (stage / "wheels" / "a.whl").write_text("w", encoding="utf-8")
    (stage / "README.md").write_text("r", encoding="utf-8")
    zip_path = tmp_path / "pack.zip"
    mod.write_zip(stage, zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        names = sorted(archive.namelist())
    assert names == ["sapfx-pack-0.1.0-win/README.md", "sapfx-pack-0.1.0-win/wheels/a.whl"]


def test_checksums_cover_stage_and_zip_without_self_reference(tmp_path):
    stage = tmp_path / "sapfx-pack-0.1.0-win"
    stage.mkdir()
    (stage / "README.md").write_text("contenu", encoding="utf-8")
    checksums = mod.write_stage_checksums(stage)
    text = checksums.read_text(encoding="ascii")
    assert mod.file_sha256(stage / "README.md") in text
    assert "README.md" in text
    assert "SHA256SUMS.txt" not in text

    zip_path = tmp_path / "pack.zip"
    mod.write_zip(stage, zip_path)
    sidecar = mod.write_checksum_file(zip_path)
    assert sidecar.read_text(encoding="ascii") == (
        "%s  pack.zip\n" % mod.file_sha256(zip_path))


def test_is_excluded_laisse_les_helpers_de_dev_hors_du_pack():
    # Revue de code des tools (2026-08-19), constat n°8 : le pack copiait les
    # arbres recorder EN ENTIER, donc aussi les helpers de développement et les
    # démos vidéo, dont rien n'est jouable sur un poste de test (gen_icons.py
    # exige Pillow ET assets/logo.png, absent du pack ; les démos exigent
    # ffmpeg et le clone cap-sflight).
    assert mod.is_excluded("tools/recorder_web/extension/gen_icons.py")
    assert mod.is_excluded("tools/recorder_web/extension/package.py")
    # ... et le pas-à-pas de soumission au store, qui ne parle QUE d'eux.
    assert mod.is_excluded("tools/recorder_web/extension/PUBLISHING.md")
    assert mod.is_excluded("tools/recorder_web/extension/PUBLISHING.fr.md")
    # PRIVACY.md, lui, est dû à qui installe l'extension : il reste livré.
    assert not mod.is_excluded("tools/recorder_web/extension/PRIVACY.md")
    assert not mod.is_excluded("tools/recorder_web/extension/PRIVACY.fr.md")
    assert mod.is_excluded("tools/recorder/demo/ecc_demo_video.robot")
    assert mod.is_excluded("tools/recorder_web/demo/fiori_demo_video.robot")
    # ... et laisse passer tout ce qui sert vraiment sur le poste cible.
    assert not mod.is_excluded("tools/recorder/sapgui_recorder.py")
    assert not mod.is_excluded("tools/recorder/recorder_gui.py")
    assert not mod.is_excluded("tools/recorder_web/extension/recorder.js")
    assert not mod.is_excluded("tools/recorder_web/extension/manifest.json")


# --- symétrie des deux canaux de distribution -------------------------------------

_EXPORT_SCRIPT = os.path.join(_REPO_ROOT, "scripts", "export_public_tree.py")


@pytest.mark.skipif(not os.path.exists(_EXPORT_SCRIPT),
                    reason="script d'export absent (arbre public exporté)")
def test_le_pack_ne_livre_rien_que_l_export_public_exclut():
    """Ce que le dépôt public ne publie pas, le pack ne le livre pas non plus.

    Régression réelle (revue packaging du 2026-08-19) : ``PACK_TREES`` copiait
    ``.claude/skills`` en bloc, donc la skill PRIVÉE de communication du studio
    est partie dans le ``sapfx-pack-0.6.6-win.zip`` livré, alors que
    ``export_public_tree.py`` l'excluait nommément depuis toujours. Deux canaux
    de distribution existent, la frontière du privé ne peut pas être tenue par
    un seul : ce garde la fait porter par les deux, avec UNE seule liste (celle
    de l'export), sans jamais avoir à recopier ici ce qu'elle contient.
    """
    spec = importlib.util.spec_from_file_location(
        "export_public_tree", _EXPORT_SCRIPT)
    export = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(export)

    fautifs = []
    for src, dest in mod.build_manifest(_REPO_ROOT):
        rel = os.path.relpath(src, _REPO_ROOT).replace(os.sep, "/")
        for prefixe in export.EXCLUDE_PREFIXES:
            if rel == prefixe.rstrip("/") or rel.startswith(prefixe):
                fautifs.append("%s (livré en %s, exclu par %r)"
                               % (rel, dest.as_posix(), prefixe))
    assert not fautifs, (
        "le pack livre des fichiers que l'export public exclut : "
        + " ; ".join(sorted(fautifs)))


@pytest.mark.skipif(not os.path.exists(_EXPORT_SCRIPT),
                    reason="script d'export absent (arbre public exporté)")
def test_le_contenu_du_pack_passe_le_scan_anti_fuite_de_l_export():
    """Le pack subit le même scan de CONTENU que l'arbre public.

    Le garde précédent raisonne sur les CHEMINS : il ne voit rien d'un secret
    écrit À L'INTÉRIEUR d'un fichier par ailleurs légitime (chemin de poste,
    adresse, nom d'un dossier privé). L'export public, lui, scanne les octets
    de chaque fichier, mais il ne tourne qu'à la main au moment de la release,
    et sur ``git archive HEAD`` : le ZIP pouvait donc être construit, testé et
    publié avant que le seul scan de contenu du projet ait jamais tourné.

    Vérifié le 2026-08-19 : passé sur le ZIP 0.6.6 réellement livré, ce scan
    sort 5 occurrences interdites et nomme le fichier fautif ; passé sur le pack
    reconstruit après correction, zéro. Il aurait donc arrêté la fuite au build.
    Le voici branché sur la CI, à chaque push, et non plus une fois par release.

    La liste de motifs vit dans ``export_public_tree.py``, volontairement absent
    de l'arbre public (il énumère ce qu'on ne veut pas publier) : d'où le skip,
    et d'où le fait que ce contrôle soit un TEST plutôt qu'une étape de
    l'assembleur, lequel est livré, lui.
    """
    spec = importlib.util.spec_from_file_location(
        "export_public_tree", _EXPORT_SCRIPT)
    export = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(export)

    fuites = []
    for src, _dest in mod.build_manifest(_REPO_ROOT):
        # Chemin relatif au DÉPÔT : c'est dans ces termes que sont écrites les
        # exceptions légitimes de la table (`NOTICE` peut citer un nom propre).
        rel = os.path.relpath(src, _REPO_ROOT).replace(os.sep, "/")
        fuites += export.scan_bytes(rel, src.read_bytes(), export.FORBIDDEN)
    assert not fuites, (
        "motif interdit dans un fichier livré par le pack : "
        + " ; ".join("%s -> %r" % (rel, motif) for rel, motif in sorted(fuites)))


# --- cohérence interne du pack ----------------------------------------------------

#: Extensions dont on lit le contenu pour y chercher des références de scripts.
_TEXTE = (".md", ".py", ".ps1", ".cmd", ".txt", ".json", ".template",
          ".robot", ".resource", ".js", ".html", ".yaml", ".yml")
#: `scripts/<nom>.py` cité dans un fichier livré.
_REF_SCRIPT = re.compile(r"scripts/([A-Za-z0-9_]+)\.py")
#: Références qui parlent du DÉPÔT, pas d'un geste que l'utilisateur du pack
#: pourrait faire : (script cité, préfixe du fichier livré, justification).
#: Une par une, comme les autres échappatoires du dépôt : ajouter une référence
#: oblige à trancher entre « embarquer » et « justifier ici ».
_REF_HORS_SUJET = (
    ("regen_agent_definitions.py", ".github/chatmodes/",
     "bandeau « fichier GÉNÉRÉ, régénérer avec » : geste de mainteneur"),
    ("build_release_pack.py", "README.",
     "les READMEs du pack disent que le pack est un artefact : corriger "
     "packaging/ et reconstruire, jamais éditer le pack en place"),
)


def test_tout_script_cite_par_un_fichier_livre_est_lui_meme_livre():
    """Une définition livrée ne peut pas piloter un script resté au dépôt.

    Deux cas trouvés à la revue du 2026-08-19, tous deux muets : la définition
    de sap-generator lançait ``scripts/check_conventions.py`` (sa gate de
    convention #1) et la commande ``/sap-eval-healer`` lançait
    ``scripts/agent_eval_harness.py``, aucun des deux n'étant au manifeste. Le
    premier est désormais embarqué, la seconde est exclue du pack (c'est un
    filet de régression du studio). Ce garde vaut dans les deux sens : ajouter
    une référence oblige à trancher.
    """
    manifest = mod.build_manifest(_REPO_ROOT)
    livres = {dest.as_posix() for _src, dest in manifest}
    manquants = set()
    for src, dest in manifest:
        if not str(src).lower().endswith(_TEXTE):
            continue
        texte = src.read_text(encoding="utf-8", errors="replace")
        for nom in _REF_SCRIPT.findall(texte):
            cible = "scripts/%s.py" % nom
            if cible in livres:
                continue
            if any(cible.endswith("/" + script)
                   and dest.as_posix().startswith(prefixe)
                   for script, prefixe, _pourquoi in _REF_HORS_SUJET):
                continue
            manquants.add("%s -> %s" % (dest.as_posix(), cible))
    assert not manquants, (
        "des fichiers livrés pilotent des scripts absents du pack : "
        + " ; ".join(sorted(manquants)))
