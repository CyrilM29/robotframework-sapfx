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
from typing import TYPE_CHECKING, Any

from pythoncom import com_error
from robot.api import logger

from sapfx_common.abap_list import (aligned_rows, attach_icons, find_list_cell, list_cells,
                                    list_summary, matching_rows)


class AbapListKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose ``self.session`` connectée."""

    if TYPE_CHECKING:
        # Contrat du composite (SapEccLibrary), pour mypy seulement : les
        # keywords annotés (type GuiElementId) font vérifier leurs corps.
        def _screen_elements(self, *args: Any, **kwargs: Any) -> Any: ...
        def wait_until_busy_done(self, *args: Any, **kwargs: Any) -> Any: ...
        session: Any

    def read_abap_list_rows(self, header="auto", rows="auto", icons: bool = False):
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
        deux cellules ; jamais une ligne ENCADRÉE, bloc de synthèse ou
        message, comme « Number of Entries Displayed » en tête de SM58 et de
        SMQ1, voir `Read Abap List Summary`), le TEXTE d'une cellule
        d'en-tête, ou le numéro de sa ligne de liste. Une liste qui ne porte
        que des lignes encadrées (SM58 sans sélection, SMQ1 vide : « Nothing
        was selected. ») rend ``[]``, le message journalisé. ``rows`` :
        ``selectable`` (seules les lignes à case : une liste sélectionnable
        SANS donnée rend ``[]``), ``all``, ou ``auto`` (``selectable`` si la
        liste porte des cases, sinon toutes les lignes sous l'en-tête moins
        les lignes de MESSAGE, reconnues à leur forme : une seule cellule
        qui recouvre plusieurs colonnes).

        ``icons=True`` ajoute à chaque ligne ``_icons`` : ``{titre d'en-tête:
        nom d'icône}`` des cellules SANS texte qui portent une icône. Une liste
        classique rend souvent un état par une icône seule (la colonne
        « Actv » de SMICM : ``S_OKAY`` sur un service actif, rien sur un
        inactif), que le texte de la cellule, vide dans les deux cas, ne
        distingue pas ; le nom d'icône est technique, donc locale-safe. Un
        appel COM par CHAQUE cellule vide des lignes rendues, toutes colonnes
        confondues (une cellule vide sans icône rend simplement ``""``) ; une
        icône ILLISIBLE fait échouer toute la lecture en nommant la cellule,
        même hors de la colonne qui intéresse l'appelant, jamais lue comme une
        absence.

        Les titres d'en-tête sont des textes LOCALISÉS : les nommer appartient
        au page object, jamais à une suite. Lecture seule.

        Exemple :
        | ${rows}=    `Read Abap List Rows`
        | Should Be Equal    ${rows}[0][CARRID]    AA
        | Should Be True    ${rows}[0][_selectable]
        | `Run Transaction`    SMICM
        | `Click Application Toolbar Button`    B_INTF
        | ${services}=    `Read Abap List Rows`    icons=True
        | Should Be Equal    ${services}[1][_icons][Actv]    S_OKAY
        """
        elements = self._screen_elements()
        result = aligned_rows(elements, header=header, rows=rows)
        for skipped in result["ignored"]:
            logger.info("Ligne %s de la liste ignorée (une cellule sur "
                        "plusieurs colonnes : message, pas une donnée) : %r"
                        % (skipped["_row"], skipped["text"]))
        if str(icons).strip().lower() not in ("true", "yes", "1"):
            return result["rows"]
        wanted_rows = {int(row["_row"]) for row in result["rows"]}
        found = {}
        unreadable = []
        for cell in list_cells(elements):
            if cell.kind != "lbl" or cell.text or cell.row not in wanted_rows:
                continue
            try:
                # la PROPRIÉTÉ est lue dans le try, jamais par un getattr à
                # défaut : un proxy sur un thread étranger lève AttributeError
                # sur IconName, et ce défaut se lirait « aucune icône »
                icon = str(self.session.findById(cell.id).IconName or "")
            except (AttributeError, com_error) as exc:
                # une icône illisible n'est jamais « aucune icône » : l'absence
                # d'icône PORTE une valeur (« Actv » vide = service inactif)
                unreadable.append("%s (%s)" % (cell.id, exc))
                continue
            if icon:
                found[cell.id] = icon
        if unreadable:
            raise AssertionError(
                "Read Abap List Rows icons=True : %d cellule(s) dont l'icône n'a pas pu être "
                "lue, donc impossible à distinguer d'une cellule sans icône : %s"
                % (len(unreadable), ", ".join(unreadable[:10])))
        return attach_icons(result, found)

    def read_abap_list_summary(self):
        """Lit le bloc de synthèse ENCADRÉ en tête de la liste classique
        affichée : une entrée ``{row, label, value}`` par ligne, dans l'ordre,
        une ligne de titre rendant ``value`` vide.

        Les moniteurs SM58, SMQ1 et SMQ2 y portent leurs compteurs (« Number
        of Entries Displayed », « Number of failed entries ») : ce sont eux, et
        non les lignes de la liste, qui disent combien d'entrées le moniteur
        a sélectionnées (SM58 n'affiche ses données qu'une ligne sur deux). Une
        liste SANS bloc rend ``[]``, jamais une erreur : c'est la forme de SM58
        lancé avec ses réglages par défaut, qui ne montre que « Nothing was
        selected. ». Les libellés sont localisés : les nommer appartient au
        page object ; les valeurs restent du texte. Lecture seule.

        Exemple :
        | `Run Transaction`    SMQ1
        | `Send Vkey`    F8
        | ${summary}=    `Read Abap List Summary`
        | Length Should Be    ${summary}    3
        """
        return list_summary(self._screen_elements())

    def double_click_abap_list_cell(self, text, column=None, header="auto"):
        """Double-clique (F2) sur la cellule d'une ligne de la liste classique
        affichée dont le texte vaut EXACTEMENT ``text`` (dans la colonne
        d'en-tête ``column`` si elle est donnée), puis VÉRIFIE que l'écran a
        changé : nouveau niveau de liste (SMQ2 : la file, puis ses LUW),
        écran de détail ou fenêtre. Rend l'identifiant de la cellule visée.

        Aucune cellule ou plusieurs = échec listant un échantillon ou les
        candidats, jamais la première venue ; un double-clic qui ne change
        rien échoue en le disant. Le geste ne fait que NAVIGUER dans une liste
        de lecture : une action (exécuter, supprimer) reste un bouton à
        presser explicitement.

        Exemple :
        | ${cell}=    `Double Click Abap List Cell`    LH    column=CARRID
        | `Send Vkey`    F3
        """
        elements = self._screen_elements()
        try:
            cell = find_list_cell(elements, text, column=column, header=header)
        except ValueError as exc:
            raise AssertionError(str(exc)) from exc
        before = [(item.id, item.text) for item in elements]
        try:
            self.session.findById(cell.id).setFocus()
            self.session.findById("wnd[0]").sendVKey(2)
        except (AttributeError, com_error) as exc:
            raise AssertionError("Double-clic impossible sur %s : %s" % (cell.id, exc)) from exc
        self.wait_until_busy_done()
        after = [(item.id, item.text) for item in self._screen_elements()]
        if after == before:
            raise AssertionError(
                "Le double-clic sur %s (%r) n'a rien ouvert : l'écran est inchangé."
                % (cell.id, text))
        return cell.id

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
