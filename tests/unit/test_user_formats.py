"""Tests hors SAP de ``sapfx_common.user_formats`` : dates et nombres dans le
format de l'utilisateur (clés DATFM/DCPFM), jamais les libellés localisés."""
import datetime

import pytest

from sapfx_common.user_formats import (
    describe_formats,
    format_date,
    format_number,
    parse_date,
    parse_number,
)


@pytest.mark.parametrize("key, expected", [
    ("1", "01.09.2026"), ("2", "09/01/2026"), ("3", "09-01-2026"),
    ("4", "2026.09.01"), ("5", "2026/09/01"), ("6", "2026-09-01"),
])
def test_format_date_suit_la_cle_datfm(key, expected):
    assert format_date("2026-09-01", key) == expected
    assert parse_date(expected, key) == "2026-09-01"


def test_format_date_accepte_un_objet_date_et_refuse_une_forme_non_iso():
    assert format_date(datetime.date(2026, 9, 1), "1") == "01.09.2026"
    with pytest.raises(ValueError, match="ISO 8601"):
        format_date("01.09.2026", "1")
    with pytest.raises(ValueError, match="invalide"):
        format_date("2026-13-01", "1")


def test_format_date_refuse_les_calendriers_non_gregoriens_en_les_nommant():
    with pytest.raises(ValueError, match="DATFM '7'"):
        format_date("2026-09-01", "7")


def test_parse_date_refuse_une_forme_qui_ne_suit_pas_le_format():
    with pytest.raises(ValueError, match="DD.MM.YYYY"):
        parse_date("2026-09-01", "1")
    assert parse_date("", "1") == ""


@pytest.mark.parametrize("key, value, expected", [
    ("", "1234.5", "1234,5"), ("X", "1234.5", "1234.5"), ("Y", "1234.5", "1234,5"),
    (" ", "1000", "1000"), ("x", "-2.50", "-2.50"),
])
def test_format_number_suit_la_notation_decimale(key, value, expected):
    assert format_number(value, key) == expected


def test_format_number_decimales_et_separateur_de_milliers():
    assert format_number("1234567.891", "", decimals=2, thousands=True) == "1.234.567,89"
    assert format_number("1234567", "Y", thousands=True) == "1 234 567"
    assert format_number(12, "X", decimals=2) == "12.00"


def test_format_number_refuse_une_notation_inconnue_ou_une_valeur_non_technique():
    with pytest.raises(ValueError, match="DCPFM"):
        format_number("1", "Z")
    with pytest.raises(ValueError, match="notation technique"):
        format_number("1.234,5", "")


def test_parse_number_rend_la_notation_technique_et_reconnait_le_signe_suffixe():
    assert parse_number("1.234,50", "") == "1234.50"
    assert parse_number("1,234.50", "X") == "1234.50"
    assert parse_number("100-", "X") == "-100"
    assert parse_number("", "") == ""
    with pytest.raises(ValueError, match="notation décimale"):
        parse_number("abc", "")


def test_describe_formats_rend_les_cles_et_leur_forme():
    described = describe_formats("1", " ", "0")
    assert described["date_format"] == "1"
    assert described["date_pattern"] == "DD.MM.YYYY"
    assert described["decimal_notation"] == ""
    assert described["decimal_example"] == "1.234.567,89"
    assert described["gregorian"] is True
    assert describe_formats("7", "X")["gregorian"] is False
