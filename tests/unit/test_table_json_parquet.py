"""Les deux formats destinés aux MACHINES (`table_json`, `table_parquet`).

Côté JSON, ce qui est verrouillé est la propriété que les scripts et les
outils décisionnels attendent : deux formes explicites (tableau et JSON
Lines), une relecture qui DÉDUIT la forme au lieu de la supposer d'après
l'extension, et des valeurs qui restent du texte.

Côté Parquet, le canal est optionnel : les tests portent donc d'abord sur son
STATUT et sur son refus, qui doivent être justes sur un poste où `pyarrow`
n'est pas installé (le cas du poste de développement le 2026-09-15). L'écriture
elle-même n'est éprouvée que là où le binding existe, et se saute ailleurs en
le disant plutôt que de simuler un succès.
"""
from __future__ import annotations

import importlib.util
import json

import pytest

from sapfx_common.table_json import (
    read_table_json,
    render_table_json,
    table_records,
    write_table_json,
)
from sapfx_common.table_parquet import (
    parquet_channel_status,
    parquet_is_available,
    read_table_parquet,
    write_table_parquet,
)

RELEVE = [
    {"MANDT": "000", "NAME": "login/min_password_lng", "VALUE": "10"},
    {"MANDT": "001", "NAME": "gw/reg_info", "VALUE": "/usr/sap/reg_info"},
]


def test_le_releve_est_reduit_aux_colonnes_voulues_en_texte():
    fiches = table_records(RELEVE, columns=["NAME", "MANDT"])
    assert fiches[0] == {"NAME": "login/min_password_lng", "MANDT": "000"}


def test_l_ordre_des_colonnes_est_preserve_dans_chaque_objet():
    # Un relevé relu doit ressembler à l'écran dont il vient.
    fiches = table_records(RELEVE, columns=["VALUE", "NAME"])
    assert list(fiches[0]) == ["VALUE", "NAME"]


def test_le_tableau_json_est_du_json_valide():
    charge = json.loads(render_table_json(RELEVE))
    assert charge == RELEVE


def test_le_json_lines_porte_un_objet_par_ligne():
    texte = render_table_json(RELEVE, lines=True)
    lignes = texte.splitlines()
    assert len(lignes) == 2
    assert json.loads(lignes[1])["NAME"] == "gw/reg_info"


def test_le_json_lines_est_compact_et_le_tableau_indente():
    assert ", " not in render_table_json(RELEVE, lines=True)
    assert "\n  " in render_table_json(RELEVE)


def test_les_accents_ne_sont_pas_echappes():
    # Un `\\u00e9` dans un fichier destiné à un humain comme à un script est
    # lisible par la machine et pénible pour tout le monde.
    assert "éàü" in render_table_json([{"V": "éàü"}])


def test_deux_rendus_de_la_meme_donnee_sont_identiques():
    assert render_table_json(RELEVE) == render_table_json(RELEVE)


def test_l_aller_retour_rend_exactement_le_releve_ecrit(tmp_path):
    cible = tmp_path / "t.json"
    write_table_json(str(cible), RELEVE)
    assert read_table_json(str(cible)) == RELEVE


def test_l_aller_retour_vaut_aussi_pour_le_json_lines(tmp_path):
    cible = tmp_path / "t.jsonl"
    verdict = write_table_json(str(cible), RELEVE, lines=True)
    assert verdict["format"] == "jsonl"
    assert read_table_json(str(cible)) == RELEVE


def test_la_relecture_deduit_la_forme_du_contenu_pas_de_l_extension(tmp_path):
    # Un fichier reçu porte souvent `.json` en étant du JSON Lines.
    cible = tmp_path / "trompeur.json"
    write_table_json(str(cible), RELEVE, lines=True)
    assert read_table_json(str(cible)) == RELEVE


def test_la_relecture_tolere_une_marque_d_ordre_d_octets(tmp_path):
    cible = tmp_path / "bom.json"
    cible.write_text(json.dumps(RELEVE), encoding="utf-8-sig")
    assert read_table_json(str(cible)) == RELEVE


def test_un_fichier_vide_rend_un_releve_vide(tmp_path):
    cible = tmp_path / "vide.json"
    cible.write_text("", encoding="utf-8")
    assert read_table_json(str(cible)) == []


def test_le_verdict_signale_un_fichier_incomplet(tmp_path):
    lignes = [{"N": str(i)} for i in range(5)]
    verdict = write_table_json(str(tmp_path / "t.json"), lignes, max_rows=2)
    assert verdict["rows"] == 2
    assert verdict["total_rows"] == 5
    assert verdict["truncated_rows"] is True


def test_le_statut_parquet_se_prononce_sans_jamais_echouer():
    statut = parquet_channel_status()
    assert set(statut) == {"available", "reason", "remedy", "version"}
    assert isinstance(statut["available"], bool)
    assert parquet_is_available() is statut["available"]


@pytest.fixture
def sans_binding(monkeypatch):
    """Simule un poste sans `pyarrow`.

    La branche de refus est ainsi éprouvée PARTOUT, y compris là où le binding
    est installé. S'en remettre à l'absence réelle ferait que chaque poste
    n'éprouve qu'une des deux branches, et jamais celle qui compte pour lui.
    """
    vrai_find_spec = importlib.util.find_spec

    def introuvable(name, *args, **kwargs):
        if name == "pyarrow" or str(name).startswith("pyarrow."):
            return None
        return vrai_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "find_spec", introuvable)


def test_un_canal_parquet_absent_nomme_sa_cause_et_son_repli(sans_binding):
    statut = parquet_channel_status()
    assert statut["available"] is False
    assert statut["reason"] == "binding_absent"
    assert "pyarrow" in statut["remedy"]
    assert "JSON Lines" in statut["remedy"]
    assert parquet_is_available() is False


def test_ecrire_sans_le_binding_echoue_en_nommant_le_remede(tmp_path,
                                                            sans_binding):
    with pytest.raises(RuntimeError) as echec:
        write_table_parquet(str(tmp_path / "t.parquet"), RELEVE)
    assert "indisponible" in str(echec.value)
    assert "pyarrow" in str(echec.value)
    assert not (tmp_path / "t.parquet").exists(), (
        "un refus ne doit laisser aucun fichier derrière lui")


def test_relire_sans_le_binding_echoue_de_la_meme_facon(tmp_path,
                                                        sans_binding):
    with pytest.raises(RuntimeError) as echec:
        read_table_parquet(str(tmp_path / "absent.parquet"))
    assert "pyarrow" in str(echec.value)


@pytest.mark.skipif(not parquet_is_available(), reason="pyarrow absent")
def test_l_aller_retour_parquet_garde_les_valeurs_en_texte(tmp_path):
    # Le typage est IMPOSÉ : laissé libre, un écrivain Parquet ferait de
    # `000` un entier, et le fichier porterait ce type pour toujours.
    cible = tmp_path / "t.parquet"
    verdict = write_table_parquet(str(cible), RELEVE)
    assert verdict["columns"] == ["MANDT", "NAME", "VALUE"]
    assert read_table_parquet(str(cible)) == RELEVE
