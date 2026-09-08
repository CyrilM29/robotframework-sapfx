"""Mixin **combo box et formats de l'utilisateur** : sélectionner par CLÉ,
lire les entrées, et saisir dates et nombres dans le format de l'utilisateur.

Relevé live le 2026-09-07 (A4H, SAP GUI 8.00) : une ``GuiComboBox`` expose ses
entrées en couples ``(Key, Value)`` et se pose par ``.Key`` comme par
``.Value`` ; le keyword hérité `Select From List By Label` ne connaît que le
libellé LOCALISÉ, échoue sur un combo en affichage par une ``AttributeError``
COM muette (``Property '<unknown>.value' can not be set``) et sur un libellé
inconnu par un ``com_error`` « invalid argument ». Les dates, elles, ne
passent que dans le format de l'utilisateur (``SU3`` > Defaults, ``DATFM``),
et les nombres dans sa notation décimale (``DCPFM``) ; une saisie ISO est
refusée par un message de type ``E`` (00/065). Logique pure dans
``sapfx_common.combo_box`` et ``sapfx_common.user_formats``.
"""
from pythoncom import com_error
from robot.api import logger

from sapfx_common.combo_box import (
    entries_as_dicts,
    find_by_key,
    find_by_label,
    format_entries,
)
from sapfx_common.user_formats import describe_formats, format_date, format_number

_TRUTHY = ("1", "true", "yes", "on")

# SU3 (« Maintain Own User Profile ») : l'onglet Defaults et ses trois combos,
# mêmes ids que dans SU01 (relevé live 2026-09-07). C'est un écran SAP
# standard, donc une primitive de bibliothèque (convention 12), comme `Use ALV
# Grid In Data Browser`.
_SU3_TCODE = "SU3"
_SU3_DEFAULTS_TAB = "wnd[0]/usr/tabsTABSTRIP1/tabpDEFA"
_SU3_SUB = "wnd[0]/usr/tabsTABSTRIP1/tabpDEFA/ssubMAINAREA:SAPLSUID_MAINTENANCE:1105/"
_SU3_DECIMAL = _SU3_SUB + "cmbSUID_ST_NODE_DEFAULTS-DCPFM"
_SU3_DATE = _SU3_SUB + "cmbSUID_ST_NODE_DEFAULTS-DATFM"
_SU3_TIME = _SU3_SUB + "cmbSUID_ST_NODE_DEFAULTS-TIMEFM"


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TRUTHY


class ComboBoxKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose ``self.session`` connectée."""

    def _combo(self, element_id):
        element_type = self.get_element_type(element_id)
        if element_type != "GuiComboBox":
            self.take_screenshot()
            raise ValueError(
                "Element '%s' est un %s, pas une GuiComboBox." % (element_id, element_type))
        return self.session.findById(element_id)

    def get_combo_box_entries(self, element_id):
        """Les entrées d'une combo box : liste de dicts ``{key, value}`` dans
        l'ordre d'affichage, la CLÉ étant la donnée technique (``A`` pour
        « Dialog » dans SU01) et la valeur le libellé localisé."""
        combo = self._combo(element_id)
        try:
            return entries_as_dicts(combo.Entries)
        except (AttributeError, com_error) as exc:
            raise ValueError("Les entrées de '%s' sont illisibles (%s)." % (element_id, exc))

    def get_combo_box_key(self, element_id):
        """La CLÉ de l'entrée sélectionnée (``Key``), rendue TELLE QUELLE :
        l'ancre locale-safe d'une assertion, là où `Get Value` rend le libellé.
        Aucun blanc n'est retiré : une combo peut porter deux entrées de clés
        distinctes ``""`` et ``" "`` (relevé live sur SM37, « Or after event »),
        et normaliser à la lecture rendrait une restauration invérifiable."""
        combo = self._combo(element_id)
        key = getattr(combo, "Key", "")
        return "" if key is None else str(key)

    def select_combo_box_entry_by_key(self, element_id, key):
        """Sélectionne l'entrée de clé ``key`` (``.Key = ...``) et vérifie la
        sélection en la relisant. Combo en affichage (``Changeable`` faux) ou
        clé absente = échec actionnable listant les entrées : jamais une
        ``AttributeError`` COM muette."""
        combo = self._combo(element_id)
        entries = entries_as_dicts(combo.Entries)
        self._combo_should_be_changeable(element_id, combo)
        entry = find_by_key(entries, key)
        if entry is None:
            self.take_screenshot()
            raise ValueError(
                "Aucune entrée de clé %r dans '%s'. Entrées :\n%s"
                % (key, element_id, format_entries(entries)))
        wanted = entry["key"]           # la clé RÉELLE, blancs compris
        combo.Key = wanted
        actual = str(getattr(combo, "Key", "") or "")
        if actual != wanted:
            self.take_screenshot()
            raise AssertionError(
                "La combo '%s' porte la clé %r après sélection de %r."
                % (element_id, actual, wanted))
        return actual

    def select_from_list_by_label(self, element_id, value):
        """Surcharge du keyword hérité : même signature, sélection par
        LIBELLÉ (préfixe insensible à la casse, puis égalité si plusieurs),
        avec les trois échecs actionnables que l'hérité ne donnait pas : combo
        en affichage, libellé inconnu (entrées listées), libellé ambigu. Pour
        une suite locale-safe, préférer `Select Combo Box Entry By Key`."""
        combo = self._combo(element_id)
        entries = entries_as_dicts(combo.Entries)
        self._combo_should_be_changeable(element_id, combo)
        matches = find_by_label(entries, value, exact=True)
        if not matches:
            matches = find_by_label(entries, value, exact=False)
        if len(matches) != 1:
            self.take_screenshot()
            if not matches:
                raise ValueError(
                    "Aucune entrée au libellé %r dans '%s' (le libellé est "
                    "LOCALISÉ : préférer Select Combo Box Entry By Key). "
                    "Entrées :\n%s" % (value, element_id, format_entries(entries)))
            raise ValueError(
                "Libellé %r ambigu dans '%s' (%d entrées) : préciser, ou passer "
                "par la clé :\n%s" % (value, element_id, len(matches),
                                       format_entries(matches)))
        combo.Key = matches[0]["key"]
        return matches[0]["key"]

    def _combo_should_be_changeable(self, element_id, combo):
        if not bool(getattr(combo, "Changeable", True)):
            self.take_screenshot()
            raise ValueError(
                "La combo '%s' est en AFFICHAGE (Changeable=False) : rien à "
                "sélectionner sur cet écran (mode Display), passer en mode "
                "modification d'abord." % element_id)

    # -- formats de l'utilisateur ---------------------------------------------

    def get_user_formats(self):
        """Lit les formats de l'UTILISATEUR connecté dans SU3 (onglet Defaults,
        clés techniques des combos, jamais leurs libellés) et revient à l'écran
        précédent par F3. Retourne un dict JSON-safe ``{date_format,
        date_pattern, decimal_notation, decimal_example, time_format,
        gregorian}`` et le MÉMORISE pour `Input Date` / `Input Number`.

        À appeler en Suite Setup : c'est un aller-retour d'écran (SU3 est un
        écran SAP standard, la primitive est donc dans la bibliothèque). Le
        format est une propriété de l'utilisateur, pas de la langue : deux
        utilisateurs de la même session EN peuvent lire ``DD.MM.YYYY`` et
        ``MM/DD/YYYY``."""
        self.run_transaction(_SU3_TCODE)
        self.wait_until_element_present(_SU3_DEFAULTS_TAB)
        self.click_element(_SU3_DEFAULTS_TAB)
        self.wait_until_busy_done()
        self.wait_until_element_present(_SU3_DATE)
        formats = describe_formats(self.get_combo_box_key(_SU3_DATE),
                                   self.get_combo_box_key(_SU3_DECIMAL),
                                   self.get_combo_box_key(_SU3_TIME))
        self.send_vkey(3)
        self.wait_until_busy_done()
        self._user_formats = formats
        logger.info("Formats de l'utilisateur : %s" % formats)
        return formats

    def _known_user_formats(self, keyword):
        formats = getattr(self, "_user_formats", None)
        if not formats:
            raise AssertionError(
                "%s a besoin des formats de l'utilisateur : appeler Get User "
                "Formats d'abord (Suite Setup), ou passer le format en argument."
                % keyword)
        return formats

    def input_date(self, element_id, iso_date, date_format=None):
        """Saisit une date donnée en ISO 8601 (``2026-09-01``) dans le champ
        ``element_id``, CONVERTIE au format de l'utilisateur (``01.09.2026``
        pour ``DD.MM.YYYY``) : la suite reste locale-safe. ``date_format`` =
        clé ``DATFM`` (``1`` à ``6``) ; sans lui, celle mémorisée par
        `Get User Formats`. Retourne la chaîne réellement saisie."""
        key = date_format if date_format not in (None, "", "None") else \
            self._known_user_formats("Input Date")["date_format"]
        text = format_date(str(iso_date), key)
        self.input_text(element_id, text)
        return text

    def input_number(self, element_id, value, decimal_notation=None, decimals=None):
        """Saisit un nombre donné en notation TECHNIQUE (``1234.5``) dans le
        champ ``element_id``, converti à la notation décimale de l'utilisateur
        (``1234,5`` pour ``1.234.567,89``). ``decimal_notation`` = clé ``DCPFM``
        (vide, ``X`` ou ``Y``) ; sans lui, celle de `Get User Formats`.
        ``decimals`` fixe le nombre de décimales. Retourne la chaîne saisie."""
        if decimal_notation in (None, "None"):
            key = self._known_user_formats("Input Number")["decimal_notation"]
        else:
            key = decimal_notation
        text = format_number(value, key,
                             None if decimals in (None, "", "None") else int(decimals))
        self.input_text(element_id, text)
        return text
