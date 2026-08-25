"""Mixin assertions visuelles : hash perceptuel et baselines d'ecran.

Le *snapshot testing* du canal pixels (dHash pur dans
``sapfx_common.visual_hash``, semantique snapshot partagee avec Fiori dans
``sapfx_common.visual_baseline``, Pillow a la frontiere, extra ``visual``) :
`Get Screen Perceptual Hash` (``mask_elements=auto`` neutralise sbar/titl),
`Screen Should Match Baseline` (``per_resolution=True`` = une baseline par
geometrie de capture), la declinaison PAR ELEMENT (`Get Element Perceptual
Hash` / `Element Should Match Baseline` : les 64 bits couvrent la seule zone
visee) et `Get Screen Tile Hashes` (grille 4x4 : la derive se localise).

Extrait de ``_perception.py`` (convention #13) : couvre ce que l'API
Scripting ne voit pas (GuiShell opaques, charts record-only).
"""
import base64

from robot.api import logger


class VisualKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Lecture seule : capture et
    compare, ne modifie aucun écran."""

    def get_screen_perceptual_hash(self, hash_size=8, mask_elements=None):
        """Capture la fenêtre SAP active et retourne son **hash perceptuel**
        (dHash hexadécimal, ``hash_size²`` bits, voir
        ``sapfx_common.visual_hash``).

        Le canal *pixels* de la perception : couvre précisément ce que l'API
        Scripting ne voit pas (GuiShell des listes modernes sans mode
        accessibilité, GuiChart/GuiMap officiellement record-only). Deux écrans
        visuellement identiques donnent le même hash ; un petit écart local, une
        distance de Hamming faible (`Screen Should Match Baseline` fait
        l'assertion).

        ``mask_elements`` **neutralise les zones légitimement volatiles** avant
        hachage (remplies de gris neutre) : ``auto`` masque la barre de statut
        et la barre de titre (l'horloge, le titre localisé : les sources
        classiques de faux positifs des snapshots), ou une liste d'ids séparés
        par des virgules pour masquer des régions choisies. Un id absent de
        l'écran est journalisé et ignoré (le masque est déclaratif, pas une
        assertion).

        Nécessite Pillow (``pip install Pillow``, extra ``visual`` du paquet)
        pour décoder le PNG ; l'algorithme lui-même est pur et testé hors SAP."""
        png = base64.b64decode(self.get_screenshot_as_base64("png"))
        pixels = self._decode_image_to_gray(png)
        regions = self._mask_regions_for(mask_elements)
        if regions:
            from sapfx_common.visual_hash import mask_regions
            pixels = mask_regions(pixels, regions)
        from sapfx_common.visual_hash import dhash_hex
        return dhash_hex(pixels, int(hash_size))

    def get_element_perceptual_hash(self, element_id, hash_size=8):
        """Hash perceptuel de la **région d'UN élément** (dHash hexadécimal),
        l'assertion visuelle ciblée là où elle a le plus de valeur : la grille
        dHash couvre l'élément seul au lieu de l'écran entier, donc un
        changement DANS un GuiShell opaque ou un GuiChart pèse sur tous les
        bits au lieu d'être dilué dans l'écran (sur une grille typique, la
        sensibilité gagne un facteur ~50).

        La région vient de `Get Element Screen Region` (le même relevé que
        l'effecteur coordonnées), convertie dans le repère de la capture de
        fenêtre. Échec explicite si l'élément n'existe pas ou sort de la
        capture. Voir `Element Should Match Baseline` pour l'assertion
        snapshot."""
        png = base64.b64decode(self.get_screenshot_as_base64("png"))
        pixels = self._decode_image_to_gray(png)
        region = self._element_image_region(element_id)
        from sapfx_common.visual_hash import crop_pixels, dhash_hex
        return dhash_hex(crop_pixels(pixels, region), int(hash_size))

    def get_screen_tile_hashes(self, tiles_x=4, tiles_y=4, hash_size=8):
        """Empreintes perceptuelles **par tuile** : la fenêtre est découpée en
        grille ``tiles_x × tiles_y`` (défaut 4×4) et chaque tuile reçoit son
        propre dHash. Retourne la liste des hex, ligne par ligne.

        Là où le hash global dilue un changement local dans l'écran entier, la
        grille le **localise** : comparer deux passages tuile à tuile
        (``sapfx_common.visual_hash.tiled_hamming``) dit *où* l'écran a bougé.
        C'est le canal fin de la sentinelle (`Check Screen Against Watch`
        l'utilise automatiquement) ; exposé ici pour les diagnostics manuels."""
        png = base64.b64decode(self.get_screenshot_as_base64("png"))
        pixels = self._decode_image_to_gray(png)
        from sapfx_common.visual_hash import tiled_dhash
        return tiled_dhash(pixels, int(tiles_x), int(tiles_y), int(hash_size))

    def screen_should_match_baseline(self, name, threshold=5,
                                     baseline_directory="visual_baselines",
                                     hash_size=8, mask_elements=None,
                                     per_resolution=False):
        """Assertion de **non-régression visuelle** de la fenêtre SAP active,
        sémantique *snapshot testing* :

        * premier passage (aucune baseline ``<name>.png``) : la capture devient
          la baseline. WARNING journalisé, le test passe (à committer si le
          rendu fait référence) ;
        * passages suivants : distance de Hamming entre le hash perceptuel de
          l'écran et celui recalculé depuis la baseline ; ``<= threshold``
          (défaut 5 sur 64 bits) = succès, sinon échec **auto-corrigible** :
          distance mesurée, chemins de la baseline et de la capture
          ``<name>.actual.png`` sauvegardée à côté pour comparaison, et le
          remède (supprimer la baseline si le changement est voulu).

        ``mask_elements`` (``auto`` ou ids séparés par des virgules) neutralise
        les zones volatiles AVANT hachage, identiquement pour la baseline et la
        capture : voir `Get Screen Perceptual Hash`. C'est le remède nominal à
        une baseline qui échoue à cause de l'horloge de la barre de statut.

        ``per_resolution=True`` garde **une baseline par géométrie de capture**
        (``<name>@1920x1032.png``) : la même suite devient comparable sur des
        postes qui n'affichent pas pareil, chacun face à sa propre référence,
        au lieu d'échouer sur une dérive qui n'est que d'échelle (une empreinte
        perceptuelle encode la géométrie autant que le contenu). Un poste sans
        référence pour sa géométrie en crée une au premier passage, comme au
        premier passage tout court ; une baseline ``<name>.png`` déjà committée
        reste utilisée telle quelle tant que la géométrie coïncide. Sans cette
        option (le défaut), un échec dont les deux géométries diffèrent le
        **dit** dans son message plutôt que de se lire comme une régression.

        ``baseline_directory`` est relatif au répertoire courant du run (le
        committer avec la suite). Le hash est **recalculé depuis le PNG** de la
        baseline à chaque assertion : changer ``hash_size`` (ou le masque)
        reste honnête. Retourne la distance mesurée (0 pour une baseline
        nouvellement créée)."""
        from sapfx_common.visual_baseline import match_baseline
        png = base64.b64decode(self.get_screenshot_as_base64("png"))
        regions = self._mask_regions_for(mask_elements)
        decode = self._decode_image_to_gray
        if regions:
            from sapfx_common.visual_hash import mask_regions
            base_decode = decode

            def decode(image_bytes):
                return mask_regions(base_decode(image_bytes), regions)
        outcome = match_baseline(name, png, decode,
                                 str(baseline_directory), int(threshold),
                                 int(hash_size), what="L'écran",
                                 per_resolution=per_resolution)
        self._log_baseline_outcome(outcome, int(threshold))
        return outcome.distance

    def element_should_match_baseline(self, name, element_id, threshold=5,
                                      baseline_directory="visual_baselines",
                                      hash_size=8, per_resolution=False):
        """Assertion de non-régression visuelle de la **région d'UN élément** :
        même sémantique snapshot que `Screen Should Match Baseline`, mais la
        baseline est le PNG *recadré* sur l'élément : l'assertion est immune à
        tout ce qui change ailleurs sur l'écran (horloge, messages, autres
        champs) et les 64 bits du hash couvrent la seule zone qui compte.

        C'est l'assertion nominale pour les zones que l'API Scripting ne lit
        pas : la grille rendue dans un GuiShell opaque, un GuiChart, une image.
        Exemple::

            Element Should Match Baseline    grille-resultats
            ...    wnd[0]/usr/cntlGRID1/shellcont/shell

        ``per_resolution=True`` : même sémantique par géométrie que
        `Screen Should Match Baseline`, ici la géométrie de la région recadrée
        (un élément n'occupe pas le même nombre de pixels d'un poste à l'autre).

        Retourne la distance mesurée (0 pour une baseline nouvellement créée).
        Échec auto-corrigible avec ``<name>.actual.png`` sauvé à côté."""
        from sapfx_common.visual_baseline import match_baseline
        png = base64.b64decode(self.get_screenshot_as_base64("png"))
        region = self._element_image_region(element_id)
        cropped = self._crop_image(png, region)
        outcome = match_baseline(name, cropped, self._decode_image_to_gray,
                                 str(baseline_directory), int(threshold),
                                 int(hash_size),
                                 what="L'élément %s" % element_id,
                                 per_resolution=per_resolution)
        self._log_baseline_outcome(outcome, int(threshold))
        return outcome.distance

    @staticmethod
    def _log_baseline_outcome(outcome, threshold):
        """Journalisation commune des deux assertions snapshot (création en
        WARNING, un PNG à committer ; conformité en info). La géométrie de
        capture est nommée : c'est elle qui dit à quel poste la référence
        vaut."""
        from sapfx_common.visual_baseline import format_geometry
        where = ("" if outcome.geometry is None
                 else " en %s" % format_geometry(outcome.geometry))
        if outcome.created:
            logger.warn(
                "Baseline visuelle créée (%s), premier passage%s : committer "
                "ce PNG s'il fait référence." % (outcome.baseline_path, where))
        else:
            logger.info("Conforme à la baseline%s (distance %d <= %d)."
                        % (where, outcome.distance, threshold))


    def _element_image_region(self, element_id):
        """Région d'un élément dans le repère de la capture de fenêtre :
        ``(left, top, width, height)``, le relevé écran de `Get Element
        Screen Region` (mixin pointeur), translaté de l'origine de la fenêtre."""
        rect = self.get_element_screen_region(element_id)
        ox, oy = self._window_origin()
        return (rect["left"] - ox, rect["top"] - oy,
                rect["width"], rect["height"])

    # Zones volatiles par défaut du masque ``auto`` : barre de statut (heure,
    # messages) et barre de titre (titre localisé) de la fenêtre principale.
    _AUTO_MASK_IDS = ("wnd[0]/sbar", "wnd[0]/titl")

    def _mask_regions_for(self, mask_elements):
        """Traduit ``mask_elements`` (None / ``auto`` / ids séparés par des
        virgules / liste) en régions du repère capture. Un id absent est
        journalisé et ignoré : le masque décrit des zones à neutraliser, il
        n'affirme pas leur présence."""
        if not mask_elements:
            return []
        if isinstance(mask_elements, str):
            ids = [part.strip() for part in mask_elements.split(",")
                   if part.strip()]
        else:
            ids = [str(part).strip() for part in mask_elements if str(part).strip()]
        if len(ids) == 1 and ids[0].lower() == "auto":
            ids = list(self._AUTO_MASK_IDS)
        ox, oy = self._window_origin()
        regions = []
        for element_id in ids:
            try:
                rect = self.get_element_screen_region(element_id)
            except AssertionError:
                logger.info("Masque visuel : élément '%s' absent de l'écran, "
                            "ignoré." % element_id)
                continue
            regions.append((rect["left"] - ox, rect["top"] - oy,
                            rect["width"], rect["height"]))
        return regions

    # -- frontières image (Pillow, stubbables en test) --------------------------

    @staticmethod
    def _decode_image_to_gray(image_bytes):
        """PNG/JPEG/BMP → matrice de gris (frontière image, stubbable en test).
        Impl partagée avec le canal Fiori dans
        ``sapfx_common.visual_baseline``, où Pillow est importé seulement à
        l'appel : l'assertion visuelle est opt-in (extra ``visual``), le reste
        de la bibliothèque n'en dépend jamais."""
        from sapfx_common.visual_baseline import decode_image_to_gray
        return decode_image_to_gray(image_bytes)

    @staticmethod
    def _crop_image(image_bytes, region):
        """Recadre un PNG sur ``region`` (left, top, width, height, repère
        capture) et retourne le PNG recadré. Frontière Pillow, stubbable.
        Lève ``ValueError`` si l'intersection avec la capture est vide."""
        try:
            from PIL import Image
        except ImportError:
            raise RuntimeError(
                "L'assertion visuelle a besoin de Pillow pour recadrer la "
                "capture : pip install Pillow (extra 'visual' du paquet "
                "robotframework-sapfx).")
        import io
        image = Image.open(io.BytesIO(image_bytes))
        x0 = max(int(region[0]), 0)
        y0 = max(int(region[1]), 0)
        x1 = min(int(region[0]) + int(region[2]), image.size[0])
        y1 = min(int(region[1]) + int(region[3]), image.size[1])
        if x1 <= x0 or y1 <= y0:
            raise ValueError(
                "Région (%s, %s, %sx%s) hors de la capture %dx%d : l'élément "
                "est-il visible dans la fenêtre ?" %
                (region[0], region[1], region[2], region[3],
                 image.size[0], image.size[1]))
        out = io.BytesIO()
        image.crop((x0, y0, x1, y1)).save(out, format="PNG")
        return out.getvalue()

