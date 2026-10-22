"""Mixin captures d'écran : la fenêtre SAP active en image.

Le canal VISUEL de la perception, sans fichier intermédiaire (MCP-safe) :
`Get Screenshot As Base64` (``HardCopyToMemory``, MIME re-vérifié par magic
bytes) et `Log Screenshot` (data-URI inline dans le log Robot autoporteur).

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
from typing import TYPE_CHECKING, Any, Literal

from pythoncom import com_error
from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError
from robot.utils import get_link_path

from sapfx_common.caller_context import current_keyword_frames, is_direct_call, swallowing_wrapper

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

    if TYPE_CHECKING:
        # Contrat du composite (SapEccLibrary), pour mypy seulement : les
        # keywords annotés (type GuiElementId) font vérifier leurs corps.
        session: Any

    def get_screenshot_as_base64(self, image_format: Literal["png", "jpeg", "jpg", "bmp", "gif"] = "png"):
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

        Un échec ATTENDU ne laisse pas d'image (depuis le 2026-10-08) : un
        keyword qui échoue sous `Run Keyword And Return Status`,
        `Run Keyword And Ignore Error` ou `Run Keyword And Expect Error`
        (BuiltIn) ne capture pas, parce que ces trois keywords avalent
        l'échec et que le run reste vert. `Run Keyword And Warn On Failure`,
        `Wait Until Keyword Succeeds` et un bloc ``TRY`` gardent la capture.
        Appelé lui-même, `Take Screenshot` capture toujours (si le réglage
        est actif). Les captures prises sur erreur se relisent par
        `Get Error Screenshots`.

        Exemple :
        | `Enable Screenshots On Error`
        | ${path}=    `Take Screenshot`    se16-initial
        | Should End With    ${path}    .png
        """
        if not getattr(self, "take_screenshots", False):
            return None
        frames = current_keyword_frames()
        on_error = not is_direct_call(frames, "Take Screenshot")
        if on_error:
            wrapper = swallowing_wrapper(frames or [])
            if wrapper:
                logger.debug("Capture sur erreur omise : l'échec est attendu par "
                             "`%s`." % wrapper)
                return None
        path = self.screenshot.take_screenshot(screenshot_name)
        if path and on_error:
            self._error_screenshot_paths().append(path)
        return path

    def _error_screenshot_paths(self):
        paths = getattr(self, "_error_screenshots", None)
        if paths is None:
            paths = self._error_screenshots = []
        return paths

    def get_error_screenshots(self):
        """Les fichiers PNG que les keywords de cette bibliothèque ont écrits
        en échouant, dans l'ordre, depuis l'import (portée de la suite). Les
        captures demandées par `Take Screenshot` lui-même n'y sont pas, ni les
        échecs attendus, qui n'en écrivent pas (voir `Take Screenshot`).

        La garde d'une campagne qui promet un run vert sans image : une
        capture sur erreur dans une suite verte est un échec rattrapé quelque
        part (un ``TRY``, une sonde écrite avec un keyword qui échoue), donc
        une image écrite pour rien et une sonde à revoir. Né du constat du
        2026-10-07 : le registre de capacités de la 754
        passait 21/21 en laissant 9 captures.

        Exemple :
        | ${captures}=    `Get Error Screenshots`
        | IF    '${SUITE STATUS}' == 'PASS'
        |     Should Be Empty    ${captures}
        | END
        """
        return list(self._error_screenshot_paths())

    def set_screenshot_directory(self, path):
        """Fixe le dossier où `Take Screenshot` et les captures sur erreur
        écrivent leurs PNG (créé au besoin) et retourne l'ancien, vide pour le
        dossier de sortie de Robot : restaurable en teardown.

        Né du scénario 11 (2026-10-07) : sous rf-mcp, le dossier de sortie de
        Robot est un dossier temporaire du serveur, et un agent qui devait
        ranger ses captures ailleurs n'avait que ``screenshot_directory`` à
        l'import, figé pour toute la session.

        Exemple :
        | ${previous}=    `Set Screenshot Directory`    ${OUTPUT DIR}/captures
        | `Enable Screenshots On Error`
        | ${path}=    `Take Screenshot`    se16-initial
        | `Set Screenshot Directory`    ${previous}
        """
        if not str(path or "").strip():
            previous = self.screenshot.directory
            self.screenshot.directory = None
            return previous or ""
        return self.screenshot.set_screenshot_directory(path) or ""

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
        """Désactive la capture sur erreur. Inutile pour un échec attendu
        sous `Run Keyword And Return Status`, `Run Keyword And Ignore Error`
        ou `Run Keyword And Expect Error`, qui ne capture plus (voir
        `Take Screenshot`) ; utile autour d'un ``TRY`` qui rattrape un échec
        prévu. `Element Is Present` sonde sans capture.

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


