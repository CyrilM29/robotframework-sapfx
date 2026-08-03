"""Utilitaires partagés par les smokes end-to-end *à travers* rf-mcp
(``ecc_through_rfmcp.py`` / ``fiori_through_rfmcp.py``) : ils pilotent les
VRAIS handlers de tools rf-mcp (``manage_session`` / ``execute_step`` / ...) en
process, exactement comme le ferait un agent via MCP. Cette factorisation évite
de dupliquer la même logique d'affichage/assertion dans les deux scripts.
"""
import re


class Checks:
    """Accumule des (label, condition) et imprime un résumé PASS/FAIL final."""

    def __init__(self):
        self.results = []

    def check(self, label, cond):
        cond = bool(cond)
        self.results.append((label, cond))
        print("   [%s] %s" % ("OK " if cond else "XX ", label))
        return cond

    def summary(self):
        print("\n== RÉSUMÉ ==")
        for label, ok in self.results:
            print("  %s %s" % ("PASS" if ok else "FAIL", label))
        n_ok = sum(1 for _, ok in self.results if ok)
        print("\n%d/%d checks OK" % (n_ok, len(self.results)))
        return 0 if n_ok == len(self.results) else 1


def show(label, res):
    ok = res.get("success") if isinstance(res, dict) else None
    text = (res.get("output") or res.get("result") or res.get("error") or "") if isinstance(res, dict) else ""
    text = str(text)
    print("[%s] success=%s  %s" % (label, ok, text[:140] + (" …" if len(text) > 140 else "")))
    return res


async def step(srv, session_id, kw, args=None, **kw2):
    """Exécute ``kw`` via le vrai ``srv.execute_step`` de rf-mcp et l'affiche."""
    return show(kw, await srv.execute_step(
        keyword=kw, arguments=args or [], session_id=session_id, use_context=True,
        raise_on_failure=False, **kw2))


def out(res):
    """Extrait la sortie texte d'un résultat de tool rf-mcp (déballe le wrapper
    ``truncated_string`` que rf-mcp utilise pour les sorties longues)."""
    if not isinstance(res, dict):
        return ""
    v = res.get("output") or res.get("result") or ""
    if isinstance(v, dict) and v.get("_type") == "truncated_string":
        v = v.get("_value", "")
    return str(v)


def num(res):
    """Premier entier trouvé dans la sortie texte d'un résultat, ou ``None``."""
    m = re.search(r"-?\d+", out(res))
    return int(m.group()) if m else None
