"""Types métier d'arguments de keywords, les petits (backlog 2.75, 2026-10-14).

Comme ``VirtualKey``, ``NameList`` et ``GuiElementId`` : un type que Robot
convertit et que Libdoc publie avec sa documentation, pour dire à un lecteur, à
un agent MCP et à l'atelier ce qu'un argument attend. Chacun rend la valeur
INCHANGÉE (le corps du keyword la normalise comme avant, un appel Python direct
ne passant pas par la conversion) et ne refuse que ce qui ne pouvait pas
marcher, en le disant.

- ``ScreenRef`` : une référence ``@N`` d'une carte numérotée d'écran ou de page ;
- ``FlpIntent`` : un intent de launchpad ``SemanticObject-action`` ;
- ``Ui5Xpath`` : une XPath sur l'arbre des contrôles UI5 (moteur ``xpath``) ;
- ``IdocNumber`` : un numéro d'IDoc (``EDIDC-DOCNUM``) ;
- ``SpoolId`` : un numéro de demande de spool (``TSP01-RQIDENT``) ;
- ``ODataPath`` et ``ODataServicePath`` : un chemin de ressource OData et la
  racine d'un service (backlog 2.83) ;
- ``RfcFunctionName`` et ``TableName`` : un module fonction appelé à distance et
  une table ou vue du dictionnaire (backlog 2.83).

Ces quatre derniers, comme ``TransactionCode`` (module ``transaction_code``) et
``FlpIntent``, disent aux outils de couverture ce qu'un argument TOUCHE : la
règle de lecture vit dans ``touch_targets``.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional, Union

from sapfx_common.idoc import normalize_docnum
from sapfx_common.spool import spool_id_argument

_REF = re.compile(r"^\s*@?\d+\s*$")


def require_screen_ref(value: object) -> str:
    text = str(value)
    if not _REF.match(text):
        raise ValueError(
            "%r n'est pas une référence de carte : un numéro, avec ou sans @ (@3 ou 3), "
            "tel que l'affiche une carte numérotée." % text)
    return text


def require_flp_intent(value: object) -> str:
    text = str(value)
    if not text.strip():
        raise ValueError("Intent de launchpad vide : donner SemanticObject-action, "
                         "par exemple EPMPurchaseOrder-approve.")
    return text


def require_ui5_xpath(value: object) -> str:
    text = str(value)
    if not text.strip().startswith(("/", "(", ".")):
        raise ValueError(
            "%r n'est pas une XPath de l'arbre UI5 : elle commence par / (//Button[@text='Edit'], "
            "//Table//Button) ; Get Ui5 Xpath rend la plus courte qui désigne un contrôle." % text)
    return text


def require_idoc_number(value: object) -> Optional[str]:
    if value is None:
        return None
    normalize_docnum(value)
    return str(value)


def require_spool_id(value: object) -> str:
    spool_id_argument(value)
    return str(value)


def _require_text(value: object, what: str, example: str) -> str:
    text = str(value)
    if not text.strip():
        raise ValueError("%s vide : donner %s." % (what, example))
    return text


def require_odata_path(value: object) -> str:
    return _require_text(value, "Chemin OData", "le chemin de la ressource, par exemple "
                         "/sap/opu/odata/sap/SEPMRA_SHOP/Products")


def require_odata_service_path(value: object) -> str:
    return _require_text(value, "Chemin de service OData", "la racine du service, par exemple "
                         "/sap/opu/odata/sap/SEPMRA_SHOP")


def require_function_name(value: object) -> str:
    return _require_text(value, "Nom de module fonction", "le module à appeler, par exemple "
                         "RFC_READ_TABLE")


def require_table_name(value: object) -> str:
    return _require_text(value, "Nom de table", "la table ou la vue du dictionnaire, par "
                         "exemple T000")


class ScreenRef(str):
    """Référence d'une cible de la carte numérotée : son numéro, avec ou sans
    ``@`` (``@3`` ou ``3``), tel que l'affiche la carte. Une référence ne vaut que pour la DERNIÈRE
    perception : l'écran changé, elle est refusée en nommant la re-perception.
    """

    # Convertisseurs sans docstring : Libdoc publierait la leur à la place du
    # contrat de la classe. Ils rendent une chaîne ORDINAIRE, celle reçue.
    @classmethod
    def from_value(cls, value: str | int) -> str:
        return require_screen_ref(value)


class FlpIntent(str):
    """Intent de navigation d'un launchpad Fiori : ``SemanticObject-action``
    (``EPMPurchaseOrder-approve``), avec ou sans ``#``, paramètres compris
    (``Object-display?id=1`` est un autre intent que ``Object-display``). Le
    hash stable d'une application, indépendant du catalogue, du thème et de la
    langue.
    """

    @classmethod
    def from_value(cls, value: str) -> str:
        return require_flp_intent(value)


class Ui5Xpath(str):
    """XPath sur l'arbre des contrôles UI5 (moteur ``xpath``), par exemple
    ``//Table//Button[@text='Edit']`` ou ``//Page//SearchField`` : les nœuds
    sont les types courts des contrôles, les attributs leurs propriétés.
    `Get Ui5 Xpath` rend la plus courte XPath qui désigne un contrôle.
    """

    @classmethod
    def from_value(cls, value: str) -> str:
        return require_ui5_xpath(value)


class IdocNumber(str):
    """Numéro d'un IDoc (``EDIDC-DOCNUM``) : des chiffres, 16 au plus, avec ou
    sans les zéros de tête (``7`` et ``0000000000000007`` désignent le même
    IDoc). Celui que rend la CLÔTURE de `Create Outbound Idoc`, jamais
    l'identifiant provisoire de l'ouverture.
    """

    @classmethod
    def from_value(cls, value: str | int | None) -> str | None:
        return require_idoc_number(value)


class SpoolId(str):
    """Numéro d'une demande de spool (``TSP01-RQIDENT``) : un entier
    strictement positif, avec ou sans zéros de tête (``23203`` ou
    ``0000023203``), tel que le rend `Get Job Spool Requests`.
    """

    @classmethod
    def from_value(cls, value: str | int) -> str:
        return require_spool_id(value)


class ODataPath(str):
    """Chemin d'une ressource OData : l'entity set d'un service, avec sa clé et
    sa navigation s'il y en a, par exemple
    ``/sap/opu/odata/sap/SEPMRA_SHOP/Products`` ou
    ``/sap/opu/odata/sap/API_BUSINESS_PARTNER/A_BusinessPartner('1000')``. Le
    service et l'entity set sont dans le chemin : c'est ce que lisent les outils
    de couverture. Un chemin relatif est résolu contre l'adresse de la session,
    une adresse complète doit rester sur son origine ; la requête
    (``?$filter=...``) peut suivre. Un chemin vide est refusé avant tout appel.
    """

    @classmethod
    def from_value(cls, value: str) -> str:
        return require_odata_path(value)


class ODataServicePath(str):
    """Racine d'un service OData : ``/sap/opu/odata/sap/SEPMRA_SHOP`` (v2),
    ``/sap/opu/odata4/sap/<binding>/srvd_a2x/sap/<service>/0001`` (v4), ou le
    chemin d'un service CAP (``/processor``). C'est l'adresse dont le
    ``$metadata`` décrit les entity sets. Un chemin vide est refusé avant tout
    appel.
    """

    @classmethod
    def from_value(cls, value: str) -> str:
        return require_odata_service_path(value)


class RfcFunctionName(str):
    """Nom d'un module fonction ABAP appelé à distance (RFC ou BAPI) :
    ``RFC_READ_TABLE``, ``BAPI_USER_GET_DETAIL``, ``STFC_CONNECTION``. Un nom
    vide est refusé avant tout appel.
    """

    @classmethod
    def from_value(cls, value: str) -> str:
        return require_function_name(value)


class TableName(str):
    """Nom d'une table ou d'une vue du dictionnaire ABAP : ``T000``, ``SCARR``,
    ``SNWD_PD``, ``/DMO/CARRIER``. C'est la table que le keyword lit, ouvre ou
    décrit, jamais un fichier. Un nom vide est refusé avant tout appel.
    """

    @classmethod
    def from_value(cls, value: str) -> str:
        return require_table_name(value)


#: Les annotations des keywords : le type à l'exécution (Robot convertit,
#: Libdoc publie), une chaîne pour mypy (les appels Python directs).
if TYPE_CHECKING:
    ScreenRefInput = str
    FlpIntentInput = str
    Ui5XpathInput = str
    IdocNumberInput = Union[str, int]
    OptionalIdocNumberInput = Optional[Union[str, int]]
    SpoolIdInput = Union[str, int]
    ODataPathInput = str
    ODataServicePathInput = str
    RfcFunctionNameInput = str
    TableNameInput = str
else:
    ScreenRefInput = ScreenRef
    FlpIntentInput = FlpIntent
    Ui5XpathInput = Ui5Xpath
    # Le convertisseur garde None : une union ferait perdre son message.
    IdocNumberInput = OptionalIdocNumberInput = IdocNumber
    SpoolIdInput = SpoolId
    ODataPathInput = ODataPath
    ODataServicePathInput = ODataServicePath
    RfcFunctionNameInput = RfcFunctionName
    TableNameInput = TableName

CONVERTERS = {ScreenRef: ScreenRef.from_value, FlpIntent: FlpIntent.from_value,
              Ui5Xpath: Ui5Xpath.from_value}
#: Le nom d'une table de dictionnaire s'emploie sur deux canaux (l'écran SE16 et
#: le RFC) : un seul convertisseur, enregistré par les deux bibliothèques
#: (`SapEccLibrary` le déclare lui-même, `SapApiLibrary` par ``API_CONVERTERS``).
API_CONVERTERS = {IdocNumber: IdocNumber.from_value, SpoolId: SpoolId.from_value,
                  ODataPath: ODataPath.from_value,
                  ODataServicePath: ODataServicePath.from_value,
                  RfcFunctionName: RfcFunctionName.from_value,
                  TableName: TableName.from_value}
