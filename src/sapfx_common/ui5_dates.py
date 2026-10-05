"""Saisie d'une date dans un champ UI5 (`Fill Ui5 Date`) : logique pure.

Le miroir web de `Input Date` (ECC, ``sapfx_common.user_formats``). Côté web
la date se TAPE dans le format que le contrôle attend, et ce format dépend de
la locale du navigateur ET du type de contrôle : mesuré le 2026-09-24 sur un
aperçu Fiori Elements RAP (ABAP Platform 2023), en ``fr`` un
``sap.m.DatePicker`` acceptait ``15/10/2026`` là où un ``sap.ui.mdc.Field``
refusait ``06/07/2025`` et acceptait ``6 juil. 2025``. Le format se calcule
DANS la page (type de liaison du champ, chapitre ``_ui5_bundle_dates.js.tpl``) ;
ici vivent la validation de l'entrée ISO, le verdict de relecture et les
messages d'échec.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any, Mapping

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def iso_date(value: Any) -> str:
    """Date d'entrée normalisée en ``AAAA-MM-JJ``.

    Accepte une ``date``/``datetime`` Python ou une chaîne ISO STRICTE : une
    forme ambiguë (``06/07/2025`` : juin ou juillet ?) est précisément ce que le
    keyword existe pour éviter, donc elle est refusée en le disant, jamais
    interprétée. Une date inexistante (``2026-02-30``) est refusée aussi."""
    if isinstance(value, _dt.datetime):
        return value.date().isoformat()
    if isinstance(value, _dt.date):
        return value.isoformat()
    text = str(value).strip()
    if not _ISO_DATE_RE.match(text):
        raise ValueError(
            "Fill Ui5 Date attend une date ISO AAAA-MM-JJ, reçu %r : le format "
            "d'AFFICHAGE est calculé par le keyword, jamais fourni par l'appelant."
            % text)
    try:
        _dt.date.fromisoformat(text)
    except ValueError:
        raise ValueError("Fill Ui5 Date : %r n'est pas une date du calendrier." % text)
    return text


def date_text_error(info: Mapping[str, Any], iso: str, description: str) -> str:
    """Message actionnable pour une réponse ``{error}`` de la sonde de format."""
    error = info.get("error")
    type_name = info.get("type") or "aucun"
    if error == "not_a_date_type":
        return ("Fill Ui5 Date %s : la valeur est liée à un type %s (date ET heure, "
                "ou heure) ; ce keyword ne saisit qu'une DATE." % (description, type_name))
    if error == "no_date_format":
        return ("Fill Ui5 Date %s : ni type de liaison formatant une date (type de "
                "liaison : %s) ni format d'affichage de date sur le contrôle ; ce "
                "n'est pas un champ date. `Fill Ui5 Input` saisit un texte libre."
                % (description, type_name))
    if error == "not_found":
        return ("Fill Ui5 Date %s : le contrôle résolu a disparu du registre avant "
                "la saisie (re-rendu) ; rejouer après `Wait For Ui5 Idle`." % description)
    return "Fill Ui5 Date %s : format de %s impossible à établir (%s)." % (
        description, iso, error)


def date_retained(readback: Any, iso: str, before: Any = None) -> bool:
    """La saisie a-t-elle été RETENUE ?

    Trois règles, dans l'ordre :

    - un refus CÔTÉ CLIENT (message ``Error`` ciblant la valeur du contrôle,
      ``client_refusal``) n'est jamais une saisie retenue ;
    - la valeur modèle relue doit valoir la date demandée ;
    - quand le champ portait DÉJÀ cette date (``before``), la valeur ne prouve
      rien, et un état ``Error`` est tenu pour un refus : un contrôle peut
      refuser SANS message (application qui ne gère pas la validation), et
      mieux vaut un rouge qui le dit qu'un vert faux.

    Hors de ce dernier cas, un état ``Error`` seul ne prouve PAS un refus :
    mesuré le 2026-09-24 sur un brouillon RAP, une validation SERVEUR (début
    après la fin) met le champ en erreur alors que la date a bien été retenue
    au modèle, et c'est ce que le test veut provoquer."""
    if not isinstance(readback, Mapping):
        return False
    if readback.get("client_refusal") is True:
        return False
    if str(readback.get("value") or "") != iso:
        return False
    if before == iso and str(readback.get("state") or "") == "Error":
        return False
    return True


def date_not_retained_message(readback: Any, iso: str, text: str,
                              description: str) -> str:
    """Échec quand la saisie n'a pas été retenue : le texte tapé, la valeur
    relue et l'état de saisie du contrôle, les indices qui distinguent une
    valeur REFUSÉE (``state=Error``) d'une saisie jamais validée.

    Un refus n'est pas forcément un refus de FORMAT : mesuré le 2026-09-24, un
    ``sap.ui.mdc.Field`` dont l'aide à la saisie VALIDE la valeur (date d'un
    vol) a refusé une date au bon format tant que la compagnie et la liaison,
    qui filtrent cette aide, n'étaient pas saisies ; la même date a été
    retenue une fois ces deux champs remplis."""
    value = state = ""
    refusal = None
    if isinstance(readback, Mapping):
        value = str(readback.get("value") or "")
        state = str(readback.get("state") or "")
        refusal = readback.get("client_refusal")
    refused = "oui" if refusal is True else "non" if refusal is False else "illisible"
    return ("Fill Ui5 Date %s : %r tapé pour %s, mais la valeur modèle relue est "
            "%r (état de saisie %r, refus du contrôle : %s). Un refus du contrôle "
            "signale une valeur REFUSÉE à la saisie : format, ou date absente de son "
            "aide à la saisie quand elle valide (saisir d'abord les champs qui la "
            "filtrent) ; une valeur inchangée sans refus, une saisie jamais validée "
            "(commit=Tab ou commit=Enter)."
            % (description, text, iso, value or "vide", state or "aucun", refused))
