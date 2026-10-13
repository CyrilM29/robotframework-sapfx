"""Mixin *journal des échecs d'autorisation* (SU53 pour un autre utilisateur).

Un refus d'autorisation affiché à l'écran ne nomme pas toujours l'objet en
cause : SE16 refuse une table par ``MO/E/419``, sans paramètre, que le droit
manquant soit ``S_TABU_DIS`` (groupe de la table) ou ``S_TABU_NAM`` (nom de
la table), mesuré le 2026-10-12 sur ABAP Platform 2023. Le journal SU53 le
nomme, avec les valeurs contrôlées et le code de retour ; un administrateur
le lit pour un AUTRE utilisateur, ce qui évite de donner SU53 au compte
restreint (qui en serait refusé au lancement).

Lecture seule. Logique pure (appariement des couples champ/valeur, lecture
« avant / après », filtre) dans ``sapfx_common.authorization_failures``.
"""
from sapfx_common import authorization_failures as journal
from sapfx_common.robot_args import as_optional_int

_SU53 = "SU53"
_OTHER_USER_BUTTON = "wnd[0]/tbar[1]/btn[5]"
_USER_FIELD = "wnd[1]/usr/ctxtG0010_BNAME"
_CONFIRM_BUTTON = "wnd[1]/tbar[0]/btn[0]"
# Le conteneur de la grille : `_grid` descend jusqu'à la GridView sous les
# deux GuiSplitterShell (la moitié haute est un HTMLViewer, jamais lue).
_JOURNAL_GRID = "wnd[0]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell/shellcont[1]/shell"


class AuthorizationFailureKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose ``self.session`` connectée
    sous un utilisateur autorisé à lire SU53 pour un autre utilisateur."""

    def read_authorization_check_failures(self, user, max_rows=None):
        """Lit le journal des contrôles d'autorisation ÉCHOUÉS de ``user``
        (SU53, « Display for Different User ») et le rend en liste de dicts
        JSON-safe ``{date, time, instance, application, display_name,
        for_user, object, rc, fields}``, le plus récent en tête. ``fields``
        est la carte ``{CHAMP: valeur}`` des couples du contrôle (jusqu'à dix,
        lus par identifiant technique de colonne) ; ``rc`` vaut ``4`` quand
        l'objet est détenu mais pas pour ces valeurs, ``12`` quand il n'est
        pas détenu du tout.

        Trois règles de lecture, toutes mesurées :

        - une ligne en échec n'est pas un BLOCAGE : SE16 contrôle
          ``S_TABU_DIS`` OU ``S_TABU_NAM``, et un accès réussi laisse aussi
          l'alternative non détenue dans le journal ; un contrôle réussi n'y
          figure jamais ;
        - le journal PERSISTE et s'accumule entre sessions et entre runs :
          lire avant le geste, lire après, et comparer par `Get New
          Authorization Check Failures`, jamais par l'heure (fuseau non
          établi) ;
        - les textes (application, nom affiché) sont localisés : rendus pour
          le lecteur, à ne pas asserter.

        Un utilisateur au journal VIDE rend ``[]`` (mesuré sur un compte de
        test sans échec : la grille est rendue, sans ligne). Le journal est
        plafonné à 100 entrées par instance : plein, chaque nouvel échec en
        chasse le plus ancien, ce que la lecture avant/après absorbe (mesuré
        sur un journal plein). Une ligne sans objet (grille incomplètement
        chargée) fait ÉCHOUER la lecture au lieu d'être écartée. La colonne
        de l'utilisateur concerné est VIDE : seul le titre de la fenêtre lie
        le journal à ``user``, et deux exécutions simultanées avec le même
        compte de test mêleraient leurs échecs (une exécution à la fois par
        compte).

        La session reste sur l'écran de SU53. ``max_rows`` borne la lecture.

        Exemple :
        | ${before}=    `Read Authorization Check Failures`    SAPFX_TABDIS
        | `Switch Sap Session`    restricted
        | ${refused}=    `Reach Se16 Selection Screen`    T000
        | `Switch Sap Session`    admin
        | ${after}=    `Read Authorization Check Failures`    SAPFX_TABDIS
        | ${fresh}=    `Get New Authorization Check Failures`    ${before}    ${after}
        | `Authorization Check Failures Should Contain`    ${fresh}    S_TABU_DIS
        | ...    rc=4    ACTVT=03    DICBERCLS=SS
        """
        name = str(user).strip().upper()
        if not name:
            raise ValueError("Read Authorization Check Failures needs a user name.")
        limit = as_optional_int(max_rows, "max_rows")
        self.run_transaction(_SU53)
        self.wait_until_busy_done()
        self.click_element(_OTHER_USER_BUTTON)
        self.wait_until_busy_done()
        self.input_text(_USER_FIELD, name)
        self.click_element(_CONFIRM_BUTTON)
        self.wait_until_busy_done()
        if self.session.findById("wnd[1]", False) is not None:
            # Utilisateur inconnu (mesuré) : la saisie reste ouverte, sans
            # message ; reconnue à sa STRUCTURE (le champ de saisie est encore
            # là). Toute autre modale est nommée, jamais prise pour celle-là.
            unknown_user = self.session.findById(_USER_FIELD, False) is not None
            self.dismiss_modal_window(window=1)
            if unknown_user:
                raise AssertionError(
                    "SU53 did not accept the user '%s' (the user dialog stayed "
                    "open and was cancelled): check that the user exists in this "
                    "client." % name)
            raise AssertionError(
                "SU53 opened an unexpected dialog after the user '%s' was "
                "entered; it was cancelled. Perceive the screen with `Get Screen "
                "Signature` before reading again." % name)
        title = str(getattr(self.session.findById("wnd[0]"), "Text", "") or "")
        if not journal.title_names_user(title, name):
            raise AssertionError(
                "SU53 does not show the journal of '%s': the window title is '%s'. "
                "Reading it would attribute another user's failures." % (name, title))
        rows = self.read_full_grid(_JOURNAL_GRID, max_rows=limit,
                                   columns=list(journal.FAILURE_COLUMNS))
        return journal.parse_failure_rows(rows)

    def get_new_authorization_check_failures(self, before, after):
        """Les entrées de ``after`` absentes de ``before`` (deux lectures de
        `Read Authorization Check Failures`), occurrences comptées : la seule
        façon fiable de rattacher des échecs à un geste, le journal
        s'accumulant entre runs.

        Exemple :
        | ${before}=    `Read Authorization Check Failures`    SAPFX_TABDIS
        | `Switch Sap Session`    restricted
        | ${refused}=    `Reach Se16 Selection Screen`    T000
        | `Switch Sap Session`    admin
        | ${after}=    `Read Authorization Check Failures`    SAPFX_TABDIS
        | ${fresh}=    `Get New Authorization Check Failures`    ${before}    ${after}
        | Should Not Be Empty    ${fresh}
        """
        return journal.new_failures(before or [], after or [])

    def authorization_check_failures_should_contain(self, failures, authorization_object,
                                                    rc=None, **fields):
        """Échoue sauf si ``failures`` porte au moins un échec de l'objet
        ``authorization_object`` dont les champs nommés ont exactement les
        valeurs données (les autres champs sont libres) et, si ``rc`` est
        donné, ce code de retour. Rend les entrées trouvées. L'échec nomme
        l'attendu et ce que la liste porte.

        Exemple :
        | ${before}=    `Read Authorization Check Failures`    SAPFX_TABDIS
        | `Authorization Check Failures Should Contain`    ${before}    S_TABU_DIS
        | ...    rc=4    ACTVT=03    DICBERCLS=SS
        """
        entries = list(failures or [])
        found = journal.matching_failures(entries, authorization_object, rc, fields)
        if not found:
            raise AssertionError(journal.format_failure_absence(
                entries, authorization_object, rc, fields))
        return found

    def authorization_check_failures_should_not_contain(self, failures, authorization_object,
                                                        rc=None, **fields):
        """L'inverse de `Authorization Check Failures Should Contain` : échoue
        si ``failures`` porte un échec de cet objet à ces valeurs (et ce code
        de retour, s'il est donné), en nommant les entrées trouvées.

        Exemple :
        | ${before}=    `Read Authorization Check Failures`    SAPFX_TABDIS
        | `Authorization Check Failures Should Not Contain`    ${before}    S_TABU_DIS
        | ...    ACTVT=03    DICBERCLS=SC
        """
        found = journal.matching_failures(list(failures or []), authorization_object,
                                          rc, fields)
        if found:
            raise AssertionError(
                "Unexpected authorization check failure(s) for %s:\n  %s" % (
                    str(authorization_object).upper(),
                    "\n  ".join(journal.describe_failure(entry) for entry in found)))
