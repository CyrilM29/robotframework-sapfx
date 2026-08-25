"""Moteur record NATIF, moitie EVENEMENTIELLE : connexion COM et boucles.

La connexion manuelle au point de connexion ``ISapSessionEvents``
(`advise_session_events` : le hack ``_query_interface_`` canonique de la demo
pywin32 connect.py, makepy plantant sur la typelib sapfewse), la boucle
`record_loop_native` (--engine native : Session.Record + Change) et
`capture_loop_native` (hit-test ``Hit`` + ``FocusChanged``).

Extrait de ``sapgui_recorder.py`` (convention #13). Le mapping pur vit dans
``recorder_native.py``.
"""
import os
import sys
import time

# Module charge par CHEMIN (Robot `Library`, spec_from_file_location des
# tests) : son dossier n'est pas forcement sur sys.path, on l'y pose pour que
# les imports entre modules voisins du recorder fonctionnent partout.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from recorder_com import (  # noqa: E402
    _matches_filter,
    _safe,
    com_error,
    element_rect,
    pythoncom,
    relative_id,
    win32api,
    win32com,
)
from recorder_capture import (  # noqa: E402
    clear_stop_file,
    format_capture_block,
    make_stop_checker,
    offset_suggestion,
)
from recorder_native import (  # noqa: E402
    flush_native_state,
    initial_native_state,
    process_change,
    recording_disabled,
    screen_elements,
    semanticize_step,
    set_vkey_resolver,
)
from recorder_poll import (  # noqa: E402
    first_session,
    hotkey_assertion_lines,
    make_hotkey_poller,
    open_record_file,
)



# IID du dispinterface ``ISapSessionEvents`` et dispids de ses événements,
# contrat COM de sapfewse (stable par définition : un IID ne change jamais),
# vérifiés contre la typelib live de SAP GUI 8.00.
SESSION_EVENTS_IID = "{67A71FA4-9381-4061-B3BB-74A545C75874}"
_SESSION_EVENT_DISPIDS = {1280: "OnChange", 1281: "OnHit", 1286: "OnFocusChanged"}


class SessionEventConnection:
    """Poignée d'abonnement aux événements de session : ``close()`` désabonne
    (idempotent, jamais d'exception, utilisé dans les teardowns)."""

    def __init__(self, connection_point, cookie):
        self._cp = connection_point
        self._cookie = cookie

    def close(self):
        if self._cp is not None:
            try:
                self._cp.Unadvise(self._cookie)
            except Exception:
                pass
            self._cp = None


