"""Mixin actions et lectures de controles UI5.

`Click Ui5 Control` / `Click Ui5 By Xpath` / `Fill Ui5 Input` (l'element
INTERACTIF interne vise, jamais la racine composite), `Read Ui5 Table`
(miroir de `Read Grid` cote ECC), `Upload File Via Ui5`, et les lectures :
`Get Ui5 Text` (ce que le navigateur AFFICHE, exige la visibilite) face a
`Get Ui5 Property`/`Get Ui5 Properties` (la propriete au registre :
propriete inconnue = echec listant les proprietes disponibles) et
`Ui5 Text Should Be`.

Extrait de ``SapFioriLibrary.py`` (convention #13).
"""
import json

from robot.api import logger

from sapfx_common.secrets import reveal_secret

from .._ui5_js import (
    READ_PROPERTY_JS,
    READ_TABLE_JS,
    RESOLVE_ROLE_JS,
)
from .._ui5_runtime import (
    build_control_selector,
    selector_to_json,
    table_read_verdict,
)




class ActionKeywords:
    """Mixin compose dans :class:`SapFioriLibrary` (voir ce module).
    Suppose la page active de Browser accessible via ``self._browser()``
    et la plomberie de ``_base.py`` disponible par composition."""

    # -- raccourcis d'interaction ---------------------------------------------

    def click_ui5_control(self, index=0, **selector_parts):
        """Résout le contrôle et clique dessus via la bibliothèque Browser.

        Re-résout puis re-clique en cas d'échec transitoire : entre la résolution et
        le clic, une vue Fiori peut se redessiner et invalider l'élément (*stale
        element*). Chaque tentative repart d'une résolution fraîche."""
        self._act_with_retry(
            lambda: self._browser().click(
                self.resolve_ui5_control(index=index, **selector_parts)),
            "click %s" % (selector_parts or "index %s" % index))

    def click_ui5_by_xpath(self, xpath, index=0):
        """Résout un **UI5 XPath hiérarchique** puis clique le contrôle obtenu.

        Pendant de `Click Ui5 Control` pour les localisateurs XPath (ex. cibler un
        bouton à l'intérieur d'un dialogue : ``//Dialog//Button[@text='OK']``).
        Re-résout à chaque tentative pour absorber un re-rendu (*stale element*)."""
        self._act_with_retry(
            lambda: self._browser().click(self.resolve_ui5_by_xpath(xpath, index=index)),
            "click xpath %s" % xpath)

    def fill_ui5_input(self, text, index=0, **selector_parts):
        """Résout un champ de saisie UI5 et le remplit avec ``text`` via Browser.

        Les champs UI5 composites (``sap.m.Input``, ``SearchField``…) rendent un élément
        interne ``<input>``/``<textarea>`` ; on s'y positionne, il est impossible de saisir
        directement dans le ``<div>`` racine du contrôle. Re-résout puis ré-essaie en
        cas d'échec transitoire (*stale element* après re-rendu).

        ``text`` accepte le type ``Secret`` de Robot Framework 7.4
        (``-v "PASSWORD: Secret:…"``) : il est déballé ICI, à la frontière du
        navigateur, jamais dans la couche Robot appelante (où un
        ``getattr(value, 'value', value)`` sortait le secret dans l'espace des
        variables de la suite). Baisser le niveau de log autour de l'appel
        reste à la charge de l'appelant, comme pour toute saisie sensible.
        """
        text = reveal_secret(text)

        def _fill():
            selector = build_control_selector(**selector_parts)
            ids = self._resolve(RESOLVE_ROLE_JS, selector_to_json(selector), str(selector))
            if not ids:
                raise AssertionError(
                    "No UI5 control matched %s on the current page.%s"
                    % (selector, self._relaxed_hint(selector_parts)))
            dom_id = self._pick_id(ids, int(index), selector)
            attr = '[id="%s"]' % dom_id
            self._browser().fill_text(
                self._scoped_selector("css=%s input, %s textarea" % (attr, attr)), text)
        self._act_with_retry(_fill, "fill %s" % (selector_parts or "index %s" % index))

    def read_ui5_table(self, index=0, **selector_parts):
        """Lit une table UI5 en une liste de dicts ``[{en-tête: valeur, ...}]``.

        Pendant Fiori de `Read Grid` (ECC). Résout la table (``sap.m.Table`` ou
        ``sap.ui.table.Table``) puis extrait ses lignes via le bundle : clés = textes
        d'en-tête de colonne (ou ``col<i>`` à défaut). Ne lit que les lignes
        **instanciées** : ``sap.ui.table.Table`` virtualise, faire défiler d'abord
        pour les grandes tables. Les lignes d'en-tête de groupe sont ignorées.

        Une table vraiment vide rend une liste vide, mais un contrôle dont les
        lignes ne se lisent pas par ce contrat ÉCHOUE en le nommant, au lieu de
        rendre la même liste vide : les deux situations sont indiscernables pour
        l'appelant, et la seconde produit un test vert qui n'affirme rien (relevé
        live sur la ``sap.ui.documentation.LightTable`` du Demo Kit OpenUI5, où le
        sélecteur résout pourtant exactement un contrôle porteur de ses lignes).
        L'échec renvoie alors vers la lecture au registre (`Get Ui5 Control Info`,
        `Get Ui5 Aggregation Info`, `Get Ui5 Properties`), la voie des tables qui
        ne suivent pas le contrat.
        """
        selector = build_control_selector(**selector_parts)
        ids = self._resolve(RESOLVE_ROLE_JS, selector_to_json(selector), str(selector))
        dom_id = self._pick_id(ids, index, selector, noun="table")
        return table_read_verdict(self._evaluate(READ_TABLE_JS, arg=dom_id), str(selector))


    def upload_file_via_ui5(self, file_path, index=0, **selector_parts):
        """Téléverse ``file_path`` dans un contrôle d'upload UI5
        (``sap.ui.unified.FileUploader``, upload d'une table Fiori Elements…) :
        résout le contrôle (mêmes sélecteurs que `Click Ui5 Control`), vise
        son ``<input type=file>`` interne (le CSS de Playwright perce les
        shadow roots ouverts au passage) et délègue à `Upload File By
        Selector` de Browser. Re-résout et ré-essaie sur échec transitoire
        (*stale element*). Sur une page UI5 Web Components sans runtime
        (moteur *wc*), résoudre l'hôte avec `Resolve Wc Control` puis appeler
        directement `Upload File By Selector` avec ``<chemin> input[type=file]``."""
        def _upload():
            selector = build_control_selector(**selector_parts)
            ids = self._resolve(RESOLVE_ROLE_JS, selector_to_json(selector),
                                str(selector))
            if not ids:
                raise AssertionError(
                    "No UI5 control matched %s on the current page.%s"
                    % (selector, self._relaxed_hint(selector_parts)))
            dom_id = self._pick_id(ids, int(index), selector)
            target = self._scoped_selector(
                'css=[id="%s"] input[type="file"]' % dom_id)
            self._browser().upload_file_by_selector(target, file_path)
        self._act_with_retry(
            _upload, "upload %s" % (selector_parts or "index %s" % index))

    def get_ui5_text(self, index=0, **selector_parts):
        """Résout un contrôle et retourne son texte visible via `Get Text` de Browser."""
        return self._browser().get_text(self.resolve_ui5_control(index=index, **selector_parts))

    def get_ui5_properties(self, property_name, **selector_parts):
        """Lit une PROPRIÉTÉ de contrôle sur **tous** les contrôles qui matchent,
        dans l'ordre du registre, et retourne la liste des valeurs (JSON-safe).

        Le complément de `Get Ui5 Text`, et non son doublon. `Get Ui5 Text` lit ce
        que le navigateur AFFICHE : il exige donc que le contrôle soit VISIBLE, et
        il rend tout ce que le contrôle dessine. Ce keyword lit la valeur portée
        par le contrôle lui-même. Deux différences qui comptent, mesurées live sur
        un launchpad :

        * un ``sap.m.StandardListItem`` qui affiche un compteur rend le texte
          ``"Accessories\\n34"`` alors que sa propriété ``title`` vaut
          ``"Accessories"`` : réinjecter le texte rendu dans un localisateur ne
          matche alors plus rien ;
        * un contrôle rendu mais MASQUÉ (colonne repliée d'un
          ``sap.f.FlexibleColumnLayout``, onglet inactif) n'a pas de texte
          lisible : `Get Text` attend une visibilité qui ne viendra pas et expire,
          ce qui ressemble à tort à une dérive de localisateur.

        Sélecteurs identiques à `Resolve Ui5 Control` (``controlType``,
        ``properties``, ``id``, ``idSuffix``, ``viewId``, ``bindingPath``,
        ``containedIn``). Lire les titres des lignes d'une liste tient alors en
        un appel ::

            ${noms}=    Get Ui5 Properties    title
            ...    controlType=StandardListItem    viewId=container---home--list

        Échoue si la propriété n'existe pas sur un contrôle matché, en listant
        les propriétés disponibles : une faute de frappe se voit tout de suite au
        lieu de rendre une liste de ``None``. Retourne une liste vide quand rien
        ne matche : c'est une lecture, pas une assertion (voir
        `Ui5 Control Should Be Visible` pour exiger une présence).

        Une propriété à valeur TABLEAU (``fieldGroupIds``) rend un vrai tableau
        JSON-safe, jamais sa coercition en chaîne (``[]`` devenait ``''``,
        indiscernable d'une chaîne vide légitime) ; les autres valeurs objet
        restent rendues en chaîne. L'inventaire DÉCLARÉ des propriétés (types,
        défauts, provenance) se lit par `Get Ui5 Control Metadata`.
        """
        selector = build_control_selector(**selector_parts)
        payload = '{"property": %s, "selector": %s}' % (
            json.dumps(str(property_name)), selector_to_json(selector))
        result = self._evaluate(READ_PROPERTY_JS, arg=payload)
        if result is None:
            raise AssertionError(
                "Aucun runtime UI5 sur la portée courante : impossible de lire la "
                "propriété '%s'. Sonder d'abord avec `Ui5 Runtime Is Present`, et "
                "vérifier la portée de frame avec `Get Ui5 Frame Stack`."
                % property_name)
        if result.get("unknown"):
            available = ", ".join(result.get("available") or []) or "aucune"
            raise AssertionError(
                "La propriété '%s' n'existe pas sur le(s) contrôle(s) matché(s) par "
                "%s. Propriétés disponibles : %s."
                % (property_name, selector, available))
        return list(result.get("values") or [])

    def get_ui5_property(self, property_name, index=0, **selector_parts):
        """Lit une PROPRIÉTÉ de contrôle sur le contrôle résolu (``index``, base 0).

        Version « un seul contrôle » de `Get Ui5 Properties`, avec le même contrat
        d'ambiguïté que `Resolve Ui5 Control` : le nombre de correspondances est
        journalisé, et un ``index`` hors bornes échoue en le disant. ::

            ${titre}=    Get Ui5 Property    title    idSuffix=--productList-0
        """
        selector = build_control_selector(**selector_parts)
        values = self.get_ui5_properties(property_name, **selector_parts)
        if not values:
            raise AssertionError(
                "No UI5 control matched %s on the current page.%s"
                % (selector, self._relaxed_hint(selector_parts)))
        if len(values) > 1:
            logger.info("%s matched %s controls; using index %s."
                        % (selector, len(values), index))
        try:
            return values[int(index)]
        except IndexError:
            raise AssertionError(
                "%s matched %s control(s); index %s is out of range."
                % (selector, len(values), index))

    def ui5_text_should_be(self, expected, index=0, **selector_parts):
        """Vérifie que le texte visible du contrôle résolu vaut ``expected``
        (comparaison exacte après trim). C'est l'assertion de VALEUR émise par le
        recorder web (Shift+Alt+clic), pendant de `Ui5 Control Should Be Visible`
        pour le contenu. ::

            Ui5 Text Should Be    42,00 EUR    idSuffix=fe::HeaderInfo::NetAmount
        """
        actual = self.get_ui5_text(index=index, **selector_parts)
        if str(actual).strip() != str(expected).strip():
            raise AssertionError(
                "UI5 control %s text is %r, expected %r."
                % (selector_parts or ("index %s" % index), actual, expected))
