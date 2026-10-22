"""Identifiant d'un élément SAP GUI, type d'argument des keywords (backlog 2.75).

Le troisième type métier, après ``VirtualKey`` et ``NameList`` : 81 keywords
de SapEccLibrary prennent un identifiant de l'API Scripting (``element_id``,
``table_id``, ``tree_id``, ``tabstrip_id``), et aucune spec ne le disait. Le
type le dit à Libdoc, aux agents MCP et à l'atelier (le viseur `@N` s'y
attache), et refuse tôt une valeur qui ne peut pas être un identifiant, avec
le remède quand l'oubli est manifeste (``usr/...`` sans ``wnd[0]/``).

La conversion rend la valeur INCHANGÉE, une chaîne ordinaire : le corps du
keyword et l'appel COM reçoivent exactement ce qu'ils recevaient avant
(convention #4, la surface de robotframework-sapguilibrary est tenue). Seule
une valeur qui ne commence ni par ``wnd[`` ni par ``/app/`` est refusée ; elle
ne pouvait de toute façon pas être trouvée par ``findById``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

#: Ce par quoi commence un identifiant : relatif à la session, ou absolu.
PREFIXES = ("wnd[", "/app/")
#: Les débuts d'identifiant d'une fenêtre, sans la fenêtre : l'oubli courant.
WINDOW_PARTS = ("usr/", "usr", "tbar[", "mbar", "sbar", "titl", "shellcont", "okcd")


def require_gui_element_id(value: object) -> str:
    """``value`` si c'est un identifiant SAP GUI, sinon ``ValueError`` qui dit
    la forme attendue et, quand c'est l'oubli de la fenêtre, le remède."""
    text = str(value)
    stripped = text.strip()
    if not stripped:
        raise ValueError("Identifiant SAP GUI vide : donner un identifiant comme "
                         "wnd[0]/usr/ctxtDATABROWSE-TABLENAME.")
    lowered = stripped.lower()
    if lowered.startswith(PREFIXES):
        return text
    hint = ""
    if lowered.startswith(WINDOW_PARTS):
        hint = " ; la fenêtre manque, voulait-on dire wnd[0]/%s ?" % stripped
    raise ValueError(
        "%r n'est pas un identifiant SAP GUI : il commence par wnd[N] (relatif à la "
        "session, wnd[0]/usr/... ou wnd[1] pour un modal) ou par /app/con[N]/ "
        "(absolu)%s. Pour un libellé visible, employer Find Element By Label."
        % (text, hint))


class GuiElementId(str):
    """Identifiant d'un élément SAP GUI, tel que l'affichent l'enregistreur,
    `Get Screen Signature` et le Scripting Tracker : relatif à la session
    (``wnd[0]/usr/ctxtDATABROWSE-TABLENAME``, ``wnd[1]`` pour un modal,
    ``wnd[0]/usr/cntlGRID1/shellcont/shell`` pour une grille) ou absolu
    (``/app/con[0]/ses[0]/wnd[0]/...``). La valeur passe telle quelle ; une
    valeur qui ne commence ni par ``wnd[`` ni par ``/app/`` est refusée avant
    tout geste, avec ``wnd[0]/`` proposé quand seule la fenêtre manque.
    """

    # Le convertisseur (ROBOT_LIBRARY_CONVERTERS), sans docstring : Libdoc
    # publierait la sienne à la place du contrat ci-dessus. Il rend une
    # chaîne ORDINAIRE, celle qu'il a reçue.
    @classmethod
    def from_value(cls, value: str) -> str:
        return require_gui_element_id(value)


# L'annotation des keywords : GuiElementId à l'exécution (Robot convertit,
# Libdoc publie le type) ; pour mypy, une chaîne, ce que passent les appels
# Python internes (un keyword qui en appelle un autre), qui ne passent pas
# par la conversion.
if TYPE_CHECKING:
    GuiElementIdInput = str
else:
    GuiElementIdInput = GuiElementId