def advise_session_events(session, on_change=None, on_hit=None,
                          on_focus_changed=None):
    """Branche des handlers Python sur les événements COM de GuiSession,
    SANS makepy. Retourne une :class:`SessionEventConnection` ; lève si la
    liaison échoue (l'appelant replie alors sur le polling).

    ``DispatchWithEvents`` est inutilisable sur la typelib sapfewse : sa
    génération makepy plante (AssertionError dans genpy, pywin32 issue #2433,
    reproduit sur pywin32 311 / SAP GUI 8.00). On se connecte donc au point de
    connexion manuellement, avec le hack canonique de la démo officielle
    ``win32com/demos/connect.py`` : le sink répond au QueryInterface pour l'IID
    du dispinterface en retournant sa propre passerelle IDispatch (légal : un
    dispinterface EST un IDispatch au niveau vtable). Validé live contre un
    A4H : les actions scriptées comme manuelles émettent bien les Change.

    Handlers (tous optionnels) : ``on_change(component, command_array)``,
    ``on_hit(component)``, ``on_focus_changed(component)`` : les composants sont
    livrés déjà enveloppés (attributs ``.Id``/``.Type`` accessibles). Un handler
    ne doit jamais déclencher d'aller-retour serveur (boucle infinie, doc
    officielle) ; toute exception y est étouffée (le pont COM ne doit pas casser)."""
    import pywintypes
    import win32com.server.util
    from win32com.server.policy import EventHandlerPolicy

    events_iid = pywintypes.IID(SESSION_EVENTS_IID)

    def _wrap_component(raw):
        try:
            return win32com.client.Dispatch(raw)
        except Exception:
            return raw               # déjà enveloppé (EventHandlerPolicy) ou None

    class _Sink:
        _public_methods_ = []
        _dispid_to_func_ = dict(_SESSION_EVENT_DISPIDS)

        def _query_interface_(self, iid):
            if iid == events_iid:
                return win32com.server.util.wrap(self, usePolicy=EventHandlerPolicy)

        # Signatures officielles : Change(session, component, commandArray),
        # Hit(session, component, innerObject), FocusChanged(session, component).
        # On indexe depuis la FIN (le marshaling peut omettre la session).
        def OnChange(self, *args):
            try:
                if on_change is not None and len(args) >= 2:
                    on_change(_wrap_component(args[-2]), args[-1])
            except Exception:
                pass

        def OnHit(self, *args):
            try:
                if on_hit is not None and len(args) >= 2:
                    on_hit(_wrap_component(args[-2]))
            except Exception:
                pass

        def OnFocusChanged(self, *args):
            try:
                if on_focus_changed is not None and args:
                    on_focus_changed(_wrap_component(args[-1]))
            except Exception:
                pass

    punk = win32com.server.util.wrap(_Sink(), usePolicy=EventHandlerPolicy)
    container = session._oleobj_.QueryInterface(
        pythoncom.IID_IConnectionPointContainer)
    connection_point = container.FindConnectionPoint(events_iid)
    return SessionEventConnection(connection_point, connection_point.Advise(punk))


