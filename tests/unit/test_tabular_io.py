"""L'écriture d'un fichier de restitution et son seul échec courant.

Ce chemin d'erreur existe pour une raison datée : le 2026-09-15, la suite
d'extraction de RSPARAM a échoué sur `PermissionError: [Errno 13] Permission
denied`, parce que le classeur produit au run précédent était resté ouvert
dans Excel. Le message système désigne le fichier et rien d'autre : lu dans un
journal, il envoie chercher un problème de droits qui n'existe pas.

Ces tests verrouillent que les trois formats nomment la cause ET le remède, et
qu'ils ne le font QUE dans ce cas : requalifier une vraie erreur de droits en
« fichier ouvert dans un tableur » enverrait sur une fausse piste à son tour.
"""
from __future__ import annotations

import builtins

import pytest

from sapfx_common.table_csv import write_table_csv
from sapfx_common.table_json import write_table_json
from sapfx_common.table_svg import write_table_svg
from sapfx_common.table_xlsx import write_table_xlsx

RELEVE = [{"NAME": "login/min_password_lng", "VALUE": "10"}]


@pytest.fixture
def fichier_verrouille(monkeypatch):
    """Simule le verrou d'un tableur sur le fichier de sortie."""
    vrai_open = builtins.open

    def refuser(path, mode="r", *args, **kwargs):
        if any(lettre in str(mode) for lettre in "wa"):
            raise PermissionError(13, "Permission denied")
        return vrai_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", refuser)


@pytest.mark.parametrize("ecrire", [write_table_svg, write_table_csv,
                                    write_table_json, write_table_xlsx])
def test_un_fichier_verrouille_echoue_en_nommant_la_cause(ecrire, tmp_path,
                                                          fichier_verrouille):
    with pytest.raises(PermissionError) as echec:
        ecrire(str(tmp_path / "sortie"), RELEVE)
    message = str(echec.value)
    assert "OUVERT dans un tableur" in message
    assert "pas d'un problème de droits" in message
    assert "sortie" in message, "le message doit désigner le fichier visé"


def test_le_message_conserve_la_cause_d_origine(tmp_path, fichier_verrouille):
    with pytest.raises(PermissionError) as echec:
        write_table_csv(str(tmp_path / "t.csv"), RELEVE)
    assert "Permission denied" in str(echec.value)


def test_l_ecriture_ordinaire_reste_inchangee(tmp_path):
    # La contre-épreuve : sans verrou, rien ne doit changer.
    verdict = write_table_csv(str(tmp_path / "t.csv"), RELEVE)
    assert verdict["rows"] == 1
    assert (tmp_path / "t.csv").exists()
