"""Mixin captures d'écran : la fenêtre SAP active en image.

Le canal VISUEL de la perception, sans fichier intermédiaire (MCP-safe) :
`Get Screenshot As Base64` (``HardCopyToMemory``, MIME re-vérifié par magic
bytes), `Log Screenshot` (data-URI inline dans le log Robot autoporteur), et
le *screenshot annoté Set-of-Mark* (`Get/Log Annotated Screenshot` : boîtes
numérotées sur les cibles actionnables + légende ``numéro -> id``, qui
alimente aussi la table de références ``@N`` de `Get Screen Map`).

Aussi la capture SUR ERREUR (`Take Screenshot`, `Enable/Disable Screenshots
On Error`), dérivée de robotframework-sapguilibrary 1.2.1 (Copyright Frank
van der Kuur, Apache License 2.0, voir NOTICE), absorbée et réécrite pour
SAPFX le 2026-10-06, noms et signatures inchangés. L'amont passait par la
bibliothèque Screenshot de Robot Framework, qui photographie l'ÉCRAN
ENTIER : tout ce que le bureau affichait partait dans le log, et la fenêtre
SAP n'y était pas forcément. La capture vise désormais la fenêtre SAP
active (`SapWindowScreenshot`), et une capture impossible ne masque jamais
l'erreur qu'elle accompagne.

Extrait de ``_perception.py`` (convention #13) : la perception texte
(signature, carte, fenêtres) reste là-bas, les assertions visuelles dans
``_visual.py``, la sentinelle dans ``_watch.py``.
"""
import base64
import os
import re

from pythoncom import com_error
from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError
from robot.utils import get_link_path


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
_MIME_EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/bmp": "bmp",
                    "image/gif": "gif"}


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


def _robot_variable(name):
    """Valeur d'une variable Robot, ``None`` hors exécution Robot (tests
    unitaires, ``--replay`` du recorder)."""
    try:
        return BuiltIn().get_variable_value(name)
    except RobotNotRunningError:
        return None


class SapWindowScreenshot:
    """La capture sur erreur : la fenêtre SAP ACTIVE (modal compris) écrite en
    PNG dans le dossier des captures (``screenshot_directory`` à l'import, à
    défaut ``${OUTPUT DIR}``) et jointe au log. Jamais une exception : une
    capture impossible (aucune session, SAP GUI sans ``HardCopyToMemory``,
    disque plein) est journalisée et rend ``None``, parce qu'elle accompagne
    toujours une autre erreur, qu'elle ne doit pas remplacer."""

    def __init__(self, window_provider, directory=None):
        self._window_provider = window_provider
        self.directory = None
        if directory is not None:
            self.set_screenshot_directory(directory)

    def set_screenshot_directory(self, path):
        """Fixe (et crée au besoin) le dossier des captures ; retourne
        l'ancien, ``None`` pour le dossier de sortie de Robot."""
        previous = self.directory
        self.directory = os.path.abspath(str(path))
        os.makedirs(self.directory, exist_ok=True)
        return previous

    def take_screenshot(self, name="sap-screenshot"):
        """Capture la fenêtre active ; chemin du fichier écrit, ou ``None``."""
        try:
            raw = self._window_provider().HardCopyToMemory(_IMAGE_TYPE_CODES["png"])
            data = _as_bytes(raw)
        except Exception as exc:                # noqa: BLE001 (accompagne une erreur)
            logger.info("Capture de la fenêtre SAP impossible (%s) : aucune image "
                        "jointe." % exc)
            return None
        extension = _MIME_EXTENSIONS.get(_sniff_mime(data), "png")
        directory = self.directory or _robot_variable("${OUTPUT DIR}") or os.getcwd()
        try:
            path = self._free_path(directory, name, extension)
            with open(path, "wb") as handle:
                handle.write(data)
        except OSError as exc:
            logger.info("Capture de la fenêtre SAP non écrite (%s)." % exc)
            return None
        log_file = _robot_variable("${LOG FILE}")
        base = os.path.dirname(log_file) if log_file and log_file != "NONE" else directory
        link = get_link_path(path, base)
        logger.info('<a href="%s"><img src="%s" width="800px"></a>' % (link, link),
                    html=True)
        return path

    @staticmethod
    def _free_path(directory, name, extension):
        """``<dossier>/<nom>_<n>.<ext>`` au premier ``n`` libre ; le nom est
        réduit à des caractères sûrs (aucun chemin ne passe par lui)."""
        stem = re.sub(r"[^\w.-]", "_", os.path.basename(str(name))).strip("._")
        stem = stem or "sap-screenshot"
        os.makedirs(directory, exist_ok=True)
        index = 1
        while True:
            path = os.path.join(directory, "%s_%d.%s" % (stem, index, extension))
            if not os.path.exists(path):
                return path
            index += 1


class ScreenshotKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Lecture seule : capture la
    fenêtre active en mémoire, ne modifie aucun écran."""

    def get_screenshot_as_base64(self, image_format="png"):
        """Capture la fenêtre SAP active *en mémoire* et retourne l'image en
        base64 (chaîne sûre à travers la frontière rf-mcp, rien n'est écrit
        sur disque).

        Passe par ``ActiveWindow.HardCopyToMemory`` (API scripting : capture
        fidèle de la fenêtre, y compris hors focus, contrairement à une
        capture GDI de l'écran). ``image_format`` : ``png`` (défaut), ``jpeg``,
        ``bmp``, ``gif``. Le format réellement retourné est re-vérifié par
        magic bytes, pas supposé.

        Complète `Get Screen Signature` (texte) d'un canal *visuel* : un
        agent (ou un rapport) peut joindre la preuve d'écran ; voir
        `Log Screenshot` pour l'ancrer dans le log Robot. Échec explicite si
        l'API est absente (SAP GUI ancien) ou si aucune session n'est ouverte.

        Exemple :
        | ${image}=    `Get Screenshot As Base64`
        | Should Start With    ${image}    iVBORw0KGgo
        """
        fmt = str(image_format).strip().lower()
        type_code = _IMAGE_TYPE_CODES.get(fmt, _IMAGE_TYPE_CODES["png"])
        try:
            raw = self.session.ActiveWindow.HardCopyToMemory(type_code)
        except (AttributeError, com_error) as exc:
            raise AssertionError(
                "HardCopyToMemory indisponible (aucune session ouverte, ou SAP GUI "
                "trop ancien) : %s" % exc) from exc
        return base64.b64encode(_as_bytes(raw)).decode("ascii")

    def log_screenshot(self, message=""):
        """Capture la fenêtre SAP active et l'*incruste dans le log Robot*
        (image inline en data-URI : le ``log.html`` reste autoporteur, aucune
        pièce jointe à archiver à côté). ``message`` : texte optionnel affiché
        au-dessus de l'image. Retourne le MIME réellement incrusté.

        Exemple :
        | ${mime}=    `Log Screenshot`    SE16 initial screen
        | Should Be Equal    ${mime}    image/png
        """
        b64 = self.get_screenshot_as_base64()
        mime = _sniff_mime(base64.b64decode(b64))
        html = '<img src="data:%s;base64,%s" style="max-width:100%%;">' % (mime, b64)
        if message:
            html = "%s<br>%s" % (message, html)
        logger.info(html, html=True)
        return mime

    # -- capture sur erreur ------------------------------------------------------

    def take_screenshot(self, screenshot_name="sap-screenshot"):
        """Capture la fenêtre SAP active dans un fichier PNG joint au log, SI
        les captures sur erreur sont activées (réglage d'import
        ``screenshots_on_error``, `Enable Screenshots On Error`) ; sans effet
        sinon. Retourne le chemin du fichier, ``None`` sans capture.

        C'est la capture que prennent les keywords en échec. Elle photographie
        la FENÊTRE SAP (``HardCopyToMemory``, modal compris), pas l'écran
        entier : rien d'autre du bureau ne part dans le log. Le fichier
        s'écrit dans ``screenshot_directory`` (réglage d'import), à défaut
        dans le dossier de sortie de Robot, sous ``<nom>_<n>.png``. Une
        capture impossible (aucune session ouverte, SAP GUI sans cette API)
        est journalisée et ne fait jamais échouer l'appelant. Pour une image
        sans fichier : `Log Screenshot`.

        Exemple :
        | `Enable Screenshots On Error`
        | ${path}=    `Take Screenshot`    se16-initial
        | Should End With    ${path}    .png
        """
        if not getattr(self, "take_screenshots", False):
            return None
        return self.screenshot.take_screenshot(screenshot_name)

    def enable_screenshots_on_error(self):
        """Active la capture de la fenêtre SAP quand un keyword échoue (voir
        `Take Screenshot`). C'est le réglage par défaut.

        Exemple :
        | `Disable Screenshots On Error`
        | ${absent}=    Run Keyword And Return Status    `Element Should Be Present`    wnd[0]/usr/txtABSENT
        | `Enable Screenshots On Error`
        """
        self.take_screenshots = True

    def disable_screenshots_on_error(self):
        """Désactive la capture sur erreur : un échec attendu (une sonde) ne
        laisse alors aucune image dans le log. `Element Is Present` sonde déjà
        sans capture.

        Exemple :
        | `Disable Screenshots On Error`
        | ${absent}=    Run Keyword And Return Status    `Element Should Be Present`    wnd[0]/usr/txtABSENT
        | `Enable Screenshots On Error`
        """
        self.take_screenshots = False

    def _active_window_for_capture(self):
        """La fenêtre que photographie la capture sur erreur (la plus haute de
        la pile : un modal ouvert est ce qu'il faut voir)."""
        return self.session.ActiveWindow

    # -- screenshot annoté (Set-of-Mark : boîtes numérotées + légende) ---------

    def get_annotated_screenshot(self, include_types=None):
        """Capture la fenêtre SAP active et y *dessine les cibles
        actionnables* : une boîte numérotée par champ modifiable /
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

        La légende est aussi enregistrée comme table de *références* ``@N``
        (voir `Get Screen Map`) : le numéro lu sur l'image se rejoue
        directement via `Click Screen Ref` / `Fill Screen Ref`.

        Exemple :
        | ${annotated}=    `Get Annotated Screenshot`
        | Dictionary Should Contain Value    ${annotated}[legend]    wnd[0]/usr/ctxtDATABROWSE-TABLENAME
        """
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
        """Capture annotée (voir `Get Annotated Screenshot`) *incrustée dans
        le log Robot* avec sa légende ``numéro -> id`` en tableau, le
        débogage de localisateurs d'un coup d'œil : chaque cible actionnable
        est numérotée sur l'image, son id copiable juste en dessous.
        Retourne la légende (dict).

        Exemple :
        | ${legend}=    `Log Annotated Screenshot`    SE16 targets
        | Dictionary Should Contain Value    ${legend}    wnd[0]/usr/ctxtDATABROWSE-TABLENAME
        """
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