def record_loop_native(engine, out_path, poll_seconds=0.1, semantic=False,
                       suite=False, stop_file=None, _writer=print,
                       _max_iterations=None, _advise=None, _pump=None,
                       _sleep=time.sleep, _elements_fn=None, _key_state_fn=None):
    """Mode enregistreur NATIF : transcrit les événements Change en keywords.

    ``semantic=True`` (``--semantic``) : chaque ligne est réécrite en keyword
    « humain » (`Fill Field By Label`, `Click Button By Label`) quand le
    libellé calculé au moment de l'événement re-résout de façon unique vers le
    même élément : l'id technique reste en commentaire (voir
    `semanticize_step`). Le déroulé émis parle alors le langage de
    ``resources/`` (convention n°1) au lieu d'ids à retravailler.

    Retourne le nombre d'étapes écrites, ou ``None`` si le mode natif est
    indisponible (événements interdits par le profil serveur, liaison COM aux
    événements impossible) : l'appelant replie alors sur `record_loop` (polling).
    ``stop_file`` (option ``--stop-file``) arrête la boucle proprement depuis
    l'extérieur (bouton « Arrêter » de la GUI), teardown compris.
    ``_advise``/``_pump``/``_max_iterations``/``_sleep``/``_elements_fn`` sont
    des points d'injection pour les tests hors SAP."""
    should_stop = make_stop_checker(stop_file)
    session = first_session(engine)
    if session is None:
        _writer("Aucune session SAP ouverte.")
        return 0
    if recording_disabled(session):
        _writer("Événements d'enregistrement désactivés par le serveur "
                "(sapgui/user_scripting_disable_recording) : repli sur le polling.")
        return None
    if _advise is None:
        if win32com is None:
            return None
        _advise = advise_session_events
    if _pump is None:
        _pump = pythoncom.PumpWaitingMessages

    counters = {"steps": 0, "visual": 0, "lost": 0, "last_error": ""}
    state = {"st": initial_native_state()}
    fh = open_record_file(out_path, suite=suite)

    def emit(line):
        text = "    " + line
        _writer(text)
        fh.write(text + "\n")
        fh.flush()
        counters["steps"] += 1

    elements_fn = _elements_fn or screen_elements

    def on_change(component, command):
        # Le sink COM étouffe TOUT ce qui remonte d'un handler (le pont ne doit
        # pas casser) : un événement perdu ici (disque plein, écran disparu
        # pendant le calcul sémantique) disparaîtrait donc sans une trace. On
        # le compte pour le dire à l'arrêt : rien d'actionnable en silence.
        try:
            eid = relative_id(_safe(component, "Id"))
            etype = _safe(component, "Type")
            state["st"], lines = process_change(state["st"], eid, etype, command)
            if lines and semantic:
                # l'écran d'origine est encore affiché au moment de l'événement :
                # c'est LE moment où le libellé de l'élément est calculable.
                elements = elements_fn(session)
                lines = [semanticize_step(line, elements) for line in lines]
            for line in lines:
                emit(line)
        except Exception as exc:
            counters["lost"] += 1
            counters["last_error"] = "%s: %s" % (type(exc).__name__, exc)

    try:
        connection = _advise(session, on_change=on_change)
    except Exception as exc:
        fh.close()
        _writer("Liaison aux événements COM impossible (%s) : repli sur le polling." % exc)
        return None

    try:
        session.Record = True
    except (AttributeError, com_error) as exc:
        connection.close()
        fh.close()
        _writer("Impossible d'activer Session.Record (%s) : repli sur le polling." % exc)
        return None

    _writer("Mode record NATIF : effectue tes actions dans SAP GUI ; chaque commande "
            "est transcrite à l'aller-retour serveur.")
    _writer("Assertions : Ctrl+Alt+A = valeur du champ focalisé, "
            "Ctrl+Alt+V = empreinte visuelle de l'écran.")
    _writer("Séquence -> %s   (Ctrl+C pour arrêter)\n" % out_path)
    # Noms de vkeys au-delà de la table statique : l'API de la session les
    # connaît tous (GetVKeyDescription) : branché le temps de l'enregistrement.
    previous_resolver = set_vkey_resolver(
        lambda code: session.GetVKeyDescription(code))
    hotkeys = make_hotkey_poller(_key_state_fn)
    assert_base = os.path.splitext(os.path.basename(out_path))[0]
    iterations = 0
    try:
        while (_max_iterations is None or iterations < _max_iterations) \
                and not should_stop():
            iterations += 1
            _pump()                     # boucle STA : livre les événements en attente
            action = hotkeys()
            if action:
                lines, counters["visual"] = hotkey_assertion_lines(
                    action, session, assert_base, counters["visual"])
                for line in lines:
                    emit(line)
            _sleep(poll_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        for line in flush_native_state(state["st"]):
            emit(line)
        set_vkey_resolver(previous_resolver)
        try:
            session.Record = False
        except (AttributeError, com_error):
            pass
        connection.close()
        fh.close()
        clear_stop_file(stop_file)
        _writer("\nArrêt : %s étape(s) enregistrée(s) dans %s"
                % (counters["steps"], out_path))
        if counters["lost"]:
            _writer("Attention : %d événement(s) NON transcrits (dernière "
                    "erreur : %s)" % (counters["lost"], counters["last_error"]))
    return counters["steps"]


# --- Mode capture NATIF : hit-test (elementVisualizationMode + événement Hit) --
#
# L'API expose aussi un « hit test mode » : ``session.elementVisualizationMode =
# True`` fait surligner par SAP GUI le contrôle sous le curseur et émet un
# événement ``Hit(session, component, innerObject)`` quand l'utilisateur CLIQUE
# un élément : le vrai clic-à-capturer officiel, supérieur au polling du focus
# (il voit aussi les éléments non focusables : labels, cellules, toolbars).
# On écoute aussi ``FocusChanged`` en complément (navigation clavier).

def capture_loop_native(engine, out_path, poll_seconds=0.1, filter_text=None,
                        stop_file=None, _writer=print, _max_iterations=None,
                        _advise=None, _pump=None, _sleep=time.sleep,
                        _cursor_fn=None):
    """Mode capture NATIF : enregistre chaque élément cliqué (Hit) ou focalisé
    (FocusChanged) via les événements de l'API, sans polling.

    ``stop_file`` (option ``--stop-file``) arrête la boucle proprement depuis
    l'extérieur, teardown compris (hit-test désarmé, désabonnement).

    Retourne le nombre de captures, ou ``None`` si le mode natif est indisponible
    (l'appelant replie sur `capture_loop`)."""
    should_stop = make_stop_checker(stop_file)
    session = first_session(engine)
    if session is None:
        _writer("Aucune session SAP ouverte.")
        return 0
    if recording_disabled(session):
        _writer("Événements désactivés par le serveur : repli sur le polling du focus.")
        return None
    if _advise is None:
        if win32com is None:
            return None
        _advise = advise_session_events
    if _pump is None:
        _pump = pythoncom.PumpWaitingMessages

    seen = {"last": None, "count": 0, "lost": 0, "last_error": ""}
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fh = open(out_path, "w", encoding="utf-8")
    fh.write("# Captures SAP GUI Spy (hit-test natif) : %s\n\n" % out_path)
    fh.flush()

    cursor_fn = _cursor_fn
    if cursor_fn is None and win32api is not None:
        cursor_fn = win32api.GetCursorPos

    def on_component(component):
        # Même règle que le record natif : le sink COM étouffe ce qui remonte
        # d'un handler, donc une capture perdue est COMPTÉE et annoncée à
        # l'arrêt plutôt que de disparaître sans trace.
        try:
            eid = relative_id(_safe(component, "Id"))
            if not eid or eid == seen["last"]:
                return
            seen["last"] = eid
            etype = _safe(component, "Type")
            if not _matches_filter(filter_text, eid, etype):
                return
            record = {"id": eid, "type": etype, "text": _safe(component, "Text")}
            block = format_capture_block(record)
            if cursor_fn is not None:
                # Zone opaque cliquée (Hit) : propose aussi le repli coordonnées ;
                # la position du curseur AU CLIC donne l'offset relatif exact.
                try:
                    x, y = cursor_fn()
                    offset = offset_suggestion(etype, eid, element_rect(component), x, y)
                except Exception:
                    offset = None
                if offset:
                    block += "\n    " + offset
            seen["count"] += 1
            _writer(block)
            fh.write(block + "\n\n")
            fh.flush()
        except Exception as exc:
            seen["lost"] += 1
            seen["last_error"] = "%s: %s" % (type(exc).__name__, exc)

    try:
        connection = _advise(session, on_hit=on_component,
                             on_focus_changed=on_component)
    except Exception as exc:
        fh.close()
        _writer("Liaison aux événements COM impossible (%s) : repli sur le polling." % exc)
        return None

    hit_mode = True
    try:
        session.elementVisualizationMode = True
    except (AttributeError, com_error):
        hit_mode = False          # FocusChanged seul reste utile (pas bloquant)

    _writer("Mode capture NATIF : %s dans SAP GUI."
            % ("clique un élément (surligné par SAP GUI) ou tabule"
               if hit_mode else "tabule sur les champs (hit-test indisponible)"))
    _writer("Chaque élément est enregistré -> %s   (Ctrl+C pour arrêter)\n" % out_path)
    iterations = 0
    try:
        while (_max_iterations is None or iterations < _max_iterations) \
                and not should_stop():
            iterations += 1
            _pump()
            _sleep(poll_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        if hit_mode:
            try:
                session.elementVisualizationMode = False
            except (AttributeError, com_error):
                pass
        connection.close()
        fh.close()
        clear_stop_file(stop_file)
        _writer("\nArrêt : %s élément(s) capturé(s) dans %s" % (seen["count"], out_path))
        if seen["lost"]:
            _writer("Attention : %d capture(s) perdue(s) (dernière erreur : %s)"
                    % (seen["lost"], seen["last_error"]))
    return seen["count"]
