"""Isolation réelle des états de bibliothèques entre suites Robot/rf-mcp."""
import importlib

import pytest
from robot.api import TestSuite as RobotTestSuite


@pytest.mark.parametrize("library_name, keyword_name, arguments", [
    ("SapEccLibrary", "Lookup Business Term", ["airline"]),
    ("SapFioriLibrary", "Lookup Business Term", ["airline"]),
    ("SapApiLibrary", "Close All Api Sessions", []),
])
def test_stateful_library_gets_one_instance_per_suite(
        library_name, keyword_name, arguments):
    instances = []

    class Listener:
        def start_library_keyword(self, data, implementation, result):
            if implementation.owner.name == library_name:
                instances.append(implementation.owner.instance)

    root = RobotTestSuite("Root")
    for child_name in ("Session A", "Session B"):
        child = root.suites.create(child_name)
        child.resource.imports.library(library_name)
        child.tests.create("Probe").body.create_keyword(
            name=keyword_name, args=arguments)

    result = root.run(
        listener=Listener(), output=None, log=None, report=None, console="none")
    assert result.return_code == 0
    assert len(instances) == 2
    assert instances[0] is not instances[1]


def test_instance_partagee_partitionne_les_etats_ecc_et_fiori(monkeypatch):
    namespace = {"value": "rfmcp:a"}
    ecc_module = importlib.import_module("SapEccLibrary.SapEccLibrary")
    fiori_module = importlib.import_module("SapFioriLibrary.SapFioriLibrary")
    monkeypatch.setattr(ecc_module, "current_execution_namespace",
                        lambda: namespace["value"])
    monkeypatch.setattr(fiori_module, "current_execution_namespace",
                        lambda: namespace["value"])

    ecc = ecc_module.SapEccLibrary(screenshots_on_error=False)
    fiori = fiori_module.SapFioriLibrary()
    session_a = object()
    ecc.session = session_a
    fiori._ui5_frame = "iframe#a"
    fiori._last_page_tree = "<A/>"

    namespace["value"] = "rfmcp:b"
    assert ecc.session == -1
    assert fiori._ui5_frame is None
    assert fiori._last_page_tree is None
    ecc.session = object()
    fiori._ui5_frame = "iframe#b"

    namespace["value"] = "rfmcp:a"
    assert ecc.session is session_a
    assert fiori._ui5_frame == "iframe#a"
    assert fiori._last_page_tree == "<A/>"
