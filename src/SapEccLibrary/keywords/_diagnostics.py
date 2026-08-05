"""Mixin de diagnostic : préflight du scripting SAP GUI et télémétrie de session.

Le SAP GUI Scripting est désactivé par défaut côté serveur
(``sapgui/user_scripting = FALSE``) et peut être **dégradé silencieusement** par
les paramètres de profil : ``user_scripting_set_readonly`` (l'API ne peut plus
rien modifier), ``user_scripting_disable_recording`` (plus aucun événement :
mode record natif du recorder inopérant), ``user_scripting_per_user``
(autorisation S_SCR requise). Aucun de ces modes ne produit d'erreur franche à
la connexion : les symptômes apparaissent plus tard, au premier keyword qui
échoue bizarrement. Ces keywords lisent l'état réel exposé par l'API
(``GuiConnection.DisabledByServer``, ``GuiSessionInfo.ScriptingModeReadOnly`` /
``ScriptingModeRecordingDisabled``, doc officielle « SAP GUI Scripting API »)
pour échouer TÔT, avec la cause exacte et le paramètre RZ11 à corriger.

Également ici : ``TestToolMode`` (supprime les popups de messages I/A au replay,
update immédiat, pensé par SAP pour les outils de test), la télémétrie de
``session.Info`` (temps de réponse, aller-retours) pour instrumenter les runs,
le préflight du **mode accessibilité**, l'autre réglage silencieux (côté
client, celui-là) dont dépend la lecture des listes ABAP classiques, et le
préflight de **posture de sécurité du poste** (`Get Client Security Status` /
`Client Security Should Be Hardened` : client patché contre la CVE-2025-0055
de l'historique de saisie, historique désactivé sur un poste où les tests
tapent de vraies données ; logique pure dans ``sapfx_common.client_security``).
Voir [docs/hardening-test-environment.md](../../../docs/hardening-test-environment.md).
"""
from pythoncom import com_error

from sapfx_common.client_security import (
    INPUT_HISTORY_UNKNOWN,
    INPUT_HISTORY_VULNERABLE,
    find_history_databases,
    input_history_cve_status,
)


def _truthy(value):
    """Interprétation Robot-friendly d'un booléen : les arguments non annotés
    arrivent en chaîne (« False » est truthy en Python, piège classique)."""
    if isinstance(value, str):
        return value.strip().lower() not in ("false", "0", "no", "non", "")
    return bool(value)


def _read(obj, attr, default=None):
    """Lecture défensive d'une propriété COM : ``default`` si absente/erreur
    (toutes les propriétés n'existent pas sur toutes les versions de SAP GUI)."""
    try:
        value = getattr(obj, attr)
    except (AttributeError, com_error):
        return default
    return default if value is None else value


class DiagnosticsKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Lecture seule sauf mention contraire.
    Suppose ``self.sapapp``/``self.connection``/``self.session`` posés par les
    keywords de connexion (`Connect To Session`, `Open Connection...`)."""

    def get_scripting_status(self):
        """Retourne un dict décrivant l'état réel du support scripting.

        Clés (``None`` = information non exposée par cette version de SAP GUI) :
        - ``gui_version`` : version du client SAP GUI (``8.0 PL6``…) ;
        - ``disabled_by_server`` : ``sapgui/user_scripting`` absent/FALSE côté serveur ;
        - ``read_only`` : mode lecture seule (``sapgui/user_scripting_set_readonly``) ;
        - ``recording_disabled`` : événements coupés
          (``sapgui/user_scripting_disable_recording``) : le mode record natif du
          recorder et tout spy événementiel sont inopérants ;
        - ``ui_guideline`` : thème/guideline actif (détection Belize/Quartz/Horizon) ;
        - ``system``/``client``/``user`` : contexte de la session.

        Lecture seule, indépendant de la locale. Voir aussi
        `Scripting Should Be Fully Enabled` pour la forme assertion."""
        sapapp = getattr(self, "sapapp", None)
        connection = getattr(self, "connection", None)
        session = getattr(self, "session", None)
        info = _read(session, "Info") if session is not None else None

        major = _read(sapapp, "MajorVersion")
        gui_version = None
        if major is not None:
            gui_version = "%s.%s PL%s" % (
                major, _read(sapapp, "MinorVersion", "?"), _read(sapapp, "Patchlevel", "?"))

        def _bool(value):
            return None if value is None else bool(value)

        return {
            "gui_version": gui_version,
            "disabled_by_server": _bool(_read(connection, "DisabledByServer")),
            "read_only": _bool(_read(info, "ScriptingModeReadOnly")),
            "recording_disabled": _bool(_read(info, "ScriptingModeRecordingDisabled")),
            "ui_guideline": _read(info, "UI_GUIDELINE"),
            "system": _read(info, "SystemName"),
            "client": _read(info, "Client"),
            "user": _read(info, "User"),
        }

    def scripting_should_be_fully_enabled(self, allow_recording_disabled=False):
        """Échoue TÔT si le scripting serveur est absent ou dégradé, avec la cause
        exacte et le paramètre de profil (RZ11) à corriger.

        À appeler en Suite Setup, juste après la connexion : chacun de ces modes
        est silencieux à la connexion et ne se manifeste que par des échecs
        étranges plus tard. ``allow_recording_disabled=True`` tolère le mode
        « événements coupés » (les tests purs marchent, seuls le record natif du
        recorder et les spys événementiels sont inopérants)."""
        status = self.get_scripting_status()
        problems = []
        if status["disabled_by_server"]:
            problems.append(
                "le scripting est désactivé côté serveur, RZ11 : "
                "sapgui/user_scripting = TRUE (en MAJUSCULES) ; si le paramètre "
                "est déjà TRUE, le système est probablement en "
                "sapgui/user_scripting_per_user = TRUE et ce compte n'a pas "
                "l'autorisation S_SCR Execute(16). C'est d'ailleurs la "
                "configuration recommandée : scripting réservé aux comptes de "
                "test (cf. docs/hardening-test-environment.md)")
        if status["read_only"]:
            problems.append(
                "le scripting est en LECTURE SEULE (aucune action possible), "
                "RZ11 : sapgui/user_scripting_set_readonly = FALSE")
        if status["recording_disabled"] and not allow_recording_disabled:
            problems.append(
                "les événements de scripting sont coupés (record natif/spys "
                "événementiels inopérants), RZ11 : "
                "sapgui/user_scripting_disable_recording = FALSE, ou appeler ce "
                "keyword avec allow_recording_disabled=True si assumé")
        if problems:
            self.take_screenshot()
            raise AssertionError(
                "SAP GUI Scripting dégradé (%s) : %s"
                % (status.get("system") or "système inconnu", " ; ".join(problems)))

    def enable_test_tool_mode(self, enabled=True):
        """Active le mode outil de test de la session (``session.TestToolMode``).

        Prévu par SAP pour les outils de test : les messages d'information et
        d'abandon (types ``I``/``A``) ne s'affichent plus en popup (ils passent
        dans la barre d'état), les messages système sont ignorés et le mode
        update du serveur devient immédiat pour cette connexion, trois sources
        classiques de replays instables. À activer en Suite Setup, désactiver
        avec ``enabled=False``. Nécessite un kernel récent (sinon sans effet)."""
        value = str(enabled).strip().lower() not in ("false", "0", "no", "non", "")
        try:
            self.session.TestToolMode = 1 if value else 0
        except (AttributeError, com_error) as exc:
            raise AssertionError(
                "Could not set TestToolMode on this session (old SAP GUI/kernel?): %s"
                % exc)

    def get_list_rendering_status(self):
        """Décrit comment l'écran ACTIF expose son contenu : le préflight du
        **mode accessibilité** SAP GUI (pendant côté client de
        `Get Scripting Status`, qui couvre le côté serveur).

        Clés :
        - ``readable_labels`` : nombre de ``GuiLabel`` porteurs de texte ET de
          géométrie (ce que `Read Abap List` sait reconstruire) ;
        - ``shell_rendered`` : l'écran contient un contrôle shell/custom
          (``GuiShell``/``GuiContainerShell``/``GuiCustomControl``) ;
        - ``list_readable`` : vrai si le contenu est lisible en labels ;
        - ``accessibility_mode_needed`` : vrai quand le contenu est **enfermé
          dans un shell sans aucun label**, la signature exacte d'une liste
          ABAP rendue sans le mode accessibilité (constaté live sur A4H / SAP
          GUI 8.00 : la sortie RSPARAM n'expose alors AUCUN label) ;
        - ``hint`` : la marche à suivre, ou ``None`` si rien à corriger.

        Le mode accessibilité est un réglage **du poste** (Options SAP GUI →
        Interaction Design → Accessibility) qui exige un redémarrage du client :
        il se provisionne, il ne s'active pas depuis un test : d'où ce keyword
        de constat, exactement comme on ne bascule pas RZ11 depuis une suite.
        Lecture seule, indépendant de la locale (aucun texte n'est interprété).

        NB : une grille ALV est *légitimement* rendue dans un shell ; sur un
        écran ALV, ``shell_rendered`` est vrai sans que rien ne soit à
        corriger (les labels y sont inutiles : lire via `Read Grid`)."""
        elements = self._screen_elements()
        labels = sum(1 for el in elements
                     if el.type == "GuiLabel" and el.left is not None
                     and (el.text or "").strip())
        shell_types = ("GuiShell", "GuiContainerShell", "GuiCustomControl")
        shell = any(el.type in shell_types for el in elements)
        needed = bool(shell and labels == 0)
        hint = None
        if needed:
            hint = ("Le contenu de cet écran est rendu dans un contrôle shell et "
                    "n'expose aucun label : une liste ABAP classique y est "
                    "illisible par scripting. Activer le mode accessibilité sur "
                    "le poste (Options SAP GUI → Interaction Design → "
                    "Accessibility) PUIS rouvrir la session ; sinon exporter la "
                    "liste (System → List → Save → Local File). Une grille ALV, "
                    "elle, se lit avec Read Grid sans rien changer.")
        return {
            "readable_labels": labels,
            "shell_rendered": shell,
            "list_readable": labels > 0,
            "accessibility_mode_needed": needed,
            "hint": hint,
        }

    def abap_list_should_be_readable(self):
        """Échoue TÔT si l'écran actif ne peut pas être lu comme liste ABAP,
        avec la cause exacte et la marche à suivre (cf. `Get List Rendering
        Status`).

        À appeler juste avant `Read Abap List` (ou en Suite Setup d'une suite
        qui lit des sorties de reports) pour transformer un « aucune liste
        détectée » découvert au milieu du run en un échec explicite qui nomme le
        réglage du poste à provisionner."""
        status = self.get_list_rendering_status()
        if status["list_readable"]:
            return
        self.take_screenshot()
        raise AssertionError(
            "L'écran actif n'expose aucun label lisible (%s). %s"
            % ("contenu dans un contrôle shell" if status["shell_rendered"]
               else "écran sans contenu de liste",
               status["hint"] or "Cet écran n'affiche probablement pas de liste."))

    def get_session_telemetry(self):
        """Retourne les compteurs de performance de ``session.Info`` du DERNIER
        aller-retour : ``response_time`` / ``interpretation_time`` (ms),
        ``roundtrips``, ``flushes``, ``low_speed_connection``.

        Utile pour instrumenter un run (journaliser le coût serveur de chaque
        étape métier) ou détecter une connexion dégradée : ``flushes`` élevés =
        beaucoup d'appels COM synchrones, candidat à l'optimisation. Clés à
        ``None`` si la propriété n'est pas exposée par cette version."""
        info = _read(self.session, "Info")
        return {
            "response_time": _read(info, "ResponseTime"),
            "interpretation_time": _read(info, "InterpretationTime"),
            "roundtrips": _read(info, "RoundTrips"),
            "flushes": _read(info, "Flushes"),
            "low_speed_connection": _read(info, "IsLowSpeedConnection"),
        }

    def get_client_security_status(self, history_dirs=None):
        """Posture de sécurité du POSTE de test (client SAP GUI) : lecture
        seule, aucun effet de bord.

        Complète `Get Scripting Status` (versant serveur) par le versant
        client. Clés :

        - ``gui_version`` : version du client (``8.0 PL6``…) ;
        - ``input_history_cve`` : ``patched`` / ``vulnerable`` / ``unknown``,
          position du client vis-à-vis de la CVE-2025-0055 (l'historique de
          saisie de SAP GUI for Windows était chiffré par un XOR à clé
          statique ; corrigé à partir de la 8.00 PL9, notes de sécurité SAP
          de janvier 2025) ;
        - ``input_history_files`` / ``input_history_present`` : bases
          d'historique (``*.db``) trouvées aux emplacements connus du poste.
          Sur un poste de TEST c'est le point important : tout ce que les
          suites saisissent dans de vrais champs peut y être persisté :
          l'historique doit être désactivé (Options SAP GUI → Local Data →
          History) et les bases existantes purgées ;
        - ``scripting`` : rappel du préflight serveur
          (``disabled_by_server`` / ``read_only`` / ``recording_disabled``) ;
        - ``hints`` : les corrections à apporter (vide si rien à signaler).

        ``history_dirs`` (répertoire ou liste) remplace les emplacements
        scannés, utile si l'historique a été déplacé via les options SAP GUI.
        Dict JSON-safe (utilisable à travers rf-mcp). Forme assertion :
        `Client Security Should Be Hardened`. Guide complet :
        docs/hardening-test-environment.md."""
        status = self.get_scripting_status()
        sapapp = getattr(self, "sapapp", None)
        cve = input_history_cve_status(
            _read(sapapp, "MajorVersion"), _read(sapapp, "MinorVersion"),
            _read(sapapp, "Patchlevel"))
        if isinstance(history_dirs, str):
            history_dirs = [history_dirs]
        files = find_history_databases(history_dirs)
        hints = []
        if cve == INPUT_HISTORY_VULNERABLE:
            hints.append(
                "client SAP GUI %s vulnérable sur l'historique de saisie "
                "(CVE-2025-0055) : monter en 8.00 PL9+ ou en 8.10+"
                % (status["gui_version"] or "?"))
        elif cve == INPUT_HISTORY_UNKNOWN:
            hints.append(
                "niveau de patch du client indéterminé : vérifier manuellement "
                "la note SAP 3472837 (chiffrement de l'historique de saisie)")
        if files:
            hints.append(
                "%d base(s) d'historique de saisie présente(s) sur ce poste : "
                "désactiver l'historique (Options SAP GUI → Local Data → "
                "History) et purger ces fichiers : les saisies des tests y "
                "sont persistées" % len(files))
        return {
            "gui_version": status["gui_version"],
            "input_history_cve": cve,
            "input_history_files": files,
            "input_history_present": bool(files),
            "scripting": {
                "disabled_by_server": status["disabled_by_server"],
                "read_only": status["read_only"],
                "recording_disabled": status["recording_disabled"],
            },
            "hints": hints,
        }

    def client_security_should_be_hardened(self, allow_input_history=False,
                                           allow_unknown_patch_level=True,
                                           history_dirs=None):
        """Échoue si le POSTE de test n'est pas durci, avec la correction
        exacte à apporter (cf. `Get Client Security Status`).

        - client vulnérable sur l'historique de saisie (CVE-2025-0055) :
          échec, toujours ;
        - bases d'historique de saisie présentes sur le poste : échec, sauf
          ``allow_input_history=True`` (assumé : poste hors production, données
          de test synthétiques) ;
        - niveau de patch indéterminé : toléré par défaut ;
          ``allow_unknown_patch_level=False`` pour l'exiger (poste durci où la
          version DOIT être identifiable).

        À appeler en Suite Setup, après `Scripting Should Be Fully Enabled`
        (versant serveur) : les deux préflights ensemble couvrent la checklist
        de docs/hardening-test-environment.md."""
        allow_history = _truthy(allow_input_history)
        allow_unknown = _truthy(allow_unknown_patch_level)
        posture = self.get_client_security_status(history_dirs)
        problems = []
        if posture["input_history_cve"] == INPUT_HISTORY_VULNERABLE:
            problems.append(
                "client SAP GUI %s vulnérable sur l'historique de saisie "
                "(CVE-2025-0055) : monter en 8.00 PL9+ ou en 8.10+"
                % (posture["gui_version"] or "?"))
        elif (posture["input_history_cve"] == INPUT_HISTORY_UNKNOWN
              and not allow_unknown):
            problems.append(
                "niveau de patch du client indéterminé (exigé par "
                "allow_unknown_patch_level=False) : vérifier les notes de "
                "sécurité SAP de janvier 2025")
        if posture["input_history_present"] and not allow_history:
            problems.append(
                "%d base(s) d'historique de saisie sur le poste (%s) : "
                "désactiver l'historique (Options SAP GUI → Local Data → "
                "History) et purger, ou appeler ce keyword avec "
                "allow_input_history=True si assumé"
                % (len(posture["input_history_files"]),
                   " ; ".join(posture["input_history_files"])))
        if problems:
            raise AssertionError(
                "Poste de test non durci : %s" % " ; ".join(problems))
