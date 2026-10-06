"""Mixin des *listes ABAP classiques adressées par ligne* : les lire
alignées sur leur en-tête et cocher la ligne d'un contenu donné.

Né de la fiche scénario 9 (A4H, 2026-10-01), sur les listes de SM37 (jobs),
SP01 (spools) et l'aperçu des étapes de SM36. `Read Abap List` reconstruit
les lignes par la géométrie et jette les cellules vides : une ligne à trou y
décale toutes ses valeurs d'une colonne, et la ligne « liste vide » d'une
liste sans donnée sort comme une donnée, donc compter ses lignes ne prouve
rien. Ces listes portent pourtant leur structure dans leurs identifiants
(``lbl[<colonne>,<ligne>]``, case ``chk[1,<ligne>]`` sur chaque ligne de
données). `Read Abap List Rows` s'en sert ; `Select Abap List Row` coche la
case de la ligne voulue (le préalable de « Job > Delete » dans SM37 et de
« Display contents » dans SP01) et relit son état.

`Read Abap List` reste tel quel (compatibilité). Logique pure dans
``sapfx_common.abap_list``.
"""
from pythoncom import com_error
from robot.api import logger

from sapfx_common.abap_list import aligned_rows, matching_rows


class AbapListKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose ``self.session`` connectée."""

    def read_abap_list_rows(self, header="auto", rows="auto"):
        """Lit la liste classique affichée en *lignes alignées sur l'en-tête* :
        une liste de dicts ``{titre d'en-tête: valeur}`` où chaque cellule est
        rattachée à sa colonne par la COLONNE de son identifiant
        (``lbl[64,13]``), une cellule absente valant ``""``, plus ``_row``
        (ligne de liste), ``_selectable`` et ``_checkbox`` (identifiant de la
        case de sélection, vide sans case).

        ``header`` : ``auto`` (dans une liste à cases, la ligne SANS case,
        au-dessus des lignes à case, dont les cellules commencent aux mêmes
        colonnes que celles des lignes à case qui la suivent, puis la plus
        fournie : le rappel des critères de SM37 porte lui aussi des cases,
        et la ligne d'information de la liste SE16 standard porte plus de
        cellules que l'en-tête ; sans case, la première ligne d'au moins
        deux cellules), le TEXTE d'une cellule d'en-tête, ou le numéro de sa
        ligne de liste. ``rows`` :
        ``selectable`` (seules les lignes à case : une liste sélectionnable
        SANS donnée rend ``[]``), ``all``, ou ``auto`` (``selectable`` si la
        liste porte des cases, sinon toutes les lignes sous l'en-tête moins
        les lignes de MESSAGE, reconnues à leur forme : une seule cellule
        qui recouvre plusieurs colonnes).

        Les titres d'en-tête sont des textes LOCALISÉS : les nommer appartient
        au page object, jamais à une suite. Lecture seule.

        Exemple :
        | ${rows}=    `Read Abap List Rows`
        | Should Be Equal    ${rows}[0][CARRID]    AA
        | Should Be True    ${rows}[0][_selectable]
        """
        result = aligned_rows(self._screen_elements(), header=header, rows=rows)
        for skipped in result["ignored"]:
            logger.info("Ligne %s de la liste ignorée (une cellule sur "
                        "plusieurs colonnes : message, pas une donnée) : %r"
                        % (skipped["_row"], skipped["text"]))
        return result["rows"]

    def select_abap_list_row(self, text, column=None, header="auto"):
        """Coche la case de sélection de la ligne dont une cellule vaut
        EXACTEMENT ``text`` (dans la colonne d'en-tête ``column`` si elle est
        donnée), RELIT la case, et rend la ligne (dict de `Read Abap List
        Rows`).

        Aucune ligne = échec listant un échantillon des valeurs (de la
        colonne, ou des premières cellules) ; plusieurs lignes = échec les
        listant, jamais la première venue ; ligne sans case = échec. Le
        préalable des actions de liste (« Job > Delete » de SM37, « Display
        contents » de SP01), qui agissent sur les lignes COCHÉES.

        Exemple :
        | ${row}=    `Select Abap List Row`    LH    column=CARRID
        | Should Be Equal    ${row}[CARRNAME]    Lufthansa
        """
        rows = self.read_abap_list_rows(header=header, rows="selectable")
        found = matching_rows(rows, text, column)
        if not found:
            sample = [row.get(column, "") if column else
                      next((v for k, v in row.items() if not k.startswith("_") and v), "")
                      for row in rows[:10]]
            raise AssertionError(
                "Aucune ligne sélectionnable de la liste ne porte %r%s (%d lignes ; "
                "échantillon : %s)." % (text, " dans la colonne %r" % column if column else "",
                                        len(rows), sample))
        if len(found) > 1:
            raise AssertionError(
                "%d lignes portent %r%s (lignes de liste %s) : préciser column=."
                % (len(found), text, " dans la colonne %r" % column if column else "",
                   [row["_row"] for row in found]))
        row = found[0]
        try:
            box = self.session.findById(row["_checkbox"])
            box.selected = True
            selected = bool(box.selected)
        except (AttributeError, com_error) as exc:
            raise AssertionError("La case %s de la ligne %s ne se coche pas : %s"
                                 % (row["_checkbox"], row["_row"], exc)) from exc
        if not selected:
            raise AssertionError("La case %s relue décochée après sélection."
                                 % row["_checkbox"])
        return row
