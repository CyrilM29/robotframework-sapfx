"""Identité d'un message de la barre de statut SAP GUI, logique pure.

`Get Status Message` rend le TYPE (``E``, ``S``, ``W``...) et le TEXTE, et le
texte est localisé : une suite ne peut donc asserter que le type, si bien que
deux refus différents du même écran sont indiscernables. Mesuré le 2026-09-08
sur ABAP 2023 (SE16) : « table inexistante » et « nom de table vide » sont
tous deux de type ``E``, mais la barre expose ``MessageId`` (la CLASSE de
message ABAP) et ``MessageNumber``, soit ``MO``/``402`` contre ``MO``/``410``.
C'est le pendant SAP GUI de l'identité de message du canal RFC
(``sapfx_common.rfc_channel.rfc_message_identity`` : classe, type, numéro,
le refus EXACT, indépendant de la langue), et la convention #3 gagne un outil
plus fin que le type seul.

Une décision assumée, à l'inverse de la clé d'une combo box : ``MessageId``
est complété à droite sur 20 caractères (``'MO                  '``), et ce
padding n'est PAS une donnée, une classe de message est ``MO``. Il est donc
retiré ; la clé d'une combo, elle, distingue réellement ``""`` de ``" "`` et
ne se normalise jamais. Typé, testé hors SAP.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

MESSAGE_CLASS_WIDTH = 20


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def normalize_message_class(value: Any) -> str:
    """La classe de message sans son padding de champ ABAP (``'MO   '`` ->
    ``'MO'``), en majuscules comme le dictionnaire la porte."""
    return _text(value).strip().upper()


def normalize_message_number(value: Any) -> str:
    """Le numéro tel quel, blancs retirés (``'402'``) ; une valeur numérique
    est rendue sur trois chiffres comme SAP l'affiche (``2`` -> ``'002'``)."""
    text = _text(value).strip()
    if text.isdigit() and len(text) < 3:
        return text.zfill(3)
    return text


def message_identity(message_type: Any, message_class: Any, message_number: Any,
                     text: Any = "", parameters: Iterable[Any] = ()) -> dict[str, Any]:
    """Le dict JSON-safe que rend `Get Status Message Identity` : ``type``,
    ``class``, ``number``, ``identity`` (``MO/E/402``, la forme du canal RFC ;
    vide quand aucun message n'est affiché : jamais une identité inventée),
    ``text`` (pour le lecteur, jamais pour une assertion) et ``parameters``
    (les variables ``&`` du message, vides retirées en queue)."""
    mtype = _text(message_type).strip().upper()
    mclass = normalize_message_class(message_class)
    number = normalize_message_number(message_number)
    params = [_text(p) for p in parameters]
    while params and not params[-1].strip():
        params.pop()
    identity = "%s/%s/%s" % (mclass, mtype, number) if mclass and number else ""
    return {"type": mtype, "class": mclass, "number": number, "identity": identity,
            "text": _text(text), "parameters": params}


def identity_matches(identity: Mapping[str, Any], message_class: Any, message_number: Any,
                     message_type: Any = None) -> bool:
    """Vrai si l'identité lue porte la classe et le numéro attendus (et le type,
    quand il est donné)."""
    if normalize_message_class(identity.get("class")) != normalize_message_class(message_class):
        return False
    if normalize_message_number(identity.get("number")) != normalize_message_number(message_number):
        return False
    if message_type not in (None, ""):
        return _text(identity.get("type")).strip().upper() == _text(message_type).strip().upper()
    return True


def format_identity_mismatch(identity: Mapping[str, Any], message_class: Any,
                             message_number: Any, message_type: Any = None) -> str:
    """Le message d'un `Status Message Should Be` qui échoue : l'attendu, le
    lu (identité ET texte, pour le lecteur), et le cas « aucun message »."""
    expected = "%s/%s/%s" % (normalize_message_class(message_class),
                             _text(message_type).strip().upper() or "*",
                             normalize_message_number(message_number))
    actual = _text(identity.get("identity"))
    if not actual:
        return ("Message de statut attendu %s, mais la barre de statut n'affiche "
                "aucun message identifiable (type %r, texte %r)."
                % (expected, identity.get("type", ""), identity.get("text", "")))
    return ("Message de statut attendu %s, lu %s (texte : %r)."
            % (expected, actual, identity.get("text", "")))
