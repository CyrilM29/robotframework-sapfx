"""Le contrat d'agents tenu, pas seulement écrit (`scripts/agent_contract.py`).

Ce garde existe parce que le script ne tournait NULLE PART : ni en CI, ni dans
le hook d'édition. Constaté le 2026-09-16 en le lançant à la main pour la
première fois depuis sa mise en place, trois sidecars sur six étaient
invalides, et pour trois causes différentes (une clé hors schéma, une
empreinte de suite périmée, une empreinte de plan périmée). Une explication
unique et plausible circulait alors, l'horodatage des preuves : elle était
fausse sur les trois, et la mesure l'a démentie.

Deux leçons y sont donc outillées ensemble. Une garde qui ne tourne nulle part
accumule de la casse silencieuse, et quand on finit par regarder, les échecs
n'ont PAS tous la même cause : un récit unique les couvrirait tous et
n'en réparerait aucun. D'où un balayage qui nomme chaque cause séparément.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[2]
_SCRIPT = _RACINE / "scripts" / "agent_contract.py"
_spec = importlib.util.spec_from_file_location("agent_contract", _SCRIPT)
contract = importlib.util.module_from_spec(_spec)
sys.modules["agent_contract"] = contract
_spec.loader.exec_module(contract)

_SIDECARS = sorted((_RACINE / "specs").glob("*.handoff.json"))


def test_le_depot_porte_au_moins_un_sidecar():
    """Sans ce contrôle, un balayage vide passerait pour un balayage vert.

    C'est le mode de panne d'un garde à périmètre dérivé : il ne rougit jamais
    parce qu'il ne regarde rien.
    """
    assert _SIDECARS, "aucun specs/*.handoff.json : le balayage ne prouve rien."


@pytest.mark.parametrize("sidecar", _SIDECARS, ids=lambda p: p.stem)
def test_chaque_handoff_est_valide_sur_l_arbre_reel(sidecar):
    """Structure ET empreintes de preuve, sur les vrais fichiers du dépôt.

    Une empreinte périmée n'est pas un détail d'intendance : le sidecar atteste
    qu'une mission a produit CES artefacts-là, donc une empreinte qui a dérivé
    fait attester un état que personne n'a validé. Le remède est nommé par le
    message d'échec du script (`--refresh` une fois le changement voulu).
    """
    data = json.loads(sidecar.read_text(encoding="utf-8-sig"))
    contract.validate_handoff(data, _RACINE)


@pytest.mark.parametrize("sidecar", _SIDECARS, ids=lambda p: p.stem)
def test_aucune_preuve_epinglee_ne_porte_de_crlf(sidecar):
    """Une empreinte prise sur des CRLF locaux est verte ICI et rouge AILLEURS.

    Le contrat épingle les OCTETS du fichier, et `.gitattributes` impose
    `eol=lf` : un fichier laissé en CRLF dans l'arbre de travail (un éditeur
    Windows, un outil qui réécrit un artefact) est signé sous une forme que
    personne d'autre ne verra jamais, puisque tout checkout frais, la CI la
    première, le rend en LF. Le sidecar passe alors sur le poste qui l'a signé
    et refuse partout ailleurs, sans que rien du contenu n'ait bougé.

    Mesuré le 2026-09-21 : sur les quatre sidecars dont l'empreinte avait
    dérivé, trois l'avaient pour une suite corrigée après revue, et le
    quatrième pour cette seule raison, invisible en local. C'est la même
    famille que les baselines visuelles liées à la géométrie de capture :
    une empreinte qui encode le POSTE au lieu du contenu.
    """
    data = json.loads(sidecar.read_text(encoding="utf-8-sig"))
    fautifs = []
    for entree in data.get("evidence", []):
        fichier = _RACINE / entree["path"]
        if fichier.exists() and b"\r\n" in fichier.read_bytes():
            fautifs.append(entree["path"])
    assert not fautifs, (
        "empreinte(s) non portables dans %s : %s porte(nt) des CRLF alors que "
        ".gitattributes impose eol=lf ; normaliser le fichier en LF puis "
        "re-signer (agent_contract.py handoff <sidecar> --refresh), sinon le "
        "sidecar est valide sur ce poste seulement."
        % (sidecar.name, ", ".join(fautifs)))


def test_le_schema_refuse_une_cle_libre_en_nommant_laquelle(tmp_path):
    """Contre-épreuve : le garde doit mordre, et dire sur quoi.

    Le schéma est fermé à dessein, une clé libre étant l'endroit exact où une
    affirmation non vérifiée entre dans un artefact censé l'être. Encore
    faut-il que le refus la nomme, sans quoi personne ne la retire : c'est
    précisément ce qui avait laissé un sidecar invalide pendant une release.
    """
    preuve = tmp_path / "plan.md"
    preuve.write_text("plan", encoding="utf-8")
    import hashlib

    data = {
        "schema_version": 1, "mission_id": "m1", "target": "a4h",
        "invariant": "un invariant", "scope": ["plan.md"], "mode": "read_only",
        "budgets": {"attempts": 2, "tool_calls": 20, "seconds": 900},
        "evidence": [{"path": "plan.md",
                      "sha256": hashlib.sha256(b"plan").hexdigest()}],
    }
    contract.validate_handoff(dict(data), tmp_path)   # valide tel quel

    with pytest.raises(ValueError) as refus:
        contract.validate_handoff(dict(data, notes="un récit non vérifié"), tmp_path)
    assert "notes" in str(refus.value)


def test_refresh_ne_touche_que_les_empreintes_et_dit_ce_qui_a_bouge(tmp_path):
    """`--refresh` est un geste EXPLICITE, pas une réparation silencieuse.

    Il re-signe les empreintes et rend ce qui a dérivé, pour que re-signer
    reste une décision visible ; il ne rattrape RIEN d'autre, donc un sidecar
    invalide pour une autre raison le reste et le dit.
    """
    import hashlib

    preuve = tmp_path / "plan.md"
    preuve.write_text("version 1", encoding="utf-8")
    data = {
        "schema_version": 1, "mission_id": "m1", "target": "a4h",
        "invariant": "un invariant", "scope": ["plan.md"], "mode": "read_only",
        "budgets": {"attempts": 2, "tool_calls": 20, "seconds": 900},
        "evidence": [{"path": "plan.md",
                      "sha256": hashlib.sha256(b"version 1").hexdigest()}],
    }
    assert contract.refresh_evidence(dict(data), tmp_path) == []

    preuve.write_text("version 2", encoding="utf-8")
    with pytest.raises(ValueError, match="Evidence hash mismatch on plan.md"):
        contract.validate_handoff(dict(data), tmp_path)

    bouge = contract.refresh_evidence(data, tmp_path)
    assert [chemin for chemin, _, _ in bouge] == ["plan.md"]
    contract.validate_handoff(data, tmp_path)   # ne lève plus


def test_refresh_ne_rattrape_pas_une_faute_de_structure(tmp_path):
    import hashlib

    preuve = tmp_path / "plan.md"
    preuve.write_text("x", encoding="utf-8")
    data = {
        "schema_version": 1, "mission_id": "m1", "target": "a4h",
        "invariant": "un invariant", "scope": ["plan.md"], "mode": "read_only",
        "budgets": {"attempts": 2, "tool_calls": 20, "seconds": 900},
        "evidence": [{"path": "plan.md", "sha256": "perime"}],
        "notes": "hors schéma",
    }
    contract.refresh_evidence(data, tmp_path)
    assert data["evidence"][0]["sha256"] == hashlib.sha256(b"x").hexdigest()
    with pytest.raises(ValueError, match="notes"):
        contract.validate_handoff(data, tmp_path)
