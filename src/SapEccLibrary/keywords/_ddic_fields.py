"""Champs d'une table du dictionnaire, lus dans DD03L par le Data Browser.

Extrait de ``_ddic.py`` : la lecture locale-indépendante du contrat de champs
d'une table, que l'inventaire DDIC et le croisement entre canaux consomment.
"""
from typing import TYPE_CHECKING, Any

from robot.api.deco import keyword

from sapfx_common.argument_types import TableNameInput

from ._diagnostics import _truthy
from ._se16 import _SE16_MAX_HITS

#: Table des champs du dictionnaire, source du contrat de champs.
_DD03L_TABLE = "DD03L"

#: Colonnes DD03L consommées par le contrat de champs : même règle que pour
#: DD02L, la lecture est RESTREINTE aux ids techniques (indépendants de la
#: locale et du profil d'affichage ALV). Relevé live : la grille en expose 31,
#: neuf suffisent à décrire un champ.
_DD03L_COLUMNS = ("FIELDNAME", "POSITION", "KEYFLAG", "ROLLNAME", "DATATYPE",
                  "LENG", "DECIMALS", "DOMNAME", "CHECKTABLE")


class DdicFieldKeywords:
    """Mixin ajouté à :class:`SapEccLibrary` : champs d'une table lus dans DD03L."""

    _truthy = staticmethod(_truthy)

    if TYPE_CHECKING:
        # Contrat du composite (SapEccLibrary), pour mypy seulement : les
        # keywords annotés (type GuiElementId) font vérifier leurs corps.
        def _read_se16_rows(self, *args: Any, **kwargs: Any) -> Any: ...
        def get_se16_selection_criteria(self, *args: Any, **kwargs: Any) -> Any: ...
        def input_text(self, *args: Any, **kwargs: Any) -> Any: ...
        def reach_se16_selection_screen(self, *args: Any, **kwargs: Any) -> Any: ...
        def send_vkey(self, *args: Any, **kwargs: Any) -> Any: ...
        def wait_until_busy_done(self, *args: Any, **kwargs: Any) -> Any: ...

    @keyword(tags=["touches:transaction:SE16"])
    def read_ddic_table_fields(self, table: TableNameInput, active_only: bool = True,
                               max_fields: int = 200, timeout=None):
        """Champs d'une table du dictionnaire (DD03L), en liste de dicts.

        Ouvre DD03L dans le Data Browser, filtre sur ``TABNAME`` (et
        ``AS4LOCAL=A``, la version active, quand ``active_only``), exécute et
        lit la grille RESTREINTE aux colonnes techniques consommées
        (``FIELDNAME``, ``POSITION``, ``KEYFLAG``, ``ROLLNAME``, ``DATATYPE``,
        ``LENG``, ``DECIMALS``, ``DOMNAME``, ``CHECKTABLE``). Les lignes sont
        rendues triées par position : la lecture est déterministe et
        indépendante de l'ordre d'affichage.

        Les critères sont résolus par NOM via `Get Se16 Selection Criteria`,
        jamais par position : c'est ce qui rend le keyword insensible au choix
        des champs de sélection persistant par utilisateur, sans avoir besoin
        de la sonde canari que la classification DD02L doit, elle, exécuter.

        Garde-fous « jamais vert et faux » :
        un plafond de lecture ATTEINT est un échec (une troncature ne doit
        jamais être muette), une grille absente hors écran de sélection nomme
        `Use ALV Grid In Data Browser`, et un résultat VIDE est un échec (la
        table est inconnue de DD03L) au lieu d'un contrat de champs vide qui
        passerait pour une table sans champ. Lecture seule.

        Exemple :
        | ${fields}=    `Read Ddic Table Fields`    SCARR
        | Should Be Equal    ${fields}[1][FIELDNAME]    CARRID
        | Should Be Equal    ${fields}[1][KEYFLAG]    X
        """
        name = str(table).strip().upper()
        if not name:
            raise AssertionError("read_ddic_table_fields: no table name given.")
        try:
            cap = int(str(max_fields).strip())
        except (TypeError, ValueError):
            cap = 0
        if cap < 1:
            raise AssertionError(
                "read_ddic_table_fields: max_fields must be a strictly "
                "positive integer.")
        state = self.reach_se16_selection_screen(_DD03L_TABLE, timeout)
        if not state["reached"]:
            raise AssertionError(
                "read_ddic_table_fields: SE16 did not reach the %s selection "
                "screen (verdict '%s'): %s. Check SE16/DDIC display "
                "authorizations." % (_DD03L_TABLE, state["verdict"],
                                     state["status_text"]
                                     or state["dialog_text"]))
        criteria = self.get_se16_selection_criteria()
        self.input_text(self._dd03l_criterion(criteria, "TABNAME"), name)
        if self._truthy(active_only):
            self.input_text(self._dd03l_criterion(criteria, "AS4LOCAL"), "A")
        self.input_text(_SE16_MAX_HITS, str(cap))
        self.send_vkey(8)
        self.wait_until_busy_done()
        rows = self._read_se16_rows(cap, list(_DD03L_COLUMNS), timeout,
                                    "read_ddic_table_fields")
        if len(rows) >= cap:
            raise AssertionError(
                "read_ddic_table_fields: the DD03L read hit its row cap (%s "
                "rows for '%s'): the field contract would be silently "
                "truncated. Raise max_fields." % (cap, name))
        if not rows:
            raise AssertionError(
                "read_ddic_table_fields: DD03L returned no field for '%s'. "
                "The object is unknown to the dictionary (or has no active "
                "version): check its name and its class in DD02L before "
                "asking for its field contract." % name)
        return sorted(rows, key=lambda row: (str(row.get("POSITION", "")),
                                             str(row.get("FIELDNAME", ""))))

    @staticmethod
    def _dd03l_criterion(criteria, field):
        """Localisateur d'un critère DD03L attendu, échec listant les critères
        réellement présents sinon (jamais une saisie à l'aveugle dans un champ
        positionnel qui aurait bougé)."""
        locator = criteria.get(field)
        if locator is None:
            raise AssertionError(
                "read_ddic_table_fields: the DD03L selection screen exposes no "
                "'%s' criterion; present criteria: %s. Reset the field "
                "selection for DD03L in SE16 (Settings > Fields for Selection) "
                "so the key fields are available."
                % (field, ", ".join(sorted(criteria))))
        return locator
