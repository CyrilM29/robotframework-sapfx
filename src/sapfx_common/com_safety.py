"""Sûreté COM partagée : initialisation défensive du thread courant.

L'API SAP GUI Scripting est COM (appartement STA) : un thread doit avoir appelé
``CoInitialize`` avant tout accès COM. En exécution Robot Framework classique, le
thread principal l'a déjà fait ; mais un orchestrateur qui exécute des keywords
hors du thread principal (rf-mcp, un ``asyncio.to_thread``...) doit le refaire
lui-même sous peine de ``RPC_E_WRONG_THREAD``. Cette même logique était dupliquée
à l'identique dans ``SapEccLibrary.keywords._connection`` (amorçage de session) et
``sap_robotmcp._rf_context`` (state provider rf-mcp) ; elle vit ici pour n'exister
qu'une fois.

Optionnel par construction : ``pythoncom`` n'est importé qu'à l'appel, et son
absence (stub de test, plateforme non-Windows) est silencieuse : ce module ne
crée donc pas de dépendance dure sur pywin32 pour le reste de ``sapfx_common``.
"""


# HRESULT de RPC_E_WRONG_THREAD : « l'application a appelé une interface qui
# était maintenue en ordre pour un thread différent ». C'est l'erreur qu'un
# proxy COM STA lève quand un AUTRE thread que celui qui l'a obtenu l'utilise ;
# mesuré le 2026-09-07 sous rf-mcp, où execute_batch et Evaluate tournent sur
# un thread différent du keyword qui a lié la session.
RPC_E_WRONG_THREAD = -2147417842

# HRESULT de RPC_E_DISCONNECTED : « l'objet invoqué s'est déconnecté de ses
# clients ». La session SAP GUI a été FERMÉE (OK-code /nex, SAP Logon arrêté,
# serveur perdu) : ce proxy ne reviendra jamais, donc attendre ne sert à rien.
# Mesuré le 2026-09-28 : après /nex, la sonde de Busy le rendait 30 s durant.
RPC_E_DISCONNECTED = -2147417848

# HRESULT qui disent que le SERVEUR COM a disparu (et non qu'il est occupé ou
# refuse l'appel) : RPC_S_SERVER_UNAVAILABLE (« le serveur RPC n'est pas
# disponible », un SAP Logon fermé dont l'entrée traîne encore dans la table
# des objets actifs), RPC_E_DISCONNECTED, et CO_E_OBJNOTCONNECTED. Une preuve
# de fermeture ne tient pour « rien n'est ouvert » QUE ces trois-là : un
# moteur occupé (RPC_E_CALL_REJECTED) ou refusant l'accès est un moteur vivant
# illisible, jamais un moteur absent (revue indépendante du 2026-10-01).
RPC_S_SERVER_UNAVAILABLE = -2147023174
CO_E_OBJNOTCONNECTED = -2147220995
# RPC_E_SERVER_DIED et RPC_E_SERVER_DIED_DNE : « l'appelé n'est pas disponible
# et a disparu ; toutes les connexions sont invalides » (l'appel exécuté ou
# non). Ajoutés à la contre-revue du 2026-10-01 sur leur DÉFINITION, sans avoir
# été provoqués sur le poste ; RPC_S_CALL_FAILED, lui, reste une panne (un
# appel échoué ne dit pas que le serveur a disparu).
RPC_E_SERVER_DIED = -2147418105        # 0x80010007
RPC_E_SERVER_DIED_DNE = -2147418094    # 0x80010012
DEAD_SERVER_HRESULTS = frozenset({RPC_S_SERVER_UNAVAILABLE, RPC_E_DISCONNECTED,
                                  CO_E_OBJNOTCONNECTED, RPC_E_SERVER_DIED,
                                  RPC_E_SERVER_DIED_DNE})


def com_hresult(exc: BaseException) -> object:
    """Le HRESULT d'une ``com_error`` (attribut ``hresult``, sinon premier
    argument), ou ``None``."""
    hresult = getattr(exc, "hresult", None)
    if hresult is not None:
        return hresult
    args = tuple(getattr(exc, "args", ()) or ())
    return args[0] if args else None


def is_dead_server_error(exc: BaseException) -> bool:
    """Vrai si ``exc`` prouve que le serveur COM a DISPARU (voir
    ``DEAD_SERVER_HRESULTS``) ; faux pour toute autre panne, y compris un
    serveur occupé ou qui refuse l'accès."""
    return com_hresult(exc) in DEAD_SERVER_HRESULTS


DISCONNECTED_HINT = (
    "la session SAP GUI a été FERMÉE (OK-code /nex ou /nend, SAP Logon arrêté, "
    "serveur perdu) : ce proxy COM ne reviendra pas, il faut rouvrir une session")


class SessionDisconnectedError(AssertionError):
    """La session SAP GUI n'existe plus : levée tout de suite par une attente
    au lieu d'expirer, et prise pour un SUCCÈS par un OK-code qui ferme la
    session (``/nex``)."""


