"""Namespace d'état pour les exécutions rf-mcp partageant une instance Robot."""
from robot.libraries.BuiltIn import BuiltIn

_DEFAULT_NAMESPACE = "__robot_suite__"
_RF_MCP_TEST_PREFIX = "MCP_Test_"


def current_execution_namespace() -> str:
    """Retourne le namespace rf-mcp courant, ou celui de la suite Robot normale.

    rf-mcp exécute chaque session dans un test synthétique ``MCP_Test_<id>``
    mais réutilise actuellement l'instance de bibliothèque entre ses namespaces,
    même avec un scope ``SUITE``. Le nom du test est disponible pendant chaque
    keyword et fournit donc la frontière stable qui manque à son cache.
    """
    try:
        test_name = BuiltIn().get_variable_value("${TEST_NAME}", "")
    except Exception:
        return _DEFAULT_NAMESPACE
    if isinstance(test_name, str) and test_name.startswith(_RF_MCP_TEST_PREFIX):
        return "rfmcp:" + test_name[len(_RF_MCP_TEST_PREFIX):]
    return _DEFAULT_NAMESPACE
