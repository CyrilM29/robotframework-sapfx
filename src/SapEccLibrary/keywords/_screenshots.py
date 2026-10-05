"""Mixin captures d'ecran : la fenetre SAP active en image, en memoire.

Le canal VISUEL de la perception, sans fichier intermediaire (MCP-safe) :
`Get Screenshot As Base64` (``HardCopyToMemory``, MIME re-verifie par magic
bytes), `Log Screenshot` (data-URI inline dans le log Robot autoporteur), et
le **screenshot annote Set-of-Mark** (`Get/Log Annotated Screenshot` : boites
numerotees sur les cibles actionnables + legende ``numero -> id``, qui
alimente aussi la table de references ``@N`` de `Get Screen Map`).

Extrait de ``_perception.py`` (convention #13) : la perception texte
(signature, carte, fenetres) reste la-bas, les assertions visuelles dans
``_visual.py``, la sentinelle dans ``_watch.py``.
"""
import base64

from pythoncom import com_error
from robot.api import logger


# Codes de l'énumération GuiImageType de l'API SAP GUI Scripting. Le format
# RÉEL du buffer retourné est re-vérifié par magic bytes (_sniff_mime) : le
# MIME annoncé ne dépend jamais du seul code demandé.
_IMAGE_TYPE_CODES = {"bmp": 0, "jpeg": 1, "jpg": 1, "png": 2, "gif": 3}

_MAGIC_MIMES = (
    (b"\x89PNG", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"BM", "image/bmp"),
    (b"GIF8", "image/gif"),
)


def _sniff_mime(data, fallback="image/png"):
    """MIME réel d'un buffer image par ses magic bytes (l'énumération
    GuiImageType a varié selon les versions, on ne lui fait pas confiance)."""
    for magic, mime in _MAGIC_MIMES:
        if data[:len(magic)] == magic:
            return mime
    return fallback


def _as_bytes(raw):
    """Buffer COM -> bytes : l'API retourne selon les versions un ``bytes``
    direct ou un SAFEARRAY (tuple d'entiers, parfois signés)."""
    if isinstance(raw, (bytes, bytearray, memoryview)):
        return bytes(raw)
    return bytes(b & 0xFF for b in raw)



class ScreenshotKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Lecture seule : capture la
    fenêtre active en mémoire, ne modifie aucun écran."""

    def get_screenshot_as_base64(self, image_format="png"):
        """Capture la fenêtre SAP active **en mémoire** et retourne l'image en
        base64 (chaîne sûre à travers la frontière rf-mcp, rien n'est écrit
        sur disque).

        Passe par ``ActiveWindow.HardCopyToMemory`` (API scripting : capture
        fidèle de la fenêtre, y compris hors focus, contrairement à une
        capture GDI de l'écran). ``image_format`` : ``png`` (défaut), ``jpeg``,
        ``bmp``, ``gif``. Le format réellement retourné est re-vérifié par
        magic bytes, pas supposé.

        Complète `Get Screen Signature` (texte) d'un canal **visuel** : un
        agent (ou un rapport) peut joindre la preuve d'écran ; voir
        `Log Screenshot` pour l'ancrer dans le log Robot. Échec explicite si
        l'API est absente (SAP GUI ancien) : `Take Screenshot` (fichier) reste
        le repli."""
        fmt = str(image_format).strip().lower()
        type_code = _IMAGE_TYPE_CODES.get(fmt, _IMAGE_TYPE_CODES["png"])
        try:
            raw = self.session.ActiveWindow.HardCopyToMemory(type_code)
        except (AttributeError, com_error) as exc:
            raise AssertionError(
                "HardCopyToMemory indisponible sur cette session (SAP GUI trop "
                "ancien ?). Utiliser Take Screenshot (fichier) en repli : %s" % exc)
        return base64.b64encode(_as_bytes(raw)).decode("ascii")

    def log_screenshot(self, message=""):
        """Capture la fenêtre SAP active et l'**incruste dans le log Robot**
        (image inline en data-URI : le ``log.html`` reste autoporteur, aucune
        pièce jointe à archiver à côté). ``message`` : texte optionnel affiché
        au-dessus de l'image. Retourne le MIME réellement incrusté."""
        b64 = self.get_screenshot_as_base64()
        mime = _sniff_mime(base64.b64decode(b64))
        html = '<img src="data:%s;base64,%s" style="max-width:100%%;">' % (mime, b64)
        if message:
            html = "%s<br>%s" % (message, html)
        logger.info(html, html=True)
        return mime

    # -- screenshot annoté (Set-of-Mark : boîtes numérotées + légende) ---------

    def get_annotated_screenshot(self, include_types=None):
        """Capture la fenêtre SAP active et y **dessine les cibles
        actionnables** : une boîte numérotée par champ modifiable /
        bouton / onglet, plus une légende ``numéro -> id``. Retourne un dict
        MCP-safe : ``image`` (PNG annoté en base64), ``mime``, ``legend``.

        C'est le pont entre la perception visuelle et l'effecteur : un agent
        (ou un humain) qui regarde l'image n'a plus à *deviner* des
        coordonnées : il lit le numéro, la légende lui donne l'id, et l'id
        alimente un keyword déterministe (`Click Element`, ou `Click Element
        At Offset` pour l'intérieur d'une zone opaque). Le patron
        « Set-of-Mark » des agents à vision, appliqué à SAP GUI.

        ``include_types`` (liste ou chaîne d'IDs de types séparés par des
        virgules, ex. ``GuiShell,GuiCustomControl``) remplace la sélection par
        défaut, utile pour n'annoter que les zones opaques. Seuls les
        éléments avec géométrie sont annotés. Nécessite Pillow (extra
        ``visual``).

        La légende est aussi enregistrée comme table de **références ``@N``**
        (voir `Get Screen Map`) : le numéro lu sur l'image se rejoue
        directement via `Click Screen Ref` / `Fill Screen Ref`."""
        png = base64.b64decode(self.get_screenshot_as_base64("png"))
        elements = self._screen_elements()
        if include_types:
            if isinstance(include_types, str):
                wanted = {part.strip() for part in include_types.split(",")
                          if part.strip()}
            else:
                wanted = {str(part).strip() for part in include_types}
            targets = [el for el in elements if el.type in wanted]
        else:
            from sapfx_common.semantic import actionable_targets
            targets = actionable_targets(elements)
        ox, oy = self._window_origin()
        boxes = []
        legend = {}
        for element in targets:
            # géométrie complète ET positive exigée : le vrai SAP GUI remonte
            # des largeurs négatives sur certains contrôles (constaté live A4H)
            if (element.left is None or element.top is None
                    or not element.width or element.width < 0
                    or not element.height or element.height < 0):
                continue
            number = str(len(boxes) + 1)
            boxes.append((number, element.left - ox, element.top - oy,
                          element.width, element.height))
            legend[number] = element.id
        annotated = self._draw_annotations(png, boxes)
        # La légende devient aussi la table de références @N : le numéro lu
        # sur l'image est directement actionnable via Click/Fill Screen Ref.
        self._register_screen_refs(legend, self._screen_header())
        return {"image": base64.b64encode(annotated).decode("ascii"),
                "mime": "image/png", "legend": legend}

    def log_annotated_screenshot(self, message="", include_types=None):
        """Capture annotée (voir `Get Annotated Screenshot`) **incrustée dans
        le log Robot** avec sa légende ``numéro -> id`` en tableau, le
        débogage de localisateurs d'un coup d'œil : chaque cible actionnable
        est numérotée sur l'image, son id copiable juste en dessous.
        Retourne la légende (dict)."""
        shot = self.get_annotated_screenshot(include_types)
        html = ('<img src="data:%s;base64,%s" style="max-width:100%%;">'
                % (shot["mime"], shot["image"]))
        if shot["legend"]:
            rows = "".join(
                "<tr><td>%s</td><td><code>%s</code></td></tr>" % (num, eid)
                for num, eid in shot["legend"].items())
            html += ('<table border="1" cellpadding="2">'
                     "<tr><th>n°</th><th>id</th></tr>%s</table>" % rows)
        if message:
            html = "%s<br>%s" % (message, html)
        logger.info(html, html=True)
        return shot["legend"]

    def _window_origin(self):
        """Origine écran de la fenêtre active, pour convertir une géométrie
        absolue (ScreenLeft/ScreenTop) dans le repère de la capture
        ``HardCopyToMemory`` (qui photographie la fenêtre, pas l'écran).
        Best-effort : (0, 0) si illisible."""
        try:
            window = self.session.ActiveWindow
            return int(window.ScreenLeft), int(window.ScreenTop)
        except (AttributeError, com_error, TypeError, ValueError):
            return 0, 0

    @staticmethod
    def _draw_annotations(image_bytes, boxes):
        """Dessine les boîtes numérotées (``(étiquette, left, top, width,
        height)``, repère capture) sur un PNG et retourne le PNG annoté.
        Frontière Pillow, stubbable en test."""
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            raise RuntimeError(
                "Le screenshot annoté a besoin de Pillow : pip install Pillow "
                "(extra 'visual' du paquet robotframework-sapfx).")
        import io
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        draw = ImageDraw.Draw(image)
        for label, left, top, width, height in boxes:
            draw.rectangle([left, top, left + width, top + height],
                           outline=(220, 30, 30), width=2)
            tag_width = 7 * len(label) + 6
            tag_top = max(top - 13, 0)
            draw.rectangle([left, tag_top, left + tag_width, tag_top + 13],
                           fill=(220, 30, 30))
            draw.text((left + 3, tag_top + 1), label, fill=(255, 255, 255))
        out = io.BytesIO()
        image.save(out, format="PNG")
        return out.getvalue()