# pywin32 (dispatch dynamique) rend la MÊME panne sous une autre forme : une
# AttributeError « <unknown>.Info », « <unknown>.GetObjectTree »... parce que
# le proxy ne peut plus interroger son type. Un vrai attribut absent sur un
# objet typé n'a pas ce préfixe.
_UNKNOWN_PROXY_MARK = "<unknown>."

# Le remède de session, tel que les agents doivent le lire.
WRONG_THREAD_HINT = (
    "la session SAP GUI est un objet COM STA lié au thread qui l'a ouverte, et "
    "cet appel vient d'un autre thread (sous rf-mcp : execute_batch et Evaluate "
    "tournent ailleurs que les keywords de bibliothèque ; passer use_context=true "
    "sur chaque execute_step, ne jamais toucher un objet COM depuis Evaluate, et "
    "devant cet état ré-attacher par Attach To Open Session 0 0)")


def is_wrong_thread_error(exc: BaseException) -> bool:
    """Vrai si ``exc`` est la panne de transport cross-thread, sous l'une de
    ses deux formes : ``com_error`` RPC_E_WRONG_THREAD, ou ``AttributeError``
    de proxy pywin32 « <unknown>.X »."""
    if isinstance(exc, AttributeError):
        return _UNKNOWN_PROXY_MARK in str(exc)
    hresult = getattr(exc, "hresult", None)
    if hresult == RPC_E_WRONG_THREAD:
        return True
    args = tuple(getattr(exc, "args", ()) or ())
    return len(args) > 0 and args[0] == RPC_E_WRONG_THREAD


def is_disconnected_error(exc: BaseException) -> bool:
    """Vrai si ``exc`` dit que la session n'existe plus : ``com_error``
    RPC_E_DISCONNECTED, ou `SessionDisconnectedError` déjà levée par une
    attente."""
    if isinstance(exc, SessionDisconnectedError):
        return True
    if getattr(exc, "hresult", None) == RPC_E_DISCONNECTED:
        return True
    args = tuple(getattr(exc, "args", ()) or ())
    return len(args) > 0 and args[0] == RPC_E_DISCONNECTED


def describe_com_failure(exc: BaseException) -> str:
    """Une ligne actionnable pour un message d'échec : nomme la panne
    cross-thread ou la session fermée quand c'en est une (avec le remède),
    sinon l'exception telle quelle. Ne lève jamais."""
    try:
        text = "%s: %s" % (type(exc).__name__, exc)
    except Exception:  # noqa: BLE001
        text = type(exc).__name__
    if is_wrong_thread_error(exc):
        return "%s (%s)" % (text, WRONG_THREAD_HINT)
    if is_disconnected_error(exc):
        return "%s (%s)" % (text, DISCONNECTED_HINT)
    return text


def ensure_com_initialized() -> None:
    """Initialise COM sur le thread courant ; ne lève jamais.

    Sans effet (bénin) si COM est déjà initialisé sur ce thread, si l'appel se
    fait depuis un environnement de test sans pywin32 (stub sans
    ``CoInitialize``), ou si pywin32 n'est simplement pas installé."""
    try:
        import pythoncom
    except ImportError:
        return  # pywin32 absent : plateforme non-Windows, ou test hors-SAP
    # Les clauses `except` sont évaluées AU MOMENT de l'exception : lire
    # ``pythoncom.com_error`` directement dans le tuple ferait lever une
    # AttributeError depuis la clause elle-même sur un stub qui n'a ni
    # ``CoInitialize`` ni ``com_error``, alors que cette fonction promet de ne
    # jamais lever. On résout le type d'abord, et on ne garde que s'il EST une
    # classe d'exception.
    com_error = getattr(pythoncom, "com_error", None)
    benign: tuple = (AttributeError,)
    if isinstance(com_error, type) and issubclass(com_error, BaseException):
        benign += (com_error,)
    try:
        pythoncom.CoInitialize()
    except benign:
        # AttributeError : stub de test sans CoInitialize ; com_error : COM déjà
        # initialisé sur ce thread (S_FALSE), bénin dans les deux cas. Volontairement
        # PAS un `except Exception` large : une vraie panne COM doit remonter ici
        # plutôt que d'être masquée et ressurgir plus tard sous une erreur confuse.
        pass


def shell_subtype(obj: object) -> str:
    """Le ``SubType`` d'un ``GuiShell`` (``GridView``, ``Tree``, ``AbapEditor``,
    ``Calendar``...), ou ``""`` pour tout objet qui ne l'expose pas (un
    conteneur, une doublure de test, un proxy COM absent). Lecture DÉFENSIVE :
    c'est la seule propriété qui distingue une grille ALV d'un arbre à
    colonnes, or les deux portent ``ColumnOrder`` (mesuré sur l'IMG de SPRO
    le 2026-09-08 : un résolveur qui ne regardait que ``ColumnOrder`` prenait
    l'arbre pour une grille)."""
    try:
        value = getattr(obj, "SubType", None)
    except Exception:                                      # noqa: BLE001
        return ""
    return "" if value is None else str(value).strip()
