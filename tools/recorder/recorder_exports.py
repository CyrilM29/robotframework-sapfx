"""Exports post-enregistrement du recorder bureau : suite, resource-first,
spec, ISTQB, rapport HTML.

Extrait de ``sapgui_recorder.py`` (module devenu monolithique) : tout ici est
PUR (texte -> texte), sans COM ni session SAP, et testé hors SAP dans
``tests/unit/test_recorder_exports.py``. ``sapgui_recorder`` ré-exporte ces
noms : les consommateurs historiques (GUI, tests, suites Robot) ne changent
pas.
"""
import os

# --- Exports post-enregistrement : suite complète, resource-first, spec --------
#
# Le déroulé brut (corps *** Test Cases *** aux ids techniques) est un BROUILLON.
# Trois exports le rapprochent d'un test maintenable, sans rien perdre :
#   * ``--suite``            : fichier .robot COMPLET (Settings + Suite Setup),
#     rejouable tel quel contre la session SAP GUI déjà ouverte ;
#   * ``--export-resources`` : la paire resource-first, un ``.resource`` où
#     chaque id devient une variable ``${LOC_…}`` enveloppée dans un keyword
#     métier, et la suite n'appelle plus QUE ces keywords (convention n°1 du
#     projet : aucun id brut dans les tests, et c'est la couche resources que
#     sap-healer sait réparer) ;
#   * ``--export-spec``      : un plan Markdown au format ``specs/`` (étapes en
#     langage métier, ids relégués en notes factuelles) : l'enregistrement
#     devient l'ENTRÉE du cycle plan → generate → heal au lieu d'un test figé.
# Tout est pur (texte -> texte) et testé hors SAP.


# Decoupe convention #13 : le socle et les trois familles d'export vivent dans
# les modules voisins ; ce module reste la PORTE D'ENTREE historique et
# re-exporte l'integralite de sa surface (GUI, sapgui_recorder, tests).
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from recorder_exports_core import (  # noqa: E402,F401
    DEFAULT_TEST_NAME as DEFAULT_TEST_NAME,
    _SUITE_SETTINGS as _SUITE_SETTINGS,
    build_record_header as build_record_header,
    parse_recorded_body as parse_recorded_body,
    count_test_cases as count_test_cases,
    replace_recorded_steps as replace_recorded_steps,
    _LOC_PREFIX as _LOC_PREFIX,
    locator_slug as locator_slug,
    _CELL_SEP as _CELL_SEP,
    _SPACE_SENTINEL as _SPACE_SENTINEL,
    _split_step as _split_step,
    rf_escape_value as rf_escape_value,
    rf_unescape_value as rf_unescape_value,
    _SECRET_ARG as _SECRET_ARG,
    _mask_secret_args as _mask_secret_args,
)
from recorder_exports_robot import (  # noqa: E402,F401
    _RESOURCE_WRAPPERS as _RESOURCE_WRAPPERS,
    steps_to_resource_first as steps_to_resource_first,
)
from recorder_exports_docs import (  # noqa: E402,F401
    md_code as md_code,
    _humanize_step as _humanize_step,
    steps_to_spec as steps_to_spec,
    _ISTQB_GENERIC_EXPECTED as _ISTQB_GENERIC_EXPECTED,
    _ISTQB_TABLE_EXPECTED as _ISTQB_TABLE_EXPECTED,
    _istqb_slug as _istqb_slug,
    _yq as _yq,
    _md_cell as _md_cell,
    _istqb_step as _istqb_step,
    _istqb_yaml_lines as _istqb_yaml_lines,
    steps_to_istqb as steps_to_istqb,
)
from recorder_exports_report import (  # noqa: E402,F401
    _REPORT_CSS as _REPORT_CSS,
    _REPORT_MIMES as _REPORT_MIMES,
    _esc as _esc,
    _SCREENSHOT_COMMENT as _SCREENSHOT_COMMENT,
    report_screenshot_loader as report_screenshot_loader,
    _humanize_channel_step as _humanize_channel_step,
    steps_to_report as steps_to_report,
    _report_shots as _report_shots,
    _strip_md_code as _strip_md_code,
)
