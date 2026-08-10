"""Mixin de localisateurs « humains » : cibler par libellé visible, pas par id.

Complète les ids techniques (qui restent le chemin nominal dans ``resources/``)
avec l'adressage qu'un utilisateur fonctionnel emploie spontanément : « le champ
à droite du libellé Table », « le bouton Exécuter ». Résolution géométrique pure
dans ``sapfx_common.semantic`` (portée de RoboSAPiens, Apache-2.0, NOTICE) sur
la perception structurée ``_screen_elements`` (chemin rapide ``GetObjectTree``).

Deux garanties de la maison : l'ambiguïté n'est **jamais** tranchée en silence
(échec avec la liste des candidats), et les keywords retournent des **chaînes**
id (jamais l'objet COM : sûr à travers la frontière rf-mcp).
"""
from sapfx_common.semantic import nearby_labels, resolve_semantic, scope_hint
from sapfx_common.vocabulary import lookup_as_dict

# Cibles par défaut de chaque keyword (adressage par famille fonctionnelle).
_INPUT_TYPES = ("GuiTextField", "GuiCTextField", "GuiPasswordField", "GuiComboBox")
# Pas de GuiLabel dans les cibles de lecture : un libellé empilé sous un autre
# serait candidat « dessous » à tort (les valeurs affichées d'un dynpro sont des
# champs non modifiables, déjà couverts). Pour lire un GuiLabel précis :
# `Find Element By Label ... control_types=GuiLabel` puis `Get Value`.
_READ_TYPES = ("GuiTextField", "GuiCTextField", "GuiComboBox",
               "GuiCheckBox", "GuiRadioButton")
# Pas de GuiMenu : SAP duplique les boutons de toolbar dans les menus (même
# texte) : l'inclure rendrait la plupart des boutons ambigus (constaté live sur
# A4H : « Number of Entries » = btn[31] ET menu[1]/menu[10]). Pour un menu :
# `Find Element By Label ... control_types=GuiMenu` puis `Click Element`.
_CLICK_TYPES = ("GuiButton", "GuiTab")

_TRUTHY = ("1", "true", "yes", "on")


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TRUTHY


def _as_types(control_types):
    """``control_types`` Robot : None, liste, ou chaîne ``"GuiButton, GuiTab"``."""
    if control_types in (None, "", "None"):
        return None
    if isinstance(control_types, str):
        return tuple(part.strip() for part in control_types.split(",") if part.strip())
    return tuple(control_types)


def _as_radius(scope_radius):
    """``scope_radius`` Robot : None (défaut du moteur) ou entier en pixels."""
    if scope_radius in (None, "", "None"):
        return None
    return int(scope_radius)


class SemanticKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose ``self.session`` connectée."""

    def find_element_by_label(self, locator, control_types=None, exact=False,
                              scope_radius=None):
        """Résout un localisateur **humain** en id SAP GUI (chaîne, collable partout).

        Grammaire du ``locator`` :
        | ``Table``           | élément ancré au libellé (à droite ou dessous ; les deux à la fois = ambiguïté remontée), sinon élément dont le texte/tooltip correspond |
        | ``@ Table``         | uniquement l'élément SOUS le libellé |
        | ``Gauche @ Haut``   | intersection : à droite de ``Gauche`` ET sous ``Haut`` (grilles de champs) |
        | ``= contenu``       | élément par son texte propre exact |
        | ``N @ Table``       | le N-ième champ (1-based) de la grille verticale sous ``Table`` |
        | ``Table @ N``       | le N-ième champ (1-based) de la grille horizontale à droite de ``Table`` |
        | ``Ancre >> Reste``  | restreint la résolution de ``Reste`` (n'importe quelle forme ci-dessus) au voisinage du libellé ``Ancre`` (doit être unique sur l'écran) : désambiguïse un libellé répété ailleurs, ou identifie un champ sans libellé propre par son tooltip |

        ``exact=False`` (défaut) compare par **préfixe** insensible à la casse,
        pensé pour les tooltips SAP qui finissent par le raccourci (``Exécuter (F8)``).
        ``control_types`` restreint les types cibles (liste ou ``"GuiButton, GuiTab"``).
        ``scope_radius`` (px) étend le voisinage de ``Ancre >> Reste`` au-delà
        du défaut (100 px) quand la cible visée est plus loin de l'ancre :
        c'est une intention de portée, pas une tolérance de rendu ; les
        tolérances d'alignement, elles, restent volontairement non exposées.

        Échoue si aucun élément ne correspond (avec les libellés réellement
        visibles dans le message ; et, pour un ``>>``, le diagnostic de la
        portée : ancre absente/ambiguë ou rayon à élargir) ou si PLUSIEURS
        correspondent (avec la liste des candidats : désambiguïser via
        ``Gauche @ Haut``, ``exact=True`` ou ``control_types``). Jamais de
        premier-match silencieux. Usage type::

            ${id}=    Find Element By Label    Table Name
            Input Text    ${id}    T000
        """
        return self._resolve_semantic_unique(locator, _as_types(control_types),
                                             _as_bool(exact),
                                             scope_radius=_as_radius(scope_radius)
                                             ).element.id

    def fill_field_by_label(self, label, value, exact=False, scope_radius=None):
        """Saisit ``value`` dans le champ désigné par son **libellé** (même
        grammaire que `Find Element By Label`, cibles restreintes aux champs de
        saisie **modifiables** ; un champ en lecture seule, comme le « to » d'un
        selection screen, n'est jamais une cible ni une position de grille).
        Retourne l'id résolu, à journaliser dans ``resources/`` si le
        localisateur a vocation à être stabilisé."""
        eid = self._resolve_semantic_unique(label, _INPUT_TYPES,
                                            _as_bool(exact),
                                            changeable_only=True,
                                            scope_radius=_as_radius(scope_radius)
                                            ).element.id
        self.input_text(eid, value)
        return eid

    def read_field_by_label(self, label, exact=False, scope_radius=None):
        """Retourne la **valeur actuelle** du champ désigné par son libellé
        (relue via COM à l'instant de l'appel, pas depuis la perception).

        Résolution en **cascade** (même principe que la grammaire : la première
        étape qui produit des matches gagne) : d'abord les champs
        **modifiables**, ainsi une position de grille compte les mêmes champs
        que `Find Element By Label` et `Fill Field By Label` (jamais le « to »
        en lecture seule d'un selection screen) ; puis, si aucun, les champs en
        lecture seule : la façon dont un dynpro d'**affichage** montre ses
        valeurs. L'ambiguïté de l'étape gagnante reste remontée, jamais
        tranchée."""
        eid = self._resolve_semantic_unique(label, _READ_TYPES,
                                            _as_bool(exact),
                                            prefer_changeable=True,
                                            scope_radius=_as_radius(scope_radius)
                                            ).element.id
        return self.get_value(eid)

    def click_button_by_label(self, label, exact=False, scope_radius=None):
        """Clique le bouton (ou onglet) désigné par son texte ou son tooltip.
        ``exact=False`` ignore le suffixe raccourci clavier des tooltips SAP
        (``Enregistrer (Ctrl+S)`` matché par ``Enregistrer``). Les entrées de
        menu sont volontairement hors cible (elles dupliquent le texte des
        boutons de toolbar) : passer par `Find Element By Label` avec
        ``control_types=GuiMenu`` pour un menu. Retourne l'id résolu."""
        eid = self._resolve_semantic_unique(label, _CLICK_TYPES,
                                            _as_bool(exact),
                                            scope_radius=_as_radius(scope_radius)
                                            ).element.id
        self.click_element(eid)
        return eid

    def pick_f4_value(self, field_id, value, column=None, timeout=None):
        """Ouvre l'**aide à la recherche** (F4, matchcode) du champ
        ``field_id``, choisit l'entrée ``value`` dans le popup de résultats et
        referme le tout : le geste quotidien « F4 puis double-clic » en un
        keyword. Retourne la valeur du champ après sélection.

        Deux formes de popup couvertes : la **grille** de résultats
        (GuiGridView : la ligne dont une colonne, ou la seule colonne
        ``column`` si son titre est fourni, vaut ``value``, choisie par
        double-clic) et la **liste à labels** (l'entrée au texte exact,
        choisie par F2). Valeur introuvable = popup refermé (F12) puis échec
        listant un échantillon des valeurs disponibles ; popup toujours
        ouvert après le choix (aide F4 à étapes, onglet de restriction) =
        échec nommant `Get Screen Signature` pour piloter ce dialogue par
        ids. La comparaison est exacte, blancs de bordure ignorés."""
        field = self.session.findById(field_id)
        field.SetFocus()
        self.send_vkey(4)
        self.wait_until_busy_done()
        self.wait_until_element_present("wnd[1]", timeout=timeout)
        elements = self._screen_elements()
        wanted = str(value).strip()
        grid = next((el for el in elements if el.type == "GuiGridView"), None)
        if grid is not None:
            picked = self._pick_f4_from_grid(grid.id, wanted, column)
        else:
            picked = self._pick_f4_from_labels(elements, wanted)
        if not picked:
            sample = self._f4_available_values(grid, elements, column)
            self.send_vkey(12, window=1)   # F12 : refermer proprement le popup
            self.wait_until_busy_done()
            self.take_screenshot()
            raise AssertionError(
                "Aucune entrée '%s' dans l'aide F4 de '%s'%s. Valeurs "
                "visibles (extrait) : %s"
                % (value, field_id,
                   " (colonne '%s')" % column if column else "",
                   sample or "aucune lisible"))
        self.wait_until_busy_done()
        if self.session.findById("wnd[1]", False) is not None:
            self.take_screenshot()
            raise AssertionError(
                "L'aide F4 de '%s' est restée ouverte après la sélection de "
                "'%s' (aide à étapes ou onglet de restriction) : piloter ce "
                "dialogue par ids (Get Screen Signature sur la fenêtre "
                "active)." % (field_id, value))
        return self.get_value(field_id)

    # -- helpers (méthodes internes) ------------------------------------------

    def _pick_f4_from_grid(self, grid_id, wanted, column):
        """Cherche ``wanted`` dans la grille de résultats F4 et la choisit par
        double-clic (le geste standard des aides à la recherche). ``column``
        (titre visible) restreint la recherche à une colonne."""
        grid = self.session.findById(grid_id)
        column_ids = list(grid.ColumnOrder)
        if column not in (None, "", "None"):
            column_ids = [self.get_column_id_by_title(grid_id, column)]
        for row in range(int(getattr(grid, "RowCount", 0) or 0)):
            for col_id in column_ids:
                if str(grid.GetCellValue(row, col_id)).strip() == wanted:
                    grid.SetCurrentCell(row, col_id)
                    grid.DoubleClickCurrentCell()
                    return True
        return False

    def _pick_f4_from_labels(self, elements, wanted):
        """Variante liste (aides F4 simples rendues en labels) : focalise
        l'entrée au texte exact puis F2 (« choisir »)."""
        for element in elements:
            if element.type == "GuiLabel" and (element.text or "").strip() == wanted:
                self.session.findById(element.id).SetFocus()
                self.send_vkey(2, window=1)
                return True
        return False

    def _f4_available_values(self, grid_element, elements, column):
        """Échantillon (trié, dédoublonné) des valeurs visibles du popup F4,
        pour rendre l'échec « valeur introuvable » actionnable."""
        values = []
        if grid_element is not None:
            grid = self.session.findById(grid_element.id)
            column_ids = list(grid.ColumnOrder)
            if column not in (None, "", "None"):
                try:
                    column_ids = [self.get_column_id_by_title(grid_element.id,
                                                              column)]
                except ValueError:
                    pass
            for row in range(min(10, int(getattr(grid, "RowCount", 0) or 0))):
                for col_id in column_ids[:1]:
                    values.append(str(grid.GetCellValue(row, col_id)).strip())
        else:
            values = [(el.text or "").strip() for el in elements
                      if el.type == "GuiLabel" and (el.text or "").strip()]
        unique = sorted({value for value in values if value})
        return ", ".join(unique[:10])

    def _resolve_semantic_unique(self, locator, types, exact,
                                 changeable_only=False, scope_radius=None,
                                 prefer_changeable=False):
        """Résolution + exigence d'unicité, avec erreurs auto-corrigibles.

        ``prefer_changeable`` : cascade en deux passes, cibles modifiables
        d'abord (positions de grille alignées sur Find/Fill), repli sur toutes
        les cibles si la première passe ne produit rien (dynpro d'affichage).
        L'ambiguïté de la passe gagnante est remontée, jamais tranchée."""
        elements = self._screen_elements()
        if prefer_changeable and not changeable_only:
            matches = resolve_semantic(elements, locator, types=types,
                                       exact=exact, changeable_only=True,
                                       scope_radius=scope_radius)
            if not matches:
                matches = resolve_semantic(elements, locator, types=types,
                                           exact=exact,
                                           scope_radius=scope_radius)
        else:
            matches = resolve_semantic(elements, locator, types=types,
                                       exact=exact,
                                       changeable_only=changeable_only,
                                       scope_radius=scope_radius)
        if len(matches) == 1:
            return matches[0]
        if not matches:
            scoped = scope_hint(elements, locator, exact=exact,
                                scope_radius=scope_radius)
            hint = "\nPortée '>>' : %s." % scoped if scoped else ""
            labels = nearby_labels(elements)
            if labels:
                hint += "\nLibellés visibles à l'écran :\n%s" % "\n".join(
                    "  - %s" % text for text in labels)
            elif not any(el.left is not None for el in elements):
                hint += ("\n(Aucune géométrie disponible sur cette session, "
                         "GetObjectTree absent et coordonnées illisibles : seuls "
                         "le texte propre et le tooltip peuvent matcher.)")
            self.take_screenshot()
            raise AssertionError(
                "Aucun élément ne correspond au libellé '%s'.%s" % (locator, hint))
        self.take_screenshot()
        candidates = "\n".join(
            "  - %s  (%s, via %s)" % (m.element.id, m.element.type, m.via)
            for m in matches)
        raise AssertionError(
            "Libellé '%s' ambigu : %d éléments correspondent. Désambiguïser "
            "avec 'Gauche @ Haut', exact=True ou control_types.\nCandidats :\n%s"
            % (locator, len(matches), candidates))

    def lookup_business_term(self, term, domain=None, threshold=0.8):
        """Résout un **terme métier** (français ou anglais, synonymes compris)
        vers sa fiche SAP : canonique, champ ABAP, table de référence, domaine.

        Le pont entre la langue d'un plan de test (« le fournisseur », « la
        compagnie aérienne ») et les champs techniques des écrans de sélection
        (LIFNR, CARRID…), utilisé tel quel par les agents sap-planner /
        sap-generator. Vocabulaire partagé ECC↔Fiori
        (``sapfx_common.vocabulary``, concept issu de playwright-praman,
        Apache-2.0, NOTICE) : MM/SD/FI + modèle Flight de démo (nos suites
        SE16). Ambiguïté ou score sous ``threshold`` = échec listant les
        candidats, jamais de premier-match silencieux. ``domain`` restreint
        au module. Dict JSON-safe (rf-mcp)."""
        return lookup_as_dict(term, domain=domain, threshold=float(threshold))
