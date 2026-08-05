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


def ensure_com_initialized() -> None:
    """Initialise COM sur le thread courant ; ne lève jamais.

    Sans effet (bénin) si COM est déjà initialisé sur ce thread, si l'appel se
    fait depuis un environnement de test sans pywin32 (stub sans
    ``CoInitialize``), ou si pywin32 n'est simplement pas installé."""
    try:
        import pythoncom
    except ImportError:
        return  # pywin32 absent : plateforme non-Windows, ou test hors-SAP
    try:
        pythoncom.CoInitialize()
    except (AttributeError, pythoncom.com_error):
        # AttributeError : stub de test sans CoInitialize ; com_error : COM déjà
        # initialisé sur ce thread (S_FALSE), bénin dans les deux cas. Volontairement
        # PAS un `except Exception` large : une vraie panne COM doit remonter ici
        # plutôt que d'être masquée et ressurgir plus tard sous une erreur confuse.
        pass
